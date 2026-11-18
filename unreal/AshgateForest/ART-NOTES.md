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

## Replacement viewmodel and field-recorded gunfire

New default SERVICE uses Mateusz Sadek's CC0 Poly Haven Service Pistol wood variant, 4K diffuse/normal/ARM and separate frame/slide/magazine. It is a different gun, not a texture-only edit of the old M1911. F3 retains the original M1911 mesh, independently tracking 8/7-round capacities. Both use new anatomical hands from para / MakeHuman's CC0 rig, retargeted per finger and baked to separate static hands/forearms (3,636 triangles each). New leather and fabric normals/roughness use Rob Tuytel's 2K Poly Haven scans. No old gloved-hand mesh is used by the new viewmodel. Legacy source assets and releases remain intact.

Tools/prepare_viewmodel.py reproduces static geometry from the retained raw sources. Tools/prepare_fieldshots.py uses A_42P.wav, a near-distance 1911 field recording in The Free Firearm Sound Library (CC0); the previous designed CZ-52 shots are preserved but no longer referenced by the active sound bank. No synthesized bass, soft saturation, shelf boost or pitch change is used in the new profile. Raw and prepared hashes, source metadata and finger targets are in SourceArt/Viewmodel. Full authorship and source URLs: licenses/forest/VIEWMODEL.txt. The recording is a stand-in for SERVICE; its source weapon is documented rather than misidentified.

Import via full UE Editor -ExecutePythonScript=Tools/viewmodel_entry.py after the Editor target is built. It imports only the new /Game/Forest/Viewmodel assets and field_shot sounds, with explicit linear data maps and OpenGL-to-DirectX normal conversion. Nanite is disabled on held meshes. Current reload remains procedural magazine/hand/slide movement rather than a full authored skeletal reload animation.

## Field-finish realism revision

The service pistol now uses separate FieldSteel / FieldPolymer / FieldRubber / FieldBore / FieldControls / FieldCrown sections. Source 4K maps are retained and augmented by an analytic material: footprint-filtered fine normal/roughness variation, sparse short scuffs, 0.12–0.45mm convex-edge wear and AO-directed cavity dirt. Polymer/rubber are non-metallic; the steel and worn edges have distinct roughness and reflectance. This is a project-authored field variant, with the original wooden pistol and M1911 assets preserved.

Geometry adds a bevelled rubber wrap following the original grip section, a 48-sided outer barrel profile, crown and bore depth (frame: 6,646 triangles, versus 5,344 previously). No original texture pixels are repainted. TEXCOORD_1/2/3 and vertex colors encode physical wear coordinates; lightmap generation is disabled to retain these channels. The importer explicitly rejects final material compile errors and missing UV/color data. Source metadata and reproduction: SourceArt/FieldFinish/manifest.json, Tools/sample_field_masks.ps1 and Tools/prepare_fieldfinish.py. Full authorship: licenses/forest/FIELD-FINISH.txt.

Hip position changes from (38,13,-8)cm to (42,11,-9), and service-pistol ADS from (28,0,-1.9) to (31,0,-1.8). Existing hand anatomy and target joints stay intact; a finer/weaker leather normal and adjusted reflectance replace the coarse glove finish. CastShadow, dynamic/contact and self-shadow-only flags are enabled on held components. No extra weapon-only light, global exposure change or engine-file edit is used. Existing forest generation/lighting and sound sources remain unchanged. Reload stays procedural rather than a new skeletal animation set.


## Surface and lighting integration, 2026-11-17

Integration keeps the FieldFinish GLB geometry but imports authored normals, recalculates tangents at higher precision and uses full precision UVs. Separate new materials reuse the unaltered attributed 4K pistol maps and leather sources; source grip color/relief is retained. Edge wear is 0.10–0.25mm. Original FieldFinish, Viewmodel, GripFit, M1911, source images, forest assets and earlier releases are untouched. No new third-party assets. The original source normals and the source material character cannot supply sculpted detail absent from the mesh. See docs/forest-integration/REPORT.md.


## P38 and recorded forest decay, 2026-11-18

New free GameAudioGDC selections by Pole Position: 2020 P38 2m-behind firing and magazine removal, plus the decay-only portion of a 2018 MP5 forest-road recording. Six locally prepared 48k PCM16 assets. P38 attacks are real separate takes; forest-layer attacks are excluded. No synthesized bass, pitch drop, saturation or borrowed simultaneous action overlay. The GDC v2.0 terms allow use in finished games but do not make these files CC0. Licensed source/derived WAVs and native audio assets are local and ignored, restored by the build helper from manifests; public Git includes code and metadata only. See licenses/forest/P38-FIELD.txt and docs/forest-p38-audio/REPORT.md. Old CC0 banks, M1911, graphics and prior releases remain preserved.
