#!/usr/bin/env python3
"""
macvitals.collect — 十一模組唯讀收集的入口(取代 diagnose.sh 裡的 python heredoc)。

用法:
  python3 -m macvitals.collect                  # 全部 11 模組 → report/data/m{1..11}_*.json
  python3 -m macvitals.collect --only m2 m7     # 只重跑指定模組(其餘模組的 JSON 不動)
  python3 -m macvitals.collect --list           # 列出模組 id / 檔名
  python3 -m macvitals.collect --data-dir DIR   # 輸出目錄(預設 report/data;環境變數 MACVITALS_DATA_DIR 亦可)
  python3 -m macvitals.collect --no-parallel    # M1/M3/M9 也改依序跑(除錯用)

行為:
  - 每個模組各自 try/except:失敗就把 {"module","error","scan_time"} 寫進該模組的 JSON,
    繼續跑其餘模組;整支程序的 exit code 仍為 0(只有用法錯誤 / 無法建立輸出目錄才非 0)。
  - M1、M3、M9 最慢且互相獨立 → ThreadPoolExecutor 並行;其餘模組在它們之後依序跑
    (M7 的「即時資源 Top」快照才不會被掃描本身的 CPU 污染)。
  - 全程持續更新 report/data/progress.json({"step","pct","done",...})供 app_server.py 顯示進度。
  - 收集階段絕對唯讀:唯一寫入的是 --data-dir 底下的 JSON。
"""
import argparse
import os
import sys
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, wait

from .modules import (m01_dupes, m02_broken, m03_large, m04_env, m05_reclaimable, m06_battery,
                      m07_system, m08_startup, m09_security, m10_crashes, m11_sharing)
from .modules.base import now_iso, write_json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DATA_DIR = os.path.join(ROOT, "report", "data")
PROGRESS_FILENAME = "progress.json"

# 固定順序 = 報告分頁順序;id 字串("M1"…)與 JSON 檔名是資料契約
MODULES = [m01_dupes, m02_broken, m03_large, m04_env, m05_reclaimable, m06_battery,
           m07_system, m08_startup, m09_security, m10_crashes, m11_sharing]
BY_ID = {m.MODULE: m for m in MODULES}
PARALLEL = ("M1", "M3", "M9")           # 最慢且互相獨立
WEIGHTS = {"M1": 3, "M3": 3, "M9": 2}   # 進度百分比的權重(其餘 1),讓進度條貼近真實耗時


# ── 終端 log(沿用 diagnose.sh 的 [INFO]/[OK]/[ERR] 風格與顏色) ────────────
class Log:
    def __init__(self, stream=None, color=None):
        self.stream = stream or sys.stdout
        if color is None:
            color = hasattr(self.stream, "isatty") and self.stream.isatty() and not os.environ.get("NO_COLOR")
        self.color = color
        self.lock = threading.Lock()

    def _c(self, code, text):
        return "\033[{}m{}\033[0m".format(code, text) if self.color else text

    def _emit(self, line):
        with self.lock:
            self.stream.write(line + "\n")
            self.stream.flush()

    def info(self, msg): self._emit(self._c("0;36", "[INFO]") + " " + msg)
    def ok(self, msg):   self._emit(self._c("0;32", "[OK]") + "   " + msg)
    def warn(self, msg): self._emit(self._c("1;33", "[WARN]") + " " + msg)
    def err(self, msg):  self._emit(self._c("0;31", "[ERR]") + "  " + msg)
    def plain(self, msg): self._emit(msg)


