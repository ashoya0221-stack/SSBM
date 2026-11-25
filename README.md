# SSBM — Tagtsukamu

スマッシュブラザーズDX **US版1.00 / Dolphin 5.0-21460** 向けに、
マスターハンドとクレイジーハンドの未使用連携技を復元するプロジェクトです。

**修正版v4です。比較録画で確認された握りダメージの欠落、命中音の欠落、
遅い解放タイミングを修正しました。**

- 握りは保持枠の相手へ直接適用。見えない相手の食らい判定と手の判定の重なりに依存しません。
- 各手が2人まで保持し、それぞれに5回分の握りダメージを適用します。
- MH側は各人6×5＋12、CH側は各人7×5＋16＋花の継続ダメージ。
- 握りの各回で命中音113と火花を出し、手の動作音0x4E212も呼び出します。
  キャラクター音声の準備時に `mhands.ssm` も読み込み対象にします。
- 解放を241フレームから、手を振り下ろす途中の212フレームへ変更。
- 手の下へ解放→下方向へ移動→床に接触して上へ跳ね返る処理を維持。

提供ファイルの照合、生成PowerPC命令、提供DOLのダメージ加算・HUD更新呼び出し・音声要求処理を
検証済みです。**Dolphin上でのv4の実動作と参考動画との完全一致は未確認です。**

[導入・確認手順](docs/dolphin-guide.md)に従い、次のどちらか1つを使用してください。
前版のコードを無効にし、旧ステートセーブを読み込まずタイトルから起動してください。

- [通常版](dist/Tagtsukamu-US-1.00.txt)
- [連携選択を固定する確認版](dist/Tagtsukamu-US-1.00-combo-test.txt)
- [通常Versus手動テスト版](dist/Tagtsukamu-US-1.00-manual.txt)

基準の[参考動画](https://www.youtube.com/watch?v=do8EdYx5OaE)は、ユーザーから提供された
動画ファイルで確認しました。動画作者の非公開の判定サイズや正確な発生フレームを
映像だけから特定することはできないため、完全一致を確認したコードではありません。


## 通常Versusでの手動テスト版

CPU版v4で使っている技本体と投げ212フレームを基準に、v5当時の二段階Human入力経路を組み合わせたテスト版です。
手の検索をfighter kind検索からP3/P4のPlayer_GetEntityへ差し替えています。人間操作側の連携要求値もUS版1.00の実行ファイルから確認し、380を使います。
3P=Master Hand、4P=Crazy Handの通常Versus設定を前提とします。

操作は4PのY＋十字キー左でCHを移動させ、到着後に3PのY＋十字キー上でMHから開始します。
4P一回だけで自動開始するv6以降の方式は使いません。
この手動テスト版はDolphinでの発動・投げをまだ確認していません。
[操作方法](docs/manual-controls.md)と[検証範囲](docs/manual-v4core-versus-validation.md)を参照してください。

## ソースからの生成

Python 3.10以降。入力ファイルをローカルの `private/` に配置します。
ゲームデータや動画はGitHubへ追加しません。

```sh
python -m venv .venv
# 作成した環境を有効にしてから実行
python -m pip install -r requirements-dev.txt
python tools/build_gecko.py private/main.dol private/PlMh.dat private/PlCh.dat
python -m unittest discover -s tests -v
```

受領したアニメーションも照合する場合は、生成コマンドに
`--master-aj private/PlMhAJ.dat --crazy-aj private/PlChAJ.dat` を追加します。
提供DOLの判定・投げ・効果音コマンドの読み取り処理を実行する追加検証は、
環境変数 `SSBM_MAIN_DOL` にそのDOLのパスを設定してから同じテストを実行します。

生成前に提供ファイルのSHA-256とアドレス・モーションの対応を照合します。
入力ファイルは変更しません。Dolphinで使う際は生成済みテキストを利用でき、
Pythonの準備は不要です。

[v4の修正内容・検証結果](docs/v4-validation.md)に、確認できた範囲と残る制限を記載しています。

## 調査資料

- [1.02の公開ソースによる予備調査](docs/research.md)
- [提供された1.00実行ファイルの解析](docs/us-1.00-analysis.md)
- [DAT・動画との照合と実装の範囲](docs/restoration.md)
- [復元用PowerPCソース](patches/tagtsukamu.s)
- [ダメージ・判定発生時間の設定](config/restoration.json)

