## 2026-11-16 r2 — 握りとFPS表示の修正

両手の掌・指の関節・手首をM1911に合わせ直し、手袋の曲面を平滑化。元の手の資産を保持した別メッシュを使用。通常・武器確認・ADSの実画面を確認しました。右上のFPSは実時間の描画回数を0.25秒ごとに集計し、ポーズ中・武器非表示でも表示します。

Editorビルド成功、Windows Build/Cook/Stage/Archive終了コード0。実PIE / 配布版はいずれも14 PASS・0 FAIL（FPSカウンターの正数・有限値の確認を追加）。D3D12 RTX 5080。MSVC 14.52.37029 / SDK 10.0.26100.0。エンジン設定・既知警告の抑制なし。

[通常とFPS](../../docs/screenshots/forest-r2-trail.png) / [握りの側面](../../docs/screenshots/forest-r2-inspect.png) / [ADS](../../docs/screenshots/forest-r2-ads.png)

既存のGodot・Depot 04・森林初版・セーブは保持。リロードは従来の手続き型動作で、専用の指アニメーションは未制作です。以下は森林初版の検証記録です。

# 森林デモの検証 — 2026-11-16

旧ゲームを保持した独立プロジェクト `unreal/AshgateForest`。Windows本体 / UE5 5.8.4 / RTX 5080 / Ryzen 9 9950X3D / 約32GB RAM。

| 項目 | 結果 |
|---|---|
| Win64 Development Editorビルド | 成功 |
| Windows Build/Cook/Stage/Archive | UAT終了コード0 |
| 実PIE worldtype=3 | 13 PASS / 0 FAIL |
| 配布版 worldtype=1 | 13 PASS / 0 FAIL |
| GPU | D3D12 RTX 5080 |
| 最終PIE・配布版の材質コンパイル失敗 / invalid ShaderMap / Fatal error | 0 |
| 旧作の保持 | 1198c3dから旧Ashgate・Godot素材・シーン・export設定の差分なし |
| 大きいUE資産の可逆保存 | 新規一時フォルダーへ復元し、SHA256完全一致 |

MSVC 14.52.37029（格納14.52.37025）、Windows SDK 10.0.26100.0。推奨より新しいMSVCの警告と既知のC4864は抑制していません。起動時Condition failedは最終PIE 19行、配布版 0行。原因を解明したという意味ではなく、エンジン本体を変更していません。

13項目は森林の配置、地形衝突と高さ、武器5部品・両腕、地形上の移動、武器確認、ADSによる中断、射撃の弾消費、リロード開始と完了、ADSカメラ、F2での景色表示と再装備です。PIEのカメラ補助模型を武器として読み込まないよう、実際のViewmodelの子部品を指定して検証しています。

公開前に、完成ZIPを別の新規フォルダーへ全展開し、ルートのAshgateForest.exeから通常ウィンドウ入力を送るゲートを設けています。13入力時点で移動・N・ADS・射撃・リロード・F2・Esc・感度ボタン・復帰・終了取消と確認終了を検証し、不合格なら公開しません。結果はRelease説明とローカルSaved/ZIPInput.log、ZIPInput-console.txtに残します。旧ゲームやそのセーブを入力検証に使いません。

## 実画面

[小径とM1911](../../docs/screenshots/forest-trail.png) / [銃の確認](../../docs/screenshots/forest-inspect.png) / [ADS](../../docs/screenshots/forest-ads.png) / [武器を下げた景色](../../docs/screenshots/forest-scenery.png) / [林内](../../docs/screenshots/forest-grove.png) / [ログ抜粋](../../docs/forest-validation.txt)

配布版の撮影サイズは1600×900、Cinematic・描画率100%。PERFORMANCE samples=603 mean=15.12ms fps=66.1 worst=400.00ms / fixed view, warm-up excluded。この区間には初回PSO生成等による最大400msのヒッチが含まれています。これは画面外描画の固定視点、約12秒のTick間隔で、GPUタイムスタンプや全域の最低FPS、入力遅延ではありません。PIEとWindows QAはRenderOffscreenでD3D12描画を維持し、通常のPC操作との干渉を避けました。

## 範囲と残作業

地形と植生・PBR・陰影を優先した森林探索の初版です。約1,178本の成木と25,605の下草・若木（固定シードの数）、苔岩・倒木を描画。原本由来の複数形状を使いますが、樹形・林床パターンの繰り返し、遠景の端、静止している枝葉、音の不足、手の造形・握りには改善余地があります。参考作品と同等の写実品質を保証するものではありません。敵・回収・脱出は実装せず、既存DEPOT 04はそのまま保存しています。

大型ネイティブ資産はGitのファイルサイズ制限のため可逆圧縮の分割データで保持し、開発用build_forest.ps1が復元します。配布版には必要なCook済みデータを含め、追加の復元操作やEditor導入は不要です。
