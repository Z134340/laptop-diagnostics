#!/usr/bin/env python3
"""
generate_report.py
讀取 report/data/*.json，輸出 report/index.html 互動式診斷報告
(含「摘要」首頁、SVG icon、白話說明、檔案用途說明)
"""
import json, os, sys, re
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).parent
DATA_DIR   = SCRIPT_DIR / "report" / "data"
OUT_HTML   = SCRIPT_DIR / "report" / "index.html"

def load(name):
    p = DATA_DIR / name
    if p.exists():
        with open(p) as f:
            return json.load(f)
    return None

def fmt_bytes(b):
    try: b = float(b)
    except Exception: return "—"
    if b >= 1024**3: return f"{b/1024**3:.2f} GB"
    if b >= 1024**2: return f"{b/1024**2:.1f} MB"
    if b >= 1024:    return f"{b/1024:.1f} KB"
    return f"{int(b)} B"

m1 = load("m1_dupes.json")
m2 = load("m2_broken.json")
m3 = load("m3_large.json")
m4 = load("m4_env.json")
m5 = load("m5_reclaimable.json")
m6 = load("m6_battery.json")
m7 = load("m7_system.json")
m8 = load("m8_startup.json")
m9 = load("m9_security.json")
m10 = load("m10_crashes.json")
m11 = load("m11_sharing.json")

scan_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# ── SVG icon helper ───────────────────────────────────────────
def ic(name, cls=""):
    return f"<svg class='ic {cls}' aria-hidden='true'><use href='#ic-{name}'/></svg>"

def note(text):
    return f"<div class='note-box'>{ic('info')}<span>{text}</span></div>"

# ── 檔案用途白話說明 ──────────────────────────────────────────
EXT_DESC = {
  ".dmg":"磁碟映像檔(安裝程式),裝完通常可刪", ".pkg":"安裝套件,安裝後通常可刪",
  ".zip":"壓縮封存檔", ".tar":"壓縮封存檔", ".gz":"壓縮檔", ".tgz":"壓縮封存檔", ".bz2":"壓縮檔", ".7z":"壓縮檔", ".rar":"壓縮檔",
  ".iso":"光碟映像檔",
  ".mp4":"影片檔", ".mov":"影片檔", ".mkv":"影片檔", ".avi":"影片檔", ".m4v":"影片檔", ".webm":"影片檔",
  ".mp3":"音訊檔", ".wav":"音訊檔", ".aiff":"音訊檔", ".flac":"音訊檔", ".m4a":"音訊檔",
  ".jpg":"圖片", ".jpeg":"圖片", ".png":"圖片", ".gif":"圖片", ".heic":"iPhone 照片", ".tiff":"圖片",
  ".raw":"相機原始檔", ".cr2":"相機原始檔", ".psd":"Photoshop 檔", ".ai":"Illustrator 檔", ".sketch":"Sketch 設計檔",
  ".pdf":"PDF 文件", ".doc":"Word 文件", ".docx":"Word 文件", ".ppt":"簡報", ".pptx":"簡報", ".xls":"試算表", ".xlsx":"試算表", ".key":"Keynote 簡報",
  ".sqlite":"資料庫檔", ".db":"資料庫檔", ".realm":"資料庫檔",
  ".app":"應用程式", ".ipa":"iOS App 安裝檔", ".apk":"Android App 安裝檔",
  ".vmdk":"虛擬機磁碟", ".qcow2":"虛擬機磁碟", ".vdi":"虛擬機磁碟", ".raw":"原始磁碟映像",
  ".log":"記錄檔", ".bin":"二進位資料檔(常為模型/權重)", ".dat":"資料檔", ".node":"Node 原生模組",
  ".framework":"程式框架", ".xcarchive":"Xcode 封存檔", ".band":"GarageBand 專案",
  ".sas7bdat":"SAS 統計資料集", ".img":"磁碟映像檔", ".jsonl":"JSON Lines 記錄檔",
  ".zst":"Zstandard 壓縮檔", ".dylib":"動態函式庫(程式元件)", ".csv":"表格資料(CSV)", ".parquet":"欄式資料檔",
}
def explain_file(path, ext):
    p = (path or "").lower()
    name = os.path.basename(p)
    ext = (ext or "").lower()
    if "docker" in p and (name.endswith(".raw") or "data.vmdk" in name or name.endswith(".qcow2")):
        return "Docker 虛擬磁碟(所有容器/映像在此,佔用大但勿手動刪)"
    if "vm_bundles" in p or "claudevm" in p or (name.endswith(".img") and "bundle" in p) or name.endswith(".img.zst"):
        return "App 虛擬機磁碟映像(執行環境,勿手動刪)"
    if ".photoslibrary" in p: return "照片圖庫(你的照片資料庫)"
    if "coresimulator" in p:  return "iOS 模擬器資料(Xcode),可用 simctl 清理"
    if "deriveddata" in p:    return "Xcode 編譯中繼檔,可安全清理"
    if "sleepimage" in name:  return "休眠記憶體映像(系統管理,勿刪)"
    if "swapfile" in name or "/vm/" in p: return "虛擬記憶體交換檔(系統管理)"
    if "crx_cache" in p or "ondevicemodel" in p or "optguide" in p or name.startswith("weights"):
        return "瀏覽器/AI 模型快取(會自動重建)"
    if "/caches/" in p or p.endswith("/caches"): return "App 快取,可清理會自動重建"
    if "/.trash" in p:        return "垃圾桶內容,可清空"
    if "node_modules" in p:   return "Node.js 套件相依目錄"
    if "/library/containers/" in p: return "App 沙盒容器資料"
    if "/mobilesync/backup" in p: return "iOS 裝置備份"
    # App 本體 / 框架 / 開發工具元件(勿單獨刪)
    if "commandlinetools" in p or "/developer/" in p or name in ("swift-frontend",) or "lldb" in name.lower():
        return "Xcode 開發工具元件(系統/CLT,勿單獨刪)"
    if ".framework/" in p or "frameworks/" in p:
        return "App 程式框架元件(App 本體一部分,勿單獨刪)"
    if "/applications/" in p and ".app/" in p:
        return "應用程式內部元件(勿單獨刪)"
    if "/downloads/" in p and ext not in EXT_DESC: return "你下載的檔案"
    if ext in EXT_DESC:       return EXT_DESC[ext]
    if "/downloads/" in p:    return "你下載的檔案"
    if "/documents/" in p:    return "你的文件檔案"
    return "一般檔案"

TOOL_DESC = {
  "node":"JavaScript 執行環境", "npm":"Node 套件管理器", "npx":"執行 Node 套件的工具",
  "python3":"Python 直譯器", "pip3":"Python 套件管理器", "ruby":"Ruby 直譯器",
  "go":"Go 編譯器", "java":"Java 執行環境", "git":"版本控制工具", "docker":"容器平台", "brew":"macOS 套件管理器",
}

# ── 各模組摘要數值 ────────────────────────────────────────────
m1_wasted = fmt_bytes(m1.get("total_wasted_bytes", 0)) if m1 else "—"
m1_groups = m1.get("total_groups", 0) if m1 else 0
m2_total  = m2.get("broken_symlinks_count", 0) if m2 else 0
m2_stale  = m2.get("stale_count", 0) if m2 else 0
m2_cats   = m2.get("categories", {}) if m2 else {}
m2_sandbox= m2_cats.get("sandbox_template", 0)
m2_applock= m2_cats.get("app_lock", 0)
m2_brew   = m2.get("brew_issues_count", 0) if m2 else 0
m3_total  = m3.get("total_found", 0) if m3 else 0
m3_gb     = m3.get("total_size_gb", 0) if m3 else 0
m4_tools  = len([v for v in (m4 or {}).get("versions", {}).values() if "not found" not in v and "error" not in v.lower()]) if m4 else 0
m5_total  = fmt_bytes(m5.get("total_reclaimable_bytes", 0)) if m5 else "—"
m5_bytes  = m5.get("total_reclaimable_bytes", 0) if m5 else 0
m6_cycle  = (m6 or {}).get("cycle_count", "—")
m6_cap    = (m6 or {}).get("maximum_capacity", "—")
m6_cond   = (m6 or {}).get("condition", "—")
m6_chg    = (m6 or {}).get("charging", "—")
m7_smart  = (m7 or {}).get("smart_status", "—")
m7_free   = (m7 or {}).get("container_free", "—")
m7_total_d= (m7 or {}).get("container_total", "—")
m7_mem    = (m7 or {}).get("memory_free_pct", "—")
m7_swap   = (m7 or {}).get("swap_usage", "—")
m7_snaps  = (m7 or {}).get("local_snapshots_count", 0) if m7 else 0
m7_uptime = (m7 or {}).get("uptime", "—")
m8_login_n= (m8 or {}).get("counts", {}).get("login_items", 0) if m8 else 0
m8_uagent_n=(m8 or {}).get("counts", {}).get("user_agents", 0) if m8 else 0
m8_sagent_n=(m8 or {}).get("counts", {}).get("system_agents", 0) if m8 else 0
m8_daemon_n=(m8 or {}).get("counts", {}).get("system_daemons", 0) if m8 else 0
m8_tp      = ((m8 or {}).get("third_party_user_agents", []) + (m8 or {}).get("third_party_system_agents", []))
m9_fw      = (m9 or {}).get("firewall", {}).get("state", "unknown")
m9_upd_n   = (m9 or {}).get("pending_updates_count", 0) if m9 else 0

# ── M1 / M3 檔案列(含白話說明欄）─────────────────────────────
m1_rows = ""
if m1:
    for i, g in enumerate(m1.get("groups", []), 1):
        first = g["files"][0]
        desc  = explain_file(first, os.path.splitext(first)[1])
        files_html = "".join(f"<div class='dupe-path'>{f}</div>" for f in g["files"])
        m1_rows += (f"<tr data-wasted=\"{g['wasted_bytes']}\"><td>{i}</td>"
                    f"<td>{fmt_bytes(g['size_bytes'])}</td><td>{g['count']}</td>"
                    f"<td class='warn'>{fmt_bytes(g['wasted_bytes'])}</td>"
                    f"<td><div class='expandable' onclick=\"this.classList.toggle('open')\">{files_html}</div></td>"
                    f"<td class='muted'>{desc}</td></tr>")

m3_rows = ""
if m3:
    for i, f in enumerate(m3.get("files", []), 1):
        desc = explain_file(f['path'], f.get('ext',''))
        m3_rows += (f"<tr><td>{i}</td><td class='file-path'>{f['path']}</td>"
                    f"<td class='num'>{f['size_mb']} MB</td><td>{f.get('last_modified','—')}</td>"
                    f"<td>{f.get('last_access','—')}</td><td>{f.get('ext','—')}</td>"
                    f"<td class='muted'>{desc}</td></tr>")

# ── M2 列 ─────────────────────────────────────────────────────
m2_stale_rows = ""
if m2:
    for item in m2.get("stale_symlinks", []):
        m2_stale_rows += f"<tr><td class='warn'>{item['path']}</td><td class='file-path'>{item.get('target','')}</td></tr>"
