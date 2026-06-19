# Laptop Diagnostics — Claude Code 任務說明

## 目標
對本機 macOS 執行四維度唯讀診斷，最終輸出 `report/index.html` 互動式報告。

## 安全邊界（硬性限制）
- **預設唯讀；診斷收集階段絕不刪除、移動、修改任何使用者檔案**
- 所有收集操作僅限 `find`（read-only）、`fdupes`、`brew`（read-only subcommands）、`md5` / `shasum`
- **修復動作（刪 symlink、改 `~/.bash_profile`、`brew upgrade` 等）必須先逐項列出、取得使用者明確授權後才執行**；不得在授權範圍外動任何真實檔案
- 若遇到需要 `sudo` 的指令，記錄「權限不足，跳過」，繼續下一步
- 暫存資料寫入 `report/data/` 目錄，不寫到系統路徑

## 執行順序
- **非技術使用者入口:雙擊 `開始體檢.command`** → 啟動 `app_server.py`(127.0.0.1:8788)→ 瀏覽器首頁按「開始體檢」→ 背景跑掃描+顯示進度 → 完成自動跳報告 → 報告內一鍵修復。打包用 `bash package.sh`(產出 `laptop-diagnostics-portable.zip`,**排除個人掃描資料**)。
- **標準入口(開發/CLI,確保一致性)：`bash run.sh`**(= diagnose.sh → generate_report.py;`--serve` 連同啟動修復伺服器、`--open` 開純檢視報告)。
- 手動分步:
  1. 安裝前置工具（`fdupes`，若未安裝）
  2. 執行 `diagnose.sh`（九模組唯讀收集 → `report/data/*.json`）
  3. `python3 generate_report.py` 生成 `report/index.html`
  4. 完成後回報九模組摘要數字
  5.（選用）`python3 repair_server.py` 啟動修復伺服器（127.0.0.1:8787），讓摘要頁「修復」按鈕能一鍵執行白名單修復；不啟動則為純唯讀檢視
- **一致性守則:任何改動 `diagnose.sh` 後,務必 `bash run.sh` 完整跑一次驗證**(`set -euo pipefail` 下,單一模組的 python 例外會中止整支腳本,且資料檔須與 `generate_report.py` 讀取的欄位一致)。
- 報告摘要頁版面固定順序:頁面說明 → 九個檢查模組一覽 → 整體判讀 → 需要你注意的事 → 運作良好的部分 → 修復涵蓋範圍。

## 前端一鍵修復（repair_server.py）+ 規則登錄表
- **修復計畫由掃描結果動態產生**：`generate_report.py` 內有「規則登錄表 `RULES`」，每條 = `applies(掃描資料)→bool` ＋ 嚴重度 ＋ 對應 `action`。報告產生時逐條套用當次掃描,命中才長出按鈕(例:防火牆關才有開火牆鈕、pip 過舊才有更新 pip 鈕、brew 全最新則升級鈕自動消失)。新增一種修復 = 加一條規則 + 一個伺服器動作。
- 靜態 HTML 無法直接執行修復，故 `repair_server.py` 提供白名單 API；按鈕按下 → confirm → POST `/api/fix` → 伺服器端**在執行當下重新驗證現況**後才執行(不吃報告快照,故舊報告頂多「無事可做」不會誤動)。
- 白名單動作（13）：`fix_path`/`brew_cleanup`/`clear_caches`/`clean_stale_symlinks`/`fix_m2`/`enable_firewall`/`open_software_update`/`brew_upgrade`/`update_pip`/`update_npm`/`thin_snapshots`/`open_filevault_settings`/`enable_gatekeeper`。
- 覆蓋:規則表 17 條,涵蓋 M1–M9 各模組的可行動發現;健康/正常項目不觸發(掃到才出對應修復)。硬體類(電池老化、SMART 異常)與需重開機者(SIP)只導引、不一鍵。
- 安全：僅綁 `127.0.0.1`、每次請求比對啟動時隨機 token、只允許白名單；需權限者（防火牆）用 `osascript ... with administrator privileges` 跳原生授權；`update_pip` 只升 pip 本身且 `--user`，不動系統 Python；不做需重啟的系統更新（只開設定頁）。

## 模組定義
| ID | 名稱 | 核心指令 |
|----|------|----------|
| M1 | 重複檔案 | `fdupes -rSn ~ 2>/dev/null` |
| M2 | 孤兒/損壞項目 | `find -L ~ -type l ! -name .DS_Store 2>/dev/null`（broken symlinks）+ `brew doctor` |
| M3 | 大型檔案 Top 50 | `find / -not \( -path /System -prune \) -not \( -path /private/var -prune \) -size +100M -type f 2>/dev/null` |
| M4 | 開發環境健檢 | `node -v`, `npm doctor`, `python3 --version`, `brew list --versions` |
| M5 | 可回收空間 | `du -sk` 各類快取/Trash/iOS 備份/DerivedData |
| M6 | 電池與電源健康 | `system_profiler SPPowerDataType` |
| M7 | 系統健康 | `diskutil info /`（SMART）、`memory_pressure`、`sysctl vm.swapusage`、`tmutil listlocalsnapshots /` |
| M8 | 登入與背景項目 | `~/Library/LaunchAgents`、`/Library/Launch{Agents,Daemons}`、登入項目（osascript） |
| M9 | 安全與更新狀態 | `fdesetup status`、`csrutil status`、`spctl --status`、`socketfilterfw --getglobalstate`、`softwareupdate -l` |

## 輸出規格
- `report/data/m1_dupes.json`
- `report/data/m2_broken.json`（含 `categories` 三分類與 `stale_symlinks` 真殘留清單）
- `report/data/m3_large.json`
- `report/data/m4_env.json`
- `report/data/m5_reclaimable.json`、`m6_battery.json`、`m7_system.json`、`m8_startup.json`、`m9_security.json`
- `report/index.html`（互動式，含九個 tab、篩選器、可釋空間加總）

## 經驗與判讀（重要，詳見 `.claude/skills/laptop-diagnostics/SKILL.md`）
- **M2 斷裂 symlink 約 99.7% 是正常的**，務必分三類，只有 `stale` 需處理：
  - `sandbox_template`（路徑含 `/Library/Containers/`）：macOS 沙盒容器範本，系統自動維護 → 勿動
  - `app_lock`（`SingletonLock`/`SingletonCookie`/`SingletonSocket`/`RunningChromeVersion`/`.lock`）：App 執行鎖 → 勿動
  - `stale`（其餘）：指向已刪目標的真殘留 → 可在授權下清理（刪前雙重確認 `islink` 且目標不存在，只 `unlink` 連結本身）
- **`brew doctor` 多為 PATH 設定問題**（非壞檔）；修 `~/.bash_profile` 後須以 `bash -lc 'brew doctor'` 驗證（非 login shell 不讀 profile，會誤報）。
- **腳本陷阱**：`diagnose.sh` 有 `set -euo pipefail`，任一 python heredoc 例外會中止全腳本。**每個用 `sys.argv` 的 heredoc 都要 `import sys`**（M3 曾因此中止）。改腳本後完整跑一次驗證。
- **效能**：M3 全碟掃描最慢；要單獨刷新某模組就複用該模組邏輯，別為了刷新而重跑整支。
- **M4 版本**：brew 管理者以 `brew outdated` 為準；系統工具（Apple python3 3.9 / 系統 ruby 2.6 / Apple git）由 macOS 控管，不單獨升，開發改用 brew 版。node 大版本升級前先 `npm ls -g` 快照全域套件。
