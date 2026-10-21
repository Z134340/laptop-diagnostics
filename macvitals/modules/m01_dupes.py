"""M1 重複檔案 —— 包裝根目錄 m1_dupes.py(純 Python:大小分桶 → 前 64 KB hash → 全檔 hash;唯讀)。"""
import os
import sys

# m1_dupes.py 留在倉庫根目錄(tests/test_p0.py 直接測它的 CLI);從別的 cwd 執行時補上路徑。
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    import m1_dupes
except ImportError:  # pragma: no cover - 只在 cwd 不是倉庫根目錄時發生
    if _ROOT not in sys.path:
        sys.path.insert(0, _ROOT)
    import m1_dupes

MODULE = "M1"
FILENAME = "m1_dupes.json"
LABEL = "重複檔案"
START_MSG = "M1 重複檔案掃描(範圍:~,排除 .Trash / node_modules / .git / 各類快取)..."


def collect(root=None):
    root = root or os.path.expanduser("~")
    return m1_dupes.build_result(root)


def summary(result):
    return m1_dupes.summary_line(result)