m2_brew_rows = ""
if m2:
    for issue in m2.get("brew_issues", []):
        cls = "error" if "Error" in issue else "warn"
        m2_brew_rows += f"<tr><td><pre class='{cls}'>{issue}</pre></td></tr>"

# ── M4 列 ─────────────────────────────────────────────────────
def ver_row(name, val):
    bad = ("not found" in val or "error" in val.lower())
    icon = ic("x", "ic-err") if bad else ic("check", "ic-ok")
    return f"<tr><td>{name}</td><td class='muted'>{TOOL_DESC.get(name,'')}</td><td>{icon}</td><td><code>{val[:80]}</code></td></tr>"
m4_ver_rows = "".join(ver_row(k, v) for k, v in (m4 or {}).get("versions", {}).items())
m4_npm_doc  = (m4 or {}).get("npm_doctor", "—")
m4_brew_pkg = (m4 or {}).get("brew_installed_packages", "—")
m4_pip_out  = (m4 or {}).get("pip_outdated", "—")
m4_nvm      = (m4 or {}).get("nvm_versions", "—")
m4_pyenv    = (m4 or {}).get("pyenv_versions", "—")

# ── M5 列 ─────────────────────────────────────────────────────
m5_rows = ""
if m5:
    for it in m5.get("items", []):
        m5_rows += (f"<tr><td>{it['label']}</td><td class='file-path'>{it['path']}</td>"
                    f"<td class='num'>{fmt_bytes(it['size_bytes'])}</td><td class='muted'>{it.get('note','')}</td></tr>")

# ── M8 列 ─────────────────────────────────────────────────────
def li_rows(items, highlight=False):
    if not items: return "<tr><td class='muted'>（無）</td></tr>"
    cls = "warn" if highlight else ""
    return "".join(f"<tr><td class='{cls}'>{x}</td></tr>" for x in items)
m8_login   = li_rows((m8 or {}).get("login_items", []))
m8_tp_user = li_rows((m8 or {}).get("third_party_user_agents", []), highlight=True)
m8_tp_sys  = li_rows((m8 or {}).get("third_party_system_agents", []), highlight=True)

# ── M9 安全卡 ─────────────────────────────────────────────────
def sec_card(label, state, hint):
    if state == "on":    cls, icon = "ok", "check"
    elif state == "off": cls, icon = "danger", "x"
    else:                cls, icon = "warn", "alert"
    txt = {"on":"開啟","off":"關閉","unknown":"未知"}.get(state, state)
    return (f"<div class='card {cls}'><div class='label'>{label}</div>"
            f"<div class='value'>{ic(icon,'ic-lg')}</div><div class='sub'>{txt}</div>"
            f"<div class='card-hint'>{hint}</div></div>")
m9_cards = ""
if m9:
    m9_cards += sec_card("FileVault 磁碟加密", m9.get("filevault", {}).get("state","unknown"), "遺失時保護資料")
    m9_cards += sec_card("SIP 系統完整性",     m9.get("sip", {}).get("state","unknown"), "防止竄改系統")
    m9_cards += sec_card("Gatekeeper",         m9.get("gatekeeper", {}).get("state","unknown"), "阻擋未簽章程式")
    m9_cards += sec_card("防火牆",              m9.get("firewall", {}).get("state","unknown"), "阻擋未授權連線")
m9_updates = (m9 or {}).get("pending_updates", [])
m9_upd_rows = "".join(f"<tr><td class='warn'>{u.replace('* Label: ','')}</td></tr>" for u in m9_updates) or "<tr><td class='ok'>系統已是最新</td></tr>"

# ── M7 即時資源占用 Top ───────────────────────────────────────
def proc_rows(rows):
    out = ""
    for p in rows or []:
        try: hot = float(p.get("cpu","0")) >= 70
        except Exception: hot = False
        out += (f"<tr><td class=\"{'warn' if hot else ''}\">{p.get('name','')}</td>"
                f"<td class='num'>{p.get('cpu','—')}%</td><td class='num'>{p.get('mem','—')}%</td>"
                f"<td class='muted'>{p.get('pid','')}</td></tr>")
    return out or "<tr><td colspan='4' class='empty'>無資料</td></tr>"
m7_cpu_rows = proc_rows((m7 or {}).get("top_cpu", []))
m7_mem_rows = proc_rows((m7 or {}).get("top_mem", []))
m7_top_cpu_max = (m7 or {}).get("top_cpu_max", 0) or 0
m7_busiest = ((m7 or {}).get("top_cpu") or [{}])[0].get("name", "—")

# ── M9 System Extensions ─────────────────────────────────────
m9_sysext = (m9 or {}).get("system_extensions", {}) or {}
m9_sysext_n = m9_sysext.get("active_count", 0)
m9_sysext_rows = "".join(f"<tr><td class='file-path'>{x}</td></tr>" for x in m9_sysext.get("active", [])) \
                 or "<tr><td class='ok'>無第三方 system extension(乾淨)</td></tr>"

# ── M10 近期當機 ──────────────────────────────────────────────
m10_30d  = (m10 or {}).get("count_30d", 0)
m10_panic= (m10 or {}).get("panic_count_30d", 0)
m10_apps = (m10 or {}).get("apps", [])
m10_worst = m10_apps[0] if m10_apps else None
m10_worst_30d = (m10_worst or {}).get("count", 0)
m10_app_rows = ""
for a in m10_apps:
    hot = a.get("count", 0) >= 5 or a.get("panic")
    badge = " <span class='hl-badge danger'>核心崩潰</span>" if a.get("panic") else ""
    m10_app_rows += (f"<tr><td class=\"{'warn' if hot else ''}\">{a.get('app','')}{badge}</td>"
                     f"<td class='num'>{a.get('count',0)}</td>"
                     f"<td class='muted'>{a.get('kinds','')}</td><td class='muted'>{a.get('last','')}</td></tr>")
m10_app_rows = m10_app_rows or "<tr><td colspan='4' class='empty'>近 30 天無當機紀錄</td></tr>"
m10_recent_rows = "".join(
    f"<tr><td>{r.get('app','')}</td><td>{r.get('kind','')}</td><td class='muted'>{r.get('date','')}</td>"
    f"<td class='muted'>{r.get('scope','')}</td></tr>" for r in (m10 or {}).get("recent", [])
) or "<tr><td colspan='4' class='empty'>無</td></tr>"

# ── M11 分享 / 遠端存取 ───────────────────────────────────────
m11_services = (m11 or {}).get("services", [])
m11_open_n   = (m11 or {}).get("open_count", 0)
m11_autologin= (m11 or {}).get("auto_login", False)
m11_open_services = [s for s in m11_services if s.get("state") == "on"]
m11_state = {s.get("key"): s.get("state") for s in m11_services}
# 已開放、但無一鍵修復(僅導引到系統設定)的服務名稱
m11_other_open = [s["name"] for s in m11_open_services if not s.get("action")]
def _m11_badge(state):
    return (f"<span class='hl-badge warn'>開啟</span>" if state == "on"
            else "<span class='cov-off'>關閉</span>")
m11_rows = "".join(
    f"<tr><td class=\"{'warn' if s.get('state')=='on' else ''}\">{s.get('name','')}</td>"
    f"<td class='num'>{s.get('port','')}</td><td>{_m11_badge(s.get('state'))}</td>"
    f"<td class='muted'>{s.get('risk','')}</td></tr>" for s in m11_services
) or "<tr><td colspan='4' class='empty'>無資料</td></tr>"

# Tailscale 與「非 loopback 監聽埠」(真實對外存取面,超出那 5 個 Apple 服務)
m11_ts = (m11 or {}).get("tailscale", {})
m11_ts_running = m11_ts.get("running", False)
m11_ts_serve   = m11_ts.get("serve_active", False)
m11_ts_funnel  = m11_ts.get("funnel_active", False)
m11_ext = (m11 or {}).get("external_listeners", [])
m11_ext_n = (m11 or {}).get("external_count", 0)
m11_ext_rows = "".join(
    f"<tr><td>{e.get('proc','')}</td><td class='file-path'>{e.get('addr','')}</td><td class='num'>{e.get('port','')}</td></tr>"
    for e in m11_ext
) or "<tr><td colspan='3' class='empty'>無服務綁在非 loopback(外部裝置碰不到)✓</td></tr>"
if not m11_ts_running:
    m11_ts_summary, m11_ts_cls = "未執行", "ok"
elif m11_ts_funnel:
    m11_ts_summary, m11_ts_cls = "Funnel 對公網暴露!", "danger"
elif m11_ts_serve:
    m11_ts_summary, m11_ts_cls = "Serve 對 tailnet 暴露", "warn"
else:
    m11_ts_summary, m11_ts_cls = "執行中 · 未對外代理", "info"

# ── 修復規則登錄表 (rule registry) ────────────────────────────
# 「掃描結果 → 修復計畫」的單一對照表。報告產生時逐條套用「當次掃描資料」,
# applies() 命中才長出對應的重點與按鈕。新增一種修復 = 加一條規則(+伺服器動作)。
m4_brew_outdated_n = (m4 or {}).get("brew_outdated_count", 0)
m4_pip_outdated_n  = (m4 or {}).get("pip_outdated_count", 0)
m4_npm_g_outdated_n= (m4 or {}).get("npm_global_outdated_count", 0)

# M7 磁碟 / M6 電池 / M9 安全 的結構化判讀(供規則表)
def _bytes(s):
    m = re.search(r'\((\d+) Bytes\)', str(s or ''))
    return int(m.group(1)) if m else 0
m7_free_b   = _bytes(m7_free)
m7_total_b  = _bytes(m7_total_d)
m7_free_pct = (m7_free_b / m7_total_b * 100) if m7_total_b else 100.0
m7_smart_ok = "verif" in str(m7_smart).lower()
_cap_m      = re.search(r'(\d+)', str(m6_cap))
m6_cap_num  = int(_cap_m.group(1)) if _cap_m else 100
m6_degraded = (m6_cap_num < 80) or (str(m6_cond).strip().lower() not in ("normal","good","—",""))
m9_fv = (m9 or {}).get("filevault", {}).get("state", "unknown")
m9_sip= (m9 or {}).get("sip", {}).get("state", "unknown")
m9_gk = (m9 or {}).get("gatekeeper", {}).get("state", "unknown")

