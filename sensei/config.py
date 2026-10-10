"""All tunables of the pipeline in one dataclass, saved next to every model as JSON."""
from __future__ import annotations

import dataclasses
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


@dataclass
class Config:
    """Pipeline settings. Defaults are the zero-label path; see SPEC.md section 4."""

    backend: str = "deep"            # "deep" (CLIP+DINOv2) | "lite" (handcrafted only, fast, no torch)
    device: str = "auto"             # auto -> cuda if available else cpu
    crop_size: int = 224
    inset: float = 0.06              # shrink each quad towards its centre before warping (avoid neighbours)
    max_images_per_camera: int = 150  # subsample train/test for fit (evenly over time)
    batch_size: int = 32
    clip_model: str = "openai/clip-vit-base-patch16"
    dino_model: str = "facebook/dinov2-small"
    # stock
    n_patch_clusters: int = 24
    pca_dims: int = 48
    level_prior: tuple = (0.15, 0.35, 0.50)  # empty, half, full (used when GMM degenerate)
    # compliance
    compliance_prior: float = 0.93
    # temporal
    smoothing_window_s: int = 300
    smoothing_weight: float = 0.0    # weight of time neighbours vs the frame itself (0 = off)
    seed: int = 0
    extra: dict = field(default_factory=dict)  # free-form knobs for experiments (kept in the JSON)

    def __post_init__(self) -> None:
        if self.backend not in ("deep", "lite"):
            raise ValueError(f"backend must be 'deep' or 'lite', got {self.backend!r}")
        self.level_prior = tuple(float(p) for p in self.level_prior)
        if len(self.level_prior) != 3:
            raise ValueError("level_prior needs 3 values (empty, half, full)")
        if not 0.0 <= self.inset < 1.0:
            raise ValueError("inset must be in [0, 1)")

    def to_dict(self) -> dict[str, Any]:
        d = dataclasses.asdict(self)
        d["level_prior"] = list(self.level_prior)
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Config":
        """Build from a dict, ignoring (and logging) unknown keys so old/new model dirs still load."""
        names = {f.name for f in dataclasses.fields(cls)}
        unknown = sorted(set(d) - names)
        if unknown:
            log.warning("Config: ignoring unknown keys %s", unknown)
        return cls(**{k: v for k, v in d.items() if k in names})

    def to_json(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def from_json(cls, path: str | Path) -> "Config":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    def replace(self, **changes: Any) -> "Config":
        """Copy with some fields changed (validated again)."""
        return dataclasses.replace(self, **changes)

    def resolve_device(self) -> str:
        """'cuda' or 'cpu' for device='auto' (imports torch lazily); otherwise the given device."""
        if self.device != "auto":
            return self.device
        try:
            import torch  # noqa: PLC0415 - optional dependency
        except ImportError:
            return "cpu"
        return "cuda" if torch.cuda.is_available() else "cpu"
