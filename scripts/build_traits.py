#!/usr/bin/env python3
"""FishBase（v24.07 Parquet）から科ごとの traits.csv を作る。

使い方:
    python3 scripts/build_traits.py Carangidae Lutjanidae ...   # 科名（FishBase の科）
    python3 scripts/build_traits.py --all                        # 日本産のいる全科
既存の traits.csv は上書きしない（--force で上書き）。対象は species_master.csv の「日本産」。
"""
import argparse, csv, os, sys, urllib.request
import duckdb

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
FB = "https://data.source.coop/cboettig/fishbase/fb/v24.07/parquet/"
CACHE = os.environ.get("FB_CACHE", os.path.expanduser("~/.cache/fishbase"))
COLS = ["SpecCode", "学名", "英名", "最大体長", "体形", "背鰭棘数", "背鰭軟条数", "臀鰭棘数", "臀鰭軟条数",
        "胸鰭条数", "側線鱗数", "尾鰭の形", "口の位置", "斑点", "横縞", "縦縞", "目立つ特徴"]


def table(name):
    os.makedirs(CACHE, exist_ok=True)
    p = os.path.join(CACHE, f"{name}.parquet")
    if not os.path.exists(p):
        urllib.request.urlretrieve(FB + f"{name}.parquet", p)
    return p


def rng(a, b):
    def n(x):
        try:
            return None if x is None or x != x else int(x)
        except (TypeError, ValueError):
            return None
    a, b = n(a), n(b)
    if a is None and b is None:
        return ""
    if a is None or b is None or a == b:
        return str(a if a is not None else b)
    return f"{min(a, b)}-{max(a, b)}"


def s(x):
    return "" if x is None or x != x else str(x).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("families", nargs="*")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    master = list(csv.DictReader(open(os.path.join(DATA, "species_master.csv"), encoding="utf-8")))
    jp = [r for r in master if r["区分"] == "日本産"]
    fams = sorted({r["科"] for r in jp}) if a.all else a.families
    con = duckdb.connect()
    sp_path, md_path = table("species"), table("morphdat")
    for fam in fams:
        rows = [r for r in jp if r["科"] == fam]
        if not rows:
            print(f"{fam}: 日本産なし", file=sys.stderr); continue
        out = os.path.join(DATA, fam.lower(), "traits.csv")
        if os.path.exists(out) and not a.force:
            print(f"{fam}: 既存のためスキップ"); continue
        codes = ",".join(str(int(r["SpecCode"])) for r in rows)
        sp = {int(x[0]): x for x in con.execute(
            f"select SpecCode, FBname, Length from '{sp_path}' where SpecCode in ({codes})").fetchall()}
        md = {}
        for x in con.execute(f"""select Speccode, BodyShapeI, DorsalSpinesMin, DorsalSpinesMax, DorsalSoftRaysMin,
                DorsalSoftRaysMax, AnalFinSpinesMin, AnalFinSpinesMax, Araymin, Araymax, Praymin, Praymax,
                ScalesLateralmin, ScalesLateralmax, CShape, PosofMouth, SpotsTTI, VerStripesTTI, HorStripesTTI,
                StrikingFeatures from '{md_path}' where Speccode in ({codes}) order by autoctr""").fetchall():
            md.setdefault(int(x[0]), x)  # 最初の記録を使う
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f); w.writerow(COLS)
            for r in sorted(rows, key=lambda r: r["学名"]):
                c = int(r["SpecCode"]); p = sp.get(c, (c, "", None)); m = md.get(c)
                ln = "" if p[2] is None or p[2] != p[2] else f"{float(p[2]):g}"
                if m:
                    w.writerow([c, r["学名"], s(p[1]), ln, s(m[1]), rng(m[2], m[3]), rng(m[4], m[5]), rng(m[6], m[7]),
                                rng(m[8], m[9]), rng(m[10], m[11]), rng(m[12], m[13]), s(m[14]), s(m[15]), s(m[16]),
                                s(m[17]), s(m[18]), s(m[19])])
                else:
                    w.writerow([c, r["学名"], s(p[1]), ln] + [""] * 13)
        print(f"{fam}: {len(rows)}種 → {os.path.relpath(out, ROOT)} (形態データあり {sum(1 for r in rows if int(r['SpecCode']) in md)})")


if __name__ == "__main__":
    main()
