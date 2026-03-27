from __future__ import annotations

import html
import ipaddress
import secrets
import socket
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from onefetch.cookie_formats import CookieFormatError, parse_cookie_input
from onefetch.secret_store import SecretStoreError, cookie_key, set_secret


@dataclass
class ImportState:
    expected_code: str
    one_time: bool
    imported_count: int = 0


def canonical_cookie_domain(domain: str) -> str:
    raw = (domain or "").strip().lower()
    parsed = urlparse(raw if "://" in raw else f"//{raw}", scheme="http")
    normalized = (parsed.hostname or raw).strip().lower()
    if normalized.startswith("www."):
        normalized = normalized[4:]
    aliases = {
        "zhihu": "zhihu.com",
        "douyin": "douyin.com",
        "doubao": "doubao.com",
        "bilibili": "bilibili.com",
        "xiaohongshu": "xiaohongshu.com",
    }
    if normalized in aliases:
        return aliases[normalized]
    if "." not in normalized:
        return normalized + ".com"
    return normalized


def generate_code() -> str:
    return secrets.token_urlsafe(6)


def _detect_lan_ip() -> str:
    def _is_rfc1918(ip: str) -> bool:
        try:
            value = ipaddress.ip_address(ip)
        except ValueError:
            return False
        if not isinstance(value, ipaddress.IPv4Address):
            return False
        return (
            value in ipaddress.ip_network("10.0.0.0/8")
            or value in ipaddress.ip_network("172.16.0.0/12")
            or value in ipaddress.ip_network("192.168.0.0/16")
        )

    candidates: list[str] = []

    # Route-selected local IP (may return VPN/virtual interface first).
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        route_ip = str(sock.getsockname()[0])
        if route_ip:
            candidates.append(route_ip)
    except Exception:
        pass
    finally:
        sock.close()

    # Hostname-resolved local IPv4s.
    try:
        _, _, ips = socket.gethostbyname_ex(socket.gethostname())
        for ip in ips:
            if ip and ip not in candidates:
                candidates.append(ip)
    except Exception:
        pass

    # Prefer common LAN private ranges, avoid virtual/test nets like 198.18.0.0/15.
    for ip in candidates:
        if _is_rfc1918(ip):
            return ip
    return ""


def _page(state: ImportState, *, message: str = "", error: bool = False) -> str:
    msg = ""
    if message:
        color = "#b42318" if error else "#027a48"
        msg = f'<div style="margin-bottom:12px;padding:10px;border-radius:8px;background:#f8f9fc;color:{color};">{html.escape(message)}</div>'
    return f"""<!doctype html>
<html lang=\"zh-CN\">
<head>
<meta charset=\"utf-8\" />
<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\" />
<title>OneFetch Cookie 导入</title>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;background:#f6f7fb;margin:0;padding:24px;}}
.card{{max-width:680px;margin:0 auto;background:#fff;border-radius:12px;padding:20px 22px;box-shadow:0 10px 28px rgba(0,0,0,.08);}}
label{{display:block;font-size:13px;color:#344054;margin:10px 0 6px;}}
input,textarea{{width:100%;box-sizing:border-box;border:1px solid #d0d5dd;border-radius:8px;padding:10px 12px;font-size:14px;}}
textarea{{min-height:120px;font-family:ui-monospace,Menlo,Consolas,monospace;}}
button{{margin-top:14px;background:#1d4ed8;color:#fff;border:none;border-radius:8px;padding:10px 14px;font-size:14px;cursor:pointer;}}
small{{color:#667085;display:block;margin-top:6px;}}
</style>
</head>
<body>
  <div class=\"card\">
    <h2 style=\"margin:0 0 8px;\">OneFetch Cookie 导入</h2>
    <p style=\"margin:0 0 14px;color:#475467;font-size:14px;\">在浏览器复制 Cookie 后粘贴到这里提交。提交后会写入远端 onefetch 的 <code>secrets.db</code>。</p>
    {msg}
    <form method=\"post\" action=\"/import\">
      <label>配对码</label>
      <input name=\"code\" value=\"{html.escape(state.expected_code)}\" required />
      <small>配对码错误会拒绝写入。</small>
      <label>域名</label>
      <input name=\"domain\" placeholder=\"例如 zhihu.com\" required />
      <label>Cookie Header String</label>
      <textarea name=\"cookie\" placeholder=\"k=v; k2=v2; ...\" required></textarea>
      <button type=\"submit\">导入到 OneFetch</button>
    </form>
  </div>
</body>
</html>"""


def serve_web_import(
    host: str,
    port: int,
    *,
    code: str = "",
    one_time: bool = True,
    share_host: str = "",
) -> int:
    state = ImportState(expected_code=(code.strip() or generate_code()), one_time=one_time)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args) -> None:  # hide cookie payload details
            return

        def _send_html(self, body: str, status: int = 200) -> None:
            data = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:
            if self.path not in {"/", "/import"}:
                self._send_html("<h3>Not Found</h3>", status=404)
                return
            self._send_html(_page(state))

        def do_POST(self) -> None:
            if self.path != "/import":
                self._send_html("<h3>Not Found</h3>", status=404)
                return
            length = int(self.headers.get("Content-Length", "0") or "0")
            body = self.rfile.read(length).decode("utf-8", errors="ignore")
            form = parse_qs(body)
            code_in = (form.get("code") or [""])[0].strip()
            domain = (form.get("domain") or [""])[0].strip()
            cookie = (form.get("cookie") or [""])[0].strip()

            if code_in != state.expected_code:
                self._send_html(_page(state, message="配对码错误", error=True), status=403)
                return
            if not domain:
                self._send_html(_page(state, message="域名不能为空", error=True), status=400)
                return
            try:
                parsed_cookie = parse_cookie_input(cookie, domain_hint=domain)
            except CookieFormatError as exc:
                self._send_html(_page(state, message=f"Cookie 格式不正确: {exc}", error=True), status=400)
                return

            canonical = canonical_cookie_domain(parsed_cookie.inferred_domain or domain)
            try:
                set_secret(cookie_key(canonical), parsed_cookie.header, secret_type="cookie")
            except SecretStoreError as exc:
                self._send_html(_page(state, message=f"写入失败: {exc}", error=True), status=500)
                return

            state.imported_count += 1
            self._send_html(_page(state, message=f"导入成功：cookie.{canonical}"))

            if state.one_time:
                threading.Thread(target=self.server.shutdown, daemon=True).start()

    server = ThreadingHTTPServer((host, port), Handler)
    print(f"[secret-web-import] listening on {host}:{port}")
    print(f"[secret-web-import] local_url: http://127.0.0.1:{port}")
    if share_host.strip():
        print(f"[secret-web-import] share_url: http://{share_host.strip()}:{port}")
        print("[secret-web-import] using explicit share host.")
    if host in {"0.0.0.0", "::"}:
        lan_ip = _detect_lan_ip()
        if lan_ip:
            print(f"[secret-web-import] lan_url: http://{lan_ip}:{port}")
            print("[secret-web-import] share lan_url with user (same LAN/Tailscale/VPN).")
        else:
            print("[secret-web-import] lan_url: <detect failed>; use host machine LAN IP manually.")
    else:
        print(f"[secret-web-import] direct_url: http://{host}:{port}")
    print(f"[secret-web-import] code: {state.expected_code}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("[secret-web-import] stopped by user")
    finally:
        server.server_close()
    return state.imported_count
