#!/usr/bin/env python3
"""
macvitals.collect 回歸測試(純標準函式庫):python3 -m unittest discover -s tests -v

涵蓋:單一模組失敗不中止其餘模組(失敗模組 JSON 含 error、exit code 0)、--only 只寫指定檔案、
未知 id 的處理、M1/M3/M9 確實並行、progress.json 內容、CLI / 薄殼 diagnose.sh 端到端、
以及 generate_report.py 對含 error 的模組 JSON 的呈現(分頁 + 摘要卡 + 規則視為未命中)。

所有會碰磁碟的模組都用 unittest.mock 換成假 collect(),測試不會掃整顆硬碟。
"""
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from macvitals import collect as mc                                   # noqa: E402
from macvitals.modules import m01_dupes, m03_large, m09_security      # noqa: E402

EXPECTED_FILES = {
    "M1": "m1_dupes.json", "M2": "m2_broken.json", "M3": "m3_large.json", "M4": "m4_env.json",
    "M5": "m5_reclaimable.json", "M6": "m6_battery.json", "M7": "m7_system.json", "M8": "m8_startup.json",
    "M9": "m9_security.json", "M10": "m10_crashes.json", "M11": "m11_sharing.json",
}


def fake_collect(mod):
    def _collect(*a, **k):
        return {"module": mod.MODULE, "scan_time": "2026-01-01T00:00:00", "fake": True}
    return _collect


class FakeModules:
    """把每個模組的 collect() 換成假的;failing 指定的模組改成拋例外。"""
    def __init__(self, failing=(), overrides=None):
        self.failing = set(failing)
        self.overrides = overrides or {}
        self._patches = []

    def __enter__(self):
        for mod in mc.MODULES:
            if mod.MODULE in self.overrides:
                side = self.overrides[mod.MODULE]
            elif mod.MODULE in self.failing:
                side = mock.Mock(side_effect=RuntimeError("boom in " + mod.MODULE))
            else:
                side = fake_collect(mod)
            p = mock.patch.object(mod, "collect", side)
            p.start(); self._patches.append(p)
        return self

    def __exit__(self, *exc):
        for p in self._patches:
            p.stop()
        return False


def read(d, name):
    return json.loads((Path(d) / name).read_text(encoding="utf-8"))


_RealLog = mc.Log


@contextlib.contextmanager
def quiet():
    """把 collect 的終端 log 與失敗模組的 traceback 導到記憶體,測試輸出保持乾淨。"""
    with mock.patch.object(mc, "Log", lambda *a, **k: _RealLog(stream=io.StringIO(), color=False)), \
         contextlib.redirect_stderr(io.StringIO()):
        yield


class TestRegistry(unittest.TestCase):
    def test_module_ids_and_filenames_match_data_contract(self):
        self.assertEqual([m.MODULE for m in mc.MODULES], ["M%d" % i for i in range(1, 12)])
        self.assertEqual({m.MODULE: m.FILENAME for m in mc.MODULES}, EXPECTED_FILES)
        for m in mc.MODULES:
            self.assertTrue(callable(m.collect), m.MODULE)
            self.assertTrue(callable(m.summary), m.MODULE)
            self.assertTrue(m.START_MSG.startswith(m.MODULE + " "), m.START_MSG)

    def test_normalize_id(self):
        for raw, want in [("m3", "M3"), ("M3", "M3"), ("3", "M3"), ("m03", "M3"), ("M11", "M11"),
                          ("x", None), ("m", None), ("", None), ("m1x", None)]:
            self.assertEqual(mc.normalize_id(raw), want, raw)


class TestFailureIsolation(unittest.TestCase):
    def test_failed_module_writes_error_and_others_continue(self):
        with tempfile.TemporaryDirectory() as d, FakeModules(failing=["M3"]):
            with quiet():
                rc = mc.main(["--data-dir", d])
            self.assertEqual(rc, 0)   # 單一模組失敗,整支仍為 0
            for mid, name in EXPECTED_FILES.items():
                self.assertTrue((Path(d) / name).exists(), name)
                data = read(d, name)
                self.assertEqual(data["module"], mid)
                self.assertIn("scan_time", data)
                if mid == "M3":
                    self.assertIn("error", data)
                    self.assertIn("boom in M3", data["error"])
                    self.assertIn("RuntimeError", data["error"])
                    self.assertNotIn("fake", data)
                else:
                    self.assertNotIn("error", data)
                    self.assertTrue(data["fake"])
            prog = read(d, "progress.json")
            self.assertTrue(prog["finished"])
            self.assertEqual(prog["pct"], 100)
            self.assertEqual(prog["step"], "done")
            self.assertEqual(prog["failed"], ["M3"])
            self.assertEqual(sorted(prog["done"]), sorted(EXPECTED_FILES))
            self.assertEqual(prog["running"], [])
            self.assertEqual(prog["total"], 11)
            self.assertEqual(set(prog["timings"]), set(EXPECTED_FILES))

    def test_every_module_failing_still_exits_zero_and_writes_all_markers(self):
        with tempfile.TemporaryDirectory() as d, FakeModules(failing=EXPECTED_FILES):
            with quiet():
                rc = mc.main(["--data-dir", d, "--no-parallel"])
            self.assertEqual(rc, 0)
            for mid, name in EXPECTED_FILES.items():
                self.assertIn("error", read(d, name))
            self.assertEqual(sorted(read(d, "progress.json")["failed"]), sorted(EXPECTED_FILES))


