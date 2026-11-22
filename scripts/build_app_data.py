#!/usr/bin/env python3
"""Build static JSON datasets for the Fish ID PWA from data/<family>/."""

import argparse
import csv
import glob
import json
import os
import re
from datetime import datetime, timezone

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT_DIR, "data")
APP_DATA_DIR = os.path.join(ROOT_DIR, "app", "data")

ALLOWED_LICENSES = {"CC0", "CC-BY", "CC-BY-NC"}

GENUS_JA_NAMES = {
    # Pomacentridae (スズメダイ科)
    "Abudefduf": "オヤビッチャ属",
    "Amblyglyphidodon": "クラカオスズメダイ属",
    "Amphiprion": "クマノミ属",
    "Cheiloprion": "アツクチスズメダイ属",
    "Chromis": "スズメダイ属",
    "Chrysiptera": "ルリスズメダイ属",
    "Dascyllus": "ミスジリュウキュウスズメダイ属",
    "Dischistodus": "ダンダラスズメダイ属",
    "Neoglyphidodon": "ヒレナガスズメダイ属",
    "Neopomacentrus": "リボンスズメダイ属",
    "Plectroglyphidodon": "イシガキスズメダイ属",
    "Pomacentrus": "ソラスズメダイ属",
    "Pomachromis": "アオスジスズメダイ属",
    "Pycnochromis": "ヒメスズメダイ属",
    "Stegastes": "クロソラスズメダイ属",
    # Epinephelidae (ハタ科)
    "Aethaloperca": "クロハタ属",
    "Anyperodon": "アズキハタ属",
    "Cephalopholis": "ユカタハタ属",
    "Chromileptes": "サラサハタ属",
    "Epinephelus": "マハタ属",
    "Gracila": "タテスジハタ属",
    "Plectropomus": "スジアラ属",
    "Saloptia": "ヤマブキハタ属",
    "Triso": "トビハタ属",
    "Variola": "バラハタ属",
    # Labridae (ベラ科)
    "Anampses": "ススキベラ属",
    "Bodianus": "タキベラ属",
    "Cheilinus": "モチノウオ属",
    "Cheilio": "カマスベラ属",
    "Choerodon": "イラ属",
    "Cirrhilabrus": "イトヒキベラ属",
    "Coris": "カンムリベラ属",
    "Cymolutes": "タテヤマベラ属",
    "Epibulus": "ギチベラ属",
    "Gomphosus": "クギベラ属",
    "Halichoeres": "ホンベラ属",
    "Hemigymnus": "タレクチベラ属",
    "Hologymnosus": "タスキベラ属",
    "Iniistius": "テンス属",
    "Labrichthys": "クロベラ属",
    "Labroides": "ホンソメワケベラ属",
    "Labropsis": "マナベベラ属",
    "Macropharyngodon": "ノドグロベラ属",
    "Novaculichthys": "オビテンスモドキ属",
    "Oxycheilinus": "ホホスジモチノウオ属",
    "Paracheilinus": "クジャクベラ属",
    "Parajulis": "キュウセン属",
    "Pseudocheilinus": "ニセモチノウオ属",
    "Pseudodax": "ブダイベラ属",
    "Pseudojuloides": "オグロベラ属",
    "Pseudolabrus": "ササノハベラ属",
    "Pteragogus": "オハグロベラ属",
    "Semicossyphus": "コブダイ属",
    "Stethojulis": "カミナリベラ属",
    "Suezichthys": "イトベラ属",
    "Thalassoma": "ニシキベラ属",
    "Wetmorella": "ハシナガベラ属",
}
# Genera not listed above get "<shortest species ja name>の仲間" (not an official genus name).


def load_photo_scores(family_dir: str) -> dict:
    """url -> {"score": float, "crop": [x0, y0, x1, y1]} from photo_scores.csv (scripts/score_photos.py)."""
    path = os.path.join(family_dir, "photo_scores.csv")
    out = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                try:
                    score = float(r["score"])
                except ValueError:
                    continue
                crop = None
                if r.get("x0"):
                    crop = [float(r[k]) for k in ("x0", "y0", "x1", "y1")]
                    if r.get("w") and r.get("h"):
                        # Fish are wider than tall; a tall box means a hanging fish or a pile.
                        ar = (crop[2] - crop[0]) * float(r["w"]) / max((crop[3] - crop[1]) * float(r["h"]), 1e-6)
                        if ar < 1.3:
                            score *= max(0.3, ar / 1.3)
                        # Tie-break among capped scores: fuller box = cleaner single fish.
                        fill = float(r["fg"] or 0) / max((crop[2] - crop[0]) * (crop[3] - crop[1]), 1e-6)
                        score = round(score + 0.05 * min(fill, 1.0), 4)
                out[r["url"]] = {"score": score, "crop": crop}
    return out


