"""M8 登入與背景項目 —— LaunchAgents / LaunchDaemons / 登入項目(osascript)。唯讀。"""
import os

from .base import now_iso
from .base import run as _run

MODULE = "M8"
FILENAME = "m8_startup.json"
LABEL = "登入與背景項目"
START_MSG = "M8 登入與背景項目..."


def listdir(p):
    try: return sorted(f for f in os.listdir(p) if f.endswith(".plist"))
    except Exception: return []


def run(cmd):
    # 原 heredoc:只取 stdout、strip、20 秒逾時、例外回 ""
    return _run(cmd, timeout=20, error_value="")


# 標出第三方(非 com.apple.)自啟項目
def third_party(lst):
    return [x for x in lst if not x.startswith("com.apple.")]


def collect(home=None):
    home = home or os.path.expanduser("~")
    user_agents   = listdir(os.path.join(home,"Library/LaunchAgents"))
    sys_agents    = listdir("/Library/LaunchAgents")
    sys_daemons   = listdir("/Library/LaunchDaemons")

    login_raw = run('osascript -e \'tell application "System Events" to get the name of every login item\'')
    login_items = [x.strip() for x in login_raw.split(",") if x.strip()] if login_raw else []

    return {
      "module": MODULE, "scan_time": now_iso(),
      "login_items": login_items,
      "user_launch_agents": user_agents,
      "system_launch_agents": sys_agents,
      "system_launch_daemons": sys_daemons,
      "third_party_user_agents": third_party(user_agents),
      "third_party_system_agents": third_party(sys_agents),
      "counts": {
        "login_items": len(login_items),
        "user_agents": len(user_agents),
        "system_agents": len(sys_agents),
        "system_daemons": len(sys_daemons),
      }
    }


def summary(r):
    c = r["counts"]
    return "  → 登入項目 {},使用者代理 {},系統代理 {},常駐 {}".format(
        c["login_items"], c["user_agents"], c["system_agents"], c["system_daemons"])
