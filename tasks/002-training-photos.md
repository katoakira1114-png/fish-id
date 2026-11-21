# 002 学習用写真を集める（スズメダイ科56種）

目的: 写真から候補を出すモデル用に、同定の確かな写真を種ごとに集める。画像そのものはリポジトリに入れず、URLとライセンスの一覧を作る。

## 集める元（優先順）
1. iNaturalist: 研究用グレードで、ライセンスが CC0 / CC-BY / CC-BY-NC の写真。API: https://api.inaturalist.org/v1/observations?taxon_name=<学名>&quality_grade=research&photo_license=cc0,cc-by,cc-by-nc&per_page=200
2. GBIF の画像付き記録: https://api.gbif.org/v1/occurrence/search?scientificName=<学名>&mediaType=StillImage&limit=300 （ライセンスが CC のものだけ）
3. FishBase の写真一覧（種ページの Pictures）

## 出力
`data/pomacentridae/photos/<学名>.csv` 列: url, source, license, author, observed_on, place, lat, lon, life_stage（幼魚/成魚/不明）
- 1種あたり最大200枚。八重山・沖縄・台湾・フィリピンの記録を優先して並べる。
- 幼魚と成魚で見た目が違う種は life_stage をできるだけ埋める。分からなければ「不明」。
- 魚が写っていないもの、標本写真、複数種が写るものは除く。

## PR に書くこと
種ごとの枚数の表と、50枚未満の種の一覧。
