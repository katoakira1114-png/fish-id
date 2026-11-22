# タスク 004: 科ごとの説明文（下書き）を作る（汎用）

traits.csv と photos/ は作成済み（scripts/build_traits.py・scripts/fetch_gbif_photos.py）。この作業は説明文だけ。

## 出力
`data/<科スラグ>/drafts/<学名>.json`（task 001 と同じ形式: ja_name, color_pattern, field_marks（最大3つ）, similar_species, photo_url, missing_traits。すべての項目に source）

## ルール
- 和名は data/species_master.csv の和名を使う（空欄の種は空のまま。「近海のみ」の種は和名なしでよい）。
- 色彩・見分け点は図鑑や論文の記述を**自分の言葉で短く**。本文の転載はしない。出典（書名・URL・DOI）を必ず付ける。根拠のない推測は書かない（その種は飛ばして PR に一覧）。
- field_marks は釣り上げた魚・水中写真の両方で見て分かることを優先。
- similar_species は同じ科で間違えやすい種の学名（日本産・近海のみ両方から）。
- 終わったら `python3 scripts/build_app_data.py <科スラグ>...` を実行して app/data を更新、`app/sw.js` の APP_CACHE 番号を +1。
- PR 本文に、科ごとの「下書きを作った種数 / 全種数」と、飛ばした種の一覧。`Closes #番号`。

## 進め方
1 Issue に複数の科がある場合、科ごとにコミットを分けてよい。種数が多くて終わらないときは、できた科だけで PR を出し、Issue に残りを書いて開いたままにする。
