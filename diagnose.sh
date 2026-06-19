#!/usr/bin/env bash
# =============================================================
# diagnose.sh — Laptop Diagnostics 唯讀收集腳本
# 執行方式：bash diagnose.sh
# 所有結果寫入 report/data/*.json，不刪除任何檔案
# =============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_DIR="$SCRIPT_DIR/report/data"
mkdir -p "$DATA_DIR"

# 顏色
RED='\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; NC='\033[0m'

log()  { echo -e "${CYAN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
ok()   { echo -e "${GREEN}[OK]${NC}   $1"; }
err()  { echo -e "${RED}[ERR]${NC}  $1"; }

echo ""
echo "======================================================"
echo "  Laptop Diagnostics — 開始診斷"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "======================================================"
echo ""

# ─────────────────────────────────────────────────────────────
# 前置：安裝 fdupes（若未安裝）
# ─────────────────────────────────────────────────────────────
log "檢查 fdupes..."
if ! command -v fdupes &>/dev/null; then
  warn "fdupes 未安裝，嘗試 brew install fdupes..."
  if command -v brew &>/dev/null; then
    brew install fdupes
    ok "fdupes 安裝完成"
  else
    err "Homebrew 不存在，M1 模組將使用備用 md5 方法"
    FDUPES_AVAILABLE=false
  fi
else
  FDUPES_AVAILABLE=true
  ok "fdupes 已就緒：$(fdupes --version 2>&1 | head -1)"
fi

# ─────────────────────────────────────────────────────────────
# M1：重複檔案
# ─────────────────────────────────────────────────────────────
log "M1 重複檔案掃描（範圍：~，排除 .Trash / node_modules / .git）..."

M1_JSON="$DATA_DIR/m1_dupes.json"

if [ "${FDUPES_AVAILABLE:-true}" = true ]; then
  # fdupes 輸出：每個重複群組以空行分隔
  TMPFILE=$(mktemp)
  fdupes -rSn \
    --exclude='.Trash' \
    --exclude='node_modules' \
    --exclude='.git' \
    ~ 2>/dev/null > "$TMPFILE" || true

  python3 - "$TMPFILE" "$M1_JSON" <<'PYEOF'
import sys, json, os

tmpfile = sys.argv[1]
out     = sys.argv[2]

groups = []
current = []
total_wasted = 0

with open(tmpfile) as f:
  for line in f:
    line = line.rstrip('\n')
    if line == '':
      if len(current) >= 2:
        try:
          size = os.path.getsize(current[0])
        except Exception:
          size = 0
        wasted = size * (len(current) - 1)
        total_wasted += wasted
        groups.append({
          "files": current,
          "size_bytes": size,
          "count": len(current),
          "wasted_bytes": wasted
        })
      current = []
    else:
      current.append(line)

# 最後一組
if len(current) >= 2:
  try:
    size = os.path.getsize(current[0])
  except Exception:
    size = 0
  wasted = size * (len(current) - 1)
  total_wasted += wasted
  groups.append({
    "files": current,
    "size_bytes": size,
    "count": len(current),
    "wasted_bytes": wasted
  })

# 依浪費空間排序
groups.sort(key=lambda x: x["wasted_bytes"], reverse=True)

result = {
  "module": "M1",
  "scan_time": __import__('datetime').datetime.now().isoformat(),
  "total_groups": len(groups),
  "total_wasted_bytes": total_wasted,
  "groups": groups[:200]   # 最多輸出 200 組避免 JSON 過大
}
with open(out, 'w') as f:
  json.dump(result, f, ensure_ascii=False, indent=2)

print(f"  → 重複群組：{len(groups)} 個，可釋空間：{total_wasted / 1024**3:.2f} GB")
PYEOF

  rm -f "$TMPFILE"
else
  # 備用：find + md5（較慢）
  log "  使用備用 md5 方法（較慢，請稍候）..."
  python3 - "$M1_JSON" <<'PYEOF'
import os, hashlib, json
from datetime import datetime
from collections import defaultdict

SCAN_ROOTS = [os.path.expanduser("~")]
EXCLUDE = {'.Trash', 'node_modules', '.git', 'Library/Caches'}

def md5_file(path, chunk=65536):
    h = hashlib.md5()
    try:
        with open(path, 'rb') as f:
            while True:
                b = f.read(chunk)
                if not b: break
                h.update(b)
        return h.hexdigest()
    except Exception:
        return None

size_map = defaultdict(list)

for root_dir in SCAN_ROOTS:
    for dirpath, dirnames, filenames in os.walk(root_dir, followlinks=False):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE and not d.startswith('.')]
        for fn in filenames:
            fp = os.path.join(dirpath, fn)
            try:
                sz = os.path.getsize(fp)
                if sz > 1024:
                    size_map[sz].append(fp)
            except Exception:
                pass

groups = []
total_wasted = 0
candidates = {sz: paths for sz, paths in size_map.items() if len(paths) > 1}

for sz, paths in candidates.items():
    hash_map = defaultdict(list)
    for p in paths:
        h = md5_file(p)
        if h:
            hash_map[h].append(p)
    for h, dupes in hash_map.items():
        if len(dupes) > 1:
            wasted = sz * (len(dupes) - 1)
            total_wasted += wasted
            groups.append({"files": dupes, "size_bytes": sz, "count": len(dupes), "wasted_bytes": wasted})

groups.sort(key=lambda x: x["wasted_bytes"], reverse=True)
result = {
  "module": "M1", "scan_time": datetime.now().isoformat(),
  "total_groups": len(groups), "total_wasted_bytes": total_wasted,
  "groups": groups[:200]
}
with open(sys.argv[1], 'w') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print(f"  → 重複群組：{len(groups)} 個，可釋空間：{total_wasted / 1024**3:.2f} GB")
PYEOF
fi

ok "M1 完成 → $M1_JSON"

# ─────────────────────────────────────────────────────────────
# M2：孤兒 / 損壞項目
# ─────────────────────────────────────────────────────────────
log "M2 孤兒與損壞項目掃描..."

M2_JSON="$DATA_DIR/m2_broken.json"

# broken symlinks
BROKEN_LINKS=$(find -L ~ -type l 2>/dev/null \
  | grep -v '.Trash' \
  | grep -v 'node_modules' \
  | grep -v '.git' \
  || true)

# brew doctor
if command -v brew &>/dev/null; then
  BREW_DOCTOR=$(brew doctor 2>&1 || true)
else
  BREW_DOCTOR="Homebrew not found"
fi

python3 - "$M2_JSON" <<PYEOF
import json, os
from datetime import datetime

broken = [p for p in """$BROKEN_LINKS""".strip().split('\n') if p] if """$BROKEN_LINKS""".strip() else []
brew_raw = """$BREW_DOCTOR"""

# ── 斷裂 symlink 三分類 ────────────────────────────────────────
# 經驗：~/Library 下絕大多數「斷裂」symlink 是 macOS / App 的正常設計，
# 並非真的壞掉。只有第三類「真殘留」才需要(在使用者授權下)清理。
#   1) sandbox_template — macOS 沙盒容器範本捷徑(~/Library/Containers/*)，
#      系統 containermanagerd 自動產生維護，刪了會重建，正常無害 → 勿動
#   2) app_lock        — App 執行期鎖檔(SingletonLock / SingletonCookie /
#      SingletonSocket / RunningChromeVersion 等)，故意指向非檔案目標，正常設計 → 勿動
#   3) stale           — 指向已刪除/暫存(已清空)目標的真殘留 → 可安全清理
LOCK_NAMES = {"SingletonLock", "SingletonCookie", "SingletonSocket", "RunningChromeVersion"}

def categorize(path):
    base = os.path.basename(path)
    if "/Library/Containers/" in path:
        return "sandbox_template"
    if base in LOCK_NAMES or base.endswith(".lock"):
        return "app_lock"
    return "stale"

cats = {"sandbox_template": 0, "app_lock": 0, "stale": 0}
stale = []
for p in broken:
    c = categorize(p)
    cats[c] += 1
    if c == "stale":
        try:
            tgt = os.readlink(p)
        except Exception:
            tgt = ""
        stale.append({"path": p, "target": tgt})

# 解析 brew doctor 段落
brew_issues = []
current_issue = []
for line in brew_raw.split('\n'):
    if line.startswith('Warning:') or line.startswith('Error:'):
        if current_issue:
            brew_issues.append('\n'.join(current_issue))
        current_issue = [line]
    elif current_issue:
        current_issue.append(line)
if current_issue:
    brew_issues.append('\n'.join(current_issue))

result = {
  "module": "M2",
  "scan_time": datetime.now().isoformat(),
  "broken_symlinks_count": len(broken),
  "categories": cats,
  "category_notes": {
    "sandbox_template": "macOS 沙盒容器範本捷徑，系統自動產生維護，正常無害，勿動",
    "app_lock": "App 執行期鎖檔(SingletonLock 等)，正常設計，勿動",
    "stale": "指向已刪除/已清空目標的真殘留，可在使用者授權下安全清理"
  },
  "stale_symlinks": stale,
  "stale_count": len(stale),
  "broken_symlinks": [{"path": p} for p in broken],
  "brew_doctor_raw": brew_raw,
  "brew_issues": brew_issues,
  "brew_issues_count": len(brew_issues)
}
with open("$M2_JSON", 'w') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print(f"  → 斷裂 symlink {len(broken)} 個：沙盒範本 {cats['sandbox_template']} / App 鎖檔 {cats['app_lock']} / 真殘留 {cats['stale']}(需處理)；Homebrew 問題 {len(brew_issues)} 項")
PYEOF

ok "M2 完成 → $M2_JSON"

# ─────────────────────────────────────────────────────────────
# M3：大型檔案 Top 50
# ─────────────────────────────────────────────────────────────
log "M3 大型檔案掃描（>100MB，排除 /System /private/var）..."

M3_JSON="$DATA_DIR/m3_large.json"

python3 - "$M3_JSON" <<'PYEOF'
import os, sys, json, subprocess
from datetime import datetime

PRUNE = {'/System', '/private', '/Volumes', '/dev', '/net', '/home'}
MIN_SIZE = 100 * 1024 * 1024  # 100 MB

files = []
for root, dirs, filenames in os.walk('/', followlinks=False):
    # 剪枝
    dirs[:] = [d for d in dirs if os.path.join(root, d) not in PRUNE
               and not os.path.join(root, d).startswith('/System')
               and not os.path.join(root, d).startswith('/private/var')
               and not os.path.join(root, d).startswith('/Volumes')]
    for fn in filenames:
        fp = os.path.join(root, fn)
        try:
            st = os.stat(fp, follow_symlinks=False)
            if st.st_size >= MIN_SIZE:
                files.append({
                    "path": fp,
                    "size_bytes": st.st_size,
                    "size_mb": round(st.st_size / 1024**2, 1),
                    "last_access": datetime.fromtimestamp(st.st_atime).strftime('%Y-%m-%d'),
                    "last_modified": datetime.fromtimestamp(st.st_mtime).strftime('%Y-%m-%d'),
                    "ext": os.path.splitext(fn)[1].lower()
                })
        except Exception:
            pass

files.sort(key=lambda x: x['size_bytes'], reverse=True)
top50 = files[:50]

result = {
  "module": "M3",
  "scan_time": datetime.now().isoformat(),
  "total_found": len(files),
  "total_size_gb": round(sum(f['size_bytes'] for f in files) / 1024**3, 2),
  "files": top50
}
with open(sys.argv[1] if len(sys.argv) > 1 else '/dev/stdout', 'w') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print(f"  → 大型檔案：{len(files)} 個，Top 50 總計 {result['total_size_gb']:.1f} GB")
PYEOF

ok "M3 完成 → $M3_JSON"

# ─────────────────────────────────────────────────────────────
# M4：開發環境健檢
# ─────────────────────────────────────────────────────────────
log "M4 開發環境健檢..."

M4_JSON="$DATA_DIR/m4_env.json"

collect() {
  local cmd="$1"
  eval "$cmd" 2>&1 || echo "not found / error"
}

python3 - "$M4_JSON" <<PYEOF
import json, subprocess, shutil
from datetime import datetime

def run(cmd):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        return (r.stdout + r.stderr).strip()
    except Exception as e:
        return f"error: {e}"

tools = {
    "node":    run("node -v"),
    "npm":     run("npm -v"),
    "npx":     run("npx -v"),
    "python3": run("python3 --version"),
    "pip3":    run("pip3 --version"),
    "ruby":    run("ruby -v"),
    "go":      run("go version"),
    "java":    run("java -version"),
    "git":     run("git --version"),
    "docker":  run("docker --version"),
    "brew":    run("brew --version"),
}

npm_doctor    = run("npm doctor") if shutil.which("npm") else "npm not found"
brew_list     = run("brew list --versions") if shutil.which("brew") else "brew not found"
pip_outdated  = run("pip3 list --outdated 2>/dev/null | head -20") if shutil.which("pip3") else "pip3 not found"

# node version managers
nvm_versions  = run("ls ~/.nvm/versions/node 2>/dev/null || echo 'nvm not found'")
pyenv_versions= run("pyenv versions 2>/dev/null || echo 'pyenv not found'")

# ── 結構化「可更新」資料(供修復規則表動態判斷) ──────────────
brew_outdated_raw = run("brew outdated --quiet 2>/dev/null") if shutil.which("brew") else ""
brew_outdated = [x for x in brew_outdated_raw.split("\n") if x.strip()] if brew_outdated_raw else []

pip_lines = [l for l in pip_outdated.split("\n") if l.strip()]
# 扣掉表頭兩行(Package/Version... 與 ---- 分隔線)
pip_outdated_count = max(0, len([l for l in pip_lines if l and not l.startswith("Package") and not l.startswith("---")]))

npm_g_raw = run("npm outdated -g --parseable 2>/dev/null") if shutil.which("npm") else ""
npm_global_outdated_count = len([x for x in npm_g_raw.split("\n") if x.strip()]) if npm_g_raw else 0

result = {
  "module": "M4",
  "scan_time": datetime.now().isoformat(),
  "versions": tools,
  "npm_doctor": npm_doctor,
  "brew_installed_packages": brew_list,
  "pip_outdated": pip_outdated,
  "pip_outdated_count": pip_outdated_count,
  "brew_outdated": brew_outdated,
  "brew_outdated_count": len(brew_outdated),
  "npm_global_outdated_count": npm_global_outdated_count,
  "nvm_versions": nvm_versions,
  "pyenv_versions": pyenv_versions
}
with open("$M4_JSON", 'w') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print(f"  → 工具版本收集完成；brew 可升級 {len(brew_outdated)}、pip 過時 {pip_outdated_count}、npm 全域過時 {npm_global_outdated_count}")
PYEOF

ok "M4 完成 → $M4_JSON"

# ─────────────────────────────────────────────────────────────
# M5：可回收空間（唯讀 du）
# ─────────────────────────────────────────────────────────────
log "M5 可回收空間掃描..."
M5_JSON="$DATA_DIR/m5_reclaimable.json"
python3 - "$M5_JSON" <<'PYEOF'
import sys, os, json, subprocess
from datetime import datetime

HOME = os.path.expanduser("~")
def dk(path):  # du -sk -> bytes，不存在回 0
    if not os.path.exists(path): return 0
    try:
        out = subprocess.run(["du","-sk",path], capture_output=True, text=True, timeout=120).stdout
        return int(out.split("\t")[0].strip()) * 1024
    except Exception:
        return 0

ITEMS = [
  ("應用程式快取 (~/Library/Caches)", os.path.join(HOME,"Library/Caches"), "App 快取，可清，App 會重建"),
  ("使用者快取 (~/.cache)",            os.path.join(HOME,".cache"),         "工具快取，可清"),
  ("npm 快取 (~/.npm)",                os.path.join(HOME,".npm"),           "用 npm cache clean --force"),
  ("Homebrew 下載快取",               os.path.join(HOME,"Library/Caches/Homebrew"), "用 brew cleanup -s"),
  ("pip 快取",                         os.path.join(HOME,"Library/Caches/pip"),      "用 pip cache purge"),
  ("垃圾桶 (~/.Trash)",               os.path.join(HOME,".Trash"),         "可清空"),
  ("iOS 裝置備份",                     os.path.join(HOME,"Library/Application Support/MobileSync/Backup"), "舊裝置備份，確認後可刪"),
  ("Xcode DerivedData",               os.path.join(HOME,"Library/Developer/Xcode/DerivedData"), "編譯中繼，可清"),
  ("CoreSimulator 模擬器",            os.path.join(HOME,"Library/Developer/CoreSimulator"), "iOS 模擬器，可用 xcrun simctl delete unavailable"),
]
items = []
for label, path, note in ITEMS:
    b = dk(path)
    if b > 0:
        items.append({"label": label, "path": path, "size_bytes": b, "note": note})
items.sort(key=lambda x: x["size_bytes"], reverse=True)

result = {
  "module": "M5", "scan_time": datetime.now().isoformat(),
  "items": items, "total_reclaimable_bytes": sum(i["size_bytes"] for i in items)
}
json.dump(result, open(sys.argv[1],'w'), ensure_ascii=False, indent=2)
print(f"  → 可回收空間估計：{result['total_reclaimable_bytes']/1024**3:.2f} GB（{len(items)} 類）")
PYEOF
ok "M5 完成 → $M5_JSON"

# ─────────────────────────────────────────────────────────────
# M6：電池與電源健康（唯讀）
# ─────────────────────────────────────────────────────────────
log "M6 電池健康..."
M6_JSON="$DATA_DIR/m6_battery.json"
python3 - "$M6_JSON" <<'PYEOF'
import sys, json, subprocess, re
from datetime import datetime

def run(cmd):
    try: return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30).stdout
    except Exception: return ""

