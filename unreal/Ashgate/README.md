# ASHGATE / DEPOT 04 — UE5 prototype

UE5 5.8.4 / C++で制作した、Windows向け一人称・ソロPvE脱出ゲームの初期版です。既存Godot版とは別のプロジェクト・配布物・保存データを使います。

## 遊ぶ

GitHub Releasesの **Ashgate-UE5-Prototype-Windows-x64.zip** を全展開し、`Ashgate.exe`を起動してください。GodotやUnreal Editorのインストールは不要です。ZIP内のファイルをばらばらに移動しないでください。

Windows 10/11 x64、DirectX 12対応GPU、Microsoft Visual C++ランタイムが必要です。ランタイム不足を表示されたPCでは、同梱の `Engine/Extras/Redist/en-us/vc_redist.x64.exe` を実行してください。本制作で追加インストールは行っていません。別PCでの互換性は未検証です。

拠点の **DEPLOY TO DEPOT 04** で出撃、**FIRING RANGE** で予備弾無制限の練習です。南西から入り、ケースや敵の物資を回収し、北東の緑の門で6秒待機して脱出します。倉庫・売買は拠点のボタンで操作します。初期版の画面表示は英語です。

| 操作 | キー |
|---|---|
| 移動 / 視点 | WASD・矢印 / マウス |
| 走る / ジャンプ | Shift / Space |
| 単発射撃 / ADS | 左クリック / 右クリック長押し |
| リロード / 武器確認 | R / N |
| 物資回収 / バッグ | E / Tab |
| 治療開始・中断 | 4 |
| バッグを閉じる / 一時停止・設定 | Esc |
| 練習の装備リセット | T（射撃場のみ） |

感度はEscメニューの +/- で変更でき、自動保存します。画質も同じメニューで切り替えられます。バッグを開いていても時間と敵は動き、Escはまずバッグだけを閉じます。通常のEscメニューはゲームを停止します。

## 実装したループ

- 約96×88mの工業区画、倉庫・事務所・作業場・コンテナ・北東の脱出門。
- 既存M1911を実寸約21.6cmで取り込み。木製グリップ、PBR材質、可動スライドとマガジン、既存音声、手袋付きの手を再利用。Nの確認は射撃・ADS・リロードで中断します。
- 7発マガジン、予備弾、反動、1.35秒のリロード。治療は2.4秒、45回復と止血、被弾で中断し完了時だけキットを消費。
- 8人の警備員の巡回・視認・銃声への反応・射撃、壁による射線遮断、既存の待機・歩行・死亡アニメーション。
- 13か所のケースと敵の回収品、12枠のバッグ、体力・出血・スタミナ。
- 10分の出撃、範囲から離れるとリセットされる6秒の脱出、300 CRの報酬、装備と回収品の倉庫返却、売買。
- 出撃前に倉庫から持ち出しを差し引いて保存。死亡・時間切れ・終了による持ち出し品の喪失。資金・装備不足時の最低限のキット。

初期倉庫はM1911×2、84発、キット×4、1,800 CR。通常出撃では銃×1、最大35発、キット最大1個を持ち出します。

## 保存とGodot版との分離

UE5のスロット名は `AshgateUE5_Profile_v1`。開発実行ではプロジェクトの `Saved/SaveGames/`、現在のWindows Development配布では展開先の `Ashgate/Saved/SaveGames/` に保存します。配布を更新するときはゲームを終了し、旧版のこのフォルダーをバックアップしてから新版へコピーしてください。

Godot版のJSONやsettings.cfgは読み書きしません。`-AshgateSmoke` / `-AshgateInputProbe` は `AshgateUE5_QA` の別スロットを使います。本番スロットを検証に使わないでください。

## 開発

`Ashgate.uproject` を指定のUEで開きます。`/Game/Maps/Depot04` のPIEでプレイできます。環境の配置は `ADepotGameMode::BuildDepot()` がプレイ開始時に生成します。Editorの編集画面では、実行時の建物が並んでいない点に注意してください。

```powershell
# UE内蔵.NETでEditorターゲットをビルド
powershell -NoProfile -ExecutionPolicy Bypass -File .\Tools\build_editor.ps1

# Editor実行 / 実際のPIEでワールド・ゲーム処理を自動検証
& 'D:\UE5\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe' .\Ashgate.uproject -AshgateSmoke '-ExecCmds=Ashgate.PIEVerify'

# Windowsパッケージ。出力先はリポジトリ内work/ue5-package（Git対象外）
powershell -NoProfile -ExecutionPolicy Bypass -File .\Tools\package_windows.ps1
```

上記ExecutionPolicy指定はそのPowerShellプロセスだけに適用し、PCの実行ポリシーは変更しません。

取り込み済みの `.uasset` / `.umap` はGitで保存するため、通常は再取り込み不要です。再生成するときだけ、UE内蔵Pythonで `Tools/convert_surfaces.py` を実行し、EditorのPythonコマンドレットで `Tools/import_art.py` を実行します。変換は既存のEdgeでオフラインのWebPをPNGへデコードし、新しいPythonパッケージをインストールしません。

## 素材・描画

M1911: egorbelous（e.belous）、CC BY 4.0。原典URL、再配布元を根拠にしたライセンス確認の限界、既存の粗さ調整は [既存クレジット](../../licenses/models/M1911.txt) を引き継ぎます。

環境素材と警備員、アニメーションの作者・ライセンスは [既存素材クレジット](../../licenses/raid/THIRD_PARTY.txt) にあります。配布ZIPにもこれらを含めます。UE変換での追加変更は [UE5素材ノート](ART-NOTES.md) を参照してください。

Lumen GI・反射、Virtual Shadow Maps、用途を選んだNanite、PBR環境材質を使います。武器・手と、透明部分のある小さな小物は通常のメッシュ描画です。広角と揺れ、ブルームは控えめにしています。

## 現段階の限界と次の制作

これは遊べる初期プロトタイプです。Bodycam相当の画作りは達成していません。建物の形状・配置、屋内照明、汚れ・小物の密度、手の造形・持ち方・リロードの動きを引き続き改善する必要があります。

警備員の経路は巡回と局所的な障害物回避です。建物を迂回するNavMesh経路探索、精密な照準・銃の持ち方、アニメーションブレンドと戦闘バランスは今後の改善項目です。回収はケースごとに1品、倉庫の回収品は一括売却する初期UIです。長時間プレイ、他のGPUや解像度、Shipping構成は別途検証が必要です。

既知のエンジン側C4864・推奨版より新しいMSVCの警告・起動時スモークテストの19件は抑制せず残しています。自動のゲーム検証はこれらと別に `LogAshgate: ... QA PASS/FAIL` で判定します。

今後は操作とループの実プレイ評価、ナビゲーションと敵の持ち方、工業区画の画作り、UIの日本語化、長時間・他PC検証の順に進めます。

## r2 メニュー修正

描画したボタンと同じUE標準HUDヒットボックスで入力を判定し、同じボタンを押して離した場合だけ動作します。ボタンを指すと色が変わります。QUIT TO DESKTOPでは確認画面を開き、CANCELまたはEscで戻れます。通常のメニュー操作はMENUログへ記録します。診断用の-AshgateInputCaptureは通常保存スロットのままF9記録だけを有効にします。
