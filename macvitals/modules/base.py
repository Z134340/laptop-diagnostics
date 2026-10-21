"""
共用工具:子程序執行、時間戳、JSON 寫檔。

收集階段絕對唯讀 —— 這裡唯一會寫的東西是 report/data/ 底下的 JSON。
"""
import json
import os
import subprocess
from datetime import datetime


def run(cmd, timeout=30, merge_stderr=False, strip=True, error_value=None):
    """執行指令並回傳文字輸出。

    cmd 為字串 → 交給 shell(沿用原 heredoc 寫法,指令內含 2>/dev/null、| head 等);
    cmd 為 list → 不經 shell。
    merge_stderr=True 時回傳 stdout + stderr(原 M4 行為);否則只回 stdout。
    逾時或任何例外:error_value 不是 None 就回傳 error_value,否則回傳 "error: <例外>"。
    """
    shell = isinstance(cmd, str)
    try:
        r = subprocess.run(cmd, shell=shell, capture_output=True, text=True,
                           errors="replace", timeout=timeout)
        out = (r.stdout + r.stderr) if merge_stderr else r.stdout
        return out.strip() if strip else out
    except Exception as exc:  # TimeoutExpired / FileNotFoundError / ...
        return error_value if error_value is not None else "error: {}".format(exc)


def now_iso():
    return datetime.now().isoformat()


def write_json(path, obj):
    """utf-8、ensure_ascii=False、indent=2;先寫暫存檔再 os.replace,讀取端永遠看不到半截檔。"""
    path = os.fspath(path)
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    tmp = "{}.tmp.{}".format(path, os.getpid())
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
