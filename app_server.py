#!/usr/bin/env python3
"""
app_server.py — Laptop Diagnostics 一站式網頁應用(給非技術使用者)
首頁一顆「開始體檢」按鈕 → 背景執行掃描並顯示進度 → 完成自動跳到報告 → 報告內可一鍵修復。

啟動:python3 app_server.py(通常由「開始體檢.command」雙擊啟動)
安全:僅綁 127.0.0.1、token 驗證;修復動作沿用 repair_server 的白名單,執行當下再驗證現況。
"""
import http.server, socketserver, json, os, subprocess, secrets, threading, time, webbrowser, sys, socket, urllib.request
from pathlib import Path

import repair_server as rs   # 重用白名單修復動作與 sh()

PORT  = 8788
_LAUNCH_BASE = Path(__file__).resolve().parent
TOKEN = secrets.token_hex(16)
BOUND_PORT = PORT   # 實際綁定的埠(main() 可能往後找空埠),供 Host/Origin 比對

def base_dir():
    """診斷腳本與報告所在的目錄。

    `__file__` 是「啟動當下」的絕對路徑,常駐服務跑好幾週後若整個專案被搬家,
    這個值就失準了(行程的 cwd 會跟著 inode 一起搬,`__file__` 不會)。
    因此以「找得到 diagnose.sh」為準:先看啟動路徑,再用目前的 cwd 當後援。
    """
    for cand in (_LAUNCH_BASE, Path.cwd()):
        if (cand / "diagnose.sh").is_file():
            return cand
    return _LAUNCH_BASE

def index_path():
    return base_dir() / "report" / "index.html"

scan = {"running": False, "done": False, "error": "", "step": "尚未開始", "pct": 0, "modules": {}}

def progress_path(base=None):
    """收集程式(python3 -m macvitals.collect)持續寫入的進度檔。"""
    return (base or base_dir()) / "report" / "data" / "progress.json"

def apply_progress(path):
    """把 progress.json 的內容對應到 scan 狀態;檔案不存在或半截(正在寫)就略過,下次再讀。

    收集端的 pct 是 0–100(依模組權重);這裡壓到 3–92,留 95 給「產生報告」、100 給完成。
    """
    try:
        with open(path, encoding="utf-8") as f:
            prog = json.load(f)
    except Exception:
        return False
    if not isinstance(prog, dict):
        return False
    try:
        pct = int(prog.get("pct") or 0)
    except Exception:
        pct = 0
    step = prog.get("message") or (f"掃描 {prog.get('step')}…" if prog.get("step") else "準備中…")
    scan.update(step=step, pct=min(92, 3 + int(pct * 0.89)),
                modules={"done": prog.get("done") or [], "running": prog.get("running") or [],
                         "failed": prog.get("failed") or [], "total": prog.get("total") or 0})
    return True

