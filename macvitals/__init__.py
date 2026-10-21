"""
macvitals — MacVitals(laptop-diagnostics)的唯讀收集套件。

  python3 -m macvitals.collect              # 跑全部 11 模組 → report/data/m{1..11}_*.json
  python3 -m macvitals.collect --only m2 m7 # 只重跑指定模組

每個模組在 macvitals/modules/mNN_*.py,提供 collect() -> dict;
輸出 JSON 的欄位名稱是與 generate_report.py 之間的資料契約,不可改。
"""
