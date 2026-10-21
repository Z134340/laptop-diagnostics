#!/usr/bin/env python3
"""
m1_dupes.py — M1 重複檔案(純 Python,不依賴 fdupes)
用法:python3 m1_dupes.py <輸出 JSON> [掃描根目錄,預設 ~]

做法:大小分桶 → 前 64 KB hash → 全檔 hash,逐層縮小要讀的檔案。
全程唯讀;略過 symlink;同一 inode 的 hardlink 視為同一份(不算浪費空間)。
"""
import sys, os, json, stat, hashlib
from datetime import datetime
from collections import defaultdict

EXCLUDE_NAMES = {".Trash", "node_modules", ".git"}
# 相對掃描根目錄;這些本來就是快取/容器範本/備份,裡面的重複檔沒有清理價值
EXCLUDE_REL = {
    "Library/Caches", "Library/Containers", "Library/Group Containers",
    "Library/Developer/CoreSimulator", "Library/Developer/Xcode/DerivedData",
    "Library/Application Support/MobileSync",
}
MIN_SIZE   = 1024        # 1 KB 以下略過(空檔與雜訊)
HEAD_BYTES = 64 * 1024
CHUNK      = 1 << 20
MAX_GROUPS = 200         # JSON 最多輸出 200 組

def _digest(path, limit=None):
    """回傳檔案(前 limit bytes 或全檔)的 sha1;讀不到回 None。"""
    h = hashlib.sha1()
    try:
        with open(path, "rb") as f:
            left = limit
            while left is None or left > 0:
                b = f.read(CHUNK if left is None else min(CHUNK, left))
                if not b:
                    break
                h.update(b)
                if left is not None:
                    left -= len(b)
        return h.hexdigest()
    except OSError:
        return None

def _safe_str(p):
    # 檔名若含非 UTF-8 位元組,json.dump 會失敗;以 U+FFFD 取代
    return os.fsencode(p).decode("utf-8", "replace")

def _walk_candidates(root):
    """回傳 {size: [path, ...]};同一 inode 只保留第一個路徑。"""
    by_size = defaultdict(list)
    seen = set()
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False, onerror=lambda e: None):
        rel = os.path.relpath(dirpath, root)
        dirnames[:] = [d for d in dirnames
                       if d not in EXCLUDE_NAMES
                       and os.path.normpath(os.path.join(rel, d)) not in EXCLUDE_REL]
        for fn in filenames:
            fp = os.path.join(dirpath, fn)
            try:
                st = os.lstat(fp)
            except OSError:
                continue
            if not stat.S_ISREG(st.st_mode) or st.st_size < MIN_SIZE:
                continue
            key = (st.st_dev, st.st_ino)
            if key in seen:
                continue
            seen.add(key)
            by_size[st.st_size].append(fp)
    return by_size

def find_duplicates(root):
    """回傳 (groups, scanned_count);groups 依浪費空間由大到小排序。"""
    by_size = _walk_candidates(root)
    scanned = sum(len(v) for v in by_size.values())
    groups = []
    for size, paths in by_size.items():
        if len(paths) < 2:
            continue
        by_head = defaultdict(list)
        for p in paths:
            h = _digest(p, HEAD_BYTES)
            if h:
                by_head[h].append(p)
        for head_paths in by_head.values():
            if len(head_paths) < 2:
                continue
            if size <= HEAD_BYTES:
                buckets = [head_paths]              # 前段即全檔
            else:
                by_full = defaultdict(list)
                for p in head_paths:
                    h = _digest(p)
                    if h:
                        by_full[h].append(p)
                buckets = [v for v in by_full.values() if len(v) >= 2]
            for files in buckets:
                files = sorted(_safe_str(p) for p in files)
                groups.append({"files": files, "size_bytes": size, "count": len(files),
                               "wasted_bytes": size * (len(files) - 1)})
    groups.sort(key=lambda g: (-g["wasted_bytes"], g["files"][0]))
    return groups, scanned

def main(argv):
    out  = argv[1]
    root = argv[2] if len(argv) > 2 else os.path.expanduser("~")
    groups, scanned = find_duplicates(root)
    total_wasted = sum(g["wasted_bytes"] for g in groups)
    result = {
        "module": "M1",
        "scan_time": datetime.now().isoformat(),
        "method": "python-hash",
        "scan_root": _safe_str(root),
        "scanned_files": scanned,
        "total_groups": len(groups),
        "total_wasted_bytes": total_wasted,
        "groups": groups[:MAX_GROUPS],
    }
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"  → 重複群組:{len(groups)} 個,可釋空間:{total_wasted / 1024**3:.2f} GB(比對 {scanned} 個檔案)")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__.strip()); sys.exit(2)
    main(sys.argv)
