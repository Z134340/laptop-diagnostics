"""M7 系統健康 —— diskutil(SMART)、memory_pressure、swap、APFS 快照、即時資源 Top。唯讀。"""
import re

from .base import now_iso
from .base import run as _run

MODULE = "M7"
FILENAME = "m7_system.json"
LABEL = "系統健康"
START_MSG = "M7 系統健康..."


def run(cmd):
    # 原 heredoc:只取 stdout、strip、60 秒逾時、例外回 "error: ..."
    return _run(cmd, timeout=60)


# 即時資源占用 Top(快照,瞬時值;-r 依 CPU 排序、-m 依記憶體排序)
def parse_ps(raw):
    rows = []
    for line in raw.strip().split("\n")[1:]:  # 跳表頭
        parts = line.split(None, 3)
        if len(parts) == 4 and parts[0].isdigit():
            rows.append({"pid": parts[0], "cpu": parts[1], "mem": parts[2], "name": parts[3]})
    return rows


def _maxcpu(rows):
    vals = []
    for r in rows:
        try: vals.append(float(r["cpu"]))
        except Exception: pass
    return max(vals) if vals else 0.0


def collect():
    disk = run("diskutil info / 2>/dev/null")
    def g(key, text=disk):
        m = re.search(r"{}:\s*(.+)".format(key), text)
        return m.group(1).strip() if m else "—"

    snaps = run("tmutil listlocalsnapshots / 2>/dev/null")
    snap_list = [l.strip() for l in snaps.split("\n") if l.startswith("com.apple.")]
    mem = run("memory_pressure 2>/dev/null | tail -2")
    mem_free = "—"
    mm = re.search(r"free percentage:\s*(\d+%)", mem)
    if mm: mem_free = mm.group(1)

    top_cpu = parse_ps(run("ps -arcwwwxo pid,pcpu,pmem,comm 2>/dev/null | head -9"))
    top_mem = parse_ps(run("ps -amcwwwxo pid,pcpu,pmem,comm 2>/dev/null | head -9"))
    top_cpu_max = _maxcpu(top_cpu)

    return {
      "module": MODULE, "scan_time": now_iso(),
      "smart_status":        g("SMART Status"),
      "volume_name":         g("Volume Name"),
      "container_total":     g("Container Total Space"),
      "container_free":      g("Container Free Space"),
      "memory_free_pct":     mem_free,
      "swap_usage":          run("sysctl -n vm.swapusage 2>/dev/null"),
      "uptime":              run("uptime"),
      "local_snapshots_count": len(snap_list),
      "local_snapshots":     snap_list[:20],
      "top_cpu":             top_cpu,
      "top_mem":             top_mem,
      "top_cpu_max":         top_cpu_max,
    }


def summary(r):
    top_cpu = r["top_cpu"]
    busiest = (top_cpu[0]["name"] + " " + top_cpu[0]["cpu"] + "%") if top_cpu else "—"
    return "  → SMART:{},可用 {},快照 {} 個,最忙程序 {}".format(
        r['smart_status'], r['container_free'], r['local_snapshots_count'], busiest)
