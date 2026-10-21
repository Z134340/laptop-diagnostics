"""M5 可回收空間 —— 各類快取 / Trash / iOS 備份 / DerivedData 的 du -sk。唯讀。"""
import os
import subprocess

from .base import now_iso

MODULE = "M5"
FILENAME = "m5_reclaimable.json"
LABEL = "可回收空間"
START_MSG = "M5 可回收空間掃描..."

HOME = os.path.expanduser("~")
ITEMS = [
  ("應用程式快取 (~/Library/Caches)", os.path.join(HOME,"Library/Caches"), "App 快取,可清,App 會重建"),
  ("使用者快取 (~/.cache)",            os.path.join(HOME,".cache"),         "工具快取,可清"),
  ("npm 快取 (~/.npm)",                os.path.join(HOME,".npm"),           "用 npm cache clean --force"),
  ("Homebrew 下載快取",               os.path.join(HOME,"Library/Caches/Homebrew"), "用 brew cleanup -s"),
  ("pip 快取",                         os.path.join(HOME,"Library/Caches/pip"),      "用 pip cache purge"),
  ("垃圾桶 (~/.Trash)",               os.path.join(HOME,".Trash"),         "可清空"),
  ("iOS 裝置備份",                     os.path.join(HOME,"Library/Application Support/MobileSync/Backup"), "舊裝置備份,確認後可刪"),
  ("Xcode DerivedData",               os.path.join(HOME,"Library/Developer/Xcode/DerivedData"), "編譯中繼,可清"),
  ("CoreSimulator 模擬器",            os.path.join(HOME,"Library/Developer/CoreSimulator"), "iOS 模擬器,可用 xcrun simctl delete unavailable"),
]


def dk(path):  # du -sk -> bytes,不存在回 0
    if not os.path.exists(path): return 0
    try:
        out = subprocess.run(["du","-sk",path], capture_output=True, text=True, errors="replace", timeout=120).stdout
        return int(out.split("\t")[0].strip()) * 1024
    except Exception:
        return 0


def collect(items=None):
    items_def = items if items is not None else ITEMS
    items = []
    for label, path, note in items_def:
        b = dk(path)
        if b > 0:
            items.append({"label": label, "path": path, "size_bytes": b, "note": note})
    items.sort(key=lambda x: x["size_bytes"], reverse=True)

    return {
      "module": MODULE, "scan_time": now_iso(),
      "items": items, "total_reclaimable_bytes": sum(i["size_bytes"] for i in items)
    }


def summary(r):
    return "  → 可回收空間估計:{:.2f} GB({} 類)".format(r['total_reclaimable_bytes']/1024**3, len(r["items"]))
