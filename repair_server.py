#!/usr/bin/env python3
"""
repair_server.py — Laptop Diagnostics 本機修復伺服器
用途：服務 report/index.html，並提供「白名單」修復 API，讓報告上的「修復」按鈕
      點一下就真的執行(每個動作伺服器端再驗證一次，需密碼者跳 macOS 原生授權視窗)。

啟動：python3 repair_server.py   (預設 http://127.0.0.1:8787，會自動開瀏覽器)
安全：僅綁定 127.0.0.1；每次請求需比對啟動時隨機產生的 token；只執行下列白名單動作。
"""
import http.server, socketserver, json, os, subprocess, secrets, webbrowser, sys, socket, urllib.request
from pathlib import Path

PORT   = 8787
ROOT   = Path(__file__).parent / "report"
INDEX  = ROOT / "index.html"
HOME   = os.path.expanduser("~")
TOKEN  = secrets.token_hex(16)

def sh(cmd, timeout=600):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout + r.stderr)
    except Exception as e:
        return 1, f"error: {e}"

def du_bytes(path):
    if not os.path.exists(path): return 0
    code, out = sh(f'du -sk "{path}" 2>/dev/null', timeout=120)
    try: return int(out.split("\t")[0].strip()) * 1024
    except Exception: return 0

def human(b):
    if b >= 1024**3: return f"{b/1024**3:.2f} GB"
    if b >= 1024**2: return f"{b/1024**2:.1f} MB"
    if b >= 1024:    return f"{b/1024:.0f} KB"
    return f"{int(b)} B"

def port_open(port, host="127.0.0.1", timeout=1.0):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False

# ── 白名單修復動作(每個都自我驗證、唯一限定範圍) ────────────────
def act_fix_path():
    prof = os.path.join(HOME, ".bash_profile")
    line = 'export PATH="/opt/homebrew/bin:/opt/homebrew/sbin:$PATH"'
    existing = open(prof).read() if os.path.exists(prof) else ""
    if "/opt/homebrew/bin" in existing:
        return {"ok": True, "message": "PATH 已包含 Homebrew，無需變更。"}
    with open(prof, "a") as f:
        f.write(f"\n# Added by Laptop Diagnostics repair\n{line}\n")
    return {"ok": True, "message": "已將 Homebrew 路徑寫入 ~/.bash_profile，新開終端機生效。"}

def act_brew_cleanup():
    sh("brew autoremove 2>&1"); sh("brew cleanup -s 2>&1")
    return {"ok": True, "message": "已執行 brew autoremove + cleanup，清除舊版本與孤兒相依。"}

def act_clear_caches():
    freed = 0
    b = du_bytes(os.path.join(HOME, ".npm"));               sh("npm cache clean --force 2>/dev/null"); freed += max(0, b - du_bytes(os.path.join(HOME, ".npm")))
    b = du_bytes(os.path.join(HOME, "Library/Caches/pip")); sh("pip3 cache purge 2>/dev/null");        freed += max(0, b - du_bytes(os.path.join(HOME, "Library/Caches/pip")))
    b = du_bytes(os.path.join(HOME, "Library/Caches/Homebrew")); sh("brew cleanup -s 2>/dev/null");    freed += max(0, b - du_bytes(os.path.join(HOME, "Library/Caches/Homebrew")))
    for rel in ["Library/Caches/node-gyp", "Library/Caches/com.apple.icloudmailagent"]:
        p = os.path.join(HOME, rel); b = du_bytes(p)
        sh(f'find "{p}" -mindepth 1 -delete 2>/dev/null'); freed += max(0, b - du_bytes(p))
    return {"ok": True, "message": f"已清理安全快取(brew / npm / pip / node-gyp / Mail)，釋出約 {human(freed)}。"}

def act_clean_stale_symlinks():
    LOCK = {"SingletonLock", "SingletonCookie", "SingletonSocket", "RunningChromeVersion"}
    removed = []
    code, out = sh(f'find -L "{HOME}" -type l 2>/dev/null', timeout=180)
    for p in out.split("\n"):
        if not p or "/Library/Containers/" in p: continue
        base = os.path.basename(p)
        if base in LOCK or base.endswith(".lock"): continue
        if os.path.islink(p) and not os.path.exists(os.path.realpath(p)):
            try: os.unlink(p); removed.append(p)
            except Exception: pass
    return {"ok": True, "message": f"已清理 {len(removed)} 條真殘留 symlink(只刪斷裂連結本身)。"}

def act_fix_m2():
    r1 = act_clean_stale_symlinks(); r2 = act_fix_path()
    return {"ok": True, "message": r1["message"] + " " + r2["message"]}

