#!/usr/bin/env python3
"""種名ごとにオープンアクセス論文を探し、候補一覧を data/<科>/literature/<学名>.json に書く。

使い方:
    python3 scripts/find_literature.py <科スラグ> [--limit 10] [--only "Genus species"]

検索先（APIキー不要）:
    - OpenAlex   https://api.openalex.org  （Crossref の DOI をほぼ網羅。is_oa で絞る）
    - J-STAGE    https://api.jstage.jst.go.jp/searchapi/do （日本語の論文・魚類学雑誌など）

ここでは候補を集めるだけ。本文を読んで形質を抜き出すのは別の作業
（tasks/003-literature-evidence.md）で、結果は data/<科>/evidence/<学名>.json に書く。
"""

import argparse
import csv
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT_DIR, "data")
UA = "fish-id-literature/0.1 (private research tool)"

# 同定に効きそうな論文を上に並べるための語
TAXO_WORDS = [
    "new species", "sp. nov", "sp. n.", "revision", "redescription", "review of",
    "taxonom", "first record", "new record", "northernmost record", "identification",
    "morpholog", "key to", "diagnos", "meristic", "synonym", "dna barcod",
    "新種", "新記録", "初記録", "記録", "再記載", "標準和名", "分類",
]


def http_get(url: str, retries: int = 3) -> bytes:
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            if i == retries - 1:
                print(f"  ! {url[:80]}… {e}", file=sys.stderr)
                return b""
            time.sleep(2 * (i + 1))
    return b""


def score(title: str, abstract: str, sci: str) -> int:
    t = (title or "").lower()
    a = (abstract or "").lower()
    s = 0
    if sci.lower() in t:
        s += 5
    elif sci.lower() in a:
        s += 2
    for w in TAXO_WORDS:
        if w in t:
            s += 3
        elif w in a:
            s += 1
    return s


def abstract_from_index(inv: dict) -> str:
    if not inv:
        return ""
    pos = []
    for word, idxs in inv.items():
        for i in idxs:
            pos.append((i, word))
    return " ".join(w for _, w in sorted(pos))


def search_openalex(sci: str, per_page: int = 25) -> list:
    params = {
        "filter": f'title_and_abstract.search:"{sci}",is_oa:true',
        "per_page": str(per_page),
        "select": "id,doi,title,publication_year,authorships,primary_location,"
                  "best_oa_location,open_access,abstract_inverted_index,language",
    }
    url = "https://api.openalex.org/works?" + urllib.parse.urlencode(params)
    raw = http_get(url)
    if not raw:
        return []
    out = []
    for w in json.loads(raw).get("results", []):
        oa = w.get("best_oa_location") or {}
        src = ((w.get("primary_location") or {}).get("source") or {})
        abstract = abstract_from_index(w.get("abstract_inverted_index"))
        authors = [a.get("author", {}).get("display_name", "") for a in w.get("authorships", [])[:6]]
        out.append({
            "title": w.get("title") or "",
            "authors": [a for a in authors if a],
            "year": w.get("publication_year"),
            "journal": src.get("display_name") or "",
            "doi": (w.get("doi") or "").replace("https://doi.org/", ""),
            "oa_url": oa.get("pdf_url") or oa.get("landing_page_url") or (w.get("open_access") or {}).get("oa_url") or "",
            "license": (oa.get("license") or "").upper(),
            "language": w.get("language") or "",
            "found_via": "OpenAlex",
            "score": score(w.get("title") or "", abstract, sci),
        })
    return out


def search_jstage(sci: str, count: int = 20) -> list:
    params = {"service": "3", "text": sci, "count": str(count)}
    url = "https://api.jstage.jst.go.jp/searchapi/do?" + urllib.parse.urlencode(params)
    raw = http_get(url)
    if not raw:
        return []
    ns = {"a": "http://www.w3.org/2005/Atom", "prism": "http://prismstandard.org/namespaces/basic/2.0/"}
    out = []
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return []
    for e in root.findall("a:entry", ns):
        def txt(path):
            el = e.find(path, ns)
            return (el.text or "").strip() if el is not None and el.text else ""
        title = txt("a:article_title/a:en") or txt("a:article_title/a:ja")
        title_ja = txt("a:article_title/a:ja")
        link = e.find("a:article_link/a:ja", ns)
        authors = [(n.text or "").strip() for n in e.findall("a:author/a:en/a:name", ns)][:6]
        out.append({
            "title": title,
            "title_ja": title_ja,
            "authors": authors,
            "year": int(txt("a:pubyear")) if txt("a:pubyear").isdigit() else None,
            "journal": txt("a:material_title/a:ja") or txt("a:material_title/a:en"),
            "doi": txt("prism:doi"),
            "oa_url": (link.text or "").strip() if link is not None and link.text else "",
            "license": "",  # J-STAGE は誌ごとに確認（多くは無料公開。転載はせず形質値と出典のみ記録）
            "language": "ja" if title_ja else "",
            "found_via": "J-STAGE",
            "score": score(title + " " + title_ja, "", sci),
        })
    return out


def species_of(family: str) -> list:
    path = os.path.join(DATA_DIR, family, "traits.csv")
    with open(path, encoding="utf-8") as f:
        return [r["学名"].strip() for r in csv.DictReader(f) if r.get("学名")]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("family")
    ap.add_argument("--limit", type=int, default=10, help="1種あたり残す候補数")
    ap.add_argument("--only", default="", help="この学名だけ検索")
    ap.add_argument("--skip-existing", action="store_true")
    args = ap.parse_args()

    out_dir = os.path.join(DATA_DIR, args.family, "literature")
    os.makedirs(out_dir, exist_ok=True)
    names = [args.only] if args.only else species_of(args.family)
    summary = []
    for i, sci in enumerate(names, 1):
        out_path = os.path.join(out_dir, f"{sci}.json")
        if args.skip_existing and os.path.exists(out_path):
            continue
        hits = search_openalex(sci) + search_jstage(sci)
        seen, merged = set(), []
        for h in sorted(hits, key=lambda x: -x["score"]):
            key = (h["doi"] or h["title"]).lower()
            if not key or key in seen:
                continue
            seen.add(key)
            merged.append(h)
        merged = merged[: args.limit]
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump({"scientific_name": sci, "searched": time.strftime("%Y-%m-%d"),
                       "candidates": merged}, f, ensure_ascii=False, indent=2)
        summary.append((sci, len(merged)))
        print(f"[{i}/{len(names)}] {sci}: {len(merged)}")
        time.sleep(0.3)  # OpenAlex polite rate
    none = [s for s, n in summary if n == 0]
    print(f"done: {len(summary)} species, {len(none)} with no OA paper")


if __name__ == "__main__":
    main()