def run_scan():
    scan.update(running=True, done=False, error="", step="準備中…", pct=2, modules={})
    try:
        base = base_dir()
        if not (base / "diagnose.sh").is_file():
            scan.update(running=False, error=(
                f"找不到 diagnose.sh(目前目錄:{base})。專案可能被搬移過;"
                "請把服務指到新的路徑後重新啟動本機體檢服務。")); return
        prog = progress_path(base)
        try:
            prog.unlink()   # 清掉上次殘留的進度檔,避免一開始就顯示舊進度
        except FileNotFoundError:
            pass
        except Exception:
            pass
        tail = []
        p = subprocess.Popen(["bash", "diagnose.sh"], cwd=str(base),
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
        def _drain():   # 只保留最後幾行,給失敗時的錯誤訊息用;進度改由 progress.json 提供
            for line in p.stdout:
                tail.append(line.rstrip())
                del tail[:-12]
        t = threading.Thread(target=_drain, daemon=True); t.start()
        while p.poll() is None:
            apply_progress(prog)
            time.sleep(0.5)
        t.join(timeout=2)
        apply_progress(prog)
        if p.returncode != 0:
            # 這支服務多半由 launchd 背景常駐,沒有終端機視窗可看;把最後幾行輸出直接帶出來。
            scan.update(running=False, error=(
                f"診斷收集失敗(diagnose.sh 退出碼 {p.returncode},目錄 {base})。"
                "最後訊息:" + " / ".join(t for t in tail[-4:] if t))); return
        scan.update(step="產生報告…", pct=95)
        r = subprocess.run(["python3", "generate_report.py"], cwd=str(base), capture_output=True, text=True)
        if r.returncode != 0:
            scan.update(running=False, error="報告產生失敗:" + r.stderr[-200:]); return
        scan.update(running=False, done=True, step="完成", pct=100)
    except Exception as e:
        scan.update(running=False, error=str(e))

LANDING = """<!DOCTYPE html><html lang="zh-TW"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0"><title>MacVitals — macOS 健康體檢</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64' fill='none'%3E%3Crect x='4' y='4' width='56' height='56' rx='16' fill='%23142a3d' stroke='%2338bdf8' stroke-width='3'/%3E%3Cpath d='M13 35H23L27.5 23L34 44L38.5 33H45' stroke='%2338bdf8' stroke-width='4' stroke-linecap='round' stroke-linejoin='round'/%3E%3Ccircle cx='49' cy='33' r='4' fill='%2334d399'/%3E%3C/svg%3E">
<style>
 :root{--bg:#0f1117;--surface:#1a1d27;--surface2:#22263a;--border:#2d3148;--text:#e2e8f0;--muted:#8892a4;--cyan:#38bdf8;--green:#34d399}
 *{box-sizing:border-box;margin:0;padding:0}
 body{background:var(--bg);color:var(--text);font-family:'SF Pro Text',-apple-system,sans-serif;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:24px}
 .card{background:var(--surface);border:1px solid var(--border);border-radius:18px;padding:40px 40px;max-width:680px;width:100%;text-align:center}
 .brand{display:flex;flex-direction:column;align-items:center;gap:6px;margin-bottom:18px}
 .mark{width:64px;height:64px;display:block}
 .word{font-size:28px;font-weight:600;letter-spacing:.01em;line-height:1}
 .word .v{color:var(--cyan)}
 .tag{font-size:12px;color:var(--muted);letter-spacing:.22em;text-transform:uppercase}
 h1{display:none}
 p.sub{color:var(--muted);font-size:14px;line-height:1.7;margin-bottom:28px}
 button{background:var(--cyan);color:#06283a;border:none;border-radius:10px;padding:15px 28px;font-size:16px;font-weight:600;cursor:pointer;display:inline-flex;align-items:center;gap:8px}
 button:hover{filter:brightness(1.08)} button:disabled{opacity:.6;cursor:default}
 .ghost{background:transparent;border:1px solid var(--border);color:var(--cyan);font-size:14px;padding:11px 20px}
 .actions{display:flex;gap:12px;justify-content:center;flex-wrap:wrap}
 .prog{display:none;margin-top:26px;text-align:left}
 .bar{height:10px;background:var(--surface2);border-radius:6px;overflow:hidden;margin:10px 0 8px}
 .fill{height:100%;width:0;background:var(--cyan);transition:width .4s;border-radius:6px}
 .step{font-size:13px;color:var(--muted)}
 .note{margin-top:22px;font-size:12px;color:var(--muted);line-height:1.7}
 .err{color:#f87171;font-size:13px;margin-top:14px}
 svg{display:block}
</style></head><body>
<div class="card">
 <div class="brand">
   <svg class="mark" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="MacVitals">
     <rect x="4" y="4" width="56" height="56" rx="16" fill="#142a3d" stroke="#38bdf8" stroke-width="2.5"/>
     <path d="M13 35 H23 L27.5 23 L34 44 L38.5 33 H45" stroke="#38bdf8" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"/>
     <circle cx="49" cy="33" r="3.6" fill="#34d399"/>
   </svg>
   <div class="word">Mac<span class="v">Vitals</span></div>
   <div class="tag">macOS 健康體檢</div>
 </div>
 <p class="sub">一鍵掃描這台 Mac 的重複檔、大型檔、開發環境、電池、系統健康、近期當機、遠端存取與安全設定,<br>完成後會產出一份好讀的報告,並可一鍵修復常見問題。<br>過程全程唯讀,不會刪改你的檔案。</p>
 <div class="actions">
   <button id="go" onclick="startScan()">
     <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M5 3l14 9-14 9z"/></svg>
     開始體檢
   </button>
   <button class="ghost" id="view" onclick="location.href='/report'" style="display:__HASREPORT__">查看上次報告</button>
 </div>
 <div class="prog" id="prog">
   <div class="bar"><div class="fill" id="fill"></div></div>
   <div class="step" id="step">準備中…</div>
 </div>
 <div class="err" id="err"></div>
 <p class="note">掃描約需數分鐘(全碟掃描最久),請保持本視窗開啟。<br>啟動本程式的終端機視窗請勿關閉。</p>
</div>
<script>
var TOKEN="__TOKEN__";
function startScan(){
  document.getElementById('go').disabled=true;
  document.getElementById('view').style.display='none';
  document.getElementById('prog').style.display='block';
  document.getElementById('err').textContent='';
  fetch('/api/scan',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token:TOKEN})})
    .then(r=>r.json()).then(()=>poll()).catch(e=>showErr(e));
}
function poll(){
  fetch('/api/scan/status').then(r=>r.json()).then(s=>{
    document.getElementById('fill').style.width=(s.pct||0)+'%';
    document.getElementById('step').textContent=s.step||'';
    if(s.error){showErr(s.error);document.getElementById('go').disabled=false;return;}
    if(s.done){document.getElementById('step').textContent='完成,正在開啟報告…';setTimeout(()=>location.href='/report',700);return;}
    setTimeout(poll,1000);
  }).catch(e=>setTimeout(poll,1500));
}
function showErr(m){document.getElementById('err').textContent='發生問題:'+m;}
// 自動模式(由 Hermes 控制台嵌入時):載入即開掃,不需再按「開始體檢」
if("__AUTO__"==="1"){startScan();}
</script>
</body></html>"""


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _send(self, code, body, ctype="application/json"):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code); self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        for k, v in rs.SECURITY_HEADERS:
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def _guard(self, post=False):
        """Host 不是本機 → 403(擋 DNS rebinding);POST 的 Origin 不是本機 → 403。"""
        if not rs.host_allowed(self.headers, BOUND_PORT):
            self._send(403, json.dumps({"ok": False, "message": "forbidden host"})); return False
        if post and not rs.origin_allowed(self.headers, BOUND_PORT):
            self._send(403, json.dumps({"ok": False, "message": "forbidden origin"})); return False
        return True

    def do_GET(self):
        if not self._guard(): return
        if self.path in ("/", "/index.html", "/auto"):
            # /auto(載入即開掃)只給本機來源:同源頁面、本機其他埠的控制台、使用者自己輸入網址。
            # 外部網站連結/視窗開過來的(Sec-Fetch-Site: cross-site)只顯示首頁,不自動開掃。
            sfs = (self.headers.get("Sec-Fetch-Site") or "").strip().lower()
            auto = "1" if (self.path == "/auto" and sfs in ("", "none", "same-origin", "same-site")) else "0"
            html = (LANDING.replace("__TOKEN__", TOKEN)
                          .replace("__HASREPORT__", "inline-flex" if index_path().exists() else "none")
                          .replace("__AUTO__", auto))
            return self._send(200, html, "text/html; charset=utf-8")
        if self.path in ("/report", "/report/", "/report/index.html"):
            if not index_path().exists():
                self.send_response(302); self.send_header("Location", "/"); self.end_headers(); return
            html = index_path().read_text(encoding="utf-8").replace("<!--REPAIR_HOOK-->",
                   f'<script>window.__REPAIR__={{"token":"{TOKEN}","enabled":true}};</script>')
            return self._send(200, html, "text/html; charset=utf-8")
        if self.path == "/api/scan/status":
            return self._send(200, json.dumps(scan, ensure_ascii=False))
        if self.path == "/api/ping":
            return self._send(200, json.dumps({"ok": True}))
        if self.path == "/favicon.ico":
            return self._send(204, b"")
        return self._send(404, "not found", "text/plain")

    def do_POST(self):
        if not self._guard(post=True): return
        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length) or "{}")
        except Exception:
            return self._send(400, json.dumps({"ok": False, "message": "bad request"}))
        if payload.get("token") != TOKEN:
            return self._send(403, json.dumps({"ok": False, "message": "授權失敗"}))
        if self.path == "/api/scan":
            if scan["running"]:
                return self._send(200, json.dumps({"ok": True, "message": "已在掃描中"}))
            threading.Thread(target=run_scan, daemon=True).start()
            return self._send(200, json.dumps({"ok": True}))
        if self.path == "/api/fix":
            fn = rs.ACTIONS.get(payload.get("action"))
            if not fn:
                return self._send(400, json.dumps({"ok": False, "message": "未知動作"}))
            try: result = fn()
            except Exception as e: result = {"ok": False, "message": f"執行錯誤:{e}"}
            return self._send(200, json.dumps(result, ensure_ascii=False))
        return self._send(404, json.dumps({"ok": False, "message": "unknown endpoint"}))


class ThreadingServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True

def _is_macvitals(port):
    """該埠是否已有一個 MacVitals 在跑(背景常駐服務或上次未關的實例)。"""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ping", timeout=2) as r:
            return r.status == 200
    except Exception:
        return False

def _free_port(start, n=20):
    """從 start 起找一個可綁定的埠;找不到回 None。"""
    for p in range(start, start + n):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("127.0.0.1", p)); s.close(); return p
        except OSError:
            s.close()
    return None

def main():
    global BOUND_PORT
    # 若 8788 已有 MacVitals 在跑(例如背景常駐服務),不要再起第二個——直接開瀏覽器。
    if _is_macvitals(PORT):
        url = f"http://127.0.0.1:{PORT}/"
        print("MacVitals 已在背景執行中,直接為你開啟報告頁,不需重複啟動。")
        if not os.environ.get("DIAG_NO_BROWSER"):
            try: webbrowser.open(url)
            except Exception: pass
        return
    port = _free_port(PORT)
    if port is None:
        print(f"連接埠 {PORT} 起算都被佔用,請關閉其他視窗或重開機後再試。")
        return
    BOUND_PORT = port
    with ThreadingServer(("127.0.0.1", port), Handler) as httpd:
        url = f"http://127.0.0.1:{port}/"
        print("=" * 56)
        print("  電腦健康體檢 已啟動")
        print(f"  請在瀏覽器操作:{url}")
        print("  ★ 請勿關閉這個視窗(關掉就會停止)。完成後可直接關閉。")
        print("=" * 56)
        if not os.environ.get("DIAG_NO_BROWSER"):
            try: webbrowser.open(url)
            except Exception: pass
        try: httpd.serve_forever()
        except KeyboardInterrupt: print("\n已結束。")

if __name__ == "__main__":
    main()