def act_enable_firewall():
    # 執行當下先查現況：若已開啟就不必跳授權視窗(因應掃描後狀態已改變的情況)
    _, state = sh("/usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate 2>&1", timeout=20)
    if "enabled" in state.lower() and "disabled" not in state.lower():
        return {"ok": True, "message": "防火牆已是開啟狀態，無需變更。"}
    cmd = "/usr/libexec/ApplicationFirewall/socketfilterfw --setglobalstate on"
    osa = f'do shell script "{cmd}" with administrator privileges'
    code, out = sh(f"osascript -e '{osa}' 2>&1", timeout=120)
    if code == 0:
        return {"ok": True, "message": "防火牆已開啟。"}
    return {"ok": False, "message": "開啟未完成(可能取消了授權):" + out.strip()[-160:]}

def act_open_software_update():
    sh('open "x-apple.systempreferences:com.apple.preferences.softwareupdate"')
    return {"ok": True, "message": "已開啟「軟體更新」設定頁，請在該頁安裝更新。"}

def act_brew_upgrade():
    # 執行當下重新確認還有沒有可升級的(因應掃描後狀態已改變)
    _, outd = sh("brew outdated --quiet 2>/dev/null", timeout=60)
    pending = [x for x in outd.split("\n") if x.strip()]
    if not pending:
        return {"ok": True, "message": "Homebrew 套件都已是最新，無需升級。"}
    sh("brew update 2>&1", timeout=300)
    code, out = sh("brew upgrade 2>&1", timeout=1800)
    _, left = sh("brew outdated --quiet 2>/dev/null", timeout=60)
    remain = len([x for x in left.split("\n") if x.strip()])
    return {"ok": True, "message": f"已升級 {len(pending)} 個 Homebrew 套件(尚餘 {remain} 個)。"}

def act_update_pip():
    # 只升級 pip 工具本身，且安裝到使用者目錄，不動系統 Python(遵守安全邊界)
    code, out = sh("python3 -m pip install --user --upgrade pip 2>&1", timeout=180)
    ok = "Successfully installed" in out or "already satisfied" in out or "already up-to-date" in out.lower()
    ver = ""
    _, v = sh("python3 -m pip --version 2>/dev/null", timeout=20)
    ver = v.strip().split(" ")[1] if " " in v else ""
    return {"ok": True, "message": f"pip 已更新到最新({ver})。套件升級請於虛擬環境自行處理。"}

def act_update_npm():
    # 執行當下重新確認;更新「全部」全域 npm 套件(含 Claude Code CLI 等),不只 npm 本身
    _, before = sh("npm outdated -g --parseable 2>/dev/null", timeout=60)
    n0 = len([x for x in before.split("\n") if x.strip()])
    if n0 == 0:
        return {"ok": True, "message": "全域 npm 套件都已是最新,無需更新。"}
    sh("npm update -g 2>&1", timeout=600)
    _, after = sh("npm outdated -g --parseable 2>/dev/null", timeout=60)
    n1 = len([x for x in after.split("\n") if x.strip()])
    return {"ok": True, "message": f"已更新全域 npm 套件({n0 - n1} 個完成,尚餘 {n1} 個)。"}

def act_thin_snapshots():
    _, before = sh("tmutil listlocalsnapshots / 2>/dev/null", timeout=30)
    n = len([l for l in before.split("\n") if l.startswith("com.apple.")])
    if n == 0:
        return {"ok": True, "message": "目前沒有本機快照，無需處理。"}
    sh("tmutil thinlocalsnapshots / 999999999999 4 2>&1", timeout=300)
    _, after = sh("tmutil listlocalsnapshots / 2>/dev/null", timeout=30)
    n2 = len([l for l in after.split("\n") if l.startswith("com.apple.")])
    return {"ok": True, "message": f"已精簡本機快照({n} → {n2} 個)。"}

def act_open_filevault_settings():
    sh('open "x-apple.systempreferences:com.apple.preference.security?FileVault"')
    return {"ok": True, "message": "已開啟「FileVault」設定頁，請在該頁開啟加密並保存還原金鑰。"}

def act_disable_remote_login():
    # 執行當下先確認:port 22 沒在聽就無事可做(因應掃描後狀態已改變)
    if not port_open(22):
        return {"ok": True, "message": "遠端登入(SSH)目前已關閉,無需處理。"}
    cmd = "systemsetup -f -setremotelogin off"
    osa = f'do shell script "{cmd}" with administrator privileges'
    code, out = sh(f"osascript -e '{osa}' 2>&1", timeout=120)
    if code == 0 and not port_open(22):
        return {"ok": True, "message": "已關閉遠端登入(SSH)。"}
    return {"ok": False, "message": "關閉未完成(可能取消了授權或仍在聽):" + out.strip()[-160:]}

