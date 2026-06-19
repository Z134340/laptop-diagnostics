#!/bin/bash
# 雙擊我即可開始 — 會啟動本機體檢程式並自動打開瀏覽器。
# (這個視窗請保持開啟;體檢完成後可直接關閉。)
cd "$(dirname "$0")" || exit 1

clear
echo "==================================================="
echo "   電腦健康體檢"
echo "==================================================="
echo ""

# 需要 python3(macOS 開發者工具內含)
if ! command -v python3 >/dev/null 2>&1; then
  echo "首次使用需要安裝一個系統元件(開發者工具)。"
  osascript -e 'display dialog "首次使用需要安裝一個系統元件(Command Line Tools)。\n\n接下來會跳出 Apple 的安裝視窗,請按「安裝」。安裝完成後,再雙擊一次本程式即可。" buttons {"好"} default button 1 with title "電腦健康體檢"' >/dev/null 2>&1
  xcode-select --install >/dev/null 2>&1
  echo "請依畫面完成安裝後,再次雙擊「開始體檢」。"
  echo "按 Enter 關閉此視窗…"; read -r _
  exit 0
fi

echo "正在啟動… 瀏覽器會自動打開操作畫面。"
echo "★ 請勿關閉這個黑色視窗(關掉就會停止)。體檢完成後可直接關閉。"
echo ""

python3 app_server.py

echo ""
echo "已結束,可以關閉這個視窗了。"
