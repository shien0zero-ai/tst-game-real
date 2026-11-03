# リアル寄り3Dゲームの開発スターター

Godot 4.6.3 の **Forward+** を使う、デスクトップ向け3Dプロジェクトです。
一人称で歩ける小さな中庭と、光・影・PBR素材を確認するためのサンプルを用意しています。
実写モデルや高解像度テクスチャを追加していくための土台です。

## 制作物の保存先

GitHub: https://github.com/shien0zero-ai/tst-game-real

今後の制作物と変更履歴は、このリポジトリの `main` ブランチにコミット・プッシュして保存します。
プロジェクトの作業方針は `AGENTS.md` にも記録しています。

## 開発環境

- このクラウド作業環境には **Godot 4.6.3** と **Blender 4.3.2** が導入済みです。
- コードは GDScript。Node.js、npm、.NET は不要です。
- プロジェクトの場所：`/workspace/tst-game-real`
- ローカルPCで編集・プレイする場合は Godot 4.6.3 以降と、Forward+ に対応した Vulkan / Metal / Direct3D 12 のグラフィック環境が必要です。

## 開く・実行する

Godot のプロジェクトマネージャーで `project.godot` をインポートし、**F5** でメインシーンを実行します。
最初の読み込み時は素材のインポートとシェーダーの準備を待ってください。

画面を使える端末では、プロジェクトのディレクトリで次のコマンドも使えます。

```sh
godot --editor --path .
godot --path .
```

クラウド環境にはディスプレイ・GPUが用意されていないため、ここでの検証には次の画面なしのチェックを使います。

```sh
sh tools/check.sh
```

シーンの読み込み、床・壁との衝突、歩行、走行、ジャンプ、落下復帰、リセット、キー割り当てを確認します。
ログと一時データは `work/godot/` に保存されます。画面上の見た目やGPU性能はローカルPCで確認してください。

## 操作

| 操作 | キー |
| --- | --- |
| 移動 | WASD / 矢印キー |
| 視点移動 | マウス |
| 走る | Shift |
| ジャンプ | Space |
| マウスを解放 | Esc |
| 操作を再開 | 左クリック |
| 開始位置へ戻る | R |

開始時はマウスをゲーム内に捕捉します。Esc で解放している間は移動を停止します。
階段には自動で段差を上る処理を入れていないため、Spaceでジャンプして上がってください。

## 編集する場所

| ファイル / フォルダー | 役割 |
| --- | --- |
| `scenes/main.tscn` | メインシーン。ワールド、プレイヤー、操作表示 |
| `scenes/world.tscn` | 照明、空、床、壁、障害物。エディタで配置を変更可能 |
| `scenes/player.tscn` | 身長1.8mの当たり判定と、目の高さ1.62mのカメラ |
| `scripts/player.gd` | 移動・視点・ジャンプ。速度とマウス感度はInspectorで調整可能 |
| `materials/` | コンクリート、金属などのPBRマテリアル |
| `assets/models/` | Blenderから書き出す3Dモデル |
| `assets/textures/` | ベースカラー、ラフネス、法線などのテクスチャ |
| `assets/audio/` | 効果音・環境音 |
| `tests/smoke.gd` | 実際のシーンと物理演算を使う動作確認 |

1 Godot unit = 1m で作成しています。リアルな比率を保つため、モデルの寸法もメートルで揃えてください。
入力の変更は「プロジェクト → プロジェクト設定 → インプットマップ」で行えます。

## Blenderからモデルを取り込む

1. Blenderで単位系を Metric、Unit Scale を 1.0 に設定します。
2. モデルを作り、Object Mode で `Ctrl+A → Rotation & Scale` を適用します。
3. `File → Export → glTF 2.0` から **glTF Binary (.glb)** を選び、`assets/models/` に保存します。Principled BSDF の Metallic / Roughness を基準に素材を設定します。
4. Godotでインポートが終わったら、`.glb` をワールドのシーンへドラッグします。
5. 床・壁などは MeshInstance3D の「Mesh → Create Trimesh Static Body」で静的な当たり判定を追加します。動く物体には単純なBox / Capsule / Convexの当たり判定を使います。

`.blend` の自動取り込みは使用せず、`.glb` で受け渡す構成です。別PCでもBlenderのインストール先に依存せず開けます。
オリジナルの `.blend` はプロジェクトの外か、`.gdignore` を置いた作業フォルダーで管理してください。

## リアルな質感を追加する

- Base Color は Albedo、Roughness は Roughness、Metallic は Metallic、Normal は Normal Map に割り当てます。
- 法線マップは OpenGL 形式（Y+）を使います。DirectX形式なら緑チャンネルの反転が必要です。
- まず実寸、太陽の向き、表面の粗さを揃えます。次に高品質なモデル・テクスチャやHDRIを追加すると、見た目を段階的に改善できます。
- サンプルの素材はプロシージャル生成です。外部素材・追加アドオン・アカウント登録は不要です。

## GPU負荷を調整する

Forward+ を標準にしています。低性能なGPUでは、まずMSAAや影の品質を下げてください。
起動できないPCでは、プロジェクト設定の Rendering → Renderer → Rendering Method を Compatibility に変更して再起動するか、次のコマンドで起動できます。

```sh
godot --path . --rendering-method gl_compatibility
```

CompatibilityではSSAOなど一部の画面効果が使えなくなり、見た目が変わります。
配布用の実行ファイルを作る場合は、Godotの「エディター → エクスポートテンプレートの管理」で4.6.3対応のテンプレートを導入し、「プロジェクト → エクスポート」から対象OSを追加してください。
