# CITY CONTENT LAB

Navara × PLATEAU × Blender × Creative Coding で、実在する3D都市モデルから「これは面白い」「どうやって作ったんだ」「自分の街でも見てみたい」と感じる作品を、自律的に発見・制作し続けるクリエイティブスタジオ。

- 公開サイト: https://ogichon.github.io/city-content-lab/
- 姉妹repo（技術検証）: https://github.com/ogichon/navara-plateau-proto
- 運用方針: [AGENTS.md](AGENTS.md) / ビジョン: [docs/vision.md](docs/vision.md) / ロードマップ: [docs/roadmap.md](docs/roadmap.md)

## 構成
- `/` トップ（コンセプト、採用作品への導線、実験一覧）
- `/viewer.html` レシピ駆動の共通ビューア（場所・カメラ・素材・時刻・演出をレシピで切替）
- `/compare.html` コンタクトシート（同一条件で複数案を横並び比較、各カードからビューアへ）
- `/gallery.html` 採用作品ギャラリー（ユーザー評価で採用されたものだけ）

## 実験
| ID | 企画 | 状態 |
|---|---|---|
| EXP-003 | MATERIAL TOKYO — 東京を異なる素材で作り直す（6素材比較） | 最初のPDCA対象 |
| EXP-002 | CITY GROWTH — 地図から都市が生える（出現順4案） | 試作 |
| EXP-001 | CITY LIFT — 東京を切り取って持ち上げる（浮遊ジオラマ） | 試作（LIFT-LITE） |

データ出典: 3D City Model (Project PLATEAU) FY2023 LOD2 - MLIT / 地理院タイル（全国最新写真） / Re:Earth Terrain
