#!/usr/bin/env python3
"""
單一本機伺服器的測試(純標準函式庫):python3 -m unittest discover -s tests -v

證明 app_server.py 這一支伺服器同時提供首頁 /、/api/scan/status、/report(沒有報告 302、有報告 200 且注入 token)、
/api/ping、/api/fix(未知動作 400、token 不符 403),而且每條路徑都套同一套守衛(外來 Host / Origin → 403)
與同一組安全標頭;repair_server.py 只剩白名單動作與守衛、沒有 HTTP 程式碼;`python3 repair_server.py`
會轉呼叫同一支伺服器;同埠已有 MacVitals 在跑時不會起第二個。
"""
import ast, json, os, socket, subprocess, sys, tempfile, threading, time, unittest, http.client, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app_server
import repair_server as rs


class TestUnifiedServer(unittest.TestCase):
    """用隨機埠起真的伺服器,逐條路徑打。"""

    @classmethod
    def setUpClass(cls):
        cls.httpd = app_server.ThreadingServer(("127.0.0.1", 0), app_server.Handler)
        cls.port = cls.httpd.server_address[1]
        cls.saved_port = app_server.BOUND_PORT
        app_server.BOUND_PORT = cls.port
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown(); cls.httpd.server_close()
        app_server.BOUND_PORT = cls.saved_port

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

    def post_json(self, path, obj, origin=None):
        h = {"Content-Type": "application/json"}
        if origin:
            h["Origin"] = origin
        return self.req("POST", path, headers=h, body=json.dumps(obj))

    def assert_security_headers(self, hdrs, where):
        self.assertEqual(hdrs.get("x-content-type-options"), "nosniff", where)
        self.assertEqual(hdrs.get("cache-control"), "no-store", where)
        self.assertIn("frame-ancestors", hdrs.get("content-security-policy", ""), where)

    # ── 同一支伺服器的各路徑 ──────────────────────────────────
    def test_landing_page_has_start_button_and_token(self):
        for path in ("/", "/index.html"):
            status, hdrs, html = self.req("GET", path)
            self.assertEqual(status, 200, path)
            self.assertTrue(hdrs.get("content-type", "").startswith("text/html"), path)
            self.assertIn("開始體檢", html)
            self.assertIn(app_server.TOKEN, html)
            self.assertNotIn("__TOKEN__", html)
            self.assert_security_headers(hdrs, path)

    def test_scan_status_is_json_with_progress_fields(self):
        status, hdrs, data = self.req("GET", "/api/scan/status")
        self.assertEqual(status, 200)
        s = json.loads(data)
        for k in ("running", "done", "error", "step", "pct", "modules"):
            self.assertIn(k, s)
        self.assert_security_headers(hdrs, "/api/scan/status")

    def test_ping(self):
        status, hdrs, data = self.req("GET", "/api/ping")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(data), {"ok": True})
        self.assert_security_headers(hdrs, "/api/ping")

    def test_report_redirects_when_missing_and_serves_with_token_when_present(self):
        saved = app_server.index_path
        try:
            with tempfile.TemporaryDirectory() as t:
                missing = Path(t) / "report" / "index.html"
                app_server.index_path = lambda: missing
                for path in ("/report", "/report/", "/report/index.html"):
                    status, hdrs, _ = self.req("GET", path)
                    self.assertEqual(status, 302, path)
                    self.assertEqual(hdrs.get("location"), "/", path)
                    self.assert_security_headers(hdrs, path)   # 302 也帶安全標頭

                missing.parent.mkdir(parents=True)
                missing.write_text("<!DOCTYPE html><html><head><!--REPAIR_HOOK--></head><body>MacVitals 報告</body></html>",
                                   encoding="utf-8")
                status, hdrs, html = self.req("GET", "/report")
                self.assertEqual(status, 200)
                self.assertTrue(hdrs.get("content-type", "").startswith("text/html"))
                self.assertNotIn("<!--REPAIR_HOOK-->", html)
                self.assertIn(f'"token":"{app_server.TOKEN}"', html)
                self.assertIn('"enabled":true', html)
                self.assertIn("MacVitals 報告", html)
                self.assert_security_headers(hdrs, "/report")
        finally:
            app_server.index_path = saved

    def test_fix_unknown_action_is_400_and_bad_token_is_403(self):
        status, _, data = self.post_json("/api/fix", {"action": "no_such_action", "token": app_server.TOKEN})
        self.assertEqual(status, 400)
        self.assertIn("未知動作", json.loads(data)["message"])
        status, _, data = self.post_json("/api/fix", {"action": "fix_path", "token": "wrong"})
        self.assertEqual(status, 403)
        self.assertFalse(json.loads(data)["ok"])
        status, _, _ = self.req("POST", "/api/fix", headers={"Content-Type": "application/json"}, body="{not json")
        self.assertEqual(status, 400)

    def test_fix_runs_whitelisted_action_through_repair_server_actions(self):
        """/api/fix 查的是 repair_server.ACTIONS:臨時塞一個假動作,證明走的是同一張表(不碰真的修復動作)。"""
        calls = []
        rs.ACTIONS["_test_noop"] = lambda: (calls.append(1) or {"ok": True, "message": "noop done"})
        try:
            status, _, data = self.post_json("/api/fix", {"action": "_test_noop", "token": app_server.TOKEN})
        finally:
            del rs.ACTIONS["_test_noop"]
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(data), {"ok": True, "message": "noop done"})
        self.assertEqual(calls, [1])

    def test_unknown_paths_are_404(self):
        status, _, _ = self.req("GET", "/nope")
        self.assertEqual(status, 404)
        status, _, _ = self.post_json("/api/nope", {"token": app_server.TOKEN})
        self.assertEqual(status, 404)

    # ── 同一套守衛套在每條路徑 ───────────────────────────────
    def test_foreign_host_is_rejected_on_every_route(self):
        for path in ("/", "/api/scan/status", "/report", "/api/ping"):
            status, _, _ = self.req("GET", path, headers={"Host": "evil.example"})
            self.assertEqual(status, 403, path)
            status, _, _ = self.req("GET", path, headers={"Host": f"127.0.0.1:{self.port + 1}"})
            self.assertEqual(status, 403, path + " (wrong port)")
        for path in ("/api/scan", "/api/fix"):
            status, _, _ = self.req("POST", path, headers={"Host": "evil.example", "Content-Type": "application/json"},
                                    body=json.dumps({"token": app_server.TOKEN, "action": "fix_path"}))
            self.assertEqual(status, 403, path)

    def test_foreign_origin_post_is_rejected_on_scan_and_fix(self):
        for path in ("/api/scan", "/api/fix"):
            status, _, data = self.post_json(path, {"token": app_server.TOKEN, "action": "no_such_action"},
                                             origin="http://evil.example")
            self.assertEqual(status, 403, path)
            self.assertIn("origin", json.loads(data)["message"])
            status, _, _ = self.req("POST", path, body=json.dumps({"token": app_server.TOKEN}),
                                    headers={"Content-Type": "application/json", "Sec-Fetch-Site": "cross-site"})
            self.assertEqual(status, 403, path + " (cross-site)")
        # 本機 Origin 通過守衛、進到 token 檢查(token 錯 → 403「授權失敗」而不是 forbidden origin)
        status, _, data = self.post_json("/api/scan", {"token": "wrong"}, origin=f"http://localhost:{self.port}")
        self.assertEqual(status, 403)
        self.assertIn("授權失敗", json.loads(data)["message"])

    def test_localhost_host_header_is_accepted(self):
        status, _, _ = self.req("GET", "/api/ping", headers={"Host": f"localhost:{self.port}"})
        self.assertEqual(status, 200)


