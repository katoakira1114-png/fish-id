#!/usr/bin/env python3
"""説明文がまだ無い種の短い一覧を出す（大きいファイルを開かずに済ませるため）。

使い方: python3 scripts/worklist.py <科スラグ> [--nearby] [--max 40]
既定は「日本産」で和名のある種だけ。1行 = 学名 <TAB> 和名 <TAB> FishBase の URL
"""
import argparse, csv, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ap = argparse.ArgumentParser()
ap.add_argument("family")
ap.add_argument("--nearby", action="store_true", help="近海のみの種も含める")
ap.add_argument("--max", type=int, default=40)
a = ap.parse_args()
drafts = os.path.join(ROOT, "data", a.family.lower(), "drafts")
rows = [r for r in csv.DictReader(open(os.path.join(ROOT, "data", "species_master.csv"), encoding="utf-8"))
        if r["科"].lower() == a.family.lower()
        and (a.nearby or (r["区分"] == "日本産" and r["和名"] and r["和名"] != "和名なし"))
        and not os.path.exists(os.path.join(drafts, r["学名"] + ".json"))]
for r in rows[:a.max]:
    print(f"{r['学名']}\t{r['和名']}\thttps://www.fishbase.se/summary/{r['SpecCode']}")
print(f"# 残り {len(rows)} 種（うち {min(len(rows), a.max)} 種を表示）")