RULES = [
  {"id":"firewall_off", "applies": lambda: m9_fw == "off", "sev":"danger", "icon":"shield", "tab":9,
   "title": lambda: "防火牆未開啟",
   "desc":"防火牆負責阻擋外部未經授權連到你電腦。目前是關閉的,強烈建議開啟。點「一鍵開啟」會跳出系統授權視窗。",
   "action":{"id":"enable_firewall","label":"一鍵開啟防火牆","confirm":"將開啟 macOS 防火牆(會跳出輸入密碼的授權視窗)。確定?"}},

  {"id":"os_updates", "applies": lambda: m9_upd_n > 0, "sev":"warn", "icon":"refresh", "tab":9,
   "title": lambda: f"{m9_upd_n} 項系統更新待安裝",
   "desc":"更新通常包含安全性修補。點「開啟更新頁」會直接帶你到系統設定的「軟體更新」。",
   "action":{"id":"open_software_update","label":"開啟更新頁","confirm":"將開啟系統設定的「軟體更新」頁面。確定?"}},

  {"id":"brew_outdated", "applies": lambda: m4_brew_outdated_n > 0, "sev":"warn", "icon":"refresh", "tab":4,
   "title": lambda: f"{m4_brew_outdated_n} 個 Homebrew 套件可升級",
   "desc":"已安裝的 Homebrew 套件有新版。點「一鍵升級」會執行 brew upgrade 全部升級(含相依)。",
   "action":{"id":"brew_upgrade","label":"一鍵升級 Homebrew","confirm":"將執行 brew upgrade 升級所有可更新的 Homebrew 套件,可能需要幾分鐘。確定?"}},

  {"id":"pip_outdated", "applies": lambda: m4_pip_outdated_n > 0, "sev":"info", "icon":"terminal", "tab":4,
   "title": lambda: f"pip 與 {m4_pip_outdated_n} 個套件版本過舊",
   "desc":"pip 工具本身版本偏舊。點「更新 pip」會安全地把 pip 升級到最新(安裝到使用者目錄,不動系統 Python)。各套件升級涉及相依風險,建議到 M4 檢視後於虛擬環境處理。",
   "action":{"id":"update_pip","label":"更新 pip","confirm":"將把 pip 工具升級到最新版(--user,不影響系統 Python)。確定?"}},

  {"id":"npm_global_outdated", "applies": lambda: m4_npm_g_outdated_n > 0, "sev":"info", "icon":"terminal", "tab":4,
   "title": lambda: f"npm 有 {m4_npm_g_outdated_n} 個全域套件可更新",
   "desc":"全域 npm 套件有新版(例如 Claude Code CLI 更新頻繁,幾乎每天有新版)。點「更新全域 npm」會用 npm update -g 把它們一起更到最新,更新後此項就會消失。",
   "action":{"id":"update_npm","label":"更新全域 npm","confirm":"將執行 npm update -g 更新所有全域 npm 套件(含 Claude Code CLI 等)到最新。確定?"}},

  {"id":"third_party_agents", "applies": lambda: bool(m8_tp), "sev":"warn", "icon":"power", "tab":8,
   "title": lambda: f"{len(m8_tp)} 個第三方開機自啟項目",
   "desc":"這些程式會在你登入時自動執行並常駐背景,可能拖慢開機、佔用資源。需逐一判斷,請到 M8 檢視後自行停用。",
   "action": None},

  {"id":"reclaimable", "applies": lambda: m5_bytes > 300*1024*1024, "sev":"info", "icon":"recycle", "tab":5,
   "title": lambda: f"約 {m5_total} 可回收空間",
   "desc":"主要是 brew/npm/pip/node-gyp/Mail 等安全快取,清理後會自動重建,不會遺失資料。",
   "action":{"id":"clear_caches","label":"一鍵清理快取","confirm":"將清理 brew/npm/pip/node-gyp/Mail 快取(App 會自動重建)。確定?"}},

  {"id":"m2_issues", "applies": lambda: (m2_stale + m2_brew) > 0, "sev":"warn", "icon":"unlink", "tab":2,
   "title": lambda: f"{m2_stale + m2_brew} 項損壞/設定待處理",
   "desc":"包含真正的殘留捷徑與 Homebrew PATH 設定;其餘數千條斷裂捷徑屬 macOS 正常設計,免處理。",
   "action":{"id":"fix_m2","label":"一鍵清理並修正","confirm":"將清理真殘留 symlink 並修正 Homebrew PATH。確定?"}},

  {"id":"dupes", "applies": lambda: bool(m1 and m1.get("total_wasted_bytes",0) > 0), "sev":"info", "icon":"copy", "tab":1,
   "title": lambda: f"{m1_groups} 組重複檔案 · 可回收 {m1_wasted}",
   "desc":"內容完全相同的檔案副本。刪檔涉及取捨,請到 M1 逐組確認後再處理(不提供一鍵刪除以策安全)。",
   "action": None},

  # ── M7 系統健康 ──
  {"id":"smart_fail", "applies": lambda: bool(m7 and str(m7_smart) not in ("—","") and not m7_smart_ok), "sev":"danger", "icon":"activity", "tab":7,
   "title": lambda: f"硬碟 SMART 狀態異常({m7_smart})",
   "desc":"硬碟自我檢測未通過,可能是故障前兆。請立即備份重要資料,並考慮送修或更換硬碟(軟體無法修復硬體)。",
   "action": None},

  {"id":"low_disk", "applies": lambda: 0 < m7_free_pct < 10, "sev":"warn", "icon":"activity", "tab":7,
   "title": lambda: f"磁碟可用空間偏低(剩 {m7_free_pct:.0f}%)",
   "desc":"剩餘空間不足會影響效能與系統更新。可先清理快取回收空間,或到 M3/M5 找大檔與可回收項目。",
   "action":{"id":"clear_caches","label":"清理快取騰空間","confirm":"將清理 brew/npm/pip/node-gyp/Mail 安全快取以回收空間。確定?"}},

  {"id":"apfs_snapshots", "applies": lambda: (m7_snaps or 0) >= 5, "sev":"info", "icon":"activity", "tab":7,
   "title": lambda: f"{m7_snaps} 個 APFS 本機快照佔用空間",
   "desc":"Time Machine 本機快照會暫時佔空間,通常系統會自動回收;數量偏多時可手動精簡。",
   "action":{"id":"thin_snapshots","label":"精簡本機快照","confirm":"將精簡 Time Machine 本機快照以回收空間。確定?"}},

  # ── M6 電池 ──
  {"id":"battery_health", "applies": lambda: bool(m6 and m6_degraded), "sev":"warn", "icon":"battery", "tab":6,
   "title": lambda: f"電池明顯老化(容量 {m6_cap}、{m6_cond})",
   "desc":"電池最大容量偏低或狀態非正常。這是硬體老化,無法以軟體修復;若影響使用,建議送 Apple 服務檢測或更換電池。",
   "action": None},

  # ── M9 安全 ──
  {"id":"filevault_off", "applies": lambda: m9_fv == "off", "sev":"danger", "icon":"shield", "tab":9,
   "title": lambda: "FileVault 磁碟加密未開啟",
   "desc":"未加密時,筆電遺失或被竊,硬碟資料可被讀取。建議開啟 FileVault(設定頁會引導你保存還原金鑰)。",
   "action":{"id":"open_filevault_settings","label":"開啟加密設定","confirm":"將開啟 FileVault 設定頁。確定?"}},

  {"id":"sip_off", "applies": lambda: m9_sip == "off", "sev":"danger", "icon":"shield", "tab":9,
   "title": lambda: "SIP 系統完整性保護已關閉",
   "desc":"SIP 防止系統檔案被竄改,關閉狀態風險高。重新開啟須重開機進入「復原模式」執行 csrutil enable,無法於此一鍵處理。",
   "action": None},

  {"id":"gatekeeper_off", "applies": lambda: m9_gk == "off", "sev":"warn", "icon":"shield", "tab":9,
   "title": lambda: "Gatekeeper 已關閉",
   "desc":"Gatekeeper 阻擋未簽章/未公證的程式。建議重新啟用;點「一鍵啟用」會跳出系統授權視窗。",
   "action":{"id":"enable_gatekeeper","label":"一鍵啟用 Gatekeeper","confirm":"將啟用 Gatekeeper(會跳出輸入密碼的授權視窗)。確定?"}},

  # ── M3 大型檔案 ──
  {"id":"large_files", "applies": lambda: (m3_total or 0) >= 20, "sev":"info", "icon":"files", "tab":3,
   "title": lambda: f"{m3_total} 個大型檔案 · 共 {m3_gb} GB",
   "desc":"超過 100MB 的大檔。大不等於該刪——M3 已標註每個檔案用途,請自行判斷後處理(不提供一鍵刪除以策安全)。",
   "action": None},

  # ── M10 近期當機 ──────────────────────────────────────────
  {"id":"kernel_panic", "applies": lambda: m10_panic > 0, "sev":"danger", "icon":"pulse", "tab":10,
   "title": lambda: f"近 30 天發生 {m10_panic} 次核心崩潰(整機重開)",
   "desc":"Kernel panic 代表系統層級崩潰、整台重新開機,常見原因是老舊驅動/核心擴充或硬體。請查 M10 崩潰來源,並更新或移除相關第三方擴充(見 M9 System Extensions)。",
   "action": None},
  {"id":"frequent_crashes", "applies": lambda: m10_worst_30d >= 5, "sev":"warn", "icon":"pulse", "tab":10,
   "title": lambda: f"{(m10_worst or {}).get('app','某 App')} 近 30 天當機 {m10_worst_30d} 次",
   "desc":"同一支程式反覆當機通常是它本身的問題(版本過舊/設定損壞),也會持續吃資源。建議更新或重裝該 App;若是你已不用的軟體,可考慮移除。不提供一鍵動作以免誤刪。",
   "action": None},

  # ── M7 即時資源 ───────────────────────────────────────────
  {"id":"high_cpu", "applies": lambda: (m7_top_cpu_max or 0) >= 80, "sev":"warn", "icon":"activity", "tab":7,
   "title": lambda: f"掃描當下有程序高 CPU 占用({m7_busiest} {m7_top_cpu_max}%)",
   "desc":"這是掃描瞬間的快照(非持續監測)。若該程序長時間維持高占用會發燙、耗電、變慢。請到「活動監視器」確認;若與 M10 反覆當機是同一支,優先處理它。不提供一鍵結束程序以免中斷你正在做的事。",
   "action": None},

  # ── M11 分享 / 遠端存取 ───────────────────────────────────
  {"id":"screen_sharing_on", "applies": lambda: m11_state.get("screen_sharing")=="on", "sev":"warn", "icon":"share", "tab":11,
   "title": lambda: "螢幕共享(VNC)目前開啟",
   "desc":"螢幕共享開啟代表他人可遠端看見並控制你的桌面。若非刻意開啟,建議關閉以縮小攻擊面。",
   "action":{"id":"disable_screen_sharing","label":"一鍵關閉螢幕共享","confirm":"將關閉「螢幕共享」服務(會跳出輸入密碼的授權視窗)。確定?"}},
  {"id":"remote_login_on", "applies": lambda: m11_state.get("remote_login")=="on", "sev":"warn", "icon":"share", "tab":11,
   "title": lambda: "遠端登入(SSH)目前開啟",
   "desc":"SSH 開啟代表他人可用帳密或金鑰透過網路登入這台 Mac。若不需要遠端登入,建議關閉。",
   "action":{"id":"disable_remote_login","label":"一鍵關閉遠端登入","confirm":"將關閉「遠端登入 SSH」服務(會跳出輸入密碼的授權視窗)。確定?"}},
  {"id":"other_sharing_on", "applies": lambda: bool(m11_other_open), "sev":"warn", "icon":"share", "tab":11,
   "title": lambda: "對外分享服務開啟:" + "、".join(m11_other_open),
   "desc":"偵測到對外開放的分享服務。若非刻意開啟,請到「系統設定 → 一般 → 共享」關閉對應項目(這類服務不提供一鍵關閉,避免誤關你正在用的分享)。",
   "action": None},
  {"id":"auto_login_on", "applies": lambda: bool(m11_autologin), "sev":"warn", "icon":"share", "tab":11,
   "title": lambda: "已啟用開機自動登入",
   "desc":"自動登入代表開機不需密碼就進入你的帳號,筆電遺失或被他人開機即可直接存取你的資料。建議到「系統設定 → 鎖定畫面 → 自動以此身分登入」關閉。",
   "action": None},
  {"id":"tailscale_funnel", "applies": lambda: bool(m11_ts_funnel), "sev":"danger", "icon":"share", "tab":11,
   "title": lambda: "Tailscale Funnel 已對「公開網際網路」暴露服務",
   "desc":"Funnel 會把你本機的服務開放給整個網際網路(不只你的 tailnet),風險很高。若非刻意,請用 `tailscale funnel off` 或在 Tailscale 設定關閉。",
   "action": None},
  {"id":"external_listeners", "applies": lambda: m11_ext_n > 0, "sev":"warn", "icon":"share", "tab":11,
   "title": lambda: f"{m11_ext_n} 個服務綁在非 loopback(其他裝置/tailnet 可連)",
   "desc":"這些服務沒有只綁 127.0.0.1,代表同網段或 tailnet(Tailscale)上的裝置可能連得到——超出那 5 個 Apple 內建分享服務的範圍。請到 M11 確認每個是不是你刻意開放的。",
   "action": None},
]

