# 手動v7：通常の大乱闘プレイヤースロットから手を取得

対象：スマブラDX US 1.00 / Dolphin 5.0-21460。

## 修正理由

v6の手動版は、共有のTagtsukamu処理から GET_HAND(kind) を使って手を検索していた。
この検索経路はボス用のファイター一覧を前提にする。一方、通常の大乱闘では3Pと4Pは通常のプレイヤースロットとして生成され、ARコードでキャラクターをマスターハンド／クレイジーハンドに変更している。

v6の起動テストはテスト側でボス用ファイター一覧を人工的に構築していたため、通常Versusのプレイヤースロットから手を取得する経路を検証していなかった。今回、手動版のこの部分を通常Versus向けに変更した。提供されたUS 1.00 DOLで関数先頭の命令列も照合した。

## v7の変更

手動版ビルドに限り、共有ランタイム内の CALL GET_HAND を get_hand_manual に置き換える。

- Master HandはP3、0-based player slot 2から Player_GetEntity(2) で取得。
- Crazy HandはP4、0-based player slot 3から Player_GetEntity(3) で取得。
- Player_GetEntity のUS 1.00呼び出し先は 0x80034090。
- CPU用通常版・確認版は変更せず、従来のボス用検索を維持。
- 4PのY＋十字キー左でCHを移動させ、到着後にMHを移動させて両手の掴みを開始する操作は維持。3Pの追加入力は不要。

これにより、手動版の手検索はデバッグ用のボス検索一覧に依存しない構成になる。

## 通常大乱闘の設定

- 通常のVersus（大乱闘）モード。デバッグモードは不要。
- 1P・2Pを同じチーム、3P・4Pを反対チームにする。
- 3PをMaster Hand、4PをCrazy Handに変更する既存コードを有効にする。
- 4人ともHuman操作にする。Dolphinのコントローラーポート4に4Pの入力を割り当てる。
- Tagtsukamuは手動版だけを有効にする。CPU版や旧手動版を同時に有効にしない。
- ゲームを完全停止して新しいコードへ交換し、旧ステートセーブを読み込まずタイトルから起動する。

操作は4PのY＋十字キー左のみ。CH到着後、MHが移動・待機し、両手が揃って掴みを始める想定。

## 検証範囲と制限

tests/test_native_startup.py の起動テストを更新し、デバッグ用ファイター一覧を構築せず、手動版のP3/P4スロット参照を検査する構成にした。テスト内の Player_GetEntity 呼び出しはP3/P4のGObjを返すサービスで置き換える。ゲーム本体のDOL、移動登録、コールバック、掴み初期化の命令経路は既存のテストハーネスで実行する。

このテストは通常大乱闘をDolphinで実プレイするテストではない。アニメーション読み込み、状態適用、画面描画、実際の衝突・音声は未検証。**通常大乱闘での完全な動作は、再生成したv7コードをDolphinで確認する必要がある。**

## v7コードの再生成

ゲームのDOL/DAT/AJはリポジトリに含めない。ローカルのprivateファイルを使って再生成する。

\`\`\`sh
python tools/build_gecko.py private/main.dol private/PlMh.dat private/PlCh.dat
\`\`\`

AJアーカイブも照合する場合：

\`\`\`sh
python tools/build_gecko.py private/main.dol private/PlMh.dat private/PlCh.dat \
  --master-aj private/PlMhAJ.dat --crazy-aj private/PlChAJ.dat
\`\`\`

生成された dist/Tagtsukamu-US-1.00-manual.txt をDolphinに登録する。GitHubに残っている旧distファイルはv6生成物なので、再生成せずにv7として使わないこと。
