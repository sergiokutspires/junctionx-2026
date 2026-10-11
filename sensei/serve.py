"""A local HTTP endpoint: one camera frame in, the status of every planogram area out.

Python standard library only (``http.server``), bound to 127.0.0.1. The model and the CLIP/DINOv2 feature
extractor are loaded once when the server starts and stay loaded between requests; requests are answered one
at a time (one model, no thread races).

    POST /analyze      body = the JPEG bytes; camera and time in headers X-Camera-Id / X-Timestamp (unix
                       seconds) or query parameters ?camera_id=...&timestamp=... . Without a camera id the
                       camera is recognised from the view (as ``submit`` does for flat folders).
    GET  /health       {"ok": true, "model": ..., "cameras": [...], "areas": N, "requests": N}

``/analyze`` answers::

    {"camera_id": "6215", "timestamp": 1751029500, "image_name": "1751029500.jpg", "elapsed_ms": 812,
     "areas": [{"area_id", "product_id", "product_name", "planogram_compliant", "stock_level", "stock_value",
                "status", "confidence", "p_levels", "p_compliant", "likely_product_name", "forecast_empty_s",
                "fallback"}, ...],
     "submission": {"6215": {"1751029500.jpg": {"<area_id>": {challenge entry}}}}}

``submission`` is exactly the challenge format for that frame, so the platform can store it as is.
"""
from __future__ import annotations

import json
import logging
import shutil
import tempfile
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

log = logging.getLogger(__name__)

MAX_BODY = 25 * 1024 * 1024   # 25 MB per frame is plenty for a 1280x720 JPEG
AREA_FIELDS = ("area_id", "product_id", "product_name", "planogram_compliant", "stock_level", "stock_value",
               "p_levels", "p_compliant", "likely_product_name", "forecast_empty_s", "fallback")


class Analyzer:
    """The loaded model plus a scratch folder for the frames being analysed."""

    def __init__(self, model_dir: str | Path, device: str | None = None, warmup: bool = True):
        from .pipeline import SenseiModel, _extractor  # noqa: PLC0415
        self.model_dir = str(model_dir)
        self.model = SenseiModel.load(model_dir)
        # no on-disk feature cache: every request is a new frame, caching would only fill the disk
        self.cfg = self.model.cfg.replace(extra={**self.model.cfg.extra, "cache_dir": None},
                                          **({"device": device} if device else {}))
        self.tmp = Path(tempfile.mkdtemp(prefix="sensei_serve_"))
        self.requests = 0
        if warmup and self.cfg.backend == "deep":
            _extractor(self.cfg)   # load CLIP + DINOv2 now, not on the first request
            self._warm()

    def _warm(self) -> None:
        """Analyse one grey frame so the first real request does not pay the one-off start-up costs."""
        import cv2  # noqa: PLC0415
        import numpy as np  # noqa: PLC0415
        cam = sorted(self.model.areas_by_cam)[0]
        w, h = self.model.meta.get("frame_size") or (1280, 720)
        ok, buf = cv2.imencode(".jpg", np.full((int(h), int(w), 3), 128, np.uint8))
        level = logging.getLogger("sensei").level
        logging.getLogger("sensei").setLevel(logging.ERROR)   # the grey frame's own warnings are noise
        try:
            if ok:
                self.analyze(buf.tobytes(), cam, 0)
        except Exception:  # noqa: BLE001 - warm-up is best effort
            log.warning("warm-up frame failed (the first request will be slower)")
        finally:
            logging.getLogger("sensei").setLevel(level)
            self.requests = 0

    def close(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def analyze(self, jpeg: bytes, camera_id: str | None = None, timestamp: int | None = None) -> dict:
        from .data import ImageRecord  # noqa: PLC0415
        from .events import status, status_confidence  # noqa: PLC0415
        from .pipeline import infer_camera, predict  # noqa: PLC0415
        t0 = time.perf_counter()
        if not jpeg:
            raise ValueError("empty body: POST the JPEG bytes")
        ts = int(timestamp) if timestamp is not None else int(time.time())
        frame = self.tmp / f"{ts}.jpg"
        frame.write_bytes(jpeg)
        try:
            cam = str(camera_id) if camera_id else None
            if cam is None:
                cam, corr = infer_camera(self.model, frame)
                if cam is None:
                    raise ValueError(f"camera not recognised from the view (best match {corr:.2f}); "
                                     "send X-Camera-Id")
            if cam not in self.model.areas_by_cam:
                raise ValueError(f"camera {cam} is not in the planogram")
            rec = ImageRecord(path=frame, camera_id=cam, image_name=frame.name, timestamp=ts, split="unknown")
            preds, rows = predict(self.model, [rec], self.cfg)
        finally:
            frame.unlink(missing_ok=True)
        self.requests += 1
        areas = []
        for r in rows:
            a = {k: r.get(k) for k in AREA_FIELDS}
            a["status"], a["confidence"] = status(r), status_confidence(r)
            areas.append(a)
        return {"camera_id": cam, "timestamp": ts, "image_name": frame.name,
                "elapsed_ms": int(round((time.perf_counter() - t0) * 1000)), "areas": areas, "submission": preds}

    def health(self) -> dict:
        return {"ok": True, "model": self.model_dir, "backend": self.cfg.backend,
                "cameras": sorted(self.model.areas_by_cam),
                "areas": sum(len(a) for a in self.model.areas_by_cam.values()), "requests": self.requests}


def make_handler(analyzer: Analyzer):
    class Handler(BaseHTTPRequestHandler):
        server_version = "FreshEyes/1"

        def _send(self, code: int, obj: dict) -> None:
            body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):   # noqa: N802 - http.server API
            if urlparse(self.path).path == "/health":
                self._send(200, analyzer.health())
            else:
                self._send(404, {"error": "GET /health or POST /analyze"})

        def do_POST(self):   # noqa: N802
            url = urlparse(self.path)
            if url.path != "/analyze":
                self._send(404, {"error": "POST /analyze"})
                return
            q = {k: v[-1] for k, v in parse_qs(url.query).items()}
            try:
                n = int(self.headers.get("Content-Length") or 0)
                if n <= 0 or n > MAX_BODY:
                    raise ValueError(f"Content-Length must be 1..{MAX_BODY} bytes")
                body = self.rfile.read(n)
                cam = self.headers.get("X-Camera-Id") or q.get("camera_id")
                ts = self.headers.get("X-Timestamp") or q.get("timestamp")
                self._send(200, analyzer.analyze(body, cam, int(ts) if ts else None))
            except ValueError as exc:
                self._send(400, {"error": str(exc)})
            except Exception as exc:  # noqa: BLE001 - keep serving
                log.exception("analyze failed")
                self._send(500, {"error": f"{type(exc).__name__}: {exc}"})

        def log_message(self, fmt, *args):   # route access logs through logging
            log.info("%s %s", self.address_string(), fmt % args)

    return Handler


def serve(model_dir: str | Path, port: int = 8765, device: str | None = None) -> None:
    analyzer = Analyzer(model_dir, device=device)
    httpd = HTTPServer(("127.0.0.1", port), make_handler(analyzer))
    print(f"Fresh Eyes endpoint on http://127.0.0.1:{port}  (POST /analyze, GET /health; Ctrl+C stops)", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        analyzer.close()
