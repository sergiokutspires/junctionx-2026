"""Teacher vs student: what would it cost to ask a frontier vision LLM about every image instead?

Estimates one Messages API call per camera frame with the same two pictures our AI labellers used
(the frame + the zoomed area sheet), using Anthropic's documented image-token approximation
(tokens ~= width * height / 750 after resizing the long edge to <= 1568 px) and list prices
(USD per million tokens, Claude API, cached 2026-10-06). Compares with our measured pipeline cost.

  .venv/Scripts/python tools/llm_cost_compare.py
"""
import json
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
PRICES = {"Claude Sonnet 5.5": (2.00, 10.00), "Claude Opus 5.5": (4.00, 20.00), "Claude Haiku 5.5": (0.10, 0.50)}
PROMPT_TOKENS = 1100        # labelling instructions + area list (our guide is ~1,000 words of text)
OUTPUT_TOKENS_PER_AREA = 45  # one JSON object per area: level, compliant, short note
OURS_CPU_S = 3.765          # tools/benchmark_cost.py, 1 core, per frame, models/real_v3_cal (bf16, the submission model):
#                             median of three back-to-back runs on 2026-10-11 (3.661 / 3.765 / 3.837, files
#                             outputs/benchmark/cost_1t_real_v3_cal_b2b_run{1,2,3}.json; cost_1t_real_v3_cal.json = the median run).
#                             An earlier single run gave 3.594 (cost_1t_real_v3_cal_first.json), two others 4.49 and 4.53 (not saved).
#                             models/real_v2: 3.43 saved (cost_1t_real_v2.json); the full-precision models/real_v1_cal measured
#                             5.16 on the same 14 frames (cost_1t.json); ~7.0 on the first 3 pictures.
VCPU_HOUR_USD = 0.0892 / 2  # AWS c7i.large on-demand, us-east-1, 2 vCPU


def image_tokens(path: Path, long_edge: int = 1568) -> float:
    """Approximate image tokens of one picture after resizing its long edge to <= ``long_edge`` px."""
    w, h = Image.open(path).size
    s = min(1.0, long_edge / max(w, h))
    return (w * s) * (h * s) / 750


def main() -> None:
    teacher = sorted((ROOT / "data/teacher").glob("*/*_areas.jpg"))
    if not teacher:
        sys.exit("No teacher sheets found in data/teacher/ (they are not published). Render them first with\n"
                 "  .venv/Scripts/python tools/render_teacher_sheets.py\n"
                 "(needs the dataset in data/raw/), then run this script again.")
    areas_per_frame = 1962 / 181
    img_tok = sum(image_tokens(p) + image_tokens(Path(str(p).replace("_areas", "_overview"))) for p in teacher) / len(teacher)
    tok_in = img_tok + PROMPT_TOKENS
    tok_out = OUTPUT_TOKENS_PER_AREA * areas_per_frame
    ours = OURS_CPU_S / 3600 * VCPU_HOUR_USD
    rows = {"ours (CLIP + DINOv2 on 1 CPU core)": ours}
    for name, (pin, pout) in PRICES.items():
        rows[f"{name}, one call per image"] = (tok_in * pin + tok_out * pout) / 1e6
    print(f"per image: ~{tok_in:,.0f} input tokens ({img_tok:,.0f} from the 2 pictures), ~{tok_out:,.0f} output tokens")
    for name, usd in rows.items():
        print(f"  {name:44s} ${usd:.6f} per image   ${usd * 1000:8.3f} per 1,000   x{usd / ours:6.0f}")
    out = ROOT / "outputs/benchmark"
    out.mkdir(parents=True, exist_ok=True)
    (out / "llm_cost_compare.json").write_text(json.dumps({"input_tokens": tok_in, "output_tokens": tok_out,
                                                           "usd_per_image": rows}, indent=1))


if __name__ == "__main__":
    main()