SEV_RANK = {"danger":0, "warn":1, "info":2}
highlights = []
for r in RULES:
    try:
        if r["applies"]():
            highlights.append((r["sev"], r["icon"], r["title"](), r["desc"], r["tab"], r.get("action")))
    except Exception:
        pass
highlights.sort(key=lambda h: SEV_RANK.get(h[0], 9))

# 正向(良好)項目
positives = []
if m6_cond and m6_cond != "—":
    positives.append(f"電池健康(循環 {m6_cycle} 次、容量 {m6_cap}、{m6_cond})")
if m7_smart and "verif" in str(m7_smart).lower():
    positives.append(f"硬碟 SMART 正常、可用空間 {m7_free}")
if m9 and m9.get("filevault",{}).get("state")=="on":
    positives.append("FileVault 磁碟加密已開啟")
if m10 and m10_30d == 0:
    positives.append("近 30 天沒有 App 當機紀錄")
if m11 and m11_open_n == 0 and not m11_autologin:
    positives.append("未開放遠端存取(SSH／螢幕共享／檔案共享皆關閉)、無自動登入")
pos_html = "".join(f"<li>{ic('check','ic-ok')}<span>{p}</span></li>" for p in positives) or "<li class='muted'>—</li>"

n_danger = sum(1 for h in highlights if h[0]=="danger")
n_warn   = sum(1 for h in highlights if h[0]=="warn")
if n_danger:
    vcls, vicon, vtitle = "danger","alert","有重要項目需要注意"
    vsub = f"發現 {n_danger} 項較重要、{n_warn} 項建議處理的項目,詳見下方。"
elif n_warn:
    vcls, vicon, vtitle = "warn","alert","大致良好,有可優化處"
    vsub = f"有 {n_warn} 項建議處理,未發現嚴重問題。"
else:
    vcls, vicon, vtitle = "ok","check","整體狀態良好"
    vsub = "未發現需要處理的重要項目。"

SEV_BADGE = {"danger":"高風險 · 建議立即處理", "warn":"中等 · 建議處理", "info":"參考 · 可選優化"}
def jsstr(s):  # 安全嵌入單引號 JS 字串(用於 double-quoted onclick 屬性內)
    return "'" + str(s).replace("\\","\\\\").replace("'","\\'").replace('"',"&quot;") + "'"
hl_html = ""
for sev, icon, title, desc, tab, action in highlights:
    badge = f"<span class='hl-badge {sev}'>{SEV_BADGE[sev]}</span>"
    fix_btn = ""
    if action:
        fix_btn = (f"<button class='hl-fix' onclick=\"doRepair('{action['id']}', this, {jsstr(action['confirm'])})\">"
                   f"{ic('check')}{action['label']}</button>")
    hl_html += (f"<div class='hl-item {sev}'><div class='hl-ic'>{ic(icon)}</div>"
                f"<div class='hl-body'><div class='hl-titlerow'><span class='hl-title'>{title}</span>{badge}</div>"
                f"<div class='hl-desc'>{desc}</div></div>"
                f"<div class='hl-actions'>{fix_btn}<button class='hl-jump' onclick='switchTab({tab})'>查看{ic('arrow')}</button></div></div>")
if not hl_html:
    hl_html = "<div class='allclear'>" + ic('check','ic-lg') + "<span>沒有需要特別注意的項目,一切良好。</span></div>"

# 模組總覽卡(摘要頁底部)
overview = [
  (1,"copy","M1 重複檔案", f"{m1_groups} 組 · 可回收 {m1_wasted}", "內容完全相同的檔案副本",
     "info" if m1_groups else "ok"),
  (2,"unlink","M2 損壞項目", f"真殘留 {m2_stale} · 總連結 {m2_total}", "斷裂捷徑與 brew 設定(多數正常)",
     "warn" if (m2_stale+m2_brew) else "ok"),
  (3,"files","M3 大型檔案", f"{m3_total} 個 · 共 {m3_gb} GB", "最佔空間的大檔案(>100MB)", "info"),
  (4,"terminal","M4 開發環境", f"{m4_tools} 項工具就緒", "開發工具版本健檢", "info"),
  (5,"recycle","M5 可回收空間", f"約 {m5_total}", "可安全清理的快取等空間", "info"),
  (6,"battery","M6 電池", f"容量 {m6_cap} · {m6_cond}", "電池老化程度",
     "ok" if str(m6_cond).lower() in ("normal","good","—") else "warn"),
  (7,"activity","M7 系統健康", f"SMART {m7_smart}", "硬碟與系統資源壓力",
     "ok" if "verif" in str(m7_smart).lower() else "warn"),
  (8,"power","M8 登入背景", f"{m8_login_n + m8_uagent_n + m8_sagent_n} 個自啟項目", "開機自動執行的程式",
     "warn" if m8_tp else "info"),
  (9,"shield","M9 安全更新",
     f"防火牆{'開啟' if m9_fw=='on' else ('關閉' if m9_fw=='off' else '未知')} · 更新 {m9_upd_n}",
     "系統安全防線與待更新",
     "danger" if (m9_fw=="off") else ("warn" if m9_upd_n else "ok")),
  (10,"pulse","M10 近期當機",
     f"近30天 {m10_30d} 筆 · 核心崩潰 {m10_panic}",
     "App 與系統的崩潰紀錄",
     "danger" if m10_panic else ("warn" if m10_worst_30d >= 5 else ("info" if m10_30d else "ok"))),
  (11,"share","M11 分享存取",
     f"對外服務開啟 {m11_open_n}/5" + (" · 自動登入" if m11_autologin else ""),
     "遠端登入與分享攻擊面",
     "warn" if (m11_open_n or m11_autologin) else "ok"),
]
ov_html = ""
for num, icon, label, val, desc, status in overview:
    ov_html += (f"<div class='mod-card {status}' onclick='switchTab({num})'>"
                f"<div class='mod-top'><span class='mod-ic'>{ic(icon)}</span>"
                f"<span class='mod-label'>{label}</span><span class='mod-arrow'>{ic('chevron')}</span></div>"
                f"<div class='mod-val'>{val}</div><div class='mod-desc'>{desc}</div></div>")

# ── 修復涵蓋範圍(由規則表動態產生,永遠與 RULES 同步) ──────────
TAB_NAMES = {1:"M1 重複檔",2:"M2 損壞項目",3:"M3 大型檔",4:"M4 開發環境",5:"M5 可回收",
             6:"M6 電池",7:"M7 系統健康",8:"M8 登入背景",9:"M9 安全更新",
             10:"M10 近期當機",11:"M11 分享存取"}
FINDING = {
  "firewall_off":"防火牆關閉", "os_updates":"系統更新待安裝", "brew_outdated":"Homebrew 套件過舊",
  "pip_outdated":"pip 版本過舊", "npm_global_outdated":"npm 全域套件過舊", "third_party_agents":"第三方開機自啟",
  "reclaimable":"快取可回收", "m2_issues":"殘留 symlink / brew PATH", "dupes":"重複檔案",
  "smart_fail":"硬碟 SMART 異常", "low_disk":"磁碟空間不足", "apfs_snapshots":"APFS 快照偏多",
  "battery_health":"電池老化", "filevault_off":"FileVault 未開啟", "sip_off":"SIP 已關閉",
  "gatekeeper_off":"Gatekeeper 已關閉", "large_files":"大型檔案佔空間",
  "kernel_panic":"核心崩潰(panic)", "frequent_crashes":"App 反覆當機", "high_cpu":"程序高 CPU 占用",
  "screen_sharing_on":"螢幕共享開啟", "remote_login_on":"遠端登入開啟",
  "other_sharing_on":"其他分享服務開啟", "auto_login_on":"開機自動登入",
  "tailscale_funnel":"Tailscale Funnel 對公網暴露", "external_listeners":"服務綁非 loopback(外部可達)",
}
MANUAL = {"smart_fail":"硬體 · 僅警示", "battery_health":"硬體 · 僅警示", "sip_off":"需 Recovery 模式",
          "dupes":"刪檔需取捨", "large_files":"需自行判斷", "third_party_agents":"需逐一判斷",
          "kernel_panic":"硬體/驅動 · 僅警示", "frequent_crashes":"更新/移除該 App", "high_cpu":"快照 · 僅警示",
          "other_sharing_on":"到系統設定關閉", "auto_login_on":"到系統設定關閉",
          "tailscale_funnel":"tailscale funnel off", "external_listeners":"需逐一確認"}
cov_active = 0
cov_rows = ""
for r in RULES:
    rid = r["id"]
    try: active = bool(r["applies"]())
    except Exception: active = False
    if active: cov_active += 1
    act = r.get("action")
    handling = (f"<span class='cov-fix'>{ic('check')}一鍵 · {act['label']}</span>" if act
                else f"<span class='cov-man'>{MANUAL.get(rid,'需人工判斷')}</span>")
    status = ("<span class='cov-on'>● 本次命中</span>" if active else "<span class='cov-off'>○ 未命中</span>")
    cov_rows += (f"<tr class=\"{'cov-active' if active else ''}\"><td>{TAB_NAMES.get(r['tab'],'')}</td>"
                 f"<td>{FINDING.get(rid, rid)}</td><td>{handling}</td><td>{status}</td></tr>")
