"""M3 大型檔案 Top 50 —— >100MB,排除 /System、/private/var、/Volumes;純 Python os.walk,唯讀。"""
import os
from datetime import datetime

from .base import now_iso

MODULE = "M3"
FILENAME = "m3_large.json"
LABEL = "大型檔案"
START_MSG = "M3 大型檔案掃描(>100MB,排除 /System /private/var)..."

PRUNE = {'/System', '/private', '/Volumes', '/dev', '/net', '/home'}
MIN_SIZE = 100 * 1024 * 1024  # 100 MB
TOP_N = 50


def _safe_str(p):
    # 檔名含非 UTF-8 位元組時 json.dump 會失敗;以 U+FFFD 取代
    return os.fsencode(p).decode("utf-8", "replace")


def scan_large_files(root="/", min_size=MIN_SIZE):
    files = []
    for cur, dirs, filenames in os.walk(root, followlinks=False):
        # 剪枝
        dirs[:] = [d for d in dirs if os.path.join(cur, d) not in PRUNE
                   and not os.path.join(cur, d).startswith('/System')
                   and not os.path.join(cur, d).startswith('/private/var')
                   and not os.path.join(cur, d).startswith('/Volumes')]
        for fn in filenames:
            fp = os.path.join(cur, fn)
            try:
                st = os.stat(fp, follow_symlinks=False)
                if st.st_size >= min_size:
                    files.append({
                        "path": _safe_str(fp),
                        "size_bytes": st.st_size,
                        "size_mb": round(st.st_size / 1024**2, 1),
                        "last_access": datetime.fromtimestamp(st.st_atime).strftime('%Y-%m-%d'),
                        "last_modified": datetime.fromtimestamp(st.st_mtime).strftime('%Y-%m-%d'),
                        "ext": os.path.splitext(fn)[1].lower()
                    })
            except Exception:
                pass
    files.sort(key=lambda x: x['size_bytes'], reverse=True)
    return files


def collect(root="/"):
    files = scan_large_files(root)
    return {
      "module": MODULE,
      "scan_time": now_iso(),
      "total_found": len(files),
      "total_size_gb": round(sum(f['size_bytes'] for f in files) / 1024**3, 2),
      "files": files[:TOP_N]
    }


def summary(r):
    return "  → 大型檔案:{} 個,Top 50 總計 {:.1f} GB".format(r["total_found"], r["total_size_gb"])
