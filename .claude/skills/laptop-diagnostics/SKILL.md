---
name: laptop-diagnostics
description: 對本機 macOS 執行多維度「唯讀」診斷(M1 重複檔 / M2 孤兒損壞 / M3 大型檔 / M4 開發環境 / M5 可回收空間 / M6 電池 / M7 系統健康 / M8 登入背景項目 / M9 安全與更新),產生 report/index.html 互動報告,並在使用者逐項授權後做安全修復。當使用者說「跑診斷 / 健檢這台 mac / 重複檔 / 斷裂 symlink / 大型檔案 / 開發環境版本 / 清理 / brew doctor / 電池 / 防火牆 / 登入項目 / 可回收空間 / 產生診斷報告」時使用。內含 M2 判讀指南與修復 playbook,避免把正常的系統 symlink 誤判為損壞。
---

# Laptop Diagnostics(macOS 唯讀診斷 + 受控修復)

## 用途
在 macOS 上跑四維度唯讀診斷,輸出 `report/index.html`,再依使用者逐項確認做安全修復。

## 安全邊界(硬性)
- 預設**唯讀**:收集階段只用 `find`(read-only)、`fdupes`、`brew`(read-only 子指令)、`md5`/`shasum`。
- **絕不自動刪除/移動/修改任何使用者檔案**。任何寫入或刪除動作,**必須先逐項列出、取得使用者明確授權**(例:互動 console 按鈕或口頭同意)後才執行。
- 遇到需要 `sudo` 的指令 → 記「權限不足,跳過」,繼續下一步。
- 暫存資料只寫 `report/data/`。

## 模組
- M1 重複檔 / M2 孤兒損壞(symlink+brew doctor) / M3 大型檔 / M4 開發環境(原始四維度)
- M5 可回收空間(各類快取/Trash/iOS 備份) / M6 電池 / M7 系統健康(SMART/記憶體/swap/APFS 快照) / M8 登入與背景項目(LaunchAgents/Daemons+登入項目,標出第三方自啟) / M9 安全與更新(FileVault/SIP/Gatekeeper/防火牆/待更新)
- 全部唯讀;報告 `report/index.html` 為九個 tab。

## 執行流程
0a. **非技術使用者:雙擊 `開始體檢.command`** → `app_server.py`(:8788)首頁按「開始體檢」→ 網頁顯示進度 → 完成自動跳報告 → 一鍵修復。`bash package.sh` 產可攜 zip(排除個人掃描資料 report/data 與 report/index.html)。
0b. **標準入口(CLI):`bash run.sh`**(diagnose.sh → generate_report.py;`--serve` 連帶起修復伺服器、`--open` 開報告)。確保每次產出一致。
1. `bash diagnose.sh` — 收集 → 寫 `report/data/m{1..9}_*.json`(M3 全碟掃描最慢,可背景跑;單獨刷新某模組就複用該模組邏輯)。
   - **資料契約**:`diagnose.sh` 產出的 JSON 欄位必須對齊 `generate_report.py` 讀取的欄位(尤其 M4 的 `brew_outdated_count`/`pip_outdated_count`/`npm_global_outdated_count`、M6/M7/M9 給規則表用的狀態欄位)。改任一邊都要兩邊一起改並完整跑 `run.sh` 驗證。
   - 報告摘要頁固定順序:說明 → 九模組一覽 → 整體判讀 → 需要你注意的事 → 運作良好 → 修復涵蓋範圍。
2. `python3 generate_report.py` — 讀 JSON → 產 `report/index.html`。
3. `open report/index.html`(純檢視);或 `python3 repair_server.py` 啟動本機修復伺服器後用 127.0.0.1:8787 開啟,摘要頁「修復」按鈕可一鍵執行。
4. 回報九模組摘要;需修復時有兩條路:(a) 對話中用 `mcp__visualize__show_widget` + `sendPrompt()` 逐項確認;(b) 報告內建修復按鈕(走 `repair_server.py` 白名單 API)。

