"""M2 孤兒 / 損壞項目 —— 斷裂 symlink(三分類)+ brew doctor。唯讀。"""
import os
import shutil
import subprocess

from .base import now_iso

MODULE = "M2"
FILENAME = "m2_broken.json"
LABEL = "孤兒/損壞項目"
START_MSG = "M2 孤兒與損壞項目掃描..."

FIND_TIMEOUT = 900   # 秒;原腳本無逾時,這裡給個上限避免整支卡死
BREW_TIMEOUT = 300

# ── 斷裂 symlink 三分類 ────────────────────────────────────────
# 經驗:~/Library 下絕大多數「斷裂」symlink 是 macOS / App 的正常設計,
# 並非真的壞掉。只有第三類「真殘留」才需要(在使用者授權下)清理。
#   1) sandbox_template — macOS 沙盒容器範本捷徑(~/Library/Containers/*),
#      系統 containermanagerd 自動產生維護,刪了會重建,正常無害 → 勿動
#   2) app_lock        — App 執行期鎖檔(SingletonLock / SingletonCookie /
#      SingletonSocket / RunningChromeVersion 等),故意指向非檔案目標,正常設計 → 勿動
#   3) stale           — 指向已刪除/暫存(已清空)目標的真殘留 → 可安全清理
LOCK_NAMES = {"SingletonLock", "SingletonCookie", "SingletonSocket", "RunningChromeVersion"}


def categorize(path):
    base = os.path.basename(path)
    if "/Library/Containers/" in path:
        return "sandbox_template"
    if base in LOCK_NAMES or base.endswith(".lock"):
        return "app_lock"
    return "stale"


def find_broken_symlinks(home):
    """等同原本的 `find -L ~ \\( -name .Trash -o -name node_modules -o -name .git \\) -prune -o -type l -print0`。
    結果以 NUL 分隔的 bytes 解析,檔名含怪字元也不會壞(不再內插進 Python 原始碼)。"""
    cmd = ["find", "-L", home,
           "(", "-name", ".Trash", "-o", "-name", "node_modules", "-o", "-name", ".git", ")", "-prune",
           "-o", "-type", "l", "-print0"]
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=FIND_TIMEOUT)
    # find 遇到權限不足會回非 0,但已輸出的結果照用(原腳本 `|| true`)
    return [p.decode("utf-8", "replace") for p in r.stdout.split(b"\0") if p]


def brew_doctor_output():
    if not shutil.which("brew"):
        return "Homebrew not found\n"
    try:
        r = subprocess.run(["brew", "doctor"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           text=True, errors="replace", timeout=BREW_TIMEOUT)
        return r.stdout
    except Exception as exc:
        return "error: {}".format(exc)


def parse_brew_issues(brew_raw):
    brew_issues = []
    current_issue = []
    for line in brew_raw.split('\n'):
        if line.startswith('Warning:') or line.startswith('Error:'):
            if current_issue:
                brew_issues.append('\n'.join(current_issue))
            current_issue = [line]
        elif current_issue:
            current_issue.append(line)
    if current_issue:
        brew_issues.append('\n'.join(current_issue))
    return brew_issues


def collect(home=None):
    home = home or os.path.expanduser("~")
    broken = find_broken_symlinks(home)
    brew_raw = brew_doctor_output()

    cats = {"sandbox_template": 0, "app_lock": 0, "stale": 0}
    stale = []
    for p in broken:
        c = categorize(p)
        cats[c] += 1
        if c == "stale":
            try:
                tgt = os.readlink(p)
            except Exception:
                tgt = ""
            stale.append({"path": p, "target": tgt})

    brew_issues = parse_brew_issues(brew_raw)

    return {
      "module": MODULE,
      "scan_time": now_iso(),
      "broken_symlinks_count": len(broken),
      "categories": cats,
      "category_notes": {
        "sandbox_template": "macOS 沙盒容器範本捷徑，系統自動產生維護，正常無害，勿動",
        "app_lock": "App 執行期鎖檔(SingletonLock 等)，正常設計，勿動",
        "stale": "指向已刪除/已清空目標的真殘留，可在使用者授權下安全清理"
      },
      "stale_symlinks": stale,
      "stale_count": len(stale),
      "broken_symlinks": [{"path": p} for p in broken],
      "brew_doctor_raw": brew_raw,
      "brew_issues": brew_issues,
      "brew_issues_count": len(brew_issues)
    }


def summary(r):
    cats = r["categories"]
    return ("  → 斷裂 symlink {} 個:沙盒範本 {} / App 鎖檔 {} / 真殘留 {}(需處理);Homebrew 問題 {} 項"
            .format(r["broken_symlinks_count"], cats['sandbox_template'], cats['app_lock'], cats['stale'],
                    r["brew_issues_count"]))
