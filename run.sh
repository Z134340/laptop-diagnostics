#!/usr/bin/env bash
# =============================================================
# run.sh — 一鍵跑完整流程,確保每次產出一致
#   1) diagnose.sh  收集九模組資料 → report/data/*.json
#   2) generate_report.py  產生 report/index.html
#   3)(選用 --serve)啟動 repair_server.py 提供一鍵修復
#
# 用法:
#   bash run.sh           # 收集 + 產報告
#   bash run.sh --serve   # 收集 + 產報告 + 啟動修復伺服器
#   bash run.sh --open    # 收集 + 產報告 + 用瀏覽器開純檢視報告
# =============================================================
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "[1/2] 執行診斷收集 (diagnose.sh)..."
if ! bash diagnose.sh; then
  echo "❌ 診斷收集失敗(diagnose.sh 非 0 退出),中止。請查看上方錯誤。"
  exit 1
fi

echo "[2/2] 產生互動式報告 (generate_report.py)..."
if ! python3 generate_report.py; then
  echo "❌ 報告產生失敗,中止。"
  exit 1
fi

echo ""
echo "✅ 完成。報告:report/index.html"
echo "   純檢視:    open report/index.html"
echo "   一鍵修復:  python3 repair_server.py  (再用它開啟的網址瀏覽報告)"

case "${1:-}" in
  --serve) echo ""; echo "啟動修復伺服器..."; exec python3 repair_server.py ;;
  --open)  open report/index.html 2>/dev/null || true ;;
esac