raw = run("system_profiler SPPowerDataType 2>/dev/null")
def grab(key):
    m = re.search(rf"{key}:\s*(.+)", raw)
    return m.group(1).strip() if m else "—"

result = {
  "module": "M6", "scan_time": datetime.now().isoformat(),
  "cycle_count":      grab("Cycle Count"),
  "condition":        grab("Condition"),
  "maximum_capacity": grab("Maximum Capacity"),
  "fully_charged":    grab("Fully Charged"),
  "charging":         grab("Charging"),
  "power_source":     grab("Connected") if "Connected" in raw else grab("Power Source State"),
  "raw": raw[:4000],
}
json.dump(result, open(sys.argv[1],'w'), ensure_ascii=False, indent=2)
print(f"  → 電池：循環 {result['cycle_count']}，容量 {result['maximum_capacity']}，狀態 {result['condition']}")
PYEOF
ok "M6 完成 → $M6_JSON"

# ─────────────────────────────────────────────────────────────
# M7：系統健康（唯讀）
# ─────────────────────────────────────────────────────────────
log "M7 系統健康..."
M7_JSON="$DATA_DIR/m7_system.json"
python3 - "$M7_JSON" <<'PYEOF'
import sys, json, subprocess, re
from datetime import datetime

def run(cmd):
    try: return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60).stdout.strip()
    except Exception as e: return f"error: {e}"

