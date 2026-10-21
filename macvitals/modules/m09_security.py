"""M9 安全與更新狀態 —— FileVault / SIP / Gatekeeper / 防火牆 / softwareupdate / System Extensions。唯讀。"""
from .base import now_iso
from .base import run as _run

MODULE = "M9"
FILENAME = "m9_security.json"
LABEL = "安全與更新"
START_MSG = "M9 安全與更新狀態..."


def run(cmd, timeout=60):
    # 原 heredoc:只取 stdout、strip、預設 60 秒逾時、例外回 "error: ..."
    return _run(cmd, timeout=timeout)


def status_of(text, on_kw, off_kw):
    t = text.lower()
    if off_kw in t: return "off"
    if on_kw in t:  return "on"
    return "unknown"


def collect():
    filevault  = run("fdesetup status 2>&1")
    sip        = run("csrutil status 2>&1")
    gatekeeper = run("spctl --status 2>&1")
    firewall   = run("/usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate 2>&1")

    # System Extensions(第三方核心/網路擴充;老舊或殘留者是當機/卡頓常見元兇,唯讀)
    sysext = run("systemextensionsctl list 2>&1")
    sysext_active = [l.strip() for l in sysext.split("\n")
                     if "activated" in l.lower() and "enabled" in l.lower()]

    # 待安裝更新(network,可能較慢;逾時則標記)
    sw = run("softwareupdate -l 2>&1", timeout=90)
    updates = [l.strip() for l in sw.split("\n") if l.strip().startswith("* Label:")]

    return {
      "module": MODULE, "scan_time": now_iso(),
      "filevault":  {"raw": filevault,  "state": "on" if "is on" in filevault.lower() else ("off" if "is off" in filevault.lower() else "unknown")},
      "sip":        {"raw": sip,        "state": "on" if "enabled" in sip.lower() else ("off" if "disabled" in sip.lower() else "unknown")},
      "gatekeeper": {"raw": gatekeeper, "state": "on" if "enabled" in gatekeeper.lower() else ("off" if "disabled" in gatekeeper.lower() else "unknown")},
      "firewall":   {"raw": firewall,   "state": "off" if "disabled" in firewall.lower() or "= 0" in firewall else ("on" if "enabled" in firewall.lower() else "unknown")},
      "pending_updates": updates,
      "pending_updates_count": len(updates),
      "softwareupdate_raw": sw[:2000],
      "system_extensions": {
        "active_count": len(sysext_active),
        "active": sysext_active[:30],
        "raw": sysext[:1500],
      },
    }


def summary(r):
    return "  → FileVault {} / SIP {} / Gatekeeper {} / 防火牆 {};待更新 {} 項".format(
        r['filevault']['state'], r['sip']['state'], r['gatekeeper']['state'], r['firewall']['state'],
        r["pending_updates_count"])
