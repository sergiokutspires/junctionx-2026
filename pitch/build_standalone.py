"""Make pitch/slides_standalone.html: slides.html with every ./assets image embedded (one file).

Usage (project root):  .venv/Scripts/python pitch/build_standalone.py
"""
import base64
import mimetypes
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    html = (HERE / "slides.html").read_text(encoding="utf-8")

    def inline(m):
        path = HERE / m.group(1)
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        data = base64.b64encode(path.read_bytes()).decode("ascii")
        return f'src="data:{mime};base64,{data}"'

    out = re.sub(r'src="(assets/[^"]+)"', inline, html)
    target = HERE / "slides_standalone.html"
    target.write_text(out, encoding="utf-8")
    print(f"wrote {target} ({target.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
