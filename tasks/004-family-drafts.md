# タスク 004: 科ごとの説明文（下書き）を作る（汎用・節約版）

traits.csv と photos/ は作成済み。この作業は説明文だけ。対象は**日本産で和名のある種だけ**（近海のみの種は作らない）。

## 手順
1. `python3 scripts/worklist.py <科スラグ>` で、まだ説明文の無い種（学名・和名・FishBase の URL）を出す。最大40種。
2. 各種の FishBase の種ページを1回だけ読み、`data/<科スラグ>/drafts.jsonl` に**1種1行**で追記する:
   `{"sci":"学名","color":"体色・模様を1文","marks":["見分け点","最大3つ"],"similar":["間違えやすい同じ科の学名"],"src":"FishBase (URL)"}`
3. `python3 scripts/expand_drafts.py <科スラグ> | tail -1`（和名・SpecCode を入れて1種1ファイルに展開する。自分で JSON ファイルを1つずつ書かない）。
4. `python3 scripts/build_app_data.py <科スラグ> | tail -1`、`app/sw.js` の APP_CACHE 番号を +1。
5. PR を出す。本文は「科ごとの 作った種数 / 残り種数」と飛ばした種だけ。

## ルール
- 日本語で、自分の言葉で短く（color は60字以内、marks は各30字以内）。本文の転載はしない。
- marks は釣り上げた魚で見て分かることを優先（体色、斑紋、鰭の形、口や歯）。
- ページに記述が無い種は推測で書かず、飛ばす。
- 1 Issue に複数の科があるときは、順に進めて合計40種で PR を出して止まる。残りは次の回に同じ Issue で続ける。