disk = run("diskutil info / 2>/dev/null")
def g(key, text=disk):
    m = re.search(rf"{key}:\s*(.+)", text)
    return m.group(1).strip() if m else "—"

snaps = run("tmutil listlocalsnapshots / 2>/dev/null")
snap_list = [l.strip() for l in snaps.split("\n") if l.startswith("com.apple.")]
mem = run("memory_pressure 2>/dev/null | tail -2")
mem_free = "—"
mm = re.search(r"free percentage:\s*(\d+%)", mem)
if mm: mem_free = mm.group(1)

result = {
  "module": "M7", "scan_time": datetime.now().isoformat(),
  "smart_status":        g("SMART Status"),
  "volume_name":         g("Volume Name"),
  "container_total":     g("Container Total Space"),
  "container_free":      g("Container Free Space"),
  "memory_free_pct":     mem_free,
  "swap_usage":          run("sysctl -n vm.swapusage 2>/dev/null"),
  "uptime":              run("uptime"),
  "local_snapshots_count": len(snap_list),
  "local_snapshots":     snap_list[:20],
}
json.dump(result, open(sys.argv[1],'w'), ensure_ascii=False, indent=2)
print(f"  → SMART：{result['smart_status']}，可用 {result['container_free']}，快照 {result['local_snapshots_count']} 個")
PYEOF
ok "M7 完成 → $M7_JSON"

