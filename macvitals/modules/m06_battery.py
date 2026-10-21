"""M6 電池與電源健康 —— system_profiler SPPowerDataType。唯讀。"""
import re

from .base import now_iso
from .base import run as _run

MODULE = "M6"
FILENAME = "m6_battery.json"
LABEL = "電池"
START_MSG = "M6 電池健康..."


def run(cmd):
    # 原 heredoc:只取 stdout、不 strip、30 秒逾時、例外回 ""
    return _run(cmd, timeout=30, strip=False, error_value="")


def collect():
    raw = run("system_profiler SPPowerDataType 2>/dev/null")
    def grab(key):
        m = re.search(r"{}:\s*(.+)".format(key), raw)
        return m.group(1).strip() if m else "—"

    return {
      "module": MODULE, "scan_time": now_iso(),
      "cycle_count":      grab("Cycle Count"),
      "condition":        grab("Condition"),
      "maximum_capacity": grab("Maximum Capacity"),
      "fully_charged":    grab("Fully Charged"),
      "charging":         grab("Charging"),
      "power_source":     grab("Connected") if "Connected" in raw else grab("Power Source State"),
      "raw": raw[:4000],
    }


def summary(r):
    return "  → 電池:循環 {},容量 {},狀態 {}".format(r['cycle_count'], r['maximum_capacity'], r['condition'])