class TestOnly(unittest.TestCase):
    def test_only_writes_just_the_requested_files(self):
        with tempfile.TemporaryDirectory() as d, FakeModules():
            with quiet():
                rc = mc.main(["--data-dir", d, "--only", "m2", "M7"])
            self.assertEqual(rc, 0)
            written = sorted(p.name for p in Path(d).iterdir())
            self.assertEqual(written, ["m2_broken.json", "m7_system.json", "progress.json"])
            prog = read(d, "progress.json")
            self.assertEqual(prog["done"], ["M2", "M7"])
            self.assertEqual(prog["total"], 2)

    def test_only_keeps_other_modules_existing_json_untouched(self):
        with tempfile.TemporaryDirectory() as d, FakeModules():
            (Path(d) / "m5_reclaimable.json").write_text('{"module":"M5","keep":1}', encoding="utf-8")
            with quiet():
                mc.main(["--data-dir", d, "--only", "m6"])
            self.assertEqual(read(d, "m5_reclaimable.json"), {"module": "M5", "keep": 1})
            self.assertTrue((Path(d) / "m6_battery.json").exists())

    def test_unknown_id_is_skipped_but_known_ones_still_run(self):
        with tempfile.TemporaryDirectory() as d, FakeModules():
            with quiet():
                rc = mc.main(["--data-dir", d, "--only", "m2", "m99"])
            self.assertEqual(rc, 0)
            self.assertTrue((Path(d) / "m2_broken.json").exists())
            self.assertEqual(read(d, "progress.json")["done"], ["M2"])

    def test_only_with_no_valid_id_is_a_usage_error(self):
        with tempfile.TemporaryDirectory() as d, FakeModules():
            with quiet():
                rc = mc.main(["--data-dir", d, "--only", "m99"])
            self.assertEqual(rc, 2)
            self.assertEqual(list(Path(d).iterdir()), [])

    def test_env_var_sets_default_data_dir(self):
        with tempfile.TemporaryDirectory() as d, FakeModules():
            with mock.patch.dict(os.environ, {"MACVITALS_DATA_DIR": d}), quiet():
                rc = mc.main(["--only", "m10"])
            self.assertEqual(rc, 0)
            self.assertTrue((Path(d) / "m10_crashes.json").exists())


class TestParallel(unittest.TestCase):
    def test_m1_m3_m9_run_concurrently(self):
        # 三個模組都在 Barrier 上等彼此;若是依序執行,Barrier 會逾時 → BrokenBarrierError → 模組被記為失敗
        barrier = threading.Barrier(3, timeout=5)
        def waiting(mod):
            def _c(*a, **k):
                barrier.wait()
                return {"module": mod.MODULE, "scan_time": "t", "parallel": True}
            return _c
        overrides = {"M1": waiting(m01_dupes), "M3": waiting(m03_large), "M9": waiting(m09_security)}
        with tempfile.TemporaryDirectory() as d, FakeModules(overrides=overrides):
            with quiet():
                rc = mc.main(["--data-dir", d, "--only", "m1", "m3", "m9", "m6"])
            self.assertEqual(rc, 0)
            for name in ("m1_dupes.json", "m3_large.json", "m9_security.json"):
                data = read(d, name)
                self.assertNotIn("error", data, data)
                self.assertTrue(data["parallel"])
            self.assertEqual(read(d, "progress.json")["failed"], [])

    def test_no_parallel_flag_runs_sequentially(self):
        barrier = threading.Barrier(3, timeout=0.5)
        def waiting(mod):
            def _c(*a, **k):
                barrier.wait()        # 依序執行時一定逾時 → 被記為失敗(證明旗標生效)
                return {"module": mod.MODULE, "scan_time": "t"}
            return _c
        overrides = {"M1": waiting(m01_dupes), "M3": waiting(m03_large), "M9": waiting(m09_security)}
        with tempfile.TemporaryDirectory() as d, FakeModules(overrides=overrides):
            with quiet():
                rc = mc.main(["--data-dir", d, "--only", "m1", "m3", "m9", "--no-parallel"])
            self.assertEqual(rc, 0)
            self.assertEqual(sorted(read(d, "progress.json")["failed"]), ["M1", "M3", "M9"])


