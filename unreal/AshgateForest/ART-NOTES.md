# 森林素材と画作り

旧版のDEPOT 04 / Godotは保持し、`unreal/AshgateForest` の独立したForestTrailモジュールで制作。M1911と両腕はコミット1198c3dのUE資産を、依存する材質・画像とともに複製しました。既存ゲームの設定・セーブを読み書きしません。

Powered by Poly Haven. 追加した森林モデル・地表画像はPoly HavenのCC0素材です。モデルの作者・URLは `licenses/forest/THIRD_PARTY.txt`、取得データとSHA256は `SourceArt/asset-manifest.json` に記録。M1911（egorbelous / CC BY 4.0）、両腕の元モデル・リグ・姿勢のクレジットは既存の `licenses/models/M1911.txt` と `licenses/raid/THIRD_PARTY.txt` を保持します。

- 原本glTFの個々の樹形を選択し、見本展示用の横並び移動を取り除いて原点に配置。メートルからUEのcmに変換。元のUV・法線・材質の参照を保ちます。
- 巨大な松のバッファはHTTP Rangeで必要な範囲だけ取得。範囲とサイズを検証し、各範囲のSHA256を記録。部分取得から全原本のMD5を検証したとは主張しません。参照glTF自体は公式MD5を検証しています。
- 大きい派生glTFバッファは60MiB未満の複数ファイルへ分割。Unreal側はNaniteの形状保持を有効にし、松の保持率1.0を正式なStaticMeshEditorSubsystem APIで適用。大きな松のネイティブUE資産は分割した可逆圧縮ファイルへ別途保存し、SHA256検証付きで復元します。画質を落とすための分割ではありません。元の選択済み形状はSourceArtに保存します。
- 草・シダ・枝葉には、JPEGの色画像とは別に公式のアルファ画像を取得。Masked / Two Sided Foliageとし、葉の透過光を有効にします。松と若木の立体的な針葉は元の不透明材質を維持し、切り抜き画像を使う葉だけにマスクを適用。透過材質をNaniteへ無理に適用しません。
- 色はsRGB、ORM・アルファは線形、法線はNormalmapとしてOpenGLのGreenを反転。地面は森林土と小径の4K画像を2m尺度でブレンドし、小径の曲線に対応するマスクを世界座標で算出します。
- 地形は256m角、1m格子の起伏付きメッシュ（131,072三角形）。解析的な丘・斜面・小径の浅い窪みと小さな凹凸を生成。単なる平面や背景画像ではありません。地形・岩・倒木は衝突を持ち、幹には簡略な衝突を配置。草葉は通過できます。
- 植生は固定シードで配置。複数の樹形と若木、回転・高さ・太さの変化を使いますが、樹形の種類や遠景の境界には繰り返しが残ります。
- Lumen GI・反射、Virtual Shadow Maps、SkyAtmosphere、Volumetric Fogを使用。物理的な実寸を基準にしつつ、環境光・露出・霧は画面に合わせたアート調整で、測光校正済みHDRIではありません。

今回は静的な森林の見た目と探索に範囲を絞っています。樹形の増加、遠景の連続性、地表の細かな散乱物、枝葉の風揺れ、足音・環境音、手指の専用アニメーションには改善余地があります。参考作品と同じ品質へ到達したという意味ではありません。


大型の松のネイティブUE資産は画質を維持した可逆圧縮の分割データとしてSourceArt/Packedへ保存。開発用build_forest.ps1がSHA256を検証して復元します。既に変更された資産は上書きしません。配布版の利用者には復元操作は不要です。

## Grip revision r2

Existing attributed glove topology and UVs were retargeted per finger joint to a two-handed M1911 grip, then Loop-subdivided once with UV seams preserved. Original view_left/view_right and all source assets are retained. Reproduction: Tools/fit_grip.py then full-editor Tools/grip_entry.py. No new external assets.

## Forest audio, 2026-11-16

15 new PCM sources under SourceArt/Audio are imported to /Game/Forest/Audio, with no edits to the original game's sounds. Stereo wind and bird loops use field recordings, rumble filters and two-second wrap crossfades. Four floor sounds come from TinyWorlds; magazine/slide/click transients use SpringySpringo's airsoft pistol. Three CZ-52 takes by Vincent Sevedge / Tabasco stand in for the M1911; archive CC BY 3.0 credits are retained despite the listing's CC0 label. Cloth and soft casing accents are original synthesis. See licenses/forest/AUDIO.txt for full source URLs, attribution and changes.

Rebuild WAVs with Tools/prepare_audio.py --cache <original downloads directory>, using installed UE libsndfile; import via full Editor -ExecutePythonScript=Tools/audio_entry.py. Sources and outputs have SHA256 records. No extra software is needed for the packaged game. Effects use gameplay audio rather than UI audio; loops pause/resume and are destroyed with the player. Footsteps follow actual grounded distance, not held keys. Magazine audio is synchronized with the revised extraction/insertion timings; slide release is exclusive to empty reloads. This is sound design, not a physical acoustic simulation or authentic M1911 recording.

## Gunshot weight and shadow readability revision

The same three attributed CZ-52 takes now retain energy above 65Hz, add a 330Hz low shelf and an original short 140-to-88Hz impact layer, use soft saturation, and extend the gated tail to 1.3 seconds. In-game shot gain changes from 0.87 to 0.95; other sound gains and source WAVs are unchanged. Reproduce with Tools/prepare_audio.py --cache <original downloads> --only-pistol; import only those takes using Tools/pistol_entry.py. This remains designed handgun audio, not an authentic M1911 field recording.

Forest skylight intensity is 500 (previously 350), neutral shadow gamma is 1.13, and exposure bias is -0.20 EV (previously -0.35). Sun strength, shadow casting, Lumen, fog and materials retain their previous settings. The purpose is to reveal detail in shade while retaining a daytime forest contrast.
