# Laptop Diagnostics — Claude Code 任務說明

## 目標
對本機 macOS 執行十一模組唯讀診斷，最終輸出 `report/index.html` 互動式報告。

## 安全邊界（硬性限制）
- **預設唯讀；診斷收集階段絕不刪除、移動、修改任何使用者檔案**
- 所有收集操作僅限 `find`（read-only）、Python 唯讀 hash 比對（`m1_dupes.py`）、`brew`（read-only subcommands）、`md5` / `shasum`
- **修復動作（刪 symlink、改 `~/.bash_profile`、`brew upgrade` 等）必須先逐項列出、取得使用者明確授權後才執行**；不得在授權範圍外動任何真實檔案
- 若遇到需要 `sudo` 的指令，記錄「權限不足，跳過」，繼續下一步
- 暫存資料寫入 `report/data/` 目錄，不寫到系統路徑（收集套件 `macvitals.collect` 唯一會寫的就是 `--data-dir`，預設 `report/data/`）

## 執行順序
- **非技術使用者入口:雙擊 `開始體檢.command`** → 啟動 `app_server.py`(**唯一的本機伺服器**,127.0.0.1:8788)→ 瀏覽器首頁按「開始體檢」→ 背景跑掃描+顯示進度 → 完成自動跳報告 → 報告內一鍵修復。打包用 `bash package.sh`(產出 `laptop-diagnostics-portable.zip`,**排除個人掃描資料**)。
- **標準入口(開發/CLI,確保一致性)：`bash run.sh`**(= diagnose.sh → generate_report.py;`--serve` 連同啟動同一支本機伺服器 `app_server.py --report` 並直接開報告頁、`--open` 開純檢視報告)。
- 手動分步:
  1. 不需安裝額外工具(M1 為純 Python 比對,不依賴 `fdupes`;整個收集套件只用標準函式庫,Apple 內建 python3 3.9 即可)
  2. `python3 -m macvitals.collect`(十一模組唯讀收集 → `report/data/*.json`;`bash diagnose.sh` 是它的薄殼,只多 banner 與顏色 log)
     - 只重跑某幾個模組:`python3 -m macvitals.collect --only m2 m7`(其餘模組的 JSON 不動);`--list` 列出模組
     - 任一模組拋例外 → 只在該模組 JSON 寫 `{"module","scan_time","error"}`,其餘模組照跑、exit code 仍為 0
     - M1 / M3 / M9 最慢且互相獨立,並行;其餘依序。進度持續寫 `report/data/progress.json`
  3. `python3 generate_report.py` 生成 `report/index.html`(含 `error` 的模組:該分頁與摘要卡顯示「此模組收集失敗:…」,規則表對它視為未命中)
  4. 完成後回報十一模組摘要數字
  5.(選用)`python3 app_server.py --report` 啟動本機伺服器(127.0.0.1:8788,與「開始體檢」是同一支)並直接開報告頁,讓摘要頁「修復」按鈕能一鍵執行白名單修復;不啟動則為純唯讀檢視
- **一致性守則:改動 `macvitals/modules/*.py` 後,先 `python3 -m unittest discover -s tests -v`,再至少 `python3 -m macvitals.collect --only <該模組> && python3 generate_report.py` 看報告;改到 JSON 欄位就是改資料契約,`generate_report.py`(與 `tests/` fixture)要同步改。合併前以 `bash run.sh` 完整跑一次。**
- 報告摘要頁版面固定順序:頁面說明 → 全部檢查模組一覽 → 整體判讀 → 需要你注意的事 → 運作良好的部分 → 修復涵蓋範圍。

