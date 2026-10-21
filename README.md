# MacVitals(laptop-diagnostics)

> **命名**:MacVitals 是產品名(介面、報告、使用手冊都用這個名字);`laptop-diagnostics` 是 GitHub repo、資料夾與 Claude Code skill 的名稱——兩者是同一個專案。

對本機 macOS 執行**十一維度唯讀診斷**,產出單檔互動式報告 `report/index.html`;並可選擇性啟動本機**一鍵修復伺服器**,讓報告上的按鈕直接執行白名單修復。

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
python3 -m macvitals.collect              # 1) 收集十一模組資料 → report/data/*.json(bash diagnose.sh 等價,只多 banner)
python3 -m macvitals.collect --only m2 m7 #    只重跑指定模組,其餘模組的 JSON 不動;--list 列出模組
python3 generate_report.py                # 2) 產生 report/index.html
open report/index.html                    # 3) 純檢視
python3 repair_server.py                  # 4)(選用)啟動修復伺服器 http://127.0.0.1:8787
```

> 不需安裝額外工具,Apple 內建的 python3 即可。M1 重複檔比對與 M3 全碟掃描最慢(已和 M9 並行),整體約數分鐘。
> 任一模組失敗不會中止整個掃描:該模組的 JSON 會寫入 `error`,報告對應分頁顯示「此模組收集失敗」,其餘模組照常。

## 檔案

| 檔案 | 用途 |
|---|---|
| `run.sh` | 標準入口,串起診斷→產報告(→可選修復伺服器) |
| `macvitals/` | 收集套件:`collect.py` 入口(逐模組隔離、`--only`、`progress.json`、M1/M3/M9 並行)+ `modules/m01_dupes.py` … `m11_sharing.py`(每模組 `collect() -> dict`)+ `modules/base.py` 共用工具 |
| `diagnose.sh` | `python3 -m macvitals.collect` 的薄殼(banner + 顏色 log + 轉傳參數),寫入 `report/data/m{1..11}_*.json` |
| `m1_dupes.py` | M1 重複檔比對(純 Python:大小分桶 → 前 64 KB hash → 全檔 hash);`macvitals/modules/m01_dupes.py` 直接包它 |
| `generate_report.py` | 讀 JSON,產出 `report/index.html`(含修復規則表) |
| `repair_server.py` | 本機白名單修復 API(僅 127.0.0.1 + token) |
| `report/index.html` | 互動報告:摘要 + M1–M11 共 12 個分頁 |
| `tests/` | 單元測試(`python3 -m unittest discover -s tests -v`,純標準函式庫) |
| `.github/workflows/ci.yml` | CI:macos-latest + Python 3.9,跑測試、`bash -n diagnose.sh`、`--only m6 m7 m8 m9 m11` smoke 並產報告 |

## 十一個診斷模組

| ID | 名稱 | 內容 |
|----|------|------|
| M1 | 重複檔案 | 純 Python 逐位元組比對找內容相同的檔案(略過 symlink、hardlink 不重複計) |
| M2 | 孤兒/損壞 | 斷裂 symlink(分沙盒範本/App 鎖檔/真殘留三類)+ `brew doctor` |
| M3 | 大型檔案 | >100MB 檔案 Top 50,附白話用途說明 |
| M4 | 開發環境 | node/python/git… 版本 + brew/pip/npm 過時清單 |
| M5 | 可回收空間 | 各類快取/暫存可釋空間 |
| M6 | 電池 | 循環次數、最大容量、健康狀態 |
| M7 | 系統健康 | SMART、可用空間、記憶體壓力、swap、APFS 快照 |
| M8 | 登入與背景 | 登入項目、LaunchAgents/Daemons(標出第三方自啟) |
| M9 | 安全與更新 | FileVault / SIP / Gatekeeper / 防火牆 / 待安裝更新 |
| M10 | 近期當機 | 近 7/30 天 App 閃退與核心崩潰(kernel panic)次數、最常當機的 App |
| M11 | 分享與遠端存取 | 遠端登入(SSH)/ 螢幕共享 / 檔案分享等對外服務、開放埠、自動登入 |

## 修復:掃到什麼 → 產出對應修復

報告摘要頁有一張**修復規則表**(`generate_report.py` 內 `RULES`):依當次掃描結果,命中的問題才會在「需要你注意的事」長出對應按鈕(例:防火牆關才有開火牆鈕;pip 過舊才有更新 pip 鈕;都正常則按鈕自動消失)。可展開「修復涵蓋範圍」看全部 27 條規則(其中 13 種可一鍵修復)與本次命中狀況。

修復伺服器白名單動作(15)、每個都在執行當下重新驗證現況:

`fix_path` · `brew_cleanup` · `clear_caches` · `clean_stale_symlinks` · `fix_m2` · `enable_firewall` · `open_software_update` · `brew_upgrade` · `update_pip` · `update_npm` · `thin_snapshots` · `open_filevault_settings` · `enable_gatekeeper` · `disable_remote_login` · `disable_screen_sharing`

- `fix_m2` 是複合動作:依序執行 `clean_stale_symlinks` 與 `fix_path`。
- 需密碼者(防火牆/Gatekeeper)會跳 macOS 原生授權視窗。
- M11 對外服務(遠端登入 SSH、螢幕共享)若開著,可一鍵關閉以縮小攻擊面。
- 硬體類(電池老化、SMART 異常)與需重開機者(SIP)只警示、不一鍵。
- 刪重複檔、停用自啟項目刻意不做一鍵 —— 導引到對應分頁由你判斷。

## 開發須知

- 收集邏輯在 `macvitals/modules/mNN_*.py`,每個模組一支檔、`collect() -> dict`。改完先跑測試,再 `python3 -m macvitals.collect --only <該模組> && python3 generate_report.py` 看報告;合併前 `bash run.sh` 完整跑一次。
- **單一模組失敗不會中止掃描**:`macvitals.collect` 對每個模組 try/except,失敗只在該模組 JSON 寫 `error` 欄位、exit code 仍為 0;報告把該分頁與摘要卡標成「此模組收集失敗」、規則視為未命中。模組內遇到指令缺失/逾時請回傳字串資料(`base.run()` 已處理),真的異常就讓例外拋出,別吞成空資料。
- **資料契約**:模組 JSON 的欄位名稱與結構要對齊 `generate_report.py` 讀取的欄位(以及 `tests/` 的 fixture);改一邊就兩邊一起改。
- 新增一種修復 = 加 1 條 `RULES`(generate_report.py)+ 1 個白名單動作(repair_server.py),並確保兩邊 action id 一致。
- 改了規則(`RULES`)或白名單動作(`ACTIONS`)後,跑 `python3 scripts/check_doc_counts.py`:它以程式碼為準,檢查 README / CLAUDE.md / SKILL.md / run.sh 裡寫的規則數、動作數、模組數是否一致(`tests/test_doc_counts.py` 也會跑它)。
- 掃描資料(檔名、指令輸出)一律當資料處理:bytes → `decode("utf-8", "replace")`、subprocess list、固定指令字串;**不要內插進 Python 原始碼或 shell 字串**(檔名含 `\N`、`"""` 曾讓整支中止,且可注入程式碼)。
- **Python 3.9 相容、只用標準函式庫**(Apple 內建 python3 就能跑):不用 `match`、不用 `X | Y` 型別語法、不加第三方套件。
- 收集階段絕對唯讀:`macvitals.collect` 唯一會寫的是 `report/data/`(或 `--data-dir` 指定目錄)。
- `generate_report.py` 裡所有來自掃描資料的字串(檔名、指令輸出、程序名…)放進 HTML 前都要經過 `e()`(html.escape)。
- 測試:`python3 -m unittest discover -s tests -v`(純標準函式庫,不需安裝任何套件;會掃磁碟的模組在測試裡被換成假的,不會跑全碟掃描)。CI 在 `.github/workflows/ci.yml`。
- 更多判讀經驗見 `.claude/skills/laptop-diagnostics/SKILL.md`。

## 重建手冊

`MacVitals 使用手冊（白話版）.docx`(封面「版本 1.3 · 2026-06-25」)由 `build_manual.js` 以 [`docx`](https://www.npmjs.com/package/docx) 套件產生(需要 Node.js)。腳本的內文與結構已與 repo 內已提交的這份 .docx 逐段對齊:用同一組截圖重建,`document.xml`、樣式、編號、頁尾等各部分與已提交檔**逐位元組相同**(僅 `docProps/core.xml` 的建立時間不同)。`docx` 套件版本固定為 `9.7.2`(9.6.0–9.7.2 的輸出相同,9.8 起的 XML 細節不同),請勿隨意升版。

```bash
npm install
npm run build:manual
```

預設輸出是目前資料夾下**同名**的 `MacVitals 使用手冊（白話版）.docx`,會直接覆蓋。想先看結果、不動已提交的檔案,可指定輸出路徑:`node build_manual.js /tmp/manual-check.docx`。改手冊內文就改 `build_manual.js` 裡的字串;改版時記得同步更新檔內的 `VERSION`(封面版本與日期)。

### 需要的 4 張截圖

腳本會讀 `manual_assets/` 內的 4 張截圖。這個資料夾已被 `.gitignore` 排除、**不入版控**(.docx 內的截圖已是去敏示範資料;自行重新截圖時請留意別帶進本機的彙總數據);缺任何一張,腳本會直接提示並結束。

| 檔案 | 內容 | 手冊中的位置 |
|---|---|---|
| `manual_assets/01_landing.png` | 首頁(「開始體檢」按鈕) | 封面、「四、怎麼使用」步驟 2(同一張用兩次) |
| `manual_assets/02_progress.png` | 掃描進行中的進度條 | 「四、怎麼使用」步驟 3 |
| `manual_assets/03_report_summary.png` | 報告摘要:十一個面向一覽(去敏示範資料) | 「五、報告怎麼看」 |
| `manual_assets/04_attention.png` | 「需要你注意的事」與右側修復按鈕(去敏示範資料) | 「六、一鍵修復怎麼用」 |

最簡單的取得方式,是直接從已提交的 .docx 把這 4 張解出來(.docx 內的圖片檔名就是內容雜湊,固定不變):

```bash
mkdir -p manual_assets
D="MacVitals 使用手冊（白話版）.docx"
unzip -p "$D" word/media/8bb2f3c0d55a1c92843129563fcbe658643dcbd4.png > manual_assets/01_landing.png
unzip -p "$D" word/media/179a69fa85bec0193d56ec03b0a9a8965f1301b6.png > manual_assets/02_progress.png
unzip -p "$D" word/media/b9d51be14810878f05a12952c83ec337e10d27c0.png > manual_assets/03_report_summary.png
unzip -p "$D" word/media/92f594428898f9e9d43a013f8f1b97f2d6367f29.png > manual_assets/04_attention.png
```

要換成新的截圖也行:同樣用這 4 個檔名放進 `manual_assets/` 即可,圖片寬度固定、高度依實際長寬比自動換算。

`laptop-diagnostics 技術實作手冊.docx` 沒有建置腳本,是手工維護的。

## 授權

MIT,見 [LICENSE](LICENSE)。
