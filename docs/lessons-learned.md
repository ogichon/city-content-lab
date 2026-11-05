# Lessons Learned — 失敗事例と再発防止

- **Draco wasm 404（技術検証repo v1-v10）**: ViteがNavaraランタイムアセットをコピーせず、建物タイルが無言で全滅した。→ vite.config.ts のコピープラグインが必須。新エフェクト追加時は dist 内のアセット存在を確認する。
- **夜の黒つぶれ（AWAKENING初期）**: After側のティント・環境光・露出が v14実証値を下回り、ベースマップが読めなくなった。→ グレーディングに下限を設け、テストで固定する。
- **evaluator残留とbfcache凍結（AWAKENING/UNDERWATERレビュー）**: タイル破棄後も評価対象が残る / 戻る操作でタイマーだけ止まり表示が凍結する。→ featureRemovedで除去、pageshowで状態リセット、中断時は「中断しました」と明示する。
- **ブルームと透明は「接続」が必要（EXP-003レビュー、2026-11-05）**: FeatureEvaluatorで emissive を返しても、選択的ブルームは addEffect の id と建物モデルの `effectIds` が接続されていなければ発光しない。同様に opacity を返しても、モデルの `transparent: true` がなければ透けない（opacity<1 の素材だけに付ける）。実証パターンは技術検証repo の underwater.ts。
- **エージェントブラウザでの描画判定**: 3D Tilesのストリーミングが遅く、見えないことと失敗を混同しやすい。→ 描画の最終判定はユーザーの実Chrome。自動判定はビルド/テスト/HTTP状態までに留める。