def load_family_names() -> dict:
    """Return lowercase-slug -> (CanonicalFamily, JapaneseName) from families_summary.csv."""
    summary_path = os.path.join(DATA_DIR, "families_summary.csv")
    mapping = {}
    if os.path.exists(summary_path):
        with open(summary_path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                fam = (row.get("科") or "").strip()
                ja = (row.get("和名") or "").strip()
                if fam:
                    mapping[fam.lower()] = (fam, ja)
    return mapping


def parse_range(raw: str) -> dict:
    """Parse an integer or integer-range trait string like '13' or '12-14'."""
    text = (raw or "").strip()
    if not text:
        return {"raw": "", "min": None, "max": None}
    nums = [int(m) for m in re.findall(r"\b\d+\b", text)]
    if not nums:
        return {"raw": text, "min": None, "max": None}
    return {"raw": text, "min": min(nums), "max": max(nums)}


def load_valid_photos(family_dir: str, sci_name: str, draft_photo_url: str, scores: dict) -> tuple:
    """Select primary CC0/CC-BY/CC-BY-NC photo and up to 6 gallery photos from photos/<sp>.csv."""
    csv_path = os.path.join(family_dir, "photos", f"{sci_name}.csv")
    if not os.path.exists(csv_path):
        return None, []

    valid = []
    with open(csv_path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            lic = (row.get("license") or "").strip()
            url = (row.get("url") or "").strip()
            if not url or lic not in ALLOWED_LICENSES:
                continue
            valid.append(
                {
                    "url": url,
                    "source": (row.get("source") or "").strip(),
                    "license": lic,
                    "author": (row.get("author") or "").strip(),
                    "observed_on": (row.get("observed_on") or "").strip(),
                    "place": (row.get("place") or "").strip(),
                    "life_stage": (row.get("life_stage") or "不明").strip(),
                    "context": (row.get("context") or "不明").strip(),
                }
            )
            sc = scores.get(url)
            if sc:
                valid[-1]["score"] = sc["score"]
                if sc["crop"]:
                    valid[-1]["crop"] = sc["crop"]

    if not valid:
        return None, []

    def rep_score(p):
        if any("score" in v for v in valid):
            # Prefer the photo where the fish is largest and clearest (salient-object score).
            return (-p.get("score", -1),)
        url_match = 0 if draft_photo_url and p["url"] == draft_photo_url else 1
        src_pref = 0 if p["source"] == "FishBase" else 1
        ctx_pref = 0 if p["context"] == "水中" else (1 if p["context"] == "釣果" else 2)
        auth_pref = 0 if p["author"] else 1
        return (url_match, src_pref, ctx_pref, auth_pref)

    primary = min(valid, key=rep_score)
    if primary.get("score", 1) < 0:
        primary = valid[0]

    gallery = [primary]
    seen_urls = {primary["url"]}
    # Try to include variety: at least one caught photo if available, then remaining priority photos
    caught = [p for p in valid if p["context"] == "釣果" and p["url"] not in seen_urls]
    for p in caught[:2]:
        gallery.append(p)
        seen_urls.add(p["url"])
    for p in valid:
        if len(gallery) >= 6:
            break
        if p["url"] not in seen_urls:
            gallery.append(p)
            seen_urls.add(p["url"])

    return primary, gallery


def build_family(family_arg: str, family_names: dict) -> dict:
    slug = family_arg.strip().lower()
    family_dir = os.path.join(DATA_DIR, slug)
    traits_path = os.path.join(family_dir, "traits.csv")
    drafts_dir = os.path.join(family_dir, "drafts")

    if not os.path.exists(traits_path):
        raise FileNotFoundError(f"Missing traits.csv: {traits_path}")

    scores = load_photo_scores(family_dir)
    canonical_family, family_ja = family_names.get(slug, (slug.capitalize(), ""))

    with open(traits_path, encoding="utf-8") as f:
        traits_rows = list(csv.DictReader(f))

    species_list = []
    for tr in sorted(traits_rows, key=lambda r: r["学名"]):
        sci = tr["学名"].strip()
        spec_code = int(tr["SpecCode"])
        genus = sci.split()[0]
        genus_ja = GENUS_JA_NAMES.get(genus, "")

        draft_path = os.path.join(drafts_dir, f"{sci}.json")
        draft = {}
        if os.path.exists(draft_path):
            with open(draft_path, encoding="utf-8") as df:
                draft = json.load(df)

        # Merge missing_traits into blank trait cells
        merged = dict(tr)
        mt_obj = draft.get("missing_traits", {}) or {}
        mt_vals = mt_obj.get("values", {}) or {}
        filled_keys = []
        for k, v in mt_vals.items():
            v_str = str(v or "").strip()
            if k in merged and not (merged[k] or "").strip() and v_str:
                merged[k] = v_str
                filled_keys.append(k)

        draft_photo_url = ((draft.get("photo_url") or {}).get("value") or "").strip()
        primary_photo, gallery = load_valid_photos(family_dir, sci, draft_photo_url, scores)

        ja_obj = draft.get("ja_name") or {}
        cp_obj = draft.get("color_pattern") or {}
        fm_obj = draft.get("field_marks") or {}
        sim_obj = draft.get("similar_species") or {}

        species_entry = {
            "spec_code": spec_code,
            "scientific_name": sci,
            "genus": genus,
            "genus_ja": genus_ja,
            "ja_name": (ja_obj.get("value") or "").strip(),
            "ja_name_source": (ja_obj.get("source") or "").strip(),
            "en_name": (merged.get("英名") or "").strip(),
            "color_pattern": (cp_obj.get("value") or "").strip(),
            "color_pattern_source": (cp_obj.get("source") or "").strip(),
            "field_marks": fm_obj.get("value") or [],
            "field_marks_source": (fm_obj.get("source") or "").strip(),
            "similar_species": sim_obj.get("value") or [],
            "similar_species_source": (sim_obj.get("source") or "").strip(),
            "photo": primary_photo,
            "photos": gallery,
            "traits": {
                "dorsal_spines": parse_range(merged.get("背鰭棘数", "")),
                "dorsal_soft_rays": parse_range(merged.get("背鰭軟条数", "")),
                "anal_spines": parse_range(merged.get("臀鰭棘数", "")),
                "anal_soft_rays": parse_range(merged.get("臀鰭軟条数", "")),
                "pectoral_rays": parse_range(merged.get("胸鰭条数", "")),
                "lateral_line_scales": parse_range(merged.get("側線鱗数", "")),
                "max_length": (merged.get("最大体長") or "").strip(),
                "body_shape": (merged.get("体形") or "").strip(),
                "caudal_fin": (merged.get("尾鰭の形") or "").strip(),
                "mouth_pos": (merged.get("口の位置") or "").strip(),
                "spots": (merged.get("斑点") or "").strip(),
                "bars": (merged.get("横縞") or "").strip(),
                "stripes": (merged.get("縦縞") or "").strip(),
                "striking_features": (merged.get("目立つ特徴") or "").strip(),
            },
            "missing_traits_filled": sorted(filled_keys),
            "missing_traits_source": (mt_obj.get("source") or "").strip() if filled_keys else "",
        }
        species_list.append(species_entry)

    # Group genera
    genera_map = {}
    for sp in species_list:
        genera_map.setdefault(sp["genus"], []).append(sp)
    for g, sps in genera_map.items():
        named = [s for s in sps if s["ja_name"] and "なし" not in s["ja_name"]]
        examples = [s["ja_name"] for s in sorted(named, key=lambda s: len(s["ja_name"]))][:3]
        ja = GENUS_JA_NAMES.get(g) or (f"{examples[0]}の仲間" if examples else f"{g}属")
        for s in sps:
            s["genus_ja"] = ja
        with_photo = [s for s in sps if s["photo"]]
        best = max(with_photo, key=lambda s: s["photo"].get("score", 0)) if with_photo else sps[0]
        genera_map[g] = {
            "genus": g,
            "ja_name": ja,
            "ja_name_official": g in GENUS_JA_NAMES,
            "examples_ja": examples,
            "species_count": len(sps),
            "representative_species": best["scientific_name"],
            "photo": best["photo"],
        }

    genera_list = sorted(genera_map.values(), key=lambda x: x["genus"])

    payload = {
        "family": canonical_family,
        "family_ja": family_ja,
        "family_slug": slug,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "species_count": len(species_list),
        "genera_count": len(genera_list),
        "genera": genera_list,
        "species": species_list,
    }

    os.makedirs(APP_DATA_DIR, exist_ok=True)
    out_path = os.path.join(APP_DATA_DIR, f"{slug}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    with_photo = sum(1 for s in species_list if s["photo"])
    print(
        f"[{slug}] Wrote {out_path}: {len(species_list)} species, "
        f"{len(genera_list)} genera, {with_photo}/{len(species_list)} with CC photos"
    )
    return payload


def update_families_manifest() -> None:
    entries = []
    for p in sorted(glob.glob(os.path.join(APP_DATA_DIR, "*.json"))):
        if os.path.basename(p) == "families.json":
            continue
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        entries.append(
            {
                "slug": d["family_slug"],
                "family": d["family"],
                "family_ja": d["family_ja"],
                "species_count": d["species_count"],
                "genera_count": d["genera_count"],
                "file": f"data/{os.path.basename(p)}",
            }
        )
    manifest_path = os.path.join(APP_DATA_DIR, "families.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump({"families": entries}, f, ensure_ascii=False, indent=2)
    print(f"Updated {manifest_path} ({len(entries)} families)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build PWA JSON data for fish families.")
    parser.add_argument(
        "families",
        nargs="*",
        help="Family folder names under data/ (e.g., pomacentridae labridae)",
    )
    parser.add_argument(
        "--family",
        action="append",
        dest="flag_families",
        help="Optional family folder name under data/",
    )
    args = parser.parse_args()

    targets = list(args.families or []) + list(args.flag_families or [])
    if not targets:
        targets = ["pomacentridae"]

    family_names = load_family_names()
    for fam in targets:
        build_family(fam, family_names)
    update_families_manifest()


if __name__ == "__main__":
    main()
