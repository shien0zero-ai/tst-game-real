# ゲーム制作の方針

- このゲームは、リアル寄りの3DゲームとしてGodot 4.6.3（Forward+）で開発する。
- ユーザーの指定により、制作物の保存先は https://github.com/shien0zero-ai/tst-game-real 。
- 今後の制作・修正も、まとまった作業が完了したらコミットし、このリポジトリの `main` ブランチへプッシュする。保存の指示は継続して有効。
- ゲームのコード・シーン・素材を変更した場合は、適切な確認を行う。画面なしの動作確認は `sh tools/check.sh` を使う。
- `.godot/`、`work/`、ログなどの一時データは `.gitignore` に従って除外する。

## UE5版（2026-11-12 引き継ぎ）
- ユーザーの明示指定により、UE5 5.8.4 / C++版を unreal/Ashgate に独立して制作する。上記Godot指定は既存Godot版の維持に適用する。
- Godot版、素材原本、既存配布ZIP、既存セーブを維持する。UE5版をGodotの取り込みと配布から除外する。
- UEの生成物・ログはGitに含めない。原作者のクレジットと素材変換の記録を保つ。
- UE5版はEditorビルド、実際のPIE、Windowsパッケージで確認する。既知のMSVC警告や起動スモークテストを抑制したりエンジンを直接変更しない。
- まとまった検証済み成果は同じリポジトリのmainへコミット・pushする。

## Visual direction (2026-11-15 user request)
- Stop the Bodycam direction. Use a conventional, readable FPS camera and realistic objects consistent with the existing M1911.
- Add modeled first-person hands/forearms, retain asset attribution, and verify the grip in actual gameplay screenshots.
- This supersedes the earlier Bodycam visual goal, while the extraction gameplay and UE5/Godot project separation remain.

## Forest exploration demo (2026-11-16 user request)
- Preserve the existing Godot game, Depot 04, all prior releases and saves.
- New forest work belongs to independent unreal/AshgateForest. Prioritize realistic terrain, foliage, lighting, shadows and atmosphere over game systems; retain playable M1911.
- Large native pine asset is preserved losslessly under SourceArt/Packed and restored with SHA256 checks by Tools/restore_assets.py. Do not overwrite an edited native asset.
- Keep Windows forest artifacts in work/forest-package and publish separate Ashgate-Forest downloads; never replace the existing Depot release assets.

## Licensed P38 audio (2026-11-18)
- P38Field source WAVs and SoundWave assets are free GDC licensed recordings, not CC0. Keep them local and ignored; do not publish standalone audio or native sound assets. Finished game Cook/PAK releases are allowed.
- Tools/ensure_p38.ps1 restores missing assets from the public manifest and imports them with the installed UE Editor. Preserve the existing CC0 banks and old releases.