## 報告 UI / 修復伺服器
- 報告 `report/index.html`:摘要首頁(整體判讀 + 依風險排序的重點 + 模組總覽)+ M1–M9 分頁;全 inline SVG icon、每頁白話說明、M1/M3 檔案附「這是什麼」用途欄。
- **修復計畫動態產生**:`generate_report.py` 內「規則登錄表 `RULES`」(條件→修復對照),依當次掃描資料命中才長按鈕(防火牆關→開火牆鈕;pip 過舊→更新 pip 鈕;brew 全新→升級鈕消失)。擴充修復=加一條規則+一個伺服器動作。
- `repair_server.py`:13 個白名單動作(`fix_path`/`brew_cleanup`/`clear_caches`/`clean_stale_symlinks`/`fix_m2`/`enable_firewall`/`open_software_update`/`brew_upgrade`/`update_pip`/`update_npm`/`thin_snapshots`/`open_filevault_settings`/`enable_gatekeeper`)。每個動作**執行當下重新驗證現況**(不吃報告快照,例:gatekeeper 已開→不跳密碼、0 快照→不處理)。僅綁 127.0.0.1、token 驗證;需權限者跳 `osascript ... administrator privileges`;`update_pip` 只升 pip 本身且 `--user`。
- 覆蓋:`RULES` 17 條對應 M1–M9 各模組發現;健康項目不觸發。硬體類(電池老化、SMART)與需 Recovery 者(SIP)只導引不一鍵。新增修復 = 加 1 條規則 + 1 個伺服器動作 + 確保兩邊 id 一致。

## ⚠️ 已知陷阱(務必遵守)
- **每個用到 `sys.argv` 的 python heredoc 都必須 `import sys`。** diagnose.sh 因 `set -euo pipefail`,任一模組的 python 例外(如 M3 漏 import sys)會讓整支腳本中止。改腳本後務必完整跑一次驗證。
- **不要重跑整支只為了刷新單一模組**:M3 全碟掃描很慢。要單獨刷新 M2,複用其 find + 分類邏輯寫該模組 JSON 即可。

## M2 判讀指南(核心經驗)
`find -L ~ -type l` 在 ~/Library 下常回報數千條「斷裂 symlink」,但**約 99.7% 是正常的**。務必分三類,只有第 3 類需處理:

| 類別 | 判定規則 | 性質 | 動作 |
|---|---|---|---|
| `sandbox_template` | 路徑含 `/Library/Containers/` | macOS 沙盒容器範本捷徑(每容器固定 8 條:Filters/KeyBindings/ColorSync/QuickLook/Components/People/兩個 security plist),`containermanagerd` 自動產生維護,刪了會重建 | **勿動** |
| `app_lock` | basename ∈ {SingletonLock, SingletonCookie, SingletonSocket, RunningChromeVersion} 或結尾 `.lock` | Chromium/Electron 類 App 的執行期鎖(SingletonSocket 指向 socket、其餘指向「主機名-PID」非檔案目標) | **勿動**(App 開著時刪會害它開不起來) |
| `stale` | 其餘 | 指向已刪除/已清空(暫存)目標的真殘留 | **可清理**(需授權) |

`brew doctor` 的「issues」多半是 **PATH 設定**(非壞檔):
- `/usr/bin` 排在 `/opt/homebrew/bin` 前 → 改 `~/.bash_profile`。
- 用 `bash -lc 'brew doctor'` 驗證(自動化的非 login shell 不讀 `~/.bash_profile`,會誤報已修好的警告)。

## 修復 Playbook(都需逐項授權)
- **清理 stale symlink**:刪前用 `os.path.islink(p) and not os.path.exists(os.path.realpath(p))` 雙重確認,只 `os.unlink` 連結本身,絕不碰目標。
- **修 Homebrew PATH**:先 `grep opt/homebrew ~/.bash_profile` 避免重複;顯示要新增的內容再 append `export PATH="/opt/homebrew/bin:/opt/homebrew/sbin:$PATH"`;以 `bash -lc` 驗證 `which python3/openssl/pip3` 指向 `/opt/homebrew`。
- **brew 升級**:先 `brew update` + `brew outdated` 列清單;升級前 `npm ls -g --depth=0` 快照全域套件(node 大版本如 25→26 可能要重裝);`brew upgrade` 後驗證版本 + `bash -lc 'brew doctor'`。
- 修復後重收集對應模組並重生報告,讓數字反映現況。

## M4 版本判讀
- brew 管理者(node、gh、python@3.12…):以 `brew outdated` 為準。
- 系統工具(Apple `python3 3.9`、系統 `ruby 2.6`、Apple `git`):由 macOS/Xcode CLT 控管,**不單獨升**,開發請改用 brew 版。
