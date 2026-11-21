# SSBM — Tagtsukamu

スマッシュブラザーズDX **US版1.00 / Dolphin 5.0-21460** 向けに、
マスターハンドとクレイジーハンドの未使用連携技を復元するプロジェクトです。

**修正版v3のGeckoコードです。どちらの手でも2人まで同時に保持できる処理と、
手の下から下向きに叩きつけ、床に当たってから上へ跳ね返す処理を追加しました。**

- 各手に2人分の保持枠を用意。2人が同じ側にいても、その側の手で両方を拘束する構成。
- 同じ手に掴まれた2人の両方に、5回の握りダメージと投げダメージを適用。
- MH側は各人6×5＋12、CH側は各人7×5＋16＋花の継続ダメージ。
- 解放は手のbone18の下12単位（手の倍率で拡大縮小）。投げ角度270度で下へ飛ばす。
- ゲーム内の床衝突で接地を検出してから、衝撃演出と90度の上向き跳ね返りへ移行。
- 通常の連携技選択に追加。確認用に連携時の選択を固定するコードも同梱。

提供ファイルによる照合とPowerPC命令実行テストは実施済みです。
**Dolphin上でのv3の衝突・描画・音声と、参考動画との完全一致は未確認です。**

[導入・確認手順](docs/dolphin-guide.md)に従い、次のどちらか1つを使用してください。
前版のコードを無効にし、旧ステートセーブを読み込まずタイトルから起動してください。

- [通常版](dist/Tagtsukamu-US-1.00.txt)
- [連携選択を固定する確認版](dist/Tagtsukamu-US-1.00-combo-test.txt)

基準の[参考動画](https://www.youtube.com/watch?v=do8EdYx5OaE)は、ユーザーから提供された
動画ファイルで確認しました。動画作者の非公開の判定サイズや正確な発生フレームを
映像だけから特定することはできないため、完全一致を確認したコードではありません。

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

[v3の修正内容・検証結果](docs/v3-validation.md)に、確認できた範囲と残る制限を記載しています。

## 調査資料

- [1.02の公開ソースによる予備調査](docs/research.md)
- [提供された1.00実行ファイルの解析](docs/us-1.00-analysis.md)
- [DAT・動画との照合と実装の範囲](docs/restoration.md)
- [復元用PowerPCソース](patches/tagtsukamu.s)
- [ダメージ・判定発生時間の設定](config/restoration.json)