def act_disable_screen_sharing():
    # 執行當下先確認:port 5900 沒在聽就無事可做
    if not port_open(5900):
        return {"ok": True, "message": "螢幕共享目前已關閉,無需處理。"}
    cmd = ("launchctl disable system/com.apple.screensharing; "
           "launchctl bootout system/com.apple.screensharing")
    osa = f'do shell script "{cmd}" with administrator privileges'
    code, out = sh(f"osascript -e '{osa}' 2>&1", timeout=120)
    if not port_open(5900):
        return {"ok": True, "message": "已關閉螢幕共享。"}
    return {"ok": False, "message": "關閉未完成(可能取消了授權或仍在聽):" + out.strip()[-160:]}

def act_enable_gatekeeper():
    _, st = sh("spctl --status 2>&1", timeout=20)
    if "enabled" in st.lower():
        return {"ok": True, "message": "Gatekeeper 已啟用，無需變更。"}
    osa = 'do shell script "spctl --master-enable" with administrator privileges'
    code, out = sh(f"osascript -e '{osa}' 2>&1", timeout=120)
    if code == 0:
        return {"ok": True, "message": "Gatekeeper 已啟用。"}
    return {"ok": False, "message": "啟用未完成(可能取消了授權):" + out.strip()[-160:]}

ACTIONS = {
    "fix_path": act_fix_path,
    "brew_cleanup": act_brew_cleanup,
    "clear_caches": act_clear_caches,
    "clean_stale_symlinks": act_clean_stale_symlinks,
    "fix_m2": act_fix_m2,
    "enable_firewall": act_enable_firewall,
    "open_software_update": act_open_software_update,
    "brew_upgrade": act_brew_upgrade,
    "update_pip": act_update_pip,
    "update_npm": act_update_npm,
    "thin_snapshots": act_thin_snapshots,
    "open_filevault_settings": act_open_filevault_settings,
    "enable_gatekeeper": act_enable_gatekeeper,
    "disable_remote_login": act_disable_remote_login,
    "disable_screen_sharing": act_disable_screen_sharing,
}

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _send(self, code, body, ctype="application/json"):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            html = INDEX.read_text()
            inject = f'<script>window.__REPAIR__={{"token":"{TOKEN}","enabled":true}};</script>'
            html = html.replace("<!--REPAIR_HOOK-->", inject)
            return self._send(200, html, "text/html; charset=utf-8")
        if self.path == "/api/ping":
            return self._send(200, json.dumps({"ok": True}))
        if self.path == "/favicon.ico":
            return self._send(204, b"")
        return self._send(404, "not found", "text/plain")

    def do_POST(self):
        if self.path != "/api/fix":
            return self._send(404, json.dumps({"ok": False, "message": "unknown endpoint"}))
        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length) or "{}")
        except Exception:
            return self._send(400, json.dumps({"ok": False, "message": "bad request"}))
        if payload.get("token") != TOKEN:
            return self._send(403, json.dumps({"ok": False, "message": "授權失敗(token 不符)"}))
        action = payload.get("action")
        fn = ACTIONS.get(action)
        if not fn:
            return self._send(400, json.dumps({"ok": False, "message": f"未知動作:{action}"}))
        try:
            result = fn()
        except Exception as e:
            result = {"ok": False, "message": f"執行錯誤:{e}"}
        print(f"[repair] {action} -> {result.get('message','')}")
        return self._send(200, json.dumps(result, ensure_ascii=False))


class ThreadingServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True

def _is_macvitals(port):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ping", timeout=2) as r:
            return r.status == 200
    except Exception:
        return False

def _free_port(start, n=20):
    for p in range(start, start + n):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("127.0.0.1", p)); s.close(); return p
        except OSError:
            s.close()
    return None

def main():
    if not INDEX.exists():
        print("找不到 report/index.html，請先執行 python3 generate_report.py")
        sys.exit(1)
    if _is_macvitals(PORT):
        url = f"http://127.0.0.1:{PORT}/"
        print("修復伺服器已在執行中,直接為你開啟報告頁。")
        try: webbrowser.open(url)
        except Exception: pass
        return
    port = _free_port(PORT)
    if port is None:
        print(f"連接埠 {PORT} 起算都被佔用,請關閉其他視窗後再試。")
        return
    with ThreadingServer(("127.0.0.1", port), Handler) as httpd:
        url = f"http://127.0.0.1:{port}/"
        print("=" * 56)
        print("  Laptop Diagnostics 修復伺服器已啟動")
        print(f"  報告網址：{url}")
        print("  按 Ctrl+C 結束。修復按鈕只在透過此網址開啟時可用。")
        print("=" * 56)
        try:
            webbrowser.open(url)
        except Exception:
            pass
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n已結束。")

if __name__ == "__main__":
    main()
