"""M11 分享與遠端存取 —— 對 localhost 探聽通訊埠、autoLoginUser、Tailscale、非 loopback 監聽。唯讀。"""
import os
import socket

from .base import now_iso
from .base import run as _run

MODULE = "M11"
FILENAME = "m11_sharing.json"
LABEL = "分享與遠端存取"
START_MSG = "M11 分享與遠端存取..."

# (key, 中文名, port, 風險說明, 修復動作 id 或 None)
SERVICES = [
  ("remote_login",  "遠端登入 (SSH)",   22,   "允許他人用帳密/金鑰透過 SSH 登入這台 Mac", "disable_remote_login"),
  ("screen_sharing","螢幕共享 (VNC)",   5900, "允許他人遠端看見並控制你的桌面",          "disable_screen_sharing"),
  ("file_sharing",  "檔案共享 (SMB)",   445,  "對外開放分享資料夾",                      None),
  ("file_sharing_afp","檔案共享 (AFP)", 548,  "對外開放分享資料夾(舊版協定)",            None),
  ("remote_mgmt",   "遠端管理 (ARD)",   3283, "Apple Remote Desktop 遠端管理",          None),
]


def port_open(port, host="127.0.0.1", timeout=1.0):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def run(cmd):
    # 原 heredoc:只取 stdout、strip、15 秒逾時、例外回 ""
    return _run(cmd, timeout=15, error_value="")


# ── Tailscale 偵測(VPN/mesh 對外暴露,不在那 5 個 Apple 服務內)──
def find_tailscale():
    for c in ["/Applications/Tailscale.app/Contents/MacOS/Tailscale",
              "/opt/homebrew/bin/tailscale", "/usr/local/bin/tailscale"]:
        if os.path.exists(c):
            return c
    p = run("command -v tailscale 2>/dev/null")
    return p if p else ""


def _proxy_active(out):
    o = (out or "").strip().lower()
    return bool(o) and "no serve" not in o and "no funnel" not in o and "no config" not in o and "error" not in o[:6]


def parse_external_listeners(lsof_out):
    """lsof -nP -iTCP -sTCP:LISTEN 的輸出 → 綁在「非 loopback」介面的監聽埠(別的裝置/tailnet 碰得到的真實面)。"""
    external = []; seen = set()
    for line in lsof_out.split("\n")[1:]:
        parts = line.split()
        if len(parts) < 2:
            continue
        proc = parts[0]; nameaddr = parts[-1]
        if "->" in nameaddr:
            continue
        if nameaddr.startswith("["):           # IPv6  [addr]:port
            addr = nameaddr.split("]")[0].lstrip("[")
            port = nameaddr.rsplit(":", 1)[-1]
        elif ":" in nameaddr:                   # IPv4 addr:port
            addr, port = nameaddr.rsplit(":", 1)
        else:
            continue
        if addr in ("127.0.0.1", "::1", "localhost", ""):   # loopback 不算對外
            continue
        key = (proc, addr, port)
        if key in seen:
            continue
        seen.add(key)
        external.append({"proc": proc, "addr": addr, "port": port})
    external.sort(key=lambda x: x["proc"].lower())
    return external


def collect():
    services = []
    open_count = 0
    for key, name, port, risk, action in SERVICES:
        is_open = port_open(port)
        if is_open: open_count += 1
        services.append({"key": key, "name": name, "port": port, "risk": risk,
                         "state": "on" if is_open else "off", "action": action})

    # 自動登入(唯讀;空 = 未設定)
    auto_login_user = run("defaults read /Library/Preferences/com.apple.loginwindow autoLoginUser 2>/dev/null")
    auto_login = bool(auto_login_user) and "does not exist" not in auto_login_user.lower()

    ts_bin = find_tailscale()
    ts_running = bool(run("pgrep -x tailscaled") or run("pgrep -f 'Tailscale.app'"))
    ts_serve  = run("'{}' serve status 2>/dev/null".format(ts_bin)) if ts_bin else ""
    ts_funnel = run("'{}' funnel status 2>/dev/null".format(ts_bin)) if ts_bin else ""
    tailscale = {
      "installed": bool(ts_bin) or ts_running,
      "running": ts_running,
      "serve_active": _proxy_active(ts_serve),
      "funnel_active": _proxy_active(ts_funnel),   # funnel = 暴露到公開網際網路!
      "serve_raw": (ts_serve or "")[:1500],
      "funnel_raw": (ts_funnel or "")[:1500],
    }

    external = parse_external_listeners(run("lsof -nP -iTCP -sTCP:LISTEN 2>/dev/null"))

    return {
      "module": MODULE, "scan_time": now_iso(),
      "services": services,
      "open_count": open_count,
      "auto_login": auto_login,
      "auto_login_user": auto_login_user if auto_login else "",
      "tailscale": tailscale,
      "external_listeners": external[:40],
      "external_count": len(external),
    }


def summary(r):
    ts = r["tailscale"]
    ts_state = ('執行中' if ts["running"] else '未執行') + \
               (", serve={}, funnel={}".format(ts['serve_active'], ts['funnel_active']) if ts["running"] else "")
    return "  → 對外服務 {}/5;Tailscale {};非 loopback 監聽 {} 個;自動登入:{}".format(
        r["open_count"], ts_state, r["external_count"], '是' if r["auto_login"] else '否')
