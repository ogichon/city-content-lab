# Architecture

## 全体
Muse（企画・統括・評価）→ Codex（実装・検証）→ GitHub（ソース・Issue・PR・実験記録）→ GitHub Pages（公開）。
Pagesは公開基盤であり実行環境ではない。制作・バッチ処理はClaude/Codexの実行環境で行う。

## 技術スタック
TypeScript + Vite + @navaramap/three 0.2.1 + three。フレームワークは導入しない（静的HTMLのマルチページ）。

## ページ構成（論理構成 → 実ファイル）
- `/` → `index.html`（トップ）
- `/gallery/` → `gallery.html`
- `/experiments/` → `compare.html` が実験一覧+コンタクトシートを兼ねる（初期はページ数を増やさない）
- `/experiments/<slug>/` → `viewer.html?recipe=<id>`（レシピが実験ページの実体）
- `/compare/` → `compare.html`
- `/viewer/` → `viewer.html`

Vite `base: "./"` でサブパス配信に対応。直リンクはクエリパラメータ方式のためリロードでも壊れない。

## レシピ方式（大量試作エンジンの中核）
`src/recipes.ts` が型と実体を持ち、`public/recipes/*.json` に同内容を書き出して記録する（再現性の証跡）。
スキーマ要素: id / experiment / location{place,tilesets} / camera{lng,lat,distance,heading,pitch} / time{iso,tint,ambient,exposure} / visual{mode: material|growth|lift|standard, material, palette} / animation{growthOrder,duration} / seed / codeVersion。
組み合わせ例: `tokyo-station + isometric + gold + sunset + city-growth`。

## バッチ生成の方針
最初は 1場所 × 3カメラ × 2素材 = 6案から。正常動作と再現性を確認してから12/24案へ拡張する。大量生成自体を目標にしない。

## ビューア実装上の継承事項
技術検証repoの architecture.md が正本。要点は AGENTS.md「既知の落とし穴」に集約。