# ── 進度檔 ──────────────────────────────────────────────────────────────
class Progress:
    """report/data/progress.json 的單一寫入者(執行緒安全)。

    格式:{"step": "M3", "message": "...", "pct": 40, "done": [...], "running": [...],
          "failed": [...], "pending": [...], "timings": {"M1": 12.3}, "total": 11,
          "started": iso, "updated": iso, "finished": false}
    """
    def __init__(self, path, module_ids):
        self.path = path
        self.ids = list(module_ids)
        self.done = []
        self.failed = []
        self.running = []
        self.timings = {}
        self.finished = False
        self.started = now_iso()
        self.lock = threading.Lock()
        self.total_w = sum(WEIGHTS.get(i, 1) for i in self.ids) or 1

    def _label(self, mid):
        m = BY_ID.get(mid)
        return "{} {}".format(mid, m.LABEL) if m else mid

    def snapshot(self):
        done_w = sum(WEIGHTS.get(i, 1) for i in self.done)
        pct = 100 if self.finished else int(100 * done_w / self.total_w)
        pending = [i for i in self.ids if i not in self.done and i not in self.running]
        if self.finished:
            step, message = "done", "收集完成"
            if self.failed:
                message += "(失敗:{})".format("、".join(self.failed))
        elif self.running:
            step = self.running[0]
            message = "、".join(self._label(i) for i in self.running) + " 掃描中…(已完成 {}/{})".format(
                len(self.done), len(self.ids))
        else:
            step, message = (self.done[-1] if self.done else ""), "準備中…"
        return {
            "step": step, "message": message, "pct": pct,
            "done": list(self.done), "running": list(self.running), "failed": list(self.failed),
            "pending": pending, "timings": dict(self.timings), "total": len(self.ids),
            "started": self.started, "updated": now_iso(), "finished": self.finished,
        }

    def write(self):
        try:
            write_json(self.path, self.snapshot())
        except Exception:
            pass   # 進度檔只是輔助顯示,寫不進去不該影響收集

    def start(self, mid):
        with self.lock:
            self.running.append(mid)
            self.write()

    def finish(self, mid, ok, seconds):
        with self.lock:
            if mid in self.running:
                self.running.remove(mid)
            self.done.append(mid)
            if not ok:
                self.failed.append(mid)
            self.timings[mid] = round(seconds, 1)
            self.write()

    def complete(self):
        with self.lock:
            self.finished = True
            self.write()


# ── 單一模組 ────────────────────────────────────────────────────────────
def run_module(mod, data_dir, progress, log):
    """跑一個模組並寫 JSON。任何例外 → 寫錯誤標記、回傳 False;永不向上拋(其餘模組照跑)。"""
    path = os.path.join(data_dir, mod.FILENAME)
    log.info(mod.START_MSG)
    progress.start(mod.MODULE)
    t0 = time.monotonic()
    ok = True
    try:
        result = mod.collect()
        write_json(path, result)
        secs = time.monotonic() - t0
        log.ok("{} 完成 → {}({:.1f}s)".format(mod.MODULE, path, secs))
        try:
            log.plain(mod.summary(result))
        except Exception:
            pass
    except Exception as exc:
        ok = False
        secs = time.monotonic() - t0
        msg = "{}: {}".format(type(exc).__name__, exc)
        log.err("{} 收集失敗:{}(已寫入錯誤標記,繼續其餘模組)".format(mod.MODULE, msg))
        sys.stderr.write(traceback.format_exc())
        sys.stderr.flush()
        try:
            write_json(path, {"module": mod.MODULE, "scan_time": now_iso(), "error": msg})
        except Exception as exc2:
            log.err("{} 連錯誤標記都寫不進 {}:{}".format(mod.MODULE, path, exc2))
    progress.finish(mod.MODULE, ok, secs)
    return ok


# ── 參數 ────────────────────────────────────────────────────────────────
def normalize_id(s):
    """'m3' / 'M3' / '3' / 'm03' → 'M3';無法解析回 None。"""
    t = str(s).strip().lower()
    if t.startswith("m"):
        t = t[1:]
    if not t.isdigit():
        return None
    return "M{}".format(int(t))


