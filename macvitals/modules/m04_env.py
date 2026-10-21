"""M4 開發環境健檢 —— 工具版本、npm doctor、brew/pip/npm 過時清單。唯讀。"""
import shutil

from .base import now_iso
from .base import run as _run

MODULE = "M4"
FILENAME = "m4_env.json"
LABEL = "開發環境"
START_MSG = "M4 開發環境健檢..."


def run(cmd):
    # 原 heredoc:stdout + stderr 合併、30 秒逾時、例外回 "error: ..."
    return _run(cmd, timeout=30, merge_stderr=True)


def collect():
    tools = {
        "node":    run("node -v"),
        "npm":     run("npm -v"),
        "npx":     run("npx -v"),
        "python3": run("python3 --version"),
        "pip3":    run("pip3 --version"),
        "ruby":    run("ruby -v"),
        "go":      run("go version"),
        "java":    run("java -version"),
        "git":     run("git --version"),
        "docker":  run("docker --version"),
        "brew":    run("brew --version"),
    }

    npm_doctor    = run("npm doctor") if shutil.which("npm") else "npm not found"
    brew_list     = run("brew list --versions") if shutil.which("brew") else "brew not found"
    pip_outdated_full = run("pip3 list --outdated 2>/dev/null") if shutil.which("pip3") else "pip3 not found"
    pip_outdated  = "\n".join(pip_outdated_full.split("\n")[:22])   # 報告只顯示表頭 + 前 20 列

    # node version managers
    nvm_versions  = run("ls ~/.nvm/versions/node 2>/dev/null || echo 'nvm not found'")
    pyenv_versions= run("pyenv versions 2>/dev/null || echo 'pyenv not found'")

    # ── 結構化「可更新」資料(供修復規則表動態判斷) ──────────────
    brew_outdated_raw = run("brew outdated --quiet 2>/dev/null") if shutil.which("brew") else ""
    brew_outdated = [x for x in brew_outdated_raw.split("\n") if x.strip()] if brew_outdated_raw else []

    # 過舊套件名單(扣掉表頭兩行);pip 工具本身是否過舊另外標出 —
    # 規則表只在「pip 本身過舊」時才長「更新 pip」鈕,否則按了按鈕(只升 pip)項目永遠不會消失
    pip_lines = [l for l in pip_outdated_full.split("\n") if l.strip()] if shutil.which("pip3") else []
    pip_pkgs  = [l.split()[0] for l in pip_lines
                 if not l.startswith("Package") and not l.startswith("---") and not l.lower().startswith("warning")]
    pip_outdated_count = len(pip_pkgs)
    pip_self_outdated  = any(p.lower() == "pip" for p in pip_pkgs)

    npm_g_raw = run("npm outdated -g --parseable 2>/dev/null") if shutil.which("npm") else ""
    npm_global_outdated_count = len([x for x in npm_g_raw.split("\n") if x.strip()]) if npm_g_raw else 0

    return {
      "module": MODULE,
      "scan_time": now_iso(),
      "versions": tools,
      "npm_doctor": npm_doctor,
      "brew_installed_packages": brew_list,
      "pip_outdated": pip_outdated,
      "pip_outdated_count": pip_outdated_count,
      "pip_self_outdated": pip_self_outdated,
      "pip_outdated_packages": pip_pkgs[:50],
      "brew_outdated": brew_outdated,
      "brew_outdated_count": len(brew_outdated),
      "npm_global_outdated_count": npm_global_outdated_count,
      "nvm_versions": nvm_versions,
      "pyenv_versions": pyenv_versions
    }


def summary(r):
    return "  → 工具版本收集完成;brew 可升級 {}、pip 過時 {}、npm 全域過時 {}".format(
        r["brew_outdated_count"], r["pip_outdated_count"], r["npm_global_outdated_count"])
