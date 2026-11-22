#!/usr/bin/env python3
"""GBIF の画像付き記録から、科ごとの写真一覧 data/<科>/photos/<学名>.csv を作る（画像は保存しない）。

使い方: python3 scripts/fetch_gbif_photos.py <科スラグ>... [--max 30] [--force]
ライセンスは CC0 / CC-BY / CC-BY-NC のみ。日本・台湾・韓国・フィリピンの記録を先に並べる。
iNaturalist 経由の「釣果」判定はしない（context は不明）。釣果優先の選別は task 002 の手順で上書きしてよい。
"""
import argparse, csv, json, os, sys, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
COLS = ["url", "source", "license", "author", "observed_on", "place", "lat", "lon", "life_stage", "context"]
NEAR = {"JP": 0, "TW": 1, "KR": 2, "PH": 3, "CN": 4}


def lic(u):
    u = (u or "").lower()
    if "publicdomain/zero" in u or u == "cc0_1_0": return "CC0"
    if "by-nc-nd" in u or "by-nc-sa" in u or "by-sa" in u or "by-nd" in u: return ""
    if "by-nc" in u or u == "cc_by_nc_4_0": return "CC-BY-NC"
    if "/by/" in u or u == "cc_by_4_0": return "CC-BY"
    return ""


def get(url):
    for i in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "fish-id/0.1"}), timeout=60) as r:
                return json.load(r)
        except Exception as e:  # noqa: BLE001
            time.sleep(3 * (i + 1)); err = e
    print(f"! {url[:90]} {err}", file=sys.stderr); return {}


def photos_for(sci, mx):
    q = urllib.parse.urlencode({"scientificName": sci, "mediaType": "StillImage", "limit": 300})
    out = []
    for o in get("https://api.gbif.org/v1/occurrence/search?" + q).get("results", []):
        if (o.get("species") or o.get("scientificName", "")).split(" (")[0] != sci and not o.get("scientificName", "").startswith(sci):
            continue
        for m in o.get("media", []):
            l = lic(m.get("license") or o.get("license"))
            if m.get("type") != "StillImage" or not l or not m.get("identifier"): continue
            url = m["identifier"].replace("/original.", "/large.") if "inaturalist" in m["identifier"] else m["identifier"]
            out.append({"url": url, "source": f"GBIF {o.get('datasetName') or o.get('publisher') or ''}".strip(),
                        "license": l, "author": m.get("rightsHolder") or m.get("creator") or o.get("recordedBy") or "",
                        "observed_on": (o.get("eventDate") or "")[:10],
                        "place": o.get("locality") or o.get("country") or "", "lat": o.get("decimalLatitude") or "",
                        "lon": o.get("decimalLongitude") or "", "life_stage": "不明", "context": "不明",
                        "_k": NEAR.get(o.get("countryCode"), 9)})
            break  # 1記録1枚
    seen, res = set(), []
    for p in sorted(out, key=lambda p: p["_k"]):
        if p["url"] in seen: continue
        seen.add(p["url"]); p.pop("_k"); res.append(p)
    return res[:mx]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("families", nargs="+"); ap.add_argument("--max", type=int, default=30)
    ap.add_argument("--force", action="store_true"); a = ap.parse_args()
    jobs = []
    for fam in a.families:
        d = os.path.join(DATA, fam)
        for r in csv.DictReader(open(os.path.join(d, "traits.csv"), encoding="utf-8")):
            p = os.path.join(d, "photos", f"{r['学名']}.csv")
            if a.force or not os.path.exists(p): jobs.append((r["学名"], p))

    def run(job):
        sci, p = job; ph = photos_for(sci, a.max)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, COLS); w.writeheader(); w.writerows(ph)
        return sci, len(ph)
    with ThreadPoolExecutor(6) as ex:
        res = list(ex.map(run, jobs))
    print(f"{len(res)}種, 0枚 {sum(1 for _, n in res if n == 0)}種")


if __name__ == "__main__":
    main()
