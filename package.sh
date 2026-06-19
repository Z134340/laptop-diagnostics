#!/usr/bin/env bash
# package.sh — 打包成可攜帶 zip,給別人用。
# 會排除「本機個人掃描資料」(report/data、report/index.html),
# 收件者雙擊「開始體檢.command」自行產生自己的報告。
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

OUT="laptop-diagnostics-portable.zip"
rm -f "$OUT"

zip -r "$OUT" . \
  -x "${OUT}" \
  -x "report/data/*" \
  -x "report/index.html" \
  -x "report/.playwright-mcp/*" -x ".playwright-mcp/*" \
  -x "*/__pycache__/*" -x "__pycache__/*" -x "*.pyc" \
  -x "*.log" \
  -x "manual_assets/*" -x "build_manual.js" -x "*.pdf" \
  -x ".git/*" \
  -x ".claude/*" \
  -x "*.DS_Store" \
  > /dev/null

echo "✅ 已打包:$OUT"
echo "--- 內容 ---"
unzip -Z1 "$OUT"
echo ""
echo "交付方式:把 $OUT 傳給對方 → 解壓縮 → 雙擊「開始體檢.command」。"