def resolve_modules(only, log):
    """--only 的 id 清單 → 模組物件(依固定順序去重)。未知 id 警告後略過。"""
    if not only:
        return list(MODULES)
    wanted = []
    for raw in only:
        mid = normalize_id(raw)
        if mid is None or mid not in BY_ID:
            log.warn("未知模組 id:{}(可用:{}),略過".format(raw, " ".join(m.lower() for m in BY_ID)))
            continue
        if mid not in wanted:
            wanted.append(mid)
    return [m for m in MODULES if m.MODULE in wanted]


def build_parser():
    p = argparse.ArgumentParser(prog="python3 -m macvitals.collect",
                                description="MacVitals 十一模組唯讀收集(每模組獨立 try/except,失敗不中止其餘)。")
    p.add_argument("--only", nargs="+", metavar="ID",
                   help="只跑指定模組,例如 --only m2 m7(其餘模組既有 JSON 不動)")
    p.add_argument("--data-dir", default=None,
                   help="輸出目錄(預設 report/data;亦可用環境變數 MACVITALS_DATA_DIR)")
    p.add_argument("--no-parallel", action="store_true", help="M1/M3/M9 也改依序執行")
    p.add_argument("--list", action="store_true", help="列出模組後結束")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    log = Log()

    if args.list:
        for m in MODULES:
            log.plain("{:<4} {:<22} {}".format(m.MODULE.lower(), m.FILENAME, m.LABEL))
        return 0

    selected = resolve_modules(args.only, log)
    if not selected:
        log.err("沒有可執行的模組(--only 指定的 id 全部無效)。")
        return 2

    data_dir = args.data_dir or os.environ.get("MACVITALS_DATA_DIR") or DEFAULT_DATA_DIR
    try:
        os.makedirs(data_dir, exist_ok=True)
    except OSError as exc:
        log.err("無法建立輸出目錄 {}:{}".format(data_dir, exc))
        return 1

    ids = [m.MODULE for m in selected]
    log.info("MacVitals 收集 {} 個模組({})→ {}".format(len(ids), "、".join(ids), data_dir))
    progress = Progress(os.path.join(data_dir, PROGRESS_FILENAME), ids)
    progress.write()

    par = [m for m in selected if m.MODULE in PARALLEL]
    seq = [m for m in selected if m.MODULE not in PARALLEL]
    if args.no_parallel or len(par) < 2:
        par, seq = [], list(selected)

    t_all = time.monotonic()
    executor = None
    try:
        if par:
            log.info("{} 互相獨立且最慢,並行執行…".format("、".join(m.MODULE for m in par)))
            executor = ThreadPoolExecutor(max_workers=len(par), thread_name_prefix="macvitals")
            futures = [executor.submit(run_module, m, data_dir, progress, log) for m in par]
            wait(futures)
            for f in futures:
                f.result()   # run_module 自己吞例外;這裡只會重新拋出真正意外的狀況
            executor.shutdown(wait=True)
            executor = None
        for m in seq:
            run_module(m, data_dir, progress, log)
    except KeyboardInterrupt:
        log.err("使用者中斷,停止收集。")
        if executor is not None:
            executor.shutdown(wait=False)
        progress.write()
        os._exit(130)   # 不等背景掃描執行緒結束
    progress.complete()

    total = time.monotonic() - t_all
    log.plain("")
    log.plain("  模組   狀態  耗時")
    for mid in ids:
        status = "失敗" if mid in progress.failed else "ok"
        log.plain("  {:<5}  {:<4}  {:>7.1f}s".format(mid, status, progress.timings.get(mid, 0.0)))
    log.plain("  合計 {:.1f}s".format(total))
    if progress.failed:
        log.warn("{} 個模組收集失敗({}),已在各自的 JSON 寫入 error 欄位;報告會標示,其餘模組不受影響。"
                 .format(len(progress.failed), "、".join(progress.failed)))
        log.warn("單獨重跑:python3 -m macvitals.collect --only {}".format(
            " ".join(m.lower() for m in progress.failed)))
    else:
        log.ok("全部模組收集完成。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