class TestRepairServerIsLibraryOnly(unittest.TestCase):
    def test_no_http_code_left_in_repair_server(self):
        for name in ("Handler", "ThreadingServer", "main", "PORT", "TOKEN", "BOUND_PORT", "_free_port", "_is_macvitals"):
            self.assertFalse(hasattr(rs, name), f"repair_server 不該再有 {name}")
        tree = ast.parse((ROOT / "repair_server.py").read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")
        for mod in ("http.server", "socketserver", "webbrowser", "urllib.request"):
            self.assertNotIn(mod, imported, f"repair_server 不該 import {mod}")
        self.assertFalse(any(isinstance(n, ast.ClassDef) for n in tree.body), "repair_server 不該再定義 class")

    def test_library_surface_used_by_app_server(self):
        self.assertIs(app_server.rs, rs)
        self.assertIs(app_server.rs.ACTIONS, rs.ACTIONS)
        self.assertTrue(rs.ACTIONS)
        self.assertTrue(all(callable(f) for f in rs.ACTIONS.values()))
        for name in ("host_allowed", "origin_allowed", "SECURITY_HEADERS", "sh"):
            self.assertTrue(hasattr(rs, name), name)
        # ACTIONS 仍是頂層 dict 字面值(scripts/check_doc_counts.py 用 ast 數它)
        tree = ast.parse((ROOT / "repair_server.py").read_text(encoding="utf-8"))
        top = [n for n in tree.body if isinstance(n, ast.Assign)
               and any(isinstance(t, ast.Name) and t.id == "ACTIONS" for t in n.targets)]
        self.assertEqual(len(top), 1)
        self.assertIsInstance(top[0].value, ast.Dict)
        self.assertEqual(len(top[0].value.keys), len(rs.ACTIONS))


def _free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    return port


def _wait_ping(port, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ping", timeout=1) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(0.1)
    return False


class TestCommandLineEntryPoints(unittest.TestCase):
    """真的以子行程啟動(DIAG_NO_BROWSER=1、隨機埠),驗證兩個指令都落到同一支伺服器,且不會重複啟動。"""

    def spawn(self, script, *args):
        env = dict(os.environ, DIAG_NO_BROWSER="1")
        return subprocess.Popen([sys.executable, "-u", str(ROOT / script), *args], cwd=str(ROOT), env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    def stop(self, p):
        if p.poll() is None:
            p.terminate()
        try:
            return p.communicate(timeout=5)[0]
        except subprocess.TimeoutExpired:
            p.kill(); return p.communicate()[0]

    def test_repair_server_cli_delegates_to_app_server_and_app_server_detects_running_instance(self):
        port = _free_port()
        p = self.spawn("repair_server.py", "--port", str(port))
        try:
            self.assertTrue(_wait_ping(port), "python3 repair_server.py 應轉呼叫 app_server 並在指定埠回 /api/ping")
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=3) as r:
                html = r.read().decode("utf-8")
            self.assertIn("開始體檢", html)       # 同一支伺服器:首頁也在
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/scan/status", timeout=3) as r:
                self.assertIn("pct", json.loads(r.read().decode("utf-8")))

            # 同埠已有 MacVitals → 第二個 app_server.py 不綁埠、直接結束(exit 0)
            q = self.spawn("app_server.py", "--port", str(port))
            try:
                out2, _ = q.communicate(timeout=15)
            except subprocess.TimeoutExpired:
                q.kill(); self.fail("第二個 app_server.py 應偵測到既有實例後立刻結束")
            self.assertEqual(q.returncode, 0, out2)
            self.assertIn("已在背景執行中", out2)
            self.assertTrue(_wait_ping(port, timeout=2))   # 原本那個還活著
        finally:
            out = self.stop(p)
        self.assertIn("app_server", out)
        self.assertIn(f"http://127.0.0.1:{port}/report", out)   # repair_server.py 轉呼叫時帶 --report


if __name__ == "__main__":
    unittest.main()