## 本機伺服器(app_server.py)+ 一鍵修復白名單(repair_server.py)+ 規則登錄表
- **只有一支本機伺服器 `app_server.py`**(127.0.0.1:8788,被占用就往後找空埠;`--port` 可改起始埠):同時提供首頁 `/`(開始體檢)、`POST /api/scan` + `GET /api/scan/status`(背景掃描與進度)、`/report`(報告,注入修復 token;沒有報告 → 302 到 `/`)、`/api/ping`、`POST /api/fix`。一套 `Handler`、一套守衛。啟動時先打 `/api/ping` 偵測同埠是否已有 MacVitals(有就只開瀏覽器不重複啟動);`DIAG_NO_BROWSER=1` 不自動開瀏覽器。
- `repair_server.py` **不再自己起 HTTP**,是純函式庫:白名單 `ACTIONS`(頂層 dict,`scripts/check_doc_counts.py` 用 ast 數它)、`host_allowed`/`origin_allowed`/`SECURITY_HEADERS`、`sh()`。`python3 repair_server.py` 會轉呼叫 `app_server.main(["--report"])`。
- **修復計畫由掃描結果動態產生**：`generate_report.py` 內有「規則登錄表 `RULES`」，每條 = `applies(掃描資料)→bool` ＋ 嚴重度 ＋ 對應 `action`。報告產生時逐條套用當次掃描,命中才長出按鈕(例:防火牆關才有開火牆鈕、pip 過舊才有更新 pip 鈕、brew 全最新則升級鈕自動消失)。新增一種修復 = 加一條規則 + 一個伺服器動作。
- 靜態 HTML 無法直接執行修復，故本機伺服器提供白名單 API(`app_server.py` 的 `POST /api/fix`,動作定義在 `repair_server.py` 的 `ACTIONS`)；按鈕按下 → confirm → POST `/api/fix` → 伺服器端**在執行當下重新驗證現況**後才執行(不吃報告快照,故舊報告頂多「無事可做」不會誤動)。
- 白名單動作（15）：`fix_path`/`brew_cleanup`/`clear_caches`/`clean_stale_symlinks`/`fix_m2`/`enable_firewall`/`open_software_update`/`brew_upgrade`/`update_pip`/`update_npm`/`thin_snapshots`/`open_filevault_settings`/`enable_gatekeeper`/`disable_remote_login`/`disable_screen_sharing`。
- 覆蓋:規則表 27 條(其中 13 種可一鍵修復),涵蓋 M1–M11 各模組的可行動發現;健康/正常項目不觸發(掃到才出對應修復)。硬體類(電池老化、SMART 異常)、需重開機者(SIP)、當機/panic/高 CPU(只警示避免誤刪 App、誤殺執行中程序)與其他分享服務只導引、不一鍵;分享服務僅可逆的螢幕共享/遠端登入提供一鍵(port-probe 重驗 + `osascript ... with administrator privileges`)。
- 安全：僅綁 `127.0.0.1`;每個請求的 `Host` 必須是本機(擋 DNS rebinding)、POST 的 `Origin`/`Sec-Fetch-Site` 必須是本機(擋跨站 POST);POST 再比對啟動時隨機 token;每個回應帶 `SECURITY_HEADERS`(nosniff、no-referrer、no-store、CSP 只允許本機頁面 iframe);只允許白名單；需權限者（防火牆）用 `osascript ... with administrator privileges` 跳原生授權；`update_pip` 只升 pip 本身且 `--user`，不動系統 Python；不做需重啟的系統更新（只開設定頁）。

## 模組定義
每個模組一支檔(`macvitals/modules/mNN_*.py`),提供 `MODULE`/`FILENAME`/`LABEL`/`START_MSG`、`collect() -> dict`、`summary(result) -> str`;`macvitals/collect.py` 的 `MODULES` 是固定順序的登錄表。

