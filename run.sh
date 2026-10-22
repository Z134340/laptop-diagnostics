#!/usr/bin/env bash
# =============================================================
# run.sh — 一鍵跑完整流程,確保每次產出一致
#   1) diagnose.sh  收集十一模組資料 → report/data/*.json
#   2) generate_report.py  產生 report/index.html
#   3)(選用 --serve)啟動本機伺服器 app_server.py 並直接開報告頁(一鍵修復可用)
#
# 用法:
#   bash run.sh           # 收集 + 產報告
#   bash run.sh --serve   # 收集 + 產報告 + 啟動本機伺服器(同「開始體檢」那一支,埠 8788)
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
echo "   一鍵修復:  python3 app_server.py --report  (再用它開啟的網址瀏覽報告)"

case "${1:-}" in
  --serve) echo ""; echo "啟動本機伺服器(app_server.py)..."; exec python3 app_server.py --report ;;
  --open)  open report/index.html 2>/dev/null || true ;;
esac
