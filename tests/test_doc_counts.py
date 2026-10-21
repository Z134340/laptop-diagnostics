#!/usr/bin/env python3
"""
文件數字檢查的測試(純標準函式庫):python3 -m unittest discover -s tests -v

真實 repo 要通過 scripts/check_doc_counts.py;另用暫存副本證明檢查器抓得到過時數字
(阿拉伯數字、中文數字)與「句型失效、整份文件找不到數字字樣」的情形,避免它變成永遠通過。
"""
import shutil, subprocess, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_doc_counts.py"
sys.path.insert(0, str(ROOT / "scripts"))
import check_doc_counts as cdc


def run_checker(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)


class TestRepoDocs(unittest.TestCase):
    def test_docs_match_code(self):
        r = run_checker()
        self.assertEqual(r.returncode, 0, "文件數字與程式碼不一致:\n" + r.stdout + r.stderr)

    def test_code_facts_are_sane(self):
        f = cdc.code_facts(ROOT)
        self.assertGreater(f["rules"], 0)
        self.assertLessEqual(f["oneclick"], f["rules"])
        self.assertGreater(f["actions"], 0)
        self.assertEqual(f["tabs"], f["modules"] + 1)


class TestChecker(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for rel in ("generate_report.py", "repair_server.py", *cdc.DOCS):
            dst = self.root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / rel, dst)

    def tearDown(self):
        self.tmp.cleanup()

    def append(self, rel, text):
        with open(self.root / rel, "a", encoding="utf-8") as fh:
            fh.write("\n" + text + "\n")

    def test_copy_passes_unmodified(self):
        r = run_checker("--root", str(self.root))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_flags_stale_arabic_number_with_location(self):
        self.append("README.md", "共 99 條規則")
        r = run_checker("--root", str(self.root))
        self.assertEqual(r.returncode, 1)
        self.assertRegex(r.stderr, r"README\.md:\d+: 寫 99")

    def test_flags_stale_chinese_numeral(self):
        self.append("CLAUDE.md", "收集九模組資料")
        r = run_checker("--root", str(self.root))
        self.assertEqual(r.returncode, 1)
        self.assertIn("CLAUDE.md", r.stderr)
        self.assertIn("寫 9", r.stderr)

    def test_flags_wrong_whitelist_action_count_and_module_range(self):
        self.append(".claude/skills/laptop-diagnostics/SKILL.md", "13 個白名單動作;寫 `report/data/m{1..9}_*.json`;M1–M9 分頁")
        r = run_checker("--root", str(self.root))
        self.assertEqual(r.returncode, 1)
        self.assertIn("寫 13", r.stderr)
        self.assertGreaterEqual(r.stderr.count("寫 9"), 2)

    def test_quantifier_uses_of_one_are_not_totals(self):
        self.append("README.md", "任一模組例外會中止;新增一種修復 = 加 1 條規則 + 1 個白名單動作")
        r = run_checker("--root", str(self.root))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_fails_when_a_doc_has_no_checkable_claims(self):
        (self.root / "run.sh").write_text("#!/usr/bin/env bash\necho hi\n", encoding="utf-8")
        r = run_checker("--root", str(self.root))
        self.assertEqual(r.returncode, 1)
        self.assertIn("run.sh", r.stderr)
        self.assertIn("找不到任何可檢查的數字字樣", r.stderr)


class TestToInt(unittest.TestCase):
    def test_conversions(self):
        for text, want in [("27", 27), ("九", 9), ("十", 10), ("十一", 11), ("二十", 20), ("二十四", 24)]:
            self.assertEqual(cdc.to_int(text), want, text)


if __name__ == "__main__":
    unittest.main()
