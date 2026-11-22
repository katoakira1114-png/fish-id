# タスク 003: オープンアクセス論文から同定根拠を集める（科ごと）

## 目的
種名ごとに論文を探し、無料で読める論文に書かれた識別形質（鰭条数・側線鱗数・鰓耙数・体色・類似種との区別点など）を**値と出典だけ**記録して、アプリの「論文の同定根拠」に表示する。

## 手順（1 Issue = 1科）
1. 候補集め: `python3 scripts/find_literature.py <科スラグ>`
   - OpenAlex（is_oa）と J-STAGE を種名で検索し、`data/<科>/literature/<学名>.json` に候補を最大10本書く（同定向きの論文が上）。
   - このファイルもコミットする（検索した証拠。0本の種も残す）。
2. 抽出: 各種の候補を上から読み、同定に効く記述を `data/<科>/evidence/<学名>.json` に書く（形式は下）。1種あたり論文3本まで・根拠10件までで十分。
3. アプリに載せる: `python3 scripts/build_app_data.py <科スラグ>` を実行し、`app/sw.js` の `APP_CACHE` の番号を1つ上げる。
4. PR 本文に: 根拠が付いた種数／候補0本の種数／既存 traits.csv と値が食い違った種（下記）を書き、`Closes #番号`。

## evidence ファイルの形式
```json
{
  "scientific_name": "Epinephelus akaara",
  "evidence": [
    {
      "trait": "dorsal_soft_rays",
      "value": "16-17",
      "vs": ["Epinephelus awoara"],
      "note": "アオハタは15-16（日本語で短く、自分の言葉で）",
      "source": {
        "cite": "著者 (年) 題名. 誌名 巻: ページ",
        "doi": "10.xxxx/xxxx",
        "url": "DOI が無いときの本文URL",
        "where": "Table 2 / p.5",
        "license": "CC-BY"
      }
    }
  ]
}
```
- `trait` は次のどれか: dorsal_spines, dorsal_soft_rays, anal_spines, anal_soft_rays, pectoral_rays, pelvic_rays, lateral_line_scales, lateral_line_pored_scales, gill_rakers, vertebrae, scale_rows, body_depth, head_length, color, juvenile_color, distinction, other
- `value` は数値なら範囲（例 `16-17`）。体色や区別点は短い日本語で要約。
- `vs` は区別の相手（学名）。無ければ空配列。

## ルール（必ず守る）
- **本文・図・表を転載しない。** 記録するのは形質の値と、自分の言葉の短い要約と、出典だけ。写真は持ってこない。
- 読むのは無料で公開されている本文だけ。ログインや購読が必要なもの、海賊版サイト（Sci-Hub 等）は使わない。
- 出典（doi か url）の無い根拠は書かない。推測で埋めない。
- 標本が日本以外の場合は note に「台湾標本」などと書く。
- 既存 `traits.csv`（FishBase 由来）と論文の値が食い違ったら、evidence に論文の値を書き、PR 本文に一覧で挙げる（traits.csv は書き換えない。Claude が判断する）。
- 学名が論文で別名（シノニム）になっていたら note に「論文では旧名 X」と書く。

## 優先順
ハタ科 → ベラ科 → スズメダイ科 → 以後 ROADMAP の科ができた順。釣りで出る種を先に。
