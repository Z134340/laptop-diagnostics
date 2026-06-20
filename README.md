# Laptop Diagnostics

對本機 macOS 執行**九維度唯讀診斷**,產出單檔互動式報告 `report/index.html`;並可選擇性啟動本機**一鍵修復伺服器**,讓報告上的按鈕直接執行白名單修復。

> 安全優先:診斷階段純唯讀,絕不刪改任何使用者檔案。任何會動到系統/檔案的修復,都需你在報告上逐項點擊確認,且伺服器端會在執行當下再次驗證現況。

## 最簡單的用法(不需要懂指令)

1. 在 Finder 裡**雙擊 `開始體檢.command`**。
   - 若跳出「無法打開,因為來自未識別的開發者」:按住 `Control` 點該檔 → 選「打開」→ 再按「打開」(只需一次)。
   - 首次使用若提示安裝「開發者工具」,按「安裝」,完成後再雙擊一次。
2. 瀏覽器會自動打開操作畫面 → 按 **「開始體檢」**。
3. 看著進度條跑完(約數分鐘),會**自動跳到報告**。
4. 報告裡「需要你注意的事」可直接按按鈕**一鍵修復**;需要密碼的會跳出系統授權視窗。
5. 結束後,關閉自動開啟的黑色終端機視窗即可。

> 過程中那個黑色視窗請勿關閉(關掉程式就停了)。全程唯讀,不會刪改你的檔案。

### 重要:一鍵修復按鈕沒反應 / 失敗?

修復按鈕需要透過「開始體檢」打開的網頁、且程式視窗仍開著才能運作。若按了沒反應或失敗,通常是:

1. **直接雙擊 `report/index.html` 開檔**(網址是 `file://…`)——這樣沒有連到程式,修復不會動。請改從「開始體檢」自動打開的網頁(網址列是 `127.0.0.1:8788`)操作。
2. **把黑色「開始體檢」視窗關掉了**——程式停止,修復就連不上。請重新雙擊「開始體檢」,再從它打開的網頁操作。

報告偵測到這情況時,會在最上方顯示黃色提示說明該怎麼做。(純看報告不受影響,只有「修復」需要程式在跑。)

## 快速開始(進階 / 開發者)

```bash
# 一鍵跑完整流程(診斷 → 產生報告)
bash run.sh

# 跑完直接開報告(純檢視)
bash run.sh --open

# 跑完並啟動修復伺服器(報告上的「修復」按鈕才會生效)
bash run.sh --serve
```

手動分步:

```bash
bash diagnose.sh          # 1) 收集九模組資料 → report/data/*.json
python3 generate_report.py # 2) 產生 report/index.html
open report/index.html     # 3) 純檢視
python3 repair_server.py   # 4)(選用)啟動修復伺服器 http://127.0.0.1:8787
```

> 第一次會自動安裝 `fdupes`(若未裝)。M3 全碟掃描最慢,整體約數分鐘。

## 檔案

| 檔案 | 用途 |
|---|---|
| `run.sh` | 標準入口,串起診斷→產報告(→可選修復伺服器) |
| `diagnose.sh` | 九模組唯讀收集,寫入 `report/data/m{1..9}_*.json` |
| `generate_report.py` | 讀 JSON,產出 `report/index.html`(含修復規則表) |
| `repair_server.py` | 本機白名單修復 API(僅 127.0.0.1 + token) |
| `report/index.html` | 互動報告:摘要 + M1–M9 共 10 個分頁 |

## 九個診斷模組

| ID | 名稱 | 內容 |
|----|------|------|
| M1 | 重複檔案 | `fdupes` 找內容相同的檔案 |
| M2 | 孤兒/損壞 | 斷裂 symlink(分沙盒範本/App 鎖檔/真殘留三類)+ `brew doctor` |
| M3 | 大型檔案 | >100MB 檔案 Top 50,附白話用途說明 |
| M4 | 開發環境 | node/python/git… 版本 + brew/pip/npm 過時清單 |
| M5 | 可回收空間 | 各類快取/暫存可釋空間 |
| M6 | 電池 | 循環次數、最大容量、健康狀態 |
| M7 | 系統健康 | SMART、可用空間、記憶體壓力、swap、APFS 快照 |
| M8 | 登入與背景 | 登入項目、LaunchAgents/Daemons(標出第三方自啟) |
| M9 | 安全與更新 | FileVault / SIP / Gatekeeper / 防火牆 / 待安裝更新 |

## 修復:掃到什麼 → 產出對應修復

報告摘要頁有一張**修復規則表**(`generate_report.py` 內 `RULES`):依當次掃描結果,命中的問題才會在「需要你注意的事」長出對應按鈕(例:防火牆關才有開火牆鈕;pip 過舊才有更新 pip 鈕;都正常則按鈕自動消失)。可展開「修復涵蓋範圍」看全部 17 條規則與本次命中狀況。

修復伺服器白名單動作(13)、每個都在執行當下重新驗證現況:

`fix_path` · `brew_cleanup` · `clear_caches` · `clean_stale_symlinks` · `fix_m2` · `enable_firewall` · `open_software_update` · `brew_upgrade` · `update_pip` · `update_npm` · `thin_snapshots` · `open_filevault_settings` · `enable_gatekeeper`

- 需密碼者(防火牆/Gatekeeper)會跳 macOS 原生授權視窗。
- 硬體類(電池老化、SMART 異常)與需重開機者(SIP)只警示、不一鍵。
- 刪重複檔、停用自啟項目刻意不做一鍵 —— 導引到對應分頁由你判斷。

## 開發須知

- 改 `diagnose.sh` 後務必 `bash run.sh` 完整跑一次驗證(`set -euo pipefail` 下,任一模組的 python 例外會中止整支)。
- **資料契約**:`diagnose.sh` 產出的 JSON 欄位要對齊 `generate_report.py` 讀取的欄位;改一邊就兩邊一起改。
- 新增一種修復 = 加 1 條 `RULES`(generate_report.py)+ 1 個白名單動作(repair_server.py),並確保兩邊 action id 一致。
- 更多判讀經驗見 `.claude/skills/laptop-diagnostics/SKILL.md`。
