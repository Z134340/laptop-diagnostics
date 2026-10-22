#!/usr/bin/env python3
"""
repair_server.py — MacVitals 修復函式庫(白名單動作 + 本機伺服器守衛)

這支檔案**不再自己起 HTTP 伺服器**。本機唯一的伺服器是 app_server.py(127.0.0.1:8788),
它同時提供首頁、掃描進度、報告與 /api/fix;/api/fix 執行的就是這裡的 ACTIONS。
這裡只放:
  - ACTIONS:白名單修復動作(每個動作在執行當下重新驗證現況;需密碼者跳 macOS 原生授權視窗)
  - host_allowed / origin_allowed / SECURITY_HEADERS:伺服器共用的 Host/Origin 守衛與安全標頭
  - sh() / du_bytes() / human() / port_open():動作用的小工具

直接執行 `python3 repair_server.py` 會轉呼叫 app_server.main(["--report"])(同一支伺服器、直接開報告頁)。
scripts/check_doc_counts.py 以 ast 讀這裡頂層的 ACTIONS 數,搬動時要同步改它。
"""
import os, subprocess, socket

HOME   = os.path.expanduser("~")

ALLOWED_HOSTNAMES = ("127.0.0.1", "localhost")

def host_allowed(headers, port):
    """只接受 Host 指向本機的請求,擋 DNS rebinding(惡意網域解析到 127.0.0.1 後讀走 token)。"""
    host = (headers.get("Host") or "").strip().lower()
    name, _, hport = host.partition(":")
    return name in ALLOWED_HOSTNAMES and (not hport or hport == str(port))

def origin_allowed(headers, port):
    """POST 必須來自本機頁面:有 Origin 就比對;沒帶 Origin 的瀏覽器跨站請求(看 Sec-Fetch-Site)也擋。
    非瀏覽器客戶端(curl 等,兩個標頭都沒有)不受影響,仍需 token。"""
    origin = (headers.get("Origin") or "").strip().lower()
    if origin:
        return origin in {f"http://{h}:{port}" for h in ALLOWED_HOSTNAMES}
    sfs = (headers.get("Sec-Fetch-Site") or "").strip().lower()
    return sfs in ("", "same-origin", "none")

SECURITY_HEADERS = (
    ("X-Content-Type-Options", "nosniff"),
    ("Referrer-Policy", "no-referrer"),
    ("Cache-Control", "no-store"),
    # 只允許本機頁面(含不同埠的本機控制台)嵌入;外部網站不得 iframe 本服務
    ("Content-Security-Policy",
     "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
     "img-src 'self' data:; connect-src 'self'; frame-ancestors 'self' http://127.0.0.1:* http://localhost:*"),
)

def sh(cmd, timeout=600):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout + r.stderr)
    except subprocess.TimeoutExpired:
        return 124, f"timeout after {timeout}s"
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
    c1, o1 = sh("brew autoremove 2>&1"); c2, o2 = sh("brew cleanup -s 2>&1")
    if c1 != 0 or c2 != 0:
        return {"ok": False, "message": "brew cleanup 未完成:" + (o1 + o2).strip()[-160:]}
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
    if code == 124 or out.startswith("error:"):
        # find 逾時/失敗時 out 不是路徑清單;以前會把那串錯誤訊息當路徑跑一遍然後回報「已清理 0 條」
        return {"ok": False, "message": "掃描家目錄逾時或失敗,未刪除任何連結,請稍後再試。"}
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
    done = max(0, len(pending) - remain)
    if code != 0:
        return {"ok": False, "message": f"brew upgrade 未完全成功(完成 {done} 個,尚餘 {remain} 個):" + out.strip()[-160:]}
    return {"ok": True, "message": f"已升級 {done} 個 Homebrew 套件(尚餘 {remain} 個)。"}

def act_update_pip():
    # 只升級 pip 工具本身，且安裝到使用者目錄，不動系統 Python(遵守安全邊界)
    code, out = sh("python3 -m pip install --user --upgrade pip 2>&1", timeout=180)
    _, v = sh("python3 -m pip --version 2>/dev/null", timeout=20)
    ver = v.strip().split(" ")[1] if " " in v else ""
    if code != 0:
        return {"ok": False, "message": "pip 更新失敗:" + out.strip()[-160:]}
    return {"ok": True, "message": f"pip 已更新到最新({ver})。套件升級請於虛擬環境自行處理。"}

def act_update_npm():
    # 執行當下重新確認;更新「全部」全域 npm 套件(含 Claude Code CLI 等),不只 npm 本身
    _, before = sh("npm outdated -g --parseable 2>/dev/null", timeout=60)
    n0 = len([x for x in before.split("\n") if x.strip()])
    if n0 == 0:
        return {"ok": True, "message": "全域 npm 套件都已是最新,無需更新。"}
    code, out = sh("npm update -g 2>&1", timeout=600)
    _, after = sh("npm outdated -g --parseable 2>/dev/null", timeout=60)
    n1 = len([x for x in after.split("\n") if x.strip()])
    if code != 0:
        return {"ok": False, "message": f"npm update -g 失敗(尚餘 {n1} 個):" + out.strip()[-160:]}
    if n1 >= n0:
        return {"ok": False, "message": f"已執行 npm update -g,但仍有 {n1} 個套件未更新(可能需手動 npm install -g <套件>@latest)。"}
    return {"ok": True, "message": f"已更新全域 npm 套件({n0 - n1} 個完成,尚餘 {n1} 個)。"}

def act_thin_snapshots():
    _, before = sh("tmutil listlocalsnapshots / 2>/dev/null", timeout=30)
    n = len([l for l in before.split("\n") if l.startswith("com.apple.")])
    if n == 0:
        return {"ok": True, "message": "目前沒有本機快照，無需處理。"}
    code, out = sh("tmutil thinlocalsnapshots / 999999999999 4 2>&1", timeout=300)
    _, after = sh("tmutil listlocalsnapshots / 2>/dev/null", timeout=30)
    n2 = len([l for l in after.split("\n") if l.startswith("com.apple.")])
    if code != 0:
        return {"ok": False, "message": f"精簡快照未完成({n} → {n2} 個):" + out.strip()[-160:]}
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

if __name__ == "__main__":
    # 修復伺服器已併入 app_server.py:這裡只轉呼叫,不留第二套 HTTP 程式碼。
    import sys
    print("repair_server.py 已不再自己起伺服器;改由 app_server.py 統一提供首頁、進度、報告與一鍵修復。")
    print("等同於執行:python3 app_server.py --report " + " ".join(sys.argv[1:]))
    import app_server
    sys.exit(app_server.main(["--report"] + sys.argv[1:]))
