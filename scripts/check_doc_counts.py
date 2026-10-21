#!/usr/bin/env python3
"""
文件數字檢查(純標準函式庫):python3 scripts/check_doc_counts.py [--root DIR]

以程式碼為準,檢查文件裡寫的數字有沒有過時:
  規則數      generate_report.py 的 RULES 條數
  可一鍵規則數  RULES 中 action 不是 None 的條數
  白名單動作數  repair_server.py 的 ACTIONS 鍵數
  模組數      固定 11(M1–M11,diagnose.sh 寫 report/data/m{1..11}_*.json);報告分頁 = 模組 + 摘要頁
然後 grep README.md、CLAUDE.md、.claude/skills/laptop-diagnostics/SKILL.md、run.sh 裡的
「N 條規則 / N 種可一鍵 / N 個白名單動作 / N 模組 / N 維度 / N 個分頁 / M1–MN / m{1..N}」字樣
(N 可寫阿拉伯數字或中文數字),任何一處和程式碼不符就列出位置並以 1 退出。

新增或移除規則/動作/模組後跑一次;數字寫法若換了新句型,在下方 CLAIMS 補一條 pattern。
"""
import argparse
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULES = 11  # M1–M11(固定值;真的多一個模組時,連同 diagnose.sh / generate_report.py 一起改這裡)
DOCS = (
    "README.md",
    "CLAUDE.md",
    ".claude/skills/laptop-diagnostics/SKILL.md",
    "run.sh",
)

_CN = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
_NUM = r"(?<![A-Za-z0-9])(\d+|[一二三四五六七八九]?十[一二三四五六七八九]?|[一二三四五六七八九])"
_DIGITS = r"(\d+)"  # 緊接在 M / { 之後的數字(不能套用 _NUM 的 lookbehind)

# (事實名稱, 句型)。句型裡的 <N> 代表要比對的數字。
CLAIMS = (
    ("rules", r"<N>\s*條規則"),
    ("rules", r"規則表\s*<N>\s*條"),
    ("rules", r"`?RULES`?\s*<N>\s*條"),
    ("oneclick", r"<N>\s*種可一鍵"),
    ("actions", r"<N>\s*個白名單動作"),
    ("actions", r"白名單動作\s*[（(]\s*<N>\s*[）)]"),
    ("modules", r"<N>\s*(?:個\s*)?(?:診斷)?模組"),
    ("modules", r"<N>\s*維度"),
    ("tabs", r"<N>\s*個\s*(?:tab|分頁)"),
    ("modules", r"M1\s*[–-]\s*M<D>"),
    ("modules", r"m\\?\{1\.\.<D>\\?\}"),
)
LABELS = {
    "rules": "RULES 條數",
    "oneclick": "可一鍵規則數",
    "actions": "白名單動作數",
    "modules": "模組數",
    "tabs": "報告分頁數(摘要 + 模組)",
}


def to_int(s):
    """'27' / '九' / '十' / '十一' / '二十' / '二十四' → int。"""
    if s.isdigit():
        return int(s)
    if "十" in s:
        tens, _, ones = s.partition("十")
        return (_CN[tens] if tens else 1) * 10 + (_CN[ones] if ones else 0)
    return _CN[s]


def _top_level_value(tree, name):
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == name for t in node.targets
        ):
            return node.value
    raise SystemExit(f"找不到頂層變數 {name}")


def _parse(path):
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def code_facts(root):
    """用 ast 讀(不 import——generate_report.py 載入時會去讀掃描資料)。"""
    rules = _top_level_value(_parse(root / "generate_report.py"), "RULES").elts
    oneclick = 0
    for rule in rules:
        for key, val in zip(rule.keys, rule.values):
            if isinstance(key, ast.Constant) and key.value == "action":
                if not (isinstance(val, ast.Constant) and val.value is None):
                    oneclick += 1
    actions = _top_level_value(_parse(root / "repair_server.py"), "ACTIONS").keys
    return {
        "rules": len(rules),
        "oneclick": oneclick,
        "actions": len(actions),
        "modules": MODULES,
        "tabs": MODULES + 1,
    }


def doc_claims(root, docs=DOCS):
    """回傳 [(相對路徑, 行號, 事實名稱, 文件寫的數字, 原文片段)]。"""
    patterns = [
        (fact, re.compile(p.replace("<N>", _NUM).replace("<D>", _DIGITS)))
        for fact, p in CLAIMS
    ]
    found = []
    for rel in docs:
        path = root / rel
        if not path.is_file():
            raise SystemExit(f"找不到文件:{rel}")
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for fact, pat in patterns:
                for m in pat.finditer(line):
                    n = to_int(m.group(1))
                    if n < 2:  # 「任一模組」「加 1 條規則」是量詞用法,不是總數
                        continue
                    found.append((rel, lineno, fact, n, m.group(0)))
    return found


def check(root):
    facts = code_facts(root)
    claims = doc_claims(root)
    problems = [
        f"{rel}:{lineno}: 寫 {got},程式碼為 {facts[fact]}({LABELS[fact]})——「{text}」"
        for rel, lineno, fact, got, text in claims
        if got != facts[fact]
    ]
    for rel in DOCS:  # 句型失效時不能無聲通過:每份文件至少要有一處可檢查的數字
        if not any(c[0] == rel for c in claims):
            problems.append(f"{rel}: 找不到任何可檢查的數字字樣(文件改寫了?請更新 CLAIMS)")
    return facts, claims, problems


def main(argv=None):
    ap = argparse.ArgumentParser(description="檢查文件裡的規則/動作/模組數字是否與程式碼一致")
    ap.add_argument("--root", type=Path, default=ROOT, help="repo 根目錄(預設:此腳本的上一層)")
    args = ap.parse_args(argv)
    facts, claims, problems = check(args.root.resolve())
    print("程式碼為準:" + "、".join(f"{LABELS[k]} {v}" for k, v in facts.items()))
    print(f"已檢查 {len(DOCS)} 份文件、{len(claims)} 處數字字樣。")
    if problems:
        print(f"\n發現 {len(problems)} 處不一致:", file=sys.stderr)
        for p in problems:
            print("  " + p, file=sys.stderr)
        return 1
    print("OK:文件數字與程式碼一致。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