# ─────────────────────────────────────────────────────────────
# M8：登入與背景項目（唯讀）
# ─────────────────────────────────────────────────────────────
log "M8 登入與背景項目..."
M8_JSON="$DATA_DIR/m8_startup.json"
python3 - "$M8_JSON" <<'PYEOF'
import sys, os, json, subprocess
from datetime import datetime

HOME = os.path.expanduser("~")
def listdir(p):
    try: return sorted(f for f in os.listdir(p) if f.endswith(".plist"))
    except Exception: return []

user_agents   = listdir(os.path.join(HOME,"Library/LaunchAgents"))
sys_agents    = listdir("/Library/LaunchAgents")
sys_daemons   = listdir("/Library/LaunchDaemons")

def run(cmd):
    try: return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception: return ""
login_raw = run('osascript -e \'tell application "System Events" to get the name of every login item\'')
login_items = [x.strip() for x in login_raw.split(",") if x.strip()] if login_raw else []

# 標出第三方（非 com.apple.）自啟項目
def third_party(lst):
    return [x for x in lst if not x.startswith("com.apple.")]

result = {
  "module": "M8", "scan_time": datetime.now().isoformat(),
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
json.dump(result, open(sys.argv[1],'w'), ensure_ascii=False, indent=2)
print(f"  → 登入項目 {len(login_items)}，使用者代理 {len(user_agents)}，系統代理 {len(sys_agents)}，常駐 {len(sys_daemons)}")
PYEOF
ok "M8 完成 → $M8_JSON"

# ─────────────────────────────────────────────────────────────
# M9：安全與更新狀態（唯讀）
# ─────────────────────────────────────────────────────────────
log "M9 安全與更新狀態..."
M9_JSON="$DATA_DIR/m9_security.json"
python3 - "$M9_JSON" <<'PYEOF'
import sys, json, subprocess
from datetime import datetime

def run(cmd, timeout=60):
    try: return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout).stdout.strip()
    except Exception as e: return f"error: {e}"

