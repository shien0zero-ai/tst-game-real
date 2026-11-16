# ASHGATE / FOREST STUDY

これまでのGodot版・DEPOT 04と分けた、UE5 5.8.4の森林探索デモです。ゲームシステムより、地形・植生・陰影・空気感を優先しています。過去のゲーム、配布ZIP、セーブは保持しています。

## 遊ぶ

**Ashgate-Forest-Windows-x64.zip**を全展開し、ルートの**AshgateForest.exe**を起動してください。Unreal Editorのインストールは不要です。Windows x64 / DirectX 12 / Visual C++ランタイムが必要です。不足を表示された場合のランタイムは `Engine/Extras/Redist/en-us/vc_redist.x64.exe` に同梱しています。この制作で追加インストールは行っていません。

| 操作 | キー |
|---|---|
| 移動・視点 | WASD・マウス |
| 走る・しゃがむ・ジャンプ | Shift・C・Space |
| M1911射撃・照準 | 左クリック・右クリック長押し |
| リロード・銃の確認 | R・N |
| 銃を下げて景色を見る・再装備 | F2 |
| 操作表示 | F1 |
| 一時停止・感度・開始地点へ戻る・終了 | Esc |

起動直後から森を歩けます。弾倉は7発、リロード用の予備弾は無制限です。敵、物資回収、脱出、装備喪失は今回のデモにはありません。感度変更はこの起動中だけ有効です。既存ゲームのプロフィールを読み書きしません。

## 森林

256×256mの起伏がある地形に、松・モミ、若木、シダ・草、苔岩、切り株・倒木を配置しています。4Kの地表材質、2Kの植生、Lumen、Virtual Shadow Maps、Nanite、葉の透過光と高度に合わせた霧を使用。初期画質はCinematic、内部描画率100%です。RTX 5080のローカルPCで検証しています。他PCの性能保証ではありません。

## 開発と記録

`AshgateForest.uproject` をUE5.8.4で開き、PIEを実行してください。森の配置と照明は `Source/ForestTrail/Forest.cpp` の `BuildForest()` が実行時に生成します。Editorの編集画面は森全体の配置済みシーンではありません。

素材の再取得・変換はUE内蔵Pythonで `Tools/prepare_forest.py`、取り込みはEditor Pythonで `Tools/import_forest.py`。原本キャッシュはリポジトリの `work/forest-source-cache` に分けています。通常の再ビルド・プレイにネット接続は不要です。

出典と変換は **ART-NOTES.md**、検証結果と実画面は **VALIDATION.md**、ライセンスは同梱 `licenses/forest/THIRD_PARTY.txt` と既存M1911・両腕のクレジットを参照してください。専用の風・環境音、動く枝葉、戦闘・進行システムは未実装です。

## 開発

ソースの場所は `unreal/AshgateForest/AshgateForest.uproject`。GitHubから取得したソースでは、まず `Tools/build_forest.ps1 -Action Editor` を実行してください（PowerShellのプロセス内実行許可で起動）。100MiBを超える松のUE資産だけはSourceArt/Packedの分割圧縮データから復元し、SHA256を確認します。既存の資産が変更されていた場合は上書きせず停止します。配布ZIPではこの手順は不要です。

同じスクリプトの `-Action Import / PIE / Windows / Verify` で素材再生成・PIE・配布・配布版検証を実行できます。`-EngineRoot` でUEの場所を指定可能。新規インストールは行いません。再取り込み前にC++ Editorターゲットをビルドしてください。

編集画面には空とPlayerStartがあり、PlayでC++のBuildForestが森林を生成します。地形は専用の生成済みStaticMesh、配置と照明はForest.cppで管理しています。

## 2026-11-16 r2

M1911の両手の握りを修正。指の関節と掌・手首を銃に合わせ、手袋を平滑化しました。右上に現在のFPSを0.25秒ごとに表示します。ポーズ中・F2で銃を下げた際も表示します。旧版は別リリースとして保持します。