| ID | 名稱 | 套件模組 | 核心做法 |
|----|------|----------|----------|
| M1 | 重複檔案 | `m01_dupes.py` → 根目錄 `m1_dupes.build_result()` | 純 Python:大小分桶 → 前 64 KB hash → 全檔 hash;略過 symlink、hardlink 不重複計(**並行群組**) |
| M2 | 孤兒/損壞項目 | `m02_broken.py` | `find -L ~ … -type l -print0`(broken symlinks,bytes 解析)+ `brew doctor`,三分類 |
| M3 | 大型檔案 Top 50 | `m03_large.py` | `os.walk('/')` 剪枝 /System /private/var /Volumes,≥100 MB(**並行群組**) |
| M4 | 開發環境健檢 | `m04_env.py` | `node -v`, `npm doctor`, `python3 --version`, `brew list --versions`, `brew outdated`, `pip3 list --outdated`, `npm outdated -g` |
| M5 | 可回收空間 | `m05_reclaimable.py` | `du -sk` 各類快取/Trash/iOS 備份/DerivedData |
| M6 | 電池與電源健康 | `m06_battery.py` | `system_profiler SPPowerDataType` |
| M7 | 系統健康 | `m07_system.py` | `diskutil info /`(SMART)、`memory_pressure`、`sysctl vm.swapusage`、`tmutil listlocalsnapshots /`、`ps` 即時資源 Top |
| M8 | 登入與背景項目 | `m08_startup.py` | `~/Library/LaunchAgents`、`/Library/Launch{Agents,Daemons}`、登入項目(osascript) |
| M9 | 安全與更新狀態 | `m09_security.py` | `fdesetup status`、`csrutil status`、`spctl --status`、`socketfilterfw --getglobalstate`、`softwareupdate -l`、`systemextensionsctl list`(**並行群組**) |
| M10 | 近期當機與診斷報告 | `m10_crashes.py` | 掃 `~/Library/Logs/DiagnosticReports` + `/Library/Logs/DiagnosticReports`(`.crash`/`.ips`/`.panic`/`.spin`/`.hang`/`.diag`),依 App 聚合近 30/7 天、標 kernel panic |
| M11 | 分享與遠端存取 | `m11_sharing.py` | 對 localhost 探聽通訊埠(22 SSH/5900 VNC/445 SMB/548 AFP/3283 ARD,`socket`)+ `autoLoginUser` + Tailscale + `lsof` 非 loopback 監聽;**勿用 `launchctl list` 判服務開關(假陽性)** |

共用工具在 `macvitals/modules/base.py`:`run(cmd, timeout, merge_stderr, strip, error_value)`、`now_iso()`、`write_json(path, obj)`(utf-8、`ensure_ascii=False`、先寫暫存檔再 `os.replace`)。

> M7 另含即時資源 Top（`ps -arcwwwxo`/`-amcwwwxo`，CPU/記憶體前段快照）。

## 輸出規格
- `report/data/m1_dupes.json`
- `report/data/m2_broken.json`（含 `categories` 三分類與 `stale_symlinks` 真殘留清單）
- `report/data/m3_large.json`
- `report/data/m4_env.json`
- `report/data/m5_reclaimable.json`、`m6_battery.json`、`m7_system.json`（含 `top_cpu`/`top_mem`/`top_cpu_max`）、`m8_startup.json`、`m9_security.json`（含 `system_extensions`）
- `report/data/m10_crashes.json`（依 App 聚合 `apps`、近 30/7 天計數、`panic_count_30d`、`recent`）
- `report/data/m11_sharing.json`（`services` 各服務 port/state、`open_count`、`auto_login`）
- `report/data/progress.json`（收集進度:`step`/`message`/`pct`/`done`/`running`/`failed`/`pending`/`timings`/`finished`;`app_server.py` 讀它畫進度條,不再猜 log 行）
- 模組收集失敗時,該模組的 JSON 只有 `{"module": "M3", "scan_time": "…", "error": "<例外類型>: <訊息>"}`;`generate_report.py` 以 `error` 欄位為判斷依據
- `report/index.html`（互動式，含 12 個分頁(摘要 + M1–M11)、篩選器、可釋空間加總）