filevault  = run("fdesetup status 2>&1")
sip        = run("csrutil status 2>&1")
gatekeeper = run("spctl --status 2>&1")
firewall   = run("/usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate 2>&1")

# 待安裝更新（network，可能較慢；逾時則標記）
sw = run("softwareupdate -l 2>&1", timeout=90)
updates = [l.strip() for l in sw.split("\n") if l.strip().startswith("* Label:")]

def status_of(text, on_kw, off_kw):
    t = text.lower()
    if off_kw in t: return "off"
    if on_kw in t:  return "on"
    return "unknown"

result = {
  "module": "M9", "scan_time": datetime.now().isoformat(),
  "filevault":  {"raw": filevault,  "state": "on" if "is on" in filevault.lower() else ("off" if "is off" in filevault.lower() else "unknown")},
  "sip":        {"raw": sip,        "state": "on" if "enabled" in sip.lower() else ("off" if "disabled" in sip.lower() else "unknown")},
  "gatekeeper": {"raw": gatekeeper, "state": "on" if "enabled" in gatekeeper.lower() else ("off" if "disabled" in gatekeeper.lower() else "unknown")},
  "firewall":   {"raw": firewall,   "state": "off" if "disabled" in firewall.lower() or "= 0" in firewall else ("on" if "enabled" in firewall.lower() else "unknown")},
  "pending_updates": updates,
  "pending_updates_count": len(updates),
  "softwareupdate_raw": sw[:2000],
}
json.dump(result, open(sys.argv[1],'w'), ensure_ascii=False, indent=2)
print(f"  → FileVault {result['filevault']['state']} / SIP {result['sip']['state']} / Gatekeeper {result['gatekeeper']['state']} / 防火牆 {result['firewall']['state']}；待更新 {len(updates)} 項")
PYEOF
ok "M9 完成 → $M9_JSON"

# ─────────────────────────────────────────────────────────────
# 完成摘要
# ─────────────────────────────────────────────────────────────
echo ""
echo "======================================================"
echo "  資料收集完成，JSON 存放於："
echo "  $DATA_DIR"
echo ""
echo "  下一步：執行 generate_report.py 產生互動式 HTML"
echo "======================================================"
