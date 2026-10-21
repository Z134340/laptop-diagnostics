#!/usr/bin/env python3
"""
P0 回歸測試(純標準函式庫):python3 -m unittest discover -s tests -v

涵蓋:M1 純 Python 重複檔比對、報告 HTML 跳脫、電池「運作良好」誤判、
pip 規則只在 pip 本身過舊時長按鈕、本機伺服器 Host/Origin 防護與 /auto 來源限制。
"""
import os, sys, json, socket, threading, tempfile, subprocess, unittest, http.client
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


# ── M1 ────────────────────────────────────────────────────────
class TestM1Dupes(unittest.TestCase):
    def test_finds_identical_files_and_ignores_hardlinks_excluded_dirs_and_tiny_files(self):
        import m1_dupes
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            (t / "a" / "node_modules").mkdir(parents=True)
            (t / "b").mkdir()
            blob = os.urandom(200_000)
            (t / "a" / "big1.bin").write_bytes(blob)
            (t / "b" / "big2.bin").write_bytes(blob)                    # 真重複
            (t / "a" / "node_modules" / "ignored.bin").write_bytes(blob) # 排除目錄
            (t / "b" / "other.bin").write_bytes(os.urandom(200_000))     # 同大小不同內容
            os.link(t / "b" / "other.bin", t / "b" / "hardlink.bin")     # 同 inode,不算浪費
            (t / "s1").write_text("tiny"); (t / "s2").write_text("tiny")  # < 1 KB 略過
            os.symlink(t / "a" / "big1.bin", t / "b" / "link.bin")       # symlink 略過
            groups, scanned = m1_dupes.find_duplicates(str(t))
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["count"], 2)
        self.assertEqual(groups[0]["size_bytes"], 200_000)
        self.assertEqual(groups[0]["wasted_bytes"], 200_000)
        self.assertEqual(scanned, 3)   # big1, big2, other(hardlink 去重)

    def test_cli_writes_expected_schema(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            (t / "x").write_bytes(b"A" * 4096); (t / "y").write_bytes(b"A" * 4096)
            out = t / "out.json"
            r = subprocess.run([sys.executable, str(ROOT / "m1_dupes.py"), str(out), str(t)],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            d = json.loads(out.read_text(encoding="utf-8"))
        for k in ("module", "scan_time", "total_groups", "total_wasted_bytes", "groups"):
            self.assertIn(k, d)
        self.assertEqual(d["module"], "M1")
        self.assertEqual(d["total_groups"], 1)
        self.assertEqual(d["total_wasted_bytes"], 4096)


# ── 報告產生器 ─────────────────────────────────────────────────
def build_report(data):
    """把 fixture 寫進暫存 data 目錄,跑 generate_report.py,回傳產出的 HTML。"""
    with tempfile.TemporaryDirectory() as t:
        d = Path(t) / "data"; d.mkdir()
        for name, obj in data.items():
            (d / name).write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
        out = Path(t) / "index.html"
        env = dict(os.environ, MACVITALS_DATA_DIR=str(d), MACVITALS_OUT_HTML=str(out))
        r = subprocess.run([sys.executable, str(ROOT / "generate_report.py")],
                           env=env, capture_output=True, text=True)
        if r.returncode != 0:
            raise AssertionError(r.stderr)
        return out.read_text(encoding="utf-8")

M6_DEGRADED = {"module": "M6", "cycle_count": "812", "condition": "Service Recommended",
               "maximum_capacity": "74%", "fully_charged": "No", "charging": "No", "raw": ""}
M6_HEALTHY  = {"module": "M6", "cycle_count": "120", "condition": "Normal",
               "maximum_capacity": "96%", "fully_charged": "Yes", "charging": "No", "raw": ""}

class TestReport(unittest.TestCase):
    def test_renders_with_no_data(self):
        html = build_report({})
        self.assertIn("MacVitals", html)

    def test_scan_strings_are_html_escaped(self):
        payload = '<img src=x onerror="alert(1)">'
        html = build_report({
            "m3_large.json": {"module": "M3", "total_found": 1, "total_size_gb": 0.1, "files": [
                {"path": f"/Users/me/Downloads/{payload}.dmg", "size_bytes": 104857600, "size_mb": 100.0,
                 "last_access": "2026-10-01", "last_modified": "2026-10-01", "ext": ".dmg"}]},
            "m8_startup.json": {"module": "M8", "login_items": [f"{payload}App"], "user_launch_agents": [],
                                "system_launch_agents": [], "system_launch_daemons": [],
                                "third_party_user_agents": [], "third_party_system_agents": [],
                                "counts": {"login_items": 1, "user_agents": 0, "system_agents": 0, "system_daemons": 0}},
            "m11_sharing.json": {"module": "M11", "services": [], "open_count": 0, "auto_login": False,
                                 "tailscale": {}, "external_count": 1,
                                 "external_listeners": [{"proc": payload, "addr": "0.0.0.0", "port": "8080"}]},
            "m10_crashes.json": {"module": "M10", "count_30d": 6, "count_7d": 1, "panic_count_30d": 0,
                                 "apps": [{"app": payload, "count": 6, "count7": 1, "kinds": "crash", "last": "2026-10-01", "panic": False}],
                                 "recent": []},
            "m6_battery.json": dict(M6_HEALTHY, condition="<b>Normal</b>"),
        })
        self.assertNotIn("<img", html)
        self.assertNotIn("<b>Normal", html)
        self.assertIn("&lt;img src=x onerror=&quot;alert(1)&quot;&gt;", html)
        # 規則標題也不能帶未跳脫的 App 名(M10 反覆當機)
        self.assertIn("&lt;img src=x onerror=&quot;alert(1)&quot;&gt; 近 30 天當機 6 次", html)

    def test_degraded_battery_is_not_listed_as_healthy(self):
        html = build_report({"m6_battery.json": M6_DEGRADED})
        self.assertIn("電池明顯老化", html)
        self.assertNotIn("電池健康(", html)

    def test_healthy_battery_is_listed_as_healthy(self):
        html = build_report({"m6_battery.json": M6_HEALTHY})
        self.assertIn("電池健康(", html)
        self.assertNotIn("電池明顯老化", html)

    def test_pip_button_only_when_pip_itself_is_outdated(self):
        base = {"module": "M4", "versions": {}, "npm_doctor": "", "brew_installed_packages": "",
                "pip_outdated": "", "brew_outdated": [], "brew_outdated_count": 0,
                "npm_global_outdated_count": 0, "nvm_versions": "", "pyenv_versions": ""}
        html = build_report({"m4_env.json": dict(base, pip_outdated_count=3, pip_self_outdated=False)})
        self.assertNotIn("doRepair('update_pip'", html)
        self.assertIn("3 個 pip 套件有新版", html)
        html = build_report({"m4_env.json": dict(base, pip_outdated_count=3, pip_self_outdated=True)})
        self.assertIn("doRepair('update_pip'", html)
        self.assertIn("2 個 pip 套件有新版", html)      # 扣掉 pip 本身


# ── 本機伺服器防護 ─────────────────────────────────────────────
class TestGuards(unittest.TestCase):
    def test_host_and_origin_helpers(self):
        import repair_server as rs
        self.assertTrue(rs.host_allowed({"Host": "127.0.0.1:8788"}, 8788))
        self.assertTrue(rs.host_allowed({"Host": "localhost:8788"}, 8788))
        self.assertFalse(rs.host_allowed({"Host": "127.0.0.1:9999"}, 8788))
        self.assertFalse(rs.host_allowed({"Host": "evil.example"}, 8788))
        self.assertFalse(rs.host_allowed({}, 8788))
        self.assertTrue(rs.origin_allowed({"Origin": "http://127.0.0.1:8788"}, 8788))
        self.assertFalse(rs.origin_allowed({"Origin": "http://evil.example"}, 8788))
        self.assertFalse(rs.origin_allowed({"Sec-Fetch-Site": "cross-site"}, 8788))
        self.assertTrue(rs.origin_allowed({}, 8788))   # curl 類非瀏覽器客戶端(仍需 token)


class TestAppServerHTTP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import app_server
        cls.app = app_server
        cls.httpd = app_server.ThreadingServer(("127.0.0.1", 0), app_server.Handler)
        cls.port = cls.httpd.server_address[1]
        app_server.BOUND_PORT = cls.port
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown(); cls.httpd.server_close()

    def req(self, method, path, headers=None, body=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        h = {"Host": f"127.0.0.1:{self.port}"}
        h.update(headers or {})
        c.request(method, path, body=body, headers=h)
        r = c.getresponse()
        data = r.read().decode("utf-8", "replace")
        hdrs = {k.lower(): v for k, v in r.getheaders()}
        c.close()
        return r.status, hdrs, data

    def test_ping_ok_with_local_host_and_has_security_headers(self):
        status, hdrs, _ = self.req("GET", "/api/ping")
        self.assertEqual(status, 200)
        self.assertIn("frame-ancestors", hdrs.get("content-security-policy", ""))
        self.assertEqual(hdrs.get("x-content-type-options"), "nosniff")

    def test_foreign_host_is_rejected(self):
        status, _, _ = self.req("GET", "/api/ping", headers={"Host": "evil.example"})
        self.assertEqual(status, 403)

    def test_post_from_foreign_origin_is_rejected_even_with_valid_token(self):
        body = json.dumps({"action": "no_such_action", "token": self.app.TOKEN})
        status, _, data = self.req("POST", "/api/fix", body=body,
                                   headers={"Origin": "http://evil.example", "Content-Type": "application/json"})
        self.assertEqual(status, 403)
        # 同樣請求、本機 Origin → 通過防護,進到動作查表(未知動作 → 400),證明擋的是 Origin 而非 token
        status, _, data = self.req("POST", "/api/fix", body=body,
                                   headers={"Origin": f"http://127.0.0.1:{self.port}", "Content-Type": "application/json"})
        self.assertEqual(status, 400)
        self.assertIn("未知動作", json.loads(data)["message"])

    def test_auto_scan_is_disabled_for_cross_site_navigation(self):
        _, _, local = self.req("GET", "/auto")
        _, _, cross = self.req("GET", "/auto", headers={"Sec-Fetch-Site": "cross-site"})
        self.assertIn('if("1"==="1")', local)
        self.assertNotIn('if("1"==="1")', cross)
        self.assertIn('if("0"==="1")', cross)


if __name__ == "__main__":
    unittest.main()