cov_total = len(RULES)
cov_oneclick = sum(1 for r in RULES if r.get("action"))

# ─────────────────────────────────────────────────────────────
HTML = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MacVitals 體檢報告</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64' fill='none'%3E%3Crect x='4' y='4' width='56' height='56' rx='16' fill='%23142a3d' stroke='%2338bdf8' stroke-width='3'/%3E%3Cpath d='M13 35H23L27.5 23L34 44L38.5 33H45' stroke='%2338bdf8' stroke-width='4' stroke-linecap='round' stroke-linejoin='round'/%3E%3Ccircle cx='49' cy='33' r='4' fill='%2334d399'/%3E%3C/svg%3E">
<style>
  :root {{
    --bg:#0f1117; --surface:#1a1d27; --surface2:#22263a; --surface3:#2a2f44;
    --border:#2d3148; --text:#e2e8f0; --muted:#8892a4;
    --cyan:#38bdf8; --green:#34d399; --yellow:#fbbf24; --red:#f87171; --purple:#a78bfa;
  }}
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{ background:var(--bg); color:var(--text); font-family:'SF Pro Text',-apple-system,BlinkMacSystemFont,sans-serif; font-size:14px; line-height:1.5; }}
  .ic {{ width:18px; height:18px; flex:none; stroke:currentColor; fill:none; stroke-width:2; stroke-linecap:round; stroke-linejoin:round; vertical-align:-3px; }}
  .ic-lg {{ width:30px; height:30px; }}
  .ic-ok {{ color:var(--green); }} .ic-err {{ color:var(--red); }}
  header {{ background:var(--surface); border-bottom:1px solid var(--border); padding:18px 32px; display:flex; align-items:center; gap:12px; flex-wrap:wrap; }}
  header .brandmark {{ width:30px; height:30px; flex:none; }}
  header h1 {{ font-size:19px; font-weight:600; letter-spacing:.01em; }}
  header h1 .v {{ color:var(--cyan); }}
  header h1 .rpt {{ font-weight:400; color:var(--muted); font-size:14px; margin-left:6px; }}
  header .meta {{ color:var(--muted); font-size:12px; }}
  .badge {{ background:var(--surface2); border:1px solid var(--border); border-radius:6px; padding:3px 10px; font-size:11px; color:var(--muted); display:inline-flex; align-items:center; gap:5px; }}
  .badge .ic {{ width:13px; height:13px; color:var(--green); }}
  .cards {{ display:grid; grid-template-columns:repeat(4,1fr); gap:16px; padding:24px 32px; }}
  .card {{ background:var(--surface); border:1px solid var(--border); border-radius:10px; padding:16px 20px; }}
  .card .label {{ color:var(--muted); font-size:11px; text-transform:uppercase; letter-spacing:.06em; margin-bottom:8px; }}
  .card .value {{ font-size:28px; font-weight:700; font-variant-numeric:tabular-nums; line-height:1.1; }}
  .card .sub {{ color:var(--muted); font-size:12px; margin-top:4px; }}
  .card .card-hint {{ color:var(--muted); font-size:11px; margin-top:8px; padding-top:8px; border-top:1px solid var(--border); }}
  .card.danger .value {{ color:var(--red); }} .card.warn .value {{ color:var(--yellow); }}
  .card.ok .value {{ color:var(--green); }} .card.info .value {{ color:var(--cyan); }}
  /* Tabs */
  .tabs {{ display:flex; flex-wrap:wrap; gap:2px; padding:0 32px; border-bottom:1px solid var(--border); background:var(--bg); position:sticky; top:0; z-index:5; }}
  .tab {{ padding:10px 16px; cursor:pointer; color:var(--muted); border-bottom:2px solid transparent; font-size:13px; font-weight:500; transition:.15s; display:flex; align-items:center; gap:7px; }}
  .tab .ic {{ width:16px; height:16px; }}
  .tab:hover {{ color:var(--text); background:var(--surface); }}
  .tab.active {{ color:var(--cyan); border-bottom-color:var(--cyan); }}
  .panel {{ display:none; padding:24px 32px; }} .panel.active {{ display:block; }}
  .panel-head {{ font-size:16px; font-weight:600; margin-bottom:6px; display:flex; align-items:center; gap:8px; }}
  .panel-head .ic {{ color:var(--cyan); width:20px; height:20px; }}
  /* note box (白話說明) */
  .note-box {{ display:flex; gap:10px; align-items:flex-start; background:var(--surface); border-left:3px solid var(--cyan); border-radius:6px; padding:12px 14px; margin:0 0 20px; font-size:13px; color:#b6c0d4; }}
  .note-box .ic {{ color:var(--cyan); width:17px; height:17px; margin-top:1px; }}
  /* table */
  .tbl-wrap {{ overflow-x:auto; border:1px solid var(--border); border-radius:8px; }}
  table {{ width:100%; border-collapse:collapse; }}
  th {{ background:var(--surface2); color:var(--muted); font-size:11px; text-transform:uppercase; padding:9px 12px; text-align:left; border-bottom:1px solid var(--border); white-space:nowrap; }}
  td {{ padding:9px 12px; border-bottom:1px solid var(--border); vertical-align:top; }}
  tr:last-child td {{ border-bottom:none; }}
  tr:hover td {{ background:var(--surface2); }}
  td.warn {{ color:var(--yellow); }} td.error {{ color:var(--red); }} td.ok {{ color:var(--green); }}
  td.num {{ font-variant-numeric:tabular-nums; text-align:right; white-space:nowrap; }}
  td.muted {{ color:var(--muted); font-size:12.5px; }}
  .file-path {{ font-family:'SF Mono',ui-monospace,monospace; font-size:12px; word-break:break-all; }}
  .filter-bar {{ display:flex; gap:12px; margin-bottom:16px; align-items:center; flex-wrap:wrap; }}
  .filter-bar input {{ background:var(--surface); border:1px solid var(--border); border-radius:7px; color:var(--text); padding:7px 12px; font-size:13px; width:300px; max-width:60vw; }}
  .filter-bar input:focus {{ outline:none; border-color:var(--cyan); }}
  .filter-bar select {{ background:var(--surface); border:1px solid var(--border); border-radius:7px; color:var(--text); padding:7px 12px; font-size:13px; }}
  .section-title {{ font-size:12px; font-weight:600; color:var(--muted); text-transform:uppercase; letter-spacing:.06em; margin:24px 0 12px; }}
  pre {{ background:var(--surface2); border:1px solid var(--border); border-radius:6px; padding:12px; font-size:12px; overflow-x:auto; white-space:pre-wrap; }}
  pre.warn {{ border-color:var(--yellow); color:var(--yellow); }} pre.error {{ border-color:var(--red); color:var(--red); }}
  .expandable {{ cursor:pointer; max-height:22px; overflow:hidden; transition:max-height .2s; }}
  .expandable.open {{ max-height:400px; }}
  .dupe-path {{ font-family:'SF Mono',monospace; font-size:11px; color:var(--muted); padding:2px 0; }}
  .dupe-path:first-child {{ color:var(--text); }}
  .empty {{ color:var(--muted); padding:24px; text-align:center; }}
  /* summary */
  .verdict {{ display:flex; align-items:center; gap:16px; background:var(--surface); border:1px solid var(--border); border-radius:12px; padding:20px 24px; margin:24px 0; }}
  .verdict.danger {{ border-left:4px solid var(--red); }} .verdict.warn {{ border-left:4px solid var(--yellow); }} .verdict.ok {{ border-left:4px solid var(--green); }}
  .verdict-ic {{ display:flex; }} .verdict.danger .verdict-ic {{ color:var(--red); }} .verdict.warn .verdict-ic {{ color:var(--yellow); }} .verdict.ok .verdict-ic {{ color:var(--green); }}
  .verdict-title {{ font-size:18px; font-weight:600; }} .verdict-sub {{ color:var(--muted); font-size:13px; margin-top:3px; }}
  .hl-item {{ display:flex; align-items:center; gap:14px; background:var(--surface); border:1px solid var(--border); border-left-width:3px; border-radius:8px; padding:14px 16px; margin-bottom:10px; }}
  .hl-item.danger {{ border-left-color:var(--red); }} .hl-item.warn {{ border-left-color:var(--yellow); }} .hl-item.info {{ border-left-color:var(--cyan); }}
  .hl-ic {{ display:flex; }} .hl-item.danger .hl-ic {{ color:var(--red); }} .hl-item.warn .hl-ic {{ color:var(--yellow); }} .hl-item.info .hl-ic {{ color:var(--cyan); }}
  .hl-body {{ flex:1; min-width:0; }} .hl-title {{ font-weight:600; font-size:14px; margin-bottom:3px; }} .hl-desc {{ color:var(--muted); font-size:12.5px; }}
  .hl-item.danger {{ background:rgba(248,113,113,.08); }}
  .hl-item.warn {{ background:rgba(251,191,36,.05); }}
  .hl-titlerow {{ display:flex; align-items:center; gap:10px; flex-wrap:wrap; margin-bottom:3px; }}
  .hl-badge {{ font-size:10.5px; font-weight:600; padding:2px 8px; border-radius:20px; letter-spacing:.02em; white-space:nowrap; }}
  .hl-badge.danger {{ background:rgba(248,113,113,.16); color:var(--red); }}
  .hl-badge.warn {{ background:rgba(251,191,36,.14); color:var(--yellow); }}
  .hl-badge.info {{ background:rgba(56,189,248,.14); color:var(--cyan); }}
  .hl-actions {{ display:flex; gap:8px; align-items:center; flex:none; }}
  .hl-jump {{ background:var(--surface2); border:1px solid var(--border); border-radius:6px; color:var(--cyan); padding:6px 12px; font-size:12px; cursor:pointer; display:inline-flex; align-items:center; gap:4px; white-space:nowrap; }}
  .hl-jump:hover {{ background:var(--surface3); }} .hl-jump .ic {{ width:14px; height:14px; }}
  .hl-fix {{ background:var(--cyan); border:1px solid var(--cyan); border-radius:6px; color:#06283a; font-weight:600; padding:6px 12px; font-size:12px; cursor:pointer; display:inline-flex; align-items:center; gap:5px; white-space:nowrap; }}
  .hl-fix:hover {{ filter:brightness(1.08); }} .hl-fix:disabled {{ opacity:.55; cursor:default; }} .hl-fix .ic {{ width:14px; height:14px; }}
  .hl-item.danger .hl-fix {{ background:var(--red); border-color:var(--red); color:#2a0a0a; }}
  .allclear {{ display:flex; align-items:center; gap:12px; color:var(--green); background:rgba(52,211,153,.07); border:1px solid rgba(52,211,153,.25); border-radius:10px; padding:18px 22px; font-size:14px; }}
  /* toast */
  #toast {{ position:fixed; right:20px; bottom:20px; display:flex; flex-direction:column; gap:10px; z-index:50; max-width:380px; }}
  .toast {{ background:var(--surface); border:1px solid var(--border); border-left:3px solid var(--cyan); border-radius:9px; padding:13px 16px; font-size:13px; color:var(--text); box-shadow:0 8px 24px rgba(0,0,0,.4); animation:tin .2s ease; }}
  .toast.ok {{ border-left-color:var(--green); }} .toast.danger {{ border-left-color:var(--red); }} .toast.warn {{ border-left-color:var(--yellow); }}
  @keyframes tin {{ from {{ opacity:0; transform:translateY(8px); }} to {{ opacity:1; transform:none; }} }}
  /* coverage */
  .coverage {{ margin-top:24px; border:1px solid var(--border); border-radius:10px; background:var(--surface); overflow:hidden; }}
  .coverage summary {{ cursor:pointer; padding:14px 18px; font-weight:600; font-size:13.5px; color:var(--cyan); list-style:none; display:flex; align-items:center; gap:9px; }}
  .coverage summary::-webkit-details-marker {{ display:none; }}
  .coverage summary .ic {{ width:17px; height:17px; }}
  .cov-chev {{ margin-left:auto; transition:transform .2s; }}
  .coverage[open] .cov-chev {{ transform:rotate(90deg); }}
  .coverage[open] summary {{ border-bottom:1px solid var(--border); }}
  .cov-body {{ padding:16px; }} .cov-body .note-box {{ margin-top:0; }}
  .coverage td {{ font-size:12.5px; }}
  .cov-fix {{ color:var(--green); display:inline-flex; align-items:center; gap:4px; }} .cov-fix .ic {{ width:13px; height:13px; }}
  .cov-man {{ color:var(--muted); }}
  .cov-on {{ color:var(--green); font-size:12px; white-space:nowrap; }} .cov-off {{ color:var(--muted); font-size:12px; white-space:nowrap; }}
  tr.cov-active td {{ background:rgba(52,211,153,.05); }}
  .pos-list {{ list-style:none; display:flex; flex-direction:column; gap:8px; margin-top:4px; }}
  .pos-list li {{ display:flex; align-items:center; gap:8px; font-size:13px; color:#b6c0d4; }}
  .mod-grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(220px,1fr)); gap:12px; }}
  .mod-card {{ background:var(--surface); border:1px solid var(--border); border-radius:10px; padding:14px 16px; cursor:pointer; transition:.15s; }}
  .mod-card:hover {{ border-color:var(--cyan); transform:translateY(-1px); }}
  .mod-card.danger {{ border-top:3px solid var(--red); }} .mod-card.warn {{ border-top:3px solid var(--yellow); }}
  .mod-card.ok {{ border-top:3px solid var(--green); }} .mod-card.info {{ border-top:3px solid var(--cyan); }}
  .mod-top {{ display:flex; align-items:center; gap:8px; margin-bottom:10px; }}
  .mod-ic {{ color:var(--cyan); display:flex; }} .mod-label {{ font-weight:600; font-size:13px; flex:1; }} .mod-arrow {{ color:var(--muted); display:flex; }} .mod-arrow .ic {{ width:15px; height:15px; }}
  .mod-val {{ font-size:15px; font-weight:600; font-variant-numeric:tabular-nums; }} .mod-desc {{ color:var(--muted); font-size:12px; margin-top:4px; }}
  .cards-2 {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; }}
  .mini-title {{ font-size:12px; font-weight:600; color:var(--muted); margin:0 0 6px; text-transform:uppercase; letter-spacing:.04em; }}
  @media (max-width:640px) {{ .cards-2 {{ grid-template-columns:1fr; }} }}
  @media (max-width:640px) {{ .cards {{ grid-template-columns:repeat(2,1fr); }} header,.tabs,.panel {{ padding-left:16px; padding-right:16px; }} }}
</style>
</head>
<body>

<svg width="0" height="0" style="position:absolute" aria-hidden="true"><defs>
  <symbol id="ic-dashboard" viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/></symbol>
  <symbol id="ic-search" viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/></symbol>
  <symbol id="ic-copy" viewBox="0 0 24 24"><rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v1"/></symbol>
  <symbol id="ic-unlink" viewBox="0 0 24 24"><path d="M9.5 14.5l5-5"/><path d="M11 6.5l1-1a3.5 3.5 0 0 1 5 5l-1 1"/><path d="M13 17.5l-1 1a3.5 3.5 0 0 1-5-5l1-1"/><path d="M4 4l16 16"/></symbol>
  <symbol id="ic-files" viewBox="0 0 24 24"><path d="M14 3v4a1 1 0 0 0 1 1h4"/><path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/></symbol>
  <symbol id="ic-terminal" viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M7 9l3 3-3 3"/><path d="M13 15h4"/></symbol>
  <symbol id="ic-recycle" viewBox="0 0 24 24"><path d="M20 11.5A8 8 0 1 0 18.4 16"/><path d="M20 4v6h-6"/></symbol>
  <symbol id="ic-battery" viewBox="0 0 24 24"><rect x="3" y="8" width="15" height="9" rx="2"/><path d="M21 11v3"/><rect x="5.5" y="10.5" width="7" height="4"/></symbol>
  <symbol id="ic-activity" viewBox="0 0 24 24"><path d="M3 12h4l2.5 7 4-15 2.5 8H21"/></symbol>
  <symbol id="ic-power" viewBox="0 0 24 24"><path d="M12 4v8"/><path d="M7.5 6.5a7 7 0 1 0 9 0"/></symbol>
  <symbol id="ic-shield" viewBox="0 0 24 24"><path d="M12 3l8 3v6c0 5-3.5 8.2-8 9-4.5-.8-8-4-8-9V6z"/></symbol>
  <symbol id="ic-check" viewBox="0 0 24 24"><path d="M5 12.5l4.5 4.5L19 7"/></symbol>
  <symbol id="ic-x" viewBox="0 0 24 24"><path d="M6 6l12 12"/><path d="M18 6L6 18"/></symbol>
  <symbol id="ic-alert" viewBox="0 0 24 24"><path d="M12 4l9 16H3z"/><path d="M12 10v4.5"/><path d="M12 17.5h.01"/></symbol>
  <symbol id="ic-info" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 11v5"/><path d="M12 7.5h.01"/></symbol>
  <symbol id="ic-refresh" viewBox="0 0 24 24"><path d="M20 11.5A8 8 0 1 0 18.4 16"/><path d="M20 4v6h-6"/></symbol>
  <symbol id="ic-arrow" viewBox="0 0 24 24"><path d="M7 17L17 7"/><path d="M8 7h9v9"/></symbol>
  <symbol id="ic-chevron" viewBox="0 0 24 24"><path d="M9 6l6 6-6 6"/></symbol>
  <symbol id="ic-pulse" viewBox="0 0 24 24"><path d="M3 12h3l2.5-7 4 15 3-10 1.5 2H21"/></symbol>
  <symbol id="ic-share" viewBox="0 0 24 24"><circle cx="6" cy="12" r="2.4"/><circle cx="18" cy="6" r="2.4"/><circle cx="18" cy="18" r="2.4"/><path d="M8.1 10.9 15.9 7.1"/><path d="M8.1 13.1 15.9 16.9"/></symbol>
</defs></svg>
<!--REPAIR_HOOK-->
<div id="toast"></div>
<div id="repair-banner" style="display:none; align-items:center; gap:12px; background:rgba(251,191,36,.12); border-bottom:1px solid var(--yellow); padding:12px 32px; font-size:13px;">
  <svg class="ic" style="color:var(--yellow)"><use href="#ic-alert"/></svg>
  <span class="rb-msg" style="flex:1; color:#e8d29a; line-height:1.6;"></span>
</div>

<header>
  <svg class="brandmark" viewBox="0 0 64 64" fill="none" role="img" aria-label="MacVitals">
    <rect x="4" y="4" width="56" height="56" rx="16" fill="#142a3d" stroke="#38bdf8" stroke-width="2.5"/>
    <path d="M13 35 H23 L27.5 23 L34 44 L38.5 33 H45" stroke="#38bdf8" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"/>
    <circle cx="49" cy="33" r="3.6" fill="#34d399"/>
  </svg>
  <h1>Mac<span class="v">Vitals</span><span class="rpt">體檢報告</span></h1>
  <span class="meta">掃描時間：{scan_time}</span>
  <span class="badge">{ic('check')} 唯讀 — 未刪除任何檔案</span>
</header>

<div class="tabs">
  <div class="tab active" onclick="switchTab(0)">{ic('dashboard')}摘要</div>
  <div class="tab" onclick="switchTab(1)">{ic('copy')}M1 重複檔案</div>
  <div class="tab" onclick="switchTab(2)">{ic('unlink')}M2 損壞項目</div>
  <div class="tab" onclick="switchTab(3)">{ic('files')}M3 大型檔案</div>
  <div class="tab" onclick="switchTab(4)">{ic('terminal')}M4 開發環境</div>
  <div class="tab" onclick="switchTab(5)">{ic('recycle')}M5 可回收空間</div>
  <div class="tab" onclick="switchTab(6)">{ic('battery')}M6 電池</div>
  <div class="tab" onclick="switchTab(7)">{ic('activity')}M7 系統健康</div>
  <div class="tab" onclick="switchTab(8)">{ic('power')}M8 登入背景</div>
  <div class="tab" onclick="switchTab(9)">{ic('shield')}M9 安全更新</div>
  <div class="tab" onclick="switchTab(10)">{ic('pulse')}M10 近期當機</div>
  <div class="tab" onclick="switchTab(11)">{ic('share')}M11 分享存取</div>
</div>

<!-- 摘要 Panel -->
<div class="panel active" id="p0">
  {note("這頁是整台電腦的健康總覽。先看「全部檢查模組一覽」掌握全貌(點任一卡片可跳到該模組看細節),接著是整體判讀與「需要你注意的事」(依重要性排序),然後是「運作良好的部分」,最後可展開「修復涵蓋範圍」對照表。")}
  <div class="section-title">全部檢查模組一覽</div>
  <div class="mod-grid">{ov_html}</div>
  <div class="verdict {vcls}">
    <div class="verdict-ic">{ic(vicon,'ic-lg')}</div>
    <div><div class="verdict-title">{vtitle}</div><div class="verdict-sub">{vsub}</div></div>
  </div>
  <div class="section-title">需要你注意的事</div>
  {hl_html}
  <div class="section-title">運作良好的部分</div>
  <ul class="pos-list">{pos_html}</ul>

  <details class="coverage">
    <summary>{ic('shield')}修復涵蓋範圍 — {cov_total} 種發現規則 · {cov_oneclick} 種可一鍵修復 · 本次命中 {cov_active} 種{ic('chevron','cov-chev')}</summary>
    <div class="cov-body">
      {note("這是「掃到什麼 → 對應修復」的完整對照,直接從規則表產生。每次掃描只會把『命中』的項目放到上方「需要你注意的事」並長出按鈕;未命中代表這台機器目前沒有該問題。硬體(電池/SMART)與需重開機(SIP)的只警示、不一鍵。")}
      <div class="tbl-wrap"><table>
        <thead><tr><th>模組</th><th>偵測到的發現</th><th>對應修復</th><th>本次狀態</th></tr></thead>
        <tbody>{cov_rows}</tbody>
      </table></div>
    </div>
  </details>
</div>

<!-- M1 Panel -->
<div class="panel" id="p1">
  <div class="panel-head">{ic('copy')}M1 重複檔案</div>
  {note("「重複檔案」指內容一模一樣的檔案(以大小＋逐位元組比對,連檔名不同也算)。保留一份、刪掉其餘副本即可省空間,不影響使用。掃描範圍是你的家目錄,已排除 .Trash／node_modules／.git。點路徑欄可展開看所有副本。")}
  <div class="filter-bar">
    <input type="text" id="m1-filter" placeholder="篩選路徑..." oninput="filterTable('m1-table', this.value, 4)">
    <select onchange="filterM1Size(this.value)">
      <option value="0">全部大小</option><option value="104857600">≥ 100 MB</option>
      <option value="10485760">≥ 10 MB</option><option value="1048576">≥ 1 MB</option>
    </select>
  </div>
  <div class="tbl-wrap"><table id="m1-table">
    <thead><tr><th>#</th><th>單檔大小</th><th>份數</th><th>浪費空間 ↓</th><th>路徑(點擊展開)</th><th>這是什麼</th></tr></thead>
    <tbody>{m1_rows if m1_rows else '<tr><td colspan="6" class="empty">未掃到重複檔案</td></tr>'}</tbody>
  </table></div>
</div>

<!-- M2 Panel -->
<div class="panel" id="p2">
  <div class="panel-head">{ic('unlink')}M2 損壞項目</div>
  {note("「斷裂 symlink」是指向已不存在目標的捷徑。數字看起來嚇人,但約 99.7% 是 macOS 與 App 的正常設計——沙盒範本與執行鎖檔都不該動。只有「真殘留」(指向已刪目標)才值得清理。brew doctor 的警告多半是 PATH 設定,不是壞檔。")}
  <div class="cards" style="padding:0 0 8px;">
    <div class="card ok"><div class="label">沙盒範本捷徑</div><div class="value">{m2_sandbox}</div><div class="sub">macOS 自動維護 · 正常</div></div>
    <div class="card ok"><div class="label">App 執行鎖檔</div><div class="value">{m2_applock}</div><div class="sub">SingletonLock 等 · 正常</div></div>
    <div class="card {'warn' if m2_stale else 'ok'}"><div class="label">真殘留(需處理)</div><div class="value">{m2_stale}</div><div class="sub">指向已刪目標 · 可清理</div></div>
    <div class="card info"><div class="label">斷裂連結總數</div><div class="value">{m2_total}</div><div class="sub">三類加總</div></div>
  </div>
  <div class="section-title">需處理:真殘留 Symlinks（{m2_stale} 個）</div>
  <div class="tbl-wrap"><table>
    <thead><tr><th>路徑</th><th>原指向(已不存在)</th></tr></thead>
    <tbody>{m2_stale_rows if m2_stale_rows else '<tr><td colspan="2" class="empty">無真殘留 symlink(其餘皆為正常的沙盒範本與 App 鎖檔)</td></tr>'}</tbody>
  </table></div>
  <div class="section-title">Homebrew 問題（{m2_brew} 項，多為 PATH 設定）</div>
  <div class="tbl-wrap"><table>
    <thead><tr><th>問題內容</th></tr></thead>
    <tbody>{m2_brew_rows if m2_brew_rows else '<tr><td class="empty">brew doctor 通過</td></tr>'}</tbody>
  </table></div>
</div>

<!-- M3 Panel -->
<div class="panel" id="p3">
  <div class="panel-head">{ic('files')}M3 大型檔案</div>
  {note("列出所有超過 100MB 的檔案(已排除 /System、/private/var)。「大」不等於「該刪」——請看最右「這是什麼」欄判斷用途:例如 .dmg/.pkg 安裝檔裝完可刪,但 Docker 虛擬磁碟、照片圖庫請勿手動刪。")}
  <div class="filter-bar">
    <input type="text" id="m3-filter" placeholder="篩選路徑或副檔名..." oninput="filterTable('m3-table', this.value, 1)">
    <select onchange="filterM3Ext(this.value)">
      <option value="">全部類型</option><option value=".dmg">.dmg</option><option value=".zip">.zip</option>
      <option value=".pkg">.pkg</option><option value=".iso">.iso</option><option value=".mp4">.mp4</option>
      <option value=".mov">.mov</option><option value=".tar">.tar</option>
    </select>
  </div>
  <div class="tbl-wrap"><table id="m3-table">
    <thead><tr><th>#</th><th>路徑</th><th>大小 ↓</th><th>修改日期</th><th>存取日期</th><th>類型</th><th>這是什麼</th></tr></thead>
    <tbody>{m3_rows if m3_rows else '<tr><td colspan="7" class="empty">無超過 100MB 的檔案</td></tr>'}</tbody>
  </table></div>
</div>

<!-- M4 Panel -->
<div class="panel" id="p4">
  <div class="panel-head">{ic('terminal')}M4 開發環境</div>
  {note("檢查常用開發工具是否安裝就緒、版本是否過時。✓ 代表已就緒,✗ 代表未安裝(若你用不到可忽略)。系統內建的 python3/ruby/git 由 macOS 控管,開發建議改用 Homebrew 版本。")}
  <div class="section-title">工具版本矩陣</div>
  <div class="tbl-wrap"><table>
    <thead><tr><th>工具</th><th>用途</th><th>狀態</th><th>版本</th></tr></thead>
    <tbody>{m4_ver_rows if m4_ver_rows else '<tr><td colspan="4" class="empty">無資料</td></tr>'}</tbody>
  </table></div>
  <div class="section-title">npm doctor(npm 環境健檢)</div><pre>{m4_npm_doc}</pre>
  <div class="section-title">pip 過時套件(前 20)</div><pre>{m4_pip_out}</pre>
  <div class="section-title">nvm 已安裝 Node 版本</div><pre>{m4_nvm}</pre>
  <div class="section-title">pyenv 已安裝 Python 版本</div><pre>{m4_pyenv}</pre>
  <div class="section-title">Homebrew 已安裝套件</div><pre style="max-height:300px;overflow-y:auto">{m4_brew_pkg}</pre>
</div>

<!-- M5 Panel -->
<div class="panel" id="p5">
  <div class="panel-head">{ic('recycle')}M5 可回收空間</div>
  {note("估算可以安全清理回收的空間,主要是各種 App 與工具的「快取」(暫存資料)。清掉後 App 下次使用會自動重建,不會遺失你的文件或設定。下表依大小排序,並附建議的清理方式。")}
  <div class="cards" style="padding:0 0 8px;">
    <div class="card info"><div class="label">可回收空間合計</div><div class="value">{m5_total}</div><div class="sub">下列項目加總</div></div>
  </div>
  <div class="section-title">可回收項目(依大小)</div>
  <div class="tbl-wrap"><table>
    <thead><tr><th>項目</th><th>路徑</th><th>大小 ↓</th><th>清理方式</th></tr></thead>
    <tbody>{m5_rows if m5_rows else '<tr><td colspan="4" class="empty">無可回收項目</td></tr>'}</tbody>
  </table></div>
</div>

<!-- M6 Panel -->
<div class="panel" id="p6">
  <div class="panel-head">{ic('battery')}M6 電池</div>
  {note("電池會隨充放電老化。判讀重點:循環次數(Apple 筆電設計壽命約 1000 次)、最大容量(低於 80% 才算明顯老化)、狀態(Normal 即正常)。三者良好就無須換電池。")}
  <div class="cards" style="padding:0 0 8px;">
    <div class="card info"><div class="label">循環次數</div><div class="value">{m6_cycle}</div><div class="sub">Cycle Count(壽命 ~1000)</div></div>
    <div class="card ok"><div class="label">最大容量</div><div class="value">{m6_cap}</div><div class="sub">低於 80% 才需留意</div></div>
    <div class="card ok"><div class="label">電池狀態</div><div class="value" style="font-size:20px">{m6_cond}</div><div class="sub">Condition</div></div>
    <div class="card info"><div class="label">充電中</div><div class="value" style="font-size:20px">{m6_chg}</div><div class="sub">Charging</div></div>
  </div>
</div>

<!-- M7 Panel -->
<div class="panel" id="p7">
  <div class="panel-head">{ic('activity')}M7 系統健康</div>
  {note("反映整體系統壓力。SMART=Verified 表示硬碟自我檢測正常;記憶體空閒過低或 swap 用量大代表記憶體吃緊;APFS 本機快照會暫時佔用空間(Time Machine 自動產生,系統會自行回收)。")}
  <div class="cards" style="padding:0 0 8px;">
    <div class="card ok"><div class="label">磁碟 SMART</div><div class="value" style="font-size:20px">{m7_smart}</div><div class="sub">硬碟自我檢測</div></div>
    <div class="card info"><div class="label">可用空間</div><div class="value" style="font-size:17px">{m7_free}</div><div class="sub">Container Free</div></div>
    <div class="card info"><div class="label">記憶體空閒</div><div class="value">{m7_mem}</div><div class="sub">free percentage</div></div>
    <div class="card {'ok' if str(m7_snaps)=='0' else 'warn'}"><div class="label">APFS 本機快照</div><div class="value">{m7_snaps}</div><div class="sub">系統自動回收</div></div>
  </div>
  <div class="section-title">即時資源占用 Top(掃描當下快照)</div>
  {note("這是掃描「那一瞬間」最吃 CPU／記憶體的程序排行,不是持續監測。偶爾某程序衝高是正常的;但若某程序長期維持高占用(會發燙、耗電、變慢),或與 M10 反覆當機是同一支,就值得到「活動監視器」進一步確認處理。≥70% 會標黃。")}
  <div class="cards-2">
    <div>
      <div class="mini-title">CPU 占用前段</div>
      <div class="tbl-wrap"><table><thead><tr><th>程序</th><th>CPU</th><th>記憶體</th><th>PID</th></tr></thead>
      <tbody>{m7_cpu_rows}</tbody></table></div>
    </div>
    <div>
      <div class="mini-title">記憶體占用前段</div>
      <div class="tbl-wrap"><table><thead><tr><th>程序</th><th>CPU</th><th>記憶體</th><th>PID</th></tr></thead>
      <tbody>{m7_mem_rows}</tbody></table></div>
    </div>
  </div>
  <div class="section-title">細節</div>
  <div class="tbl-wrap"><table><tbody>
    <tr><td class="muted">磁碟總容量</td><td>{m7_total_d}</td></tr>
    <tr><td class="muted">Swap 使用(虛擬記憶體)</td><td>{m7_swap}</td></tr>
    <tr><td class="muted">開機時間 / 系統負載</td><td>{m7_uptime}</td></tr>
  </tbody></table></div>
</div>

<!-- M8 Panel -->
<div class="panel" id="p8">
  <div class="panel-head">{ic('power')}M8 登入背景</div>
  {note("列出開機/登入時自動啟動、並常駐背景的程式。太多會拖慢開機、長期佔用資源。「第三方項目」(非 com.apple 開頭)特別標黃——那是你裝的軟體放的;不認得的可到「系統設定 → 一般 → 登入項目與擴充功能」停用。")}
  <div class="cards" style="padding:0 0 8px;">
    <div class="card info"><div class="label">登入項目</div><div class="value">{m8_login_n}</div><div class="sub">Login Items</div></div>
    <div class="card info"><div class="label">使用者代理</div><div class="value">{m8_uagent_n}</div><div class="sub">~/Library/LaunchAgents</div></div>
    <div class="card info"><div class="label">系統代理</div><div class="value">{m8_sagent_n}</div><div class="sub">/Library/LaunchAgents</div></div>
    <div class="card info"><div class="label">系統常駐</div><div class="value">{m8_daemon_n}</div><div class="sub">LaunchDaemons</div></div>
  </div>
  <div class="section-title">登入項目</div>
  <div class="tbl-wrap"><table><tbody>{m8_login}</tbody></table></div>
  <div class="section-title">第三方使用者自啟代理(值得檢視)</div>
  <div class="tbl-wrap"><table><tbody>{m8_tp_user}</tbody></table></div>
  <div class="section-title">第三方系統自啟代理(值得檢視)</div>
  <div class="tbl-wrap"><table><tbody>{m8_tp_sys}</tbody></table></div>
</div>

<!-- M9 Panel -->
<div class="panel" id="p9">
  <div class="panel-head">{ic('shield')}M9 安全更新</div>
  {note("四道安全防線:FileVault(整碟加密,筆電遺失時保護資料)、SIP(防止系統被竄改)、Gatekeeper(阻擋未簽章 App)、防火牆(阻擋未授權的網路連入)。綠色=開啟為佳。下方列出待安裝的系統更新。")}
  <div class="cards" style="padding:0 0 8px;">{m9_cards}</div>
  <div class="section-title">待安裝更新（{m9_upd_n} 項）</div>
  <div class="tbl-wrap"><table><tbody>{m9_upd_rows}</tbody></table></div>
  <div class="section-title">已啟用的 System Extensions（{m9_sysext_n} 個）</div>
  {note("System Extension 是第三方 App 安裝的核心／網路擴充(防毒、VPN、虛擬網卡等)。正常使用中的不用動;但已移除 App 殘留的、或老舊版本的擴充,是當機(kernel panic)與卡頓的常見元兇——若看到不認得或早該移除的,從對應 App 的設定移除。")}
  <div class="tbl-wrap"><table><tbody>{m9_sysext_rows}</tbody></table></div>
</div>

<!-- M10 Panel -->
<div class="panel" id="p10">
  <div class="panel-head">{ic('pulse')}M10 近期當機</div>
  {note("彙整 macOS 自動保存的崩潰／診斷報告(~/Library/Logs/DiagnosticReports 與系統目錄),依 App 統計近 30 天的當機次數。同一支程式反覆當機通常是它本身的問題;『核心崩潰(panic)』則是系統層級、會整台重開,多與老舊驅動或 System Extension 有關。這頁只判讀、不自動刪除任何東西。")}
  <div class="cards" style="padding:0 0 8px;">
    <div class="card {'info' if m10_30d else 'ok'}"><div class="label">近 30 天當機報告</div><div class="value">{m10_30d}</div><div class="sub">所有 App 合計</div></div>
    <div class="card {'danger' if m10_panic else 'ok'}"><div class="label">核心崩潰 (panic)</div><div class="value">{m10_panic}</div><div class="sub">整機重開 · 近 30 天</div></div>
    <div class="card info"><div class="label">最頻繁來源</div><div class="value" style="font-size:16px">{(m10_worst or {}).get('app','—')}</div><div class="sub">近 30 天 {(m10_worst or {}).get('count',0)} 次</div></div>
  </div>
  <div class="section-title">依 App 統計(近 30 天)</div>
  <div class="tbl-wrap"><table>
    <thead><tr><th>程序 / App</th><th>30 天</th><th>類型</th><th>最近一次</th></tr></thead>
    <tbody>{m10_app_rows}</tbody>
  </table></div>
  <div class="section-title">最近 20 筆報告</div>
  <div class="tbl-wrap"><table>
    <thead><tr><th>程序 / App</th><th>類型</th><th>時間</th><th>範圍</th></tr></thead>
    <tbody>{m10_recent_rows}</tbody>
  </table></div>
</div>

<!-- M11 Panel -->
<div class="panel" id="p11">
  <div class="panel-head">{ic('share')}M11 分享存取</div>
  {note("檢查這台 Mac 對外開放了哪些遠端存取／分享服務——這些是別人能從網路接觸到你電腦的『門』。做法是對本機通訊埠探聽(唯讀),反映服務是否真的在聽。非刻意開啟的建議關閉以縮小攻擊面。螢幕共享與遠端登入可一鍵關閉(會跳原生授權視窗);其餘請到「系統設定 → 一般 → 共享」處理。")}
  <div class="cards" style="padding:0 0 8px;">
    <div class="card {'warn' if m11_open_n else 'ok'}"><div class="label">對外服務開啟</div><div class="value">{m11_open_n}<span style="font-size:15px;color:var(--muted)"> / 5</span></div><div class="sub">越少越安全</div></div>
    <div class="card {'warn' if m11_autologin else 'ok'}"><div class="label">開機自動登入</div><div class="value" style="font-size:20px">{'是' if m11_autologin else '否'}</div><div class="sub">遺失時免密碼進入</div></div>
    <div class="card {m11_ts_cls}"><div class="label">Tailscale</div><div class="value" style="font-size:16px">{'執行中' if m11_ts_running else '未執行'}</div><div class="sub">{m11_ts_summary}</div></div>
    <div class="card {'warn' if m11_ext_n else 'ok'}"><div class="label">非 loopback 監聽</div><div class="value">{m11_ext_n}</div><div class="sub">外部裝置可達的服務</div></div>
  </div>
  <div class="section-title">遠端存取 / 分享服務(Apple 內建)</div>
  <div class="tbl-wrap"><table>
    <thead><tr><th>服務</th><th>通訊埠</th><th>狀態</th><th>風險說明</th></tr></thead>
    <tbody>{m11_rows}</tbody>
  </table></div>
  <div class="section-title">綁在非 loopback 的監聽埠(其他裝置 / Tailscale tailnet 可連)</div>
  {note("這裡列出「沒有只綁 127.0.0.1」的服務——同網段或 tailnet 上的裝置可能連得到,涵蓋非 Apple 的服務(例如自架伺服器)。空白代表所有服務都只綁本機、外部碰不到。注意:Tailscale 的 serve/funnel 即使服務只綁本機也可能把它代理出去,請一併看上方 Tailscale 狀態(Funnel = 對公開網際網路,風險最高)。")}
  <div class="tbl-wrap"><table>
    <thead><tr><th>程序</th><th>綁定位址</th><th>通訊埠</th></tr></thead>
    <tbody>{m11_ext_rows}</tbody>
  </table></div>
</div>

<script>
function switchTab(i) {{
  document.querySelectorAll('.tab').forEach((t,idx) => t.classList.toggle('active', idx===i));
  document.querySelectorAll('.panel').forEach((p,idx) => p.classList.toggle('active', idx===i));
  window.scrollTo({{top:0, behavior:'smooth'}});
}}
function showToast(msg, kind) {{
  const t = document.createElement('div');
  t.className = 'toast ' + (kind||'');
  t.textContent = msg;
  document.getElementById('toast').appendChild(t);
  setTimeout(() => {{ t.style.transition='opacity .4s'; t.style.opacity='0'; setTimeout(()=>t.remove(), 400); }}, 6000);
}}
var BANNER_DIRECT = '修復功能需要從「開始體檢」自動打開的網頁操作。你目前可能是直接打開了報告檔。請回到「開始體檢」的視窗,使用它打開的網頁(網址列會是 127.0.0.1)來查看與修復。';
var BANNER_DOWN = '「開始體檢」的程式視窗似乎已關閉,所以修復暫時無法執行。請重新雙擊「開始體檢」,再從它打開的網頁操作修復。';
function showBanner(msg) {{
  var b = document.getElementById('repair-banner');
  if (b) {{ b.querySelector('.rb-msg').textContent = msg; b.style.display = 'flex'; }}
}}
function doRepair(action, btn, confirmMsg) {{
  if (!window.__REPAIR__ || !window.__REPAIR__.enabled) {{
    showBanner(BANNER_DIRECT);
    showToast('無法修復:' + BANNER_DIRECT, 'warn');
    return;
  }}
  if (!confirm(confirmMsg || '確定要執行此修復嗎？')) return;
  const old = btn.innerHTML;
  btn.disabled = true; btn.textContent = '處理中…';
  fetch('/api/fix', {{
    method:'POST', headers:{{'Content-Type':'application/json'}},
    body: JSON.stringify({{action: action, token: window.__REPAIR__.token}})
  }})
  .then(r => r.json())
  .then(d => {{
    showToast(d.message || (d.ok ? '完成' : '未完成'), d.ok ? 'ok' : 'danger');
    btn.innerHTML = old; btn.disabled = false;
  }})
  .catch(e => {{ showBanner(BANNER_DOWN); showToast('無法修復:' + BANNER_DOWN, 'danger'); btn.innerHTML = old; btn.disabled = false; }});
}}
// 載入時先確認修復是否可用,不可用就顯示明確橫幅指引
(function() {{
  if (!window.__REPAIR__ || !window.__REPAIR__.enabled) {{ showBanner(BANNER_DIRECT); return; }}
  fetch('/api/ping').then(function(r) {{ if (!r.ok) throw 0; }}).catch(function() {{ showBanner(BANNER_DOWN); }});
}})();
function filterTable(tableId, q, colIdx) {{
  const rows = document.querySelectorAll('#'+tableId+' tbody tr');
  const lq = q.toLowerCase();
  rows.forEach(r => {{
    const cell = r.cells[colIdx];
    r.style.display = (!lq || (cell && cell.textContent.toLowerCase().includes(lq))) ? '' : 'none';
  }});
}}
function filterM1Size(minBytes) {{
  document.querySelectorAll('#m1-table tbody tr').forEach(r => {{
    const wasted = parseInt(r.dataset.wasted || '0');
    r.style.display = wasted >= parseInt(minBytes) ? '' : 'none';
  }});
}}
function filterM3Ext(ext) {{
  document.querySelectorAll('#m3-table tbody tr').forEach(r => {{
    const extCell = r.cells[5];
    r.style.display = (!ext || (extCell && extCell.textContent === ext)) ? '' : 'none';
  }});
}}
</script>
</body>
</html>
"""

OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
with open(OUT_HTML, "w") as f:
    f.write(HTML)

print(f"\n✅ 報告已生成：{OUT_HTML}")
print(f"   用瀏覽器開啟：open {OUT_HTML}")
