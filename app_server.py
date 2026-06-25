#!/usr/bin/env python3
"""
app_server.py — Laptop Diagnostics 一站式網頁應用(給非技術使用者)
首頁一顆「開始體檢」按鈕 → 背景執行掃描並顯示進度 → 完成自動跳到報告 → 報告內可一鍵修復。

啟動:python3 app_server.py(通常由「開始體檢.command」雙擊啟動)
安全:僅綁 127.0.0.1、token 驗證;修復動作沿用 repair_server 的白名單,執行當下再驗證現況。
"""
import http.server, socketserver, json, os, subprocess, secrets, threading, re, webbrowser, sys, socket, urllib.request
from pathlib import Path

import repair_server as rs   # 重用白名單修復動作與 sh()

PORT  = 8788
BASE  = Path(__file__).parent
INDEX = BASE / "report" / "index.html"
TOKEN = secrets.token_hex(16)

scan = {"running": False, "done": False, "error": "", "step": "尚未開始", "pct": 0}

def run_scan():
    scan.update(running=True, done=False, error="", step="準備中…", pct=2)
    try:
        p = subprocess.Popen(["bash", "diagnose.sh"], cwd=str(BASE),
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in p.stdout:
            if "fdupes" in line and "安裝" in line:
                scan.update(step="準備工具 (fdupes)…", pct=5)
            mok = re.search(r'M(\d{1,2}) 完成', line)
            mrun = re.search(r'M(\d{1,2}) ', line)
            if mok:
                n = int(mok.group(1)); scan.update(step=f"M{n} 完成", pct=min(92, 5 + n * 8))
            elif mrun:
                n = int(mrun.group(1)); scan.update(step=f"掃描 M{n}…", pct=min(90, 5 + (n - 1) * 8))
        p.wait()
        if p.returncode != 0:
            scan.update(running=False, error="診斷收集失敗,請看終端機視窗的訊息。"); return
        scan.update(step="產生報告…", pct=95)
        r = subprocess.run(["python3", "generate_report.py"], cwd=str(BASE), capture_output=True, text=True)
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
        self.send_header("Content-Length", str(len(data))); self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path in ("/", "/index.html", "/auto"):
            auto = "1" if self.path == "/auto" else "0"
            html = (LANDING.replace("__TOKEN__", TOKEN)
                          .replace("__HASREPORT__", "inline-flex" if INDEX.exists() else "none")
                          .replace("__AUTO__", auto))
            return self._send(200, html, "text/html; charset=utf-8")
        if self.path in ("/report", "/report/", "/report/index.html"):
            if not INDEX.exists():
                self.send_response(302); self.send_header("Location", "/"); self.end_headers(); return
            html = INDEX.read_text().replace("<!--REPAIR_HOOK-->",
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
