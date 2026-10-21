#!/usr/bin/env bash
# =============================================================
# diagnose.sh — Laptop Diagnostics 唯讀收集(薄殼)
#
# 實際收集邏輯在 Python 套件 macvitals/(python3 -m macvitals.collect):
#   每個模組獨立 try/except,任一模組失敗只會在它的 JSON 寫入 error 欄位,
#   其餘模組照跑;M1/M3/M9 並行;進度寫到 report/data/progress.json。
# 這支腳本只負責 banner、顏色 log 與轉傳參數,讓 run.sh、開始體檢.command、
# package.sh 與 app_server.py 不用改。
#
# 用法:
#   bash diagnose.sh                   # 全部 11 模組 → report/data/*.json
#   bash diagnose.sh --only m2 m7      # 只重跑指定模組
#   bash diagnose.sh --list            # 列出模組
# 所有結果寫入 report/data/*.json,不刪除任何檔案
# =============================================================

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

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

if ! command -v python3 >/dev/null 2>&1; then
  err "找不到 python3(macOS 開發者工具內含;可執行 xcode-select --install 安裝)。"
  exit 1
fi

# `python3 -m macvitals.collect` 需要以倉庫根目錄為 cwd 才找得到套件
cd "$SCRIPT_DIR" || exit 1

log "收集由 Python 套件執行:python3 -m macvitals.collect $*"
python3 -m macvitals.collect "$@"
rc=$?

if [ "$rc" -ne 0 ]; then
  err "收集程式異常結束(退出碼 $rc)。單一模組失敗不會造成這個結果;請查看上方訊息。"
  exit "$rc"
fi

echo ""
echo "======================================================"
echo "  資料收集完成,JSON 存放於:"
echo "  ${MACVITALS_DATA_DIR:-$SCRIPT_DIR/report/data}"
echo ""
echo "  下一步:執行 generate_report.py 產生互動式 HTML"
echo "======================================================"
