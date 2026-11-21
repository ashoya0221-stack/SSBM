# SSBM — Tagtsukamu

スマッシュブラザーズDX **US版1.00 / Dolphin 5.0-21460** 向けに、
マスターハンドとクレイジーハンドの未使用連携技を復元するプロジェクトです。

**試験用のGeckoコードを実装済みです。Dolphin上の動作はまだ未検証です。**
生成したPowerPC命令を命令エミュレータで検証していますが、実際のゲームでの
衝突・演出・花の継続ダメージ・発生タイミングの一致は別途確認が必要です。

- 各手が別の相手を掴み、最大2人を同時に拘束する構成。
- マスターハンド：6%の握り5回＋12%の投げ。
- クレイジーハンド：7%の握り5回＋16%の投げ＋花の継続ダメージ。
- 通常の連携技選択に追加。確認用に連携時の選択を固定するコードも同梱。
- 空振り、片手の死亡、相手の拘束関係が解消された場合の復帰処理。

[導入・確認手順](docs/dolphin-guide.md)に従い、次のどちらか1つを使用してください。

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

生成前に提供ファイルのSHA-256とアドレス・モーションの対応を照合します。
入力ファイルは変更しません。Dolphinで使う際は生成済みテキストを利用でき、
Pythonの準備は不要です。

## 調査資料

- [1.02の公開ソースによる予備調査](docs/research.md)
- [提供された1.00実行ファイルの解析](docs/us-1.00-analysis.md)
- [DAT・動画との照合と実装の範囲](docs/restoration.md)
- [復元用PowerPCソース](patches/tagtsukamu.s)
- [ダメージ・判定発生時間の設定](config/restoration.json)

