#!/usr/bin/env python3
"""短い形式の data/<科>/drafts.jsonl を、1種1ファイルの下書き（task 001 形式）に展開する。

使い方: python3 scripts/expand_drafts.py <科スラグ>...
drafts.jsonl は1行1種: {"sci": 学名, "color": 体色, "marks": [見分け点], "similar": [学名], "src": 出典}
和名・SpecCode は species_master.csv から自動で入る。既にある下書きは上書きしない。
"""
import csv, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
master = {r["学名"]: r for r in csv.DictReader(open(os.path.join(ROOT, "data", "species_master.csv"), encoding="utf-8"))}
for fam in sys.argv[1:]:
    d = os.path.join(ROOT, "data", fam.lower())
    src_path = os.path.join(d, "drafts.jsonl")
    if not os.path.exists(src_path):
        print(f"{fam}: drafts.jsonl がありません"); continue
    os.makedirs(os.path.join(d, "drafts"), exist_ok=True)
    made, bad = 0, []
    for n, line in enumerate(open(src_path, encoding="utf-8"), 1):
        line = line.strip()
        if not line:
            continue
        try:
            x = json.loads(line)
            m = master[x["sci"]]
            assert x.get("src"), "src なし"
        except Exception as e:
            bad.append(f"{n}行目: {e}"); continue
        out = os.path.join(d, "drafts", x["sci"] + ".json")
        if os.path.exists(out):
            continue
        s = x["src"]
        json.dump({
            "scientific_name": x["sci"], "spec_code": int(m["SpecCode"]),
            "ja_name": {"value": "" if m["和名"] == "和名なし" else m["和名"], "source": "日本産魚類全種目録（本村, 2026）" if m["和名"] else ""},
            "color_pattern": {"value": x.get("color", ""), "source": s},
            "field_marks": {"value": x.get("marks", [])[:3], "source": s},
            "similar_species": {"value": x.get("similar", []), "source": s},
            "photo_url": {"value": "", "source": ""},
            "missing_traits": {"values": {}, "source": ""},
        }, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        made += 1
    print(f"{fam}: {made} 種を展開" + (f" / エラー {len(bad)}: " + "; ".join(bad[:5]) if bad else ""))
