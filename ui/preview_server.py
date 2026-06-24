"""
Local HTTP preview server for charts.

- Runs on localhost:PORT in a background thread (no main-thread restriction)
- Browser opens once; subsequent HTML updates trigger auto-reload via polling
- PREVIEW mode active so Chart.js shows sample data (no DHIS2 connection needed)
"""
from __future__ import annotations
import hashlib
import http.server
import threading
import time
import webbrowser
import socketserver

PORT = 15432
_html_content = "<html><body><p style='font-family:sans-serif;padding:40px'>Loading preview…</p></body></html>"
_html_version = "0"
_server_started = False
_browser_opened = False
_last_poll_time: float = 0.0   # updated each time browser polls /version
_BROWSER_TIMEOUT = 3.0         # seconds without a poll → assume tab closed
_lock = threading.Lock()

# JS injected into every served page: polls /version and reloads when changed
_RELOAD_JS = """\
<script>
(function(){
  var _v='%s';
  setInterval(function(){
    fetch('/version').then(function(r){return r.text();}).then(function(v){
      if(v!==_v){_v=v;window.location.reload();}
    }).catch(function(){});
  },600);
})();
</script>"""


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        global _last_poll_time
        if self.path == "/version":
            _last_poll_time = time.monotonic()
            data = _html_version.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(data)
        else:
            html = _html_content
            # Inject auto-reload script before </body>
            reload = _RELOAD_JS % _html_version
            if "</body>" in html:
                html = html.replace("</body>", reload + "\n</body>", 1)
            else:
                html += reload
            data = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(data)

    def do_POST(self):
        """Accept POST /update with raw HTML body — updates preview without restarting."""
        if self.path == "/update":
            global _html_content, _html_version
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8")
            with _lock:
                _html_content = body
                _html_version = hashlib.md5(body.encode()).hexdigest()[:8]
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, fmt, *args):
        pass  # suppress server logs


def _start_server():
    with socketserver.TCPServer(("", PORT), _Handler) as httpd:
        httpd.serve_forever()


def update_preview(html: str, title: str = "Chart Preview"):
    """Update the preview content. Opens browser on first call."""
    global _html_content, _html_version, _server_started, _browser_opened

    with _lock:
        _html_content = html
        _html_version = hashlib.md5(html.encode()).hexdigest()[:8]

        if not _server_started:
            _server_started = True
            t = threading.Thread(target=_start_server, daemon=True)
            t.start()
            threading.Event().wait(0.3)  # brief wait for server to bind

        browser_is_closed = (
            not _browser_opened or
            (time.monotonic() - _last_poll_time) > _BROWSER_TIMEOUT
        )
        if browser_is_closed:
            _browser_opened = True
            webbrowser.open(f"http://localhost:{PORT}/")
