"""Show the staff app on people's phones: serve it from this laptop and display a QR code.

Nothing is uploaded anywhere. Phones must be on the same network as the laptop. Protection, because the app shows
the store's camera pictures: a secret key inside the QR code (no key, no app), only clients on the laptop's own
network (same /16, or private addresses), and the server stops by itself after --hours.

  .venv/Scripts/python tools/share_app.py                # newest demo app, port 8080, 4 hours
  .venv/Scripts/python tools/share_app.py --dir outputs/rehearsal_0850/dashboard
Or double-click SHARE_APP.bat. Stop with Ctrl+C (or close the window).
"""
import argparse
import http.server
import ipaddress
import secrets
import socket
import threading
import webbrowser
from functools import partial
from http import cookies
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
# Stable app first; the full-day replay is shared on request: SHARE_APP.bat --dir outputs/day_replay/dashboard
CANDIDATES = ("outputs/rehearsal_final/dashboard", "outputs/rehearsal_0850/dashboard", "outputs/day_replay/dashboard")
COOKIE = "fresh_eyes_key"


def lan_ip() -> str:
    """The address other devices on this network use to reach the laptop (no packet is sent)."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
        except OSError:
            return "127.0.0.1"


def make_handler(directory: Path, key: str, host_ip: str, stats: dict):
    own_net = ipaddress.ip_network(f"{host_ip}/16", strict=False)

    class Handler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, fmt, *args):  # quiet: one line per new visitor instead
            pass

        def _allowed_client(self) -> bool:
            ip = ipaddress.ip_address(self.client_address[0])
            return ip.is_loopback or ip.is_private or ip in own_net

        def do_GET(self):
            if not self._allowed_client():
                self.send_error(403, "Not on the local network")
                return
            query = parse_qs(urlparse(self.path).query)
            jar = cookies.SimpleCookie(self.headers.get("Cookie", ""))
            has_cookie = COOKIE in jar and secrets.compare_digest(jar[COOKIE].value, key)
            if query.get("k", [""])[0] == key:
                if self.client_address[0] not in stats["visitors"]:
                    stats["visitors"].add(self.client_address[0])
                    print(f"  new visitor: {self.client_address[0]} ({len(stats['visitors'])} so far)")
                self.send_response(302)
                self.send_header("Set-Cookie", f"{COOKIE}={key}; Path=/; HttpOnly; SameSite=Lax; Max-Age=86400")
                self.send_header("Location", "/index.html")
                self.end_headers()
                return
            if not has_cookie:
                body = ("<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width'>"
                        "<body style='font:20px system-ui;padding:2em'><h1>Fresh Eyes</h1>"
                        "<p>Scan the QR code on the screen to open the staff app.</p></body>").encode()
                self.send_response(403)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            super().do_GET()

        def do_HEAD(self):
            self.send_error(405)

        def end_headers(self):
            self.send_header("Cache-Control", "no-store")
            super().end_headers()

    return partial(Handler, directory=str(directory))


def write_qr_page(url: str, out: Path, folder: Path) -> Path:
    import segno  # dev dependency, only needed here
    out.mkdir(parents=True, exist_ok=True)
    qr = segno.make(url, error="m")
    qr.save(out / "qr.png", scale=14, border=2)
    svg = qr.svg_inline(scale=14, border=2)
    page = out / "qr.html"
    page.write_text(f"""<!doctype html><html lang=en><meta charset=utf-8><title>Fresh Eyes - scan me</title>
<meta name=viewport content="width=device-width, initial-scale=1">
<style>body{{margin:0;min-height:100vh;display:grid;place-items:center;background:#fff;color:#14171c;
font:22px/1.4 system-ui,-apple-system,"Segoe UI",sans-serif;text-align:center}}h1{{font-size:56px;margin:.2em 0}}
.qr svg{{width:min(70vh,80vw);height:auto}}p{{margin:.3em}}small{{color:#5b6370}}</style>
<div><h1>Fresh Eyes</h1><p>Scan to open the staff app on your phone</p><div class=qr>{svg}</div>
<p><b>Same Wi-Fi as this laptop.</b> Nothing is uploaded: the app runs from this laptop.</p>
<small>{url.split('?')[0]} · serving {folder.relative_to(ROOT) if folder.is_relative_to(ROOT) else folder}</small></div>
</html>""", encoding="utf-8")
    return page


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", default=None, help="the dashboard folder to share (default: the newest demo app)")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--hours", type=float, default=4.0, help="stop serving after this many hours")
    ap.add_argument("--no-open", action="store_true", help="do not open the QR page in the browser")
    args = ap.parse_args()
    folder = Path(args.dir) if args.dir else next((ROOT / c for c in CANDIDATES if (ROOT / c / "index.html").exists()), None)
    if folder is None or not (folder / "index.html").exists():
        raise SystemExit("No dashboard found. Build one first (python -m sensei submit ... or sensei dashboard ...).")
    folder = folder.resolve()
    ip, key = lan_ip(), secrets.token_urlsafe(9)
    stats = {"visitors": set()}
    server = http.server.ThreadingHTTPServer(("0.0.0.0", args.port), make_handler(folder, key, ip, stats))
    url = f"http://{ip}:{args.port}/?k={key}"
    page = write_qr_page(url, ROOT / "outputs" / "share", folder)
    print("=" * 70)
    print(f"Sharing the staff app from {folder}")
    print(f"Phones on the same Wi-Fi: scan the QR code (opened in your browser) or go to\n  {url}")
    print(f"Stops automatically after {args.hours:g} h. Press Ctrl+C to stop now.")
    print("If Windows asks whether Python may use the network: allow it on PRIVATE networks.")
    print("=" * 70)
    if not args.no_open:
        webbrowser.open(page.as_uri())
    stopper = threading.Timer(args.hours * 3600, server.shutdown)
    stopper.daemon = True  # Ctrl+C must not wait for the timer
    stopper.start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        print(f"Stopped. {len(stats['visitors'])} visitor(s).")


if __name__ == "__main__":
    main()
