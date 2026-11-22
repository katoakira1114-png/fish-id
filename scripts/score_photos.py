#!/usr/bin/env python3
"""Score candidate photos by how large and clear the fish is (salient-object mask).

Uses the IS-Net general-use salient object model (ONNX, from rembg releases).
Writes data/<family>/photo_scores.csv: url, fg, bbox (x0,y0,x1,y1 as 0-1), score, w, h.
The aspect penalty (tall box = hanging fish / pile) is applied in build_app_data.py.
Only the first N licensed photos per species are scored (all 釣果 photos first).

  pip install onnxruntime pillow numpy
  curl -L -o isnet.onnx https://github.com/danielgatis/rembg/releases/download/v0.0.0/isnet-general-use.onnx
  python scripts/score_photos.py epinephelidae --model isnet.onnx
"""
import argparse, csv, glob, io, os, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import onnxruntime as ort
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALLOWED = {"CC0", "CC-BY", "CC-BY-NC"}
SIZE = 1024


def fetch(url):
    small = url.replace("/large.", "/medium.")  # iNat: 500px is enough for scoring
    for u in (small, url):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "fish-id"}), timeout=30) as r:
                return Image.open(io.BytesIO(r.read())).convert("RGB")
        except Exception:
            continue
    return None


def mask_of(sess, img):
    x = np.asarray(img.resize((SIZE, SIZE), Image.BILINEAR), dtype=np.float32) / 255.0
    x = (x - 0.5) / 1.0
    x = x.transpose(2, 0, 1)[None]
    out = sess.run(None, {sess.get_inputs()[0].name: x})[0][0, 0]
    out = (out - out.min()) / (out.max() - out.min() + 1e-8)
    return out


def measure(m):
    b = m > 0.5
    fg = float(b.mean())
    if fg < 0.01:
        return fg, None, 0.0
    ys, xs = np.nonzero(b)
    x0, x1 = np.percentile(xs, [1, 99]) / SIZE
    y0, y1 = np.percentile(ys, [1, 99]) / SIZE
    bw, bh = max(x1 - x0, 1e-3), max(y1 - y0, 1e-3)
    area = bw * bh
    fill = fg / area
    score = np.sqrt(min(area, 0.6)) * min(fill / 0.55, 1.0)
    cut_l, cut_r = x0 < 0.01, x1 > 0.99
    if cut_l and cut_r:
        score *= 0.6  # fish (or scene) runs off both sides
    elif cut_l or cut_r:
        score *= 0.85
    if area > 0.9 and fill < 0.6:
        score *= 0.5  # whole-frame blob: busy reef/scene, not one fish
    return fg, (round(x0, 3), round(y0, 3), round(x1, 3), round(y1, 3)), round(float(score), 4)


def candidates(path, n):
    rows = [r for r in csv.DictReader(open(path, encoding="utf-8")) if r.get("license") in ALLOWED and r.get("url")]
    caught = [r for r in rows if r.get("context") == "釣果"][: n // 2]
    rest = [r for r in rows if r not in caught]
    return [r["url"] for r in caught + rest][:n]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("families", nargs="+")
    ap.add_argument("--model", default="isnet.onnx")
    ap.add_argument("--per-species", type=int, default=10)
    a = ap.parse_args()
    sess = ort.InferenceSession(a.model, providers=["CPUExecutionProvider"])
    for fam in a.families:
        out_path = os.path.join(ROOT, "data", fam, "photo_scores.csv")
        done = {}
        if os.path.exists(out_path):
            done = {r["url"]: r for r in csv.DictReader(open(out_path, encoding="utf-8"))}
        urls = []
        for p in sorted(glob.glob(os.path.join(ROOT, "data", fam, "photos", "*.csv"))):
            urls += [u for u in candidates(p, a.per_species) if u not in done]
        print(f"[{fam}] {len(urls)} photos to score", flush=True)
        with open(out_path, "a", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            if not done:
                w.writerow(["url", "fg", "x0", "y0", "x1", "y1", "score", "w", "h"])
            with ThreadPoolExecutor(8) as ex:
                for i, (u, img) in enumerate(zip(urls, ex.map(fetch, urls))):
                    if img is None:
                        w.writerow([u, "", "", "", "", "", "-1"]); continue
                    fg, bb, s = measure(mask_of(sess, img))
                    w.writerow([u, round(fg, 3), *(bb or ("", "", "", "")), s, img.width, img.height])
                    if i % 100 == 0:
                        f.flush(); print(f"  {i}/{len(urls)}", flush=True)


if __name__ == "__main__":
    main()
