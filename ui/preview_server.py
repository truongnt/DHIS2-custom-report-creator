"""
Local HTTP preview server for charts.

- Runs on localhost:PORT in a background thread (no main-thread restriction)
- Browser opens once; subsequent HTML updates trigger auto-reload via polling
- PREVIEW mode active so Chart.js shows sample data (no DHIS2 connection needed)
- When credentials are configured via configure_proxy(), /api/* is proxied to DHIS2
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

# DHIS2 proxy config — set by configure_proxy() after successful connect
_dhis2_api_url: str | None = None   # e.g. "https://hmis.gov.la/hmis/api"
_dhis2_auth: tuple[str, str] | None = None  # (username, password)

# Geo boundary cache — set by set_geo_cache() from fixture data
# Dict of level → list of geoFeature objects ({id, ty, co, ...})
_geo_cache: dict = {}

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


def configure_proxy(api_url: str, username: str, password: str) -> None:
    """Call after successful DHIS2 connect so the server can proxy /api/* requests."""
    global _dhis2_api_url, _dhis2_auth
    _dhis2_api_url = api_url.rstrip("/")   # e.g. "https://hmis.gov.la/hmis/api"
    _dhis2_auth = (username, password)


def set_geo_cache(geo: dict) -> None:
    """Store geoFeature lists from fixture; served at /api/geoFeatures?...LEVEL-N...

    geo: dict mapping level string ("2","3","4","5") → list of feature dicts.
    """
    global _geo_cache
    _geo_cache = geo


class _Handler(http.server.BaseHTTPRequestHandler):
    def handle_one_request(self):
        # The browser routinely closes/refreshes the preview tab mid-response (the
        # auto-reload poller does this). Swallow the resulting client-disconnect errors
        # so they don't spam stderr with harmless tracebacks.
        try:
            super().handle_one_request()
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            self.close_connection = True

    def log_message(self, *args):
        pass  # quiet — no per-request console spam

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

        elif self.path.startswith("/api/geoFeatures"):
            # Try geo cache first (populated from fixture data)
            import re as _re, json as _json
            served = False
            if _geo_cache:
                lvl_m = _re.search(r'LEVEL-(\d+)', self.path)
                if lvl_m:
                    feats = _geo_cache.get(lvl_m.group(1), [])
                    if feats:
                        body = _json.dumps(feats).encode()
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")
                        self.send_header("Access-Control-Allow-Origin", "*")
                        self.send_header("Content-Length", str(len(body)))
                        self.end_headers()
                        self.wfile.write(body)
                        served = True
            if not served and _dhis2_api_url:
                # Proxy fallback (e.g. live session or cache miss)
                sub = self.path[5:]
                target = _dhis2_api_url + "/" + sub
                try:
                    import requests as _req
                    resp = _req.get(target, auth=_dhis2_auth, timeout=60)
                    body = resp.content
                    self.send_response(resp.status_code)
                    ct = resp.headers.get("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Type", ct)
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                except Exception as exc:
                    msg = str(exc).encode()
                    self.send_response(502)
                    self.send_header("Content-Type", "text/plain")
                    self.send_header("Content-Length", str(len(msg)))
                    self.end_headers()
                    self.wfile.write(msg)
            elif not served:
                self.send_response(503)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"No geo cache and no proxy configured")

        elif self.path.startswith("/api/") and _dhis2_api_url:
            # Proxy DHIS2 API calls — strip leading "/api/" and forward to real server
            sub = self.path[5:]  # e.g. "geoFeatures?ou=..."
            target = _dhis2_api_url + "/" + sub
            try:
                import requests as _req
                resp = _req.get(target, auth=_dhis2_auth, timeout=60)
                body = resp.content
                self.send_response(resp.status_code)
                ct = resp.headers.get("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Type", ct)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except Exception as exc:
                msg = str(exc).encode()
                self.send_response(502)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(msg)))
                self.end_headers()
                self.wfile.write(msg)

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
        """Accept POST /update (HTML) or /log (JS debug lines)."""
        length = int(self.headers.get("Content-Length", 0))
        body   = self.rfile.read(length).decode("utf-8", errors="replace")

        if self.path == "/log":
            try:
                from ui.debug_logger import log_js
                import json as _json
                entry = _json.loads(body)
                log_js(entry.get("level", "log"), entry.get("msg", body))
            except Exception:
                pass
            self.send_response(204)
            self.end_headers()
            return

        if self.path == "/update":
            global _html_content, _html_version
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


class _TCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    # Threaded: maps fire several concurrent /api/geoFeatures requests (points + overlay
    # borders) via Promise.all; a single-threaded server resets the extra connections.
    allow_reuse_address = True
    daemon_threads = True


def _start_server():
    with _TCPServer(("127.0.0.1", PORT), _Handler) as httpd:
        httpd.serve_forever()


def is_preview_open() -> bool:
    """True if a preview tab is (likely) open — browser was opened and has polled recently.

    Lets callers push an update that auto-reloads the open tab without force-opening a new one.
    """
    return _browser_opened and (time.monotonic() - _last_poll_time) <= _BROWSER_TIMEOUT


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
