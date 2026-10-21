"""M10 近期當機與診斷報告 —— 掃 DiagnosticReports,依 App 聚合近 30/7 天、標 kernel panic。唯讀。"""
import os
import re
from datetime import datetime

from .base import now_iso

MODULE = "M10"
FILENAME = "m10_crashes.json"
LABEL = "近期當機"
START_MSG = "M10 近期當機與診斷報告..."

KINDS = (".crash", ".ips", ".panic", ".spin", ".hang", ".diag", ".wakeups_resource", ".cpu_resource")
DAY = 86400


def default_dirs(home=None):
    home = home or os.path.expanduser("~")
    return [os.path.join(home, "Library/Logs/DiagnosticReports"),
            "/Library/Logs/DiagnosticReports"]


def collect(dirs=None):
    dirs = dirs if dirs is not None else default_dirs()
    now = datetime.now().timestamp()

    reports = []
    for d in dirs:
        if not os.path.isdir(d): continue
        scope = "system" if d.startswith("/Library") else "user"
        try: names = os.listdir(d)
        except Exception: continue
        for fn in names:
            ext = os.path.splitext(fn)[1].lower()
            if ext not in KINDS: continue
            fp = os.path.join(d, fn)
            try: st = os.stat(fp)
            except Exception: continue
            # App 名 = 檔名在第一個 -YYYY-MM-DD 之前的部分
            app = re.split(r'[-_]\d{4}-\d{2}-\d{2}', fn)[0] or fn
            is_panic = (ext == ".panic") or ("panic" in fn.lower()) or app.lower().startswith("kernel")
            reports.append({
                "app": app, "kind": ext.lstrip("."), "file": fn, "scope": scope,
                "ts": st.st_mtime, "date": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M"),
                "is_panic": is_panic,
            })

    c30, c7 = now - 30*DAY, now - 7*DAY
    recent30 = [r for r in reports if r["ts"] >= c30]
    recent7  = [r for r in recent30 if r["ts"] >= c7]
    panic30  = [r for r in recent30 if r["is_panic"]]

    agg = {}
    for r in recent30:
        a = agg.get(r["app"])
        if not a:
            a = {"app": r["app"], "count": 0, "count7": 0, "kinds": set(),
                 "last": r["date"], "last_ts": r["ts"], "panic": False}
            agg[r["app"]] = a
        a["count"] += 1
        if r["ts"] >= c7: a["count7"] += 1
        a["kinds"].add(r["kind"])
        if r["ts"] > a["last_ts"]: a["last_ts"], a["last"] = r["ts"], r["date"]
        if r["is_panic"]: a["panic"] = True
    apps = sorted(agg.values(), key=lambda x: (x["count"], x["count7"]), reverse=True)
    for a in apps:
        a["kinds"] = ",".join(sorted(a["kinds"])); a.pop("last_ts", None)

    recent_list = sorted(recent30, key=lambda x: x["ts"], reverse=True)[:20]
    for r in recent_list: r.pop("ts", None)

    return {
      "module": MODULE, "scan_time": now_iso(),
      "total_reports": len(reports),
      "count_30d": len(recent30), "count_7d": len(recent7),
      "panic_count_30d": len(panic30),
      "apps": apps[:25],
      "recent": recent_list,
    }


def summary(r):
    apps = r["apps"]
    worst = "{}×{}".format(apps[0]['app'], apps[0]['count']) if apps else "無"
    return "  → 近30天當機報告 {} 筆(近7天 {}),核心崩潰 {},最頻繁:{}".format(
        r["count_30d"], r["count_7d"], r["panic_count_30d"], worst)