class TestEndToEnd(unittest.TestCase):
    """真的跑一個便宜、純本機檔案系統的模組(M10),走 CLI 與薄殼 diagnose.sh。"""
    def test_cli_module_entry_point(self):
        with tempfile.TemporaryDirectory() as d:
            r = subprocess.run([sys.executable, "-m", "macvitals.collect", "--only", "m10", "--data-dir", d],
                               cwd=str(ROOT), capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            data = read(d, "m10_crashes.json")
            self.assertEqual(data["module"], "M10")
            for k in ("scan_time", "total_reports", "count_30d", "count_7d", "panic_count_30d", "apps", "recent"):
                self.assertIn(k, data)
            self.assertIn("M10 完成", r.stdout)

    def test_diagnose_sh_is_a_thin_wrapper_that_forwards_args(self):
        with tempfile.TemporaryDirectory() as d:
            r = subprocess.run(["bash", str(ROOT / "diagnose.sh"), "--only", "m10", "--data-dir", d],
                               cwd=str(ROOT), capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertTrue((Path(d) / "m10_crashes.json").exists())
            self.assertIn("Laptop Diagnostics", r.stdout)     # banner 保留
            self.assertIn("macvitals.collect", r.stdout)

    def test_diagnose_sh_syntax(self):
        r = subprocess.run(["bash", "-n", str(ROOT / "diagnose.sh")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)


# ── 報告對「模組收集失敗」的呈現 ───────────────────────────────
def build_report(data):
    with tempfile.TemporaryDirectory() as t:
        d = Path(t) / "data"; d.mkdir()
        for name, obj in data.items():
            (d / name).write_text(obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False), encoding="utf-8")
        out = Path(t) / "index.html"
        env = dict(os.environ, MACVITALS_DATA_DIR=str(d), MACVITALS_OUT_HTML=str(out))
        r = subprocess.run([sys.executable, str(ROOT / "generate_report.py")], env=env, capture_output=True, text=True)
        if r.returncode != 0:
            raise AssertionError(r.stderr)
        return out.read_text(encoding="utf-8")


class TestReportFailedModule(unittest.TestCase):
    def test_failed_module_is_shown_and_its_rules_do_not_fire(self):
        # 故意在 error JSON 裡夾帶會命中「防火牆未開啟」的資料:規則必須視為未命中
        html = build_report({"m9_security.json": {"module": "M9", "scan_time": "t", "error": "RuntimeError: boom <b>x</b>",
                                                  "firewall": {"state": "off"}, "pending_updates_count": 3}})
        self.assertIn("此模組收集失敗:</b>RuntimeError: boom &lt;b&gt;x&lt;/b&gt;", html)   # 分頁提示,且已跳脫
        self.assertIn("此模組收集失敗:RuntimeError: boom &lt;b&gt;x&lt;/b&gt;", html)       # 摘要卡
        self.assertIn("mod-card fail", html)
        self.assertNotIn("<b>x</b>", html)
        self.assertNotIn("防火牆未開啟", html)
        self.assertNotIn("項系統更新待安裝", html)
        self.assertIn("未命中(模組收集失敗)", html)
        self.assertIn("1 個模組收集失敗(M9)", html)
        self.assertIn("--only m9", html)

    def test_healthy_modules_show_no_failure_markers(self):
        html = build_report({"m6_battery.json": {"module": "M6", "cycle_count": "120", "condition": "Normal",
                                                 "maximum_capacity": "96%", "fully_charged": "Yes", "charging": "No", "raw": ""}})
        self.assertNotIn("此模組收集失敗", html)
        self.assertNotIn("mod-card fail", html)
        self.assertNotIn("模組收集失敗(", html)

    def test_corrupt_json_is_treated_as_collection_failure(self):
        html = build_report({"m3_large.json": "{not json"})
        self.assertIn("此模組收集失敗:</b>讀取 m3_large.json 失敗", html)


# ── app_server 讀 progress.json ────────────────────────────────
class TestAppServerProgress(unittest.TestCase):
    def test_apply_progress_maps_file_to_scan_state(self):
        import app_server
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "progress.json"
            self.assertFalse(app_server.apply_progress(p))          # 不存在 → 略過
            p.write_text("{half", encoding="utf-8")
            self.assertFalse(app_server.apply_progress(p))          # 半截 → 略過
            p.write_text(json.dumps({"step": "M3", "message": "M1 重複檔案、M3 大型檔案 掃描中…", "pct": 50,
                                     "done": ["M9"], "running": ["M1", "M3"], "failed": [], "total": 11}), encoding="utf-8")
            self.assertTrue(app_server.apply_progress(p))
            self.assertEqual(app_server.scan["step"], "M1 重複檔案、M3 大型檔案 掃描中…")
            self.assertEqual(app_server.scan["pct"], 3 + int(50 * 0.89))
            self.assertEqual(app_server.scan["modules"]["running"], ["M1", "M3"])
            p.write_text(json.dumps({"step": "done", "pct": 100, "done": [], "running": [], "failed": ["M3"], "total": 11}), encoding="utf-8")
            app_server.apply_progress(p)
            self.assertLessEqual(app_server.scan["pct"], 92)        # 95/100 留給產生報告與完成
            self.assertEqual(app_server.scan["modules"]["failed"], ["M3"])


if __name__ == "__main__":
    unittest.main()