## 經驗與判讀（重要，詳見 `.claude/skills/laptop-diagnostics/SKILL.md`）
- **M2 斷裂 symlink 約 99.7% 是正常的**，務必分三類，只有 `stale` 需處理：
  - `sandbox_template`（路徑含 `/Library/Containers/`）：macOS 沙盒容器範本，系統自動維護 → 勿動
  - `app_lock`（`SingletonLock`/`SingletonCookie`/`SingletonSocket`/`RunningChromeVersion`/`.lock`）：App 執行鎖 → 勿動
  - `stale`（其餘）：指向已刪目標的真殘留 → 可在授權下清理（刪前雙重確認 `islink` 且目標不存在，只 `unlink` 連結本身）
- **`brew doctor` 多為 PATH 設定問題**（非壞檔）；修 `~/.bash_profile` 後須以 `bash -lc 'brew doctor'` 驗證（非 login shell 不讀 profile，會誤報）。
- **套件結構**:`macvitals/collect.py`(入口:逐模組 try/except 隔離、`--only`、`progress.json`、M1/M3/M9 `ThreadPoolExecutor` 並行)→ `macvitals/modules/mNN_*.py`(每模組 `collect() -> dict`、`summary(result)`)→ `macvitals/modules/base.py`(`run()`/`now_iso()`/`write_json()`)。`diagnose.sh` 只是薄殼,`run.sh`/`開始體檢.command`/`app_server.py` 照常呼叫它。
- **模組失敗語意**:模組內「指令不存在/逾時」由 `base.run()` 回傳字串(`"error: …"` 或 `""`),那是正常資料、規則表照判;只有真的拋例外才是模組失敗 → 收集端寫 `error` 欄位、報告標示、規則視為未命中。**不要在模組裡用大 try/except 把例外吞成空資料**,那會讓報告把「沒掃到」當成「沒問題」。
- **掃描資料絕不內插進程式碼或 shell 字串**:檔名一律走 bytes → `decode("utf-8", "replace")`(M2 `find -print0`、M1/M3 `os.fsencode`)、指令用 subprocess list 或固定字串(舊版曾把 `find` 結果塞進 heredoc 原始碼,檔名含 `\N` 就 SyntaxError 整支中止,且可被構造檔名注入)。
- **M7 的即時資源 Top 必須在並行群組之後才跑**(collect.py 的順序刻意如此),否則快照會把掃描本身(python3/find 高 CPU)誤報成「程序高 CPU 占用」。
- **Python 3.9 相容、只用標準函式庫**:不用 `match`、不用 `X | Y` 型別語法、不加第三方套件(Apple 內建 python3 就能跑)。CI(`.github/workflows/ci.yml`:macos-latest、`setup-python` 鎖 3.9)跑單元測試、`bash -n diagnose.sh`、`python3 -m macvitals.collect --only m6 m7 m8 m9 m11 && python3 generate_report.py` smoke。
- **報告 HTML 跳脫**：`generate_report.py` 所有掃描資料字串都要過 `e()`（html.escape）。報告由本機伺服器提供且含修復 token，未跳脫的檔名可注入 script 直接呼叫 `/api/fix`。
- **測試**：`python3 -m unittest discover -s tests -v`（純標準函式庫;`test_p0.py` P0 回歸、`test_collect.py` 收集隔離/`--only`/並行/進度檔/報告對失敗模組的呈現、`test_server.py` 單一伺服器同時回 `/`、`/api/scan/status`、`/report`、`/api/fix` 與外來 Host/Origin 403、`repair_server.py` 只是函式庫、`python3 repair_server.py` 轉呼叫 `app_server`。會掃磁碟的模組在測試裡以 `unittest.mock` 換成假 `collect()`,不會真的全碟掃描）。
- **效能**：M1 / M3 全碟掃描最慢(已與 M9 並行)；要單獨刷新某模組用 `python3 -m macvitals.collect --only mN`，別為了刷新而重跑整支。
- **M4 版本**：brew 管理者以 `brew outdated` 為準；系統工具（Apple python3 3.9 / 系統 ruby 2.6 / Apple git）由 macOS 控管，不單獨升，開發改用 brew 版。node 大版本升級前先 `npm ls -g` 快照全域套件。
