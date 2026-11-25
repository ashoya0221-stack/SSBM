# 通常Versus手動版：v4コア＋P3/P4プレイヤー枠検索

## 基準にした実装

技本体はCPU用v4と同じソース `patches/tagtsukamu.s` と `config/restoration.json` を使用する。
投げ開始はv4で採用した**212フレーム**。241フレームへ戻さない。
手動開始経路は、後のv6/v7/v8で追加された「4P到着時に自動でMHを呼ぶ」フックではなく、
v5当時のHuman入力経路に戻す。

## 通常Versus向けの差分

手動ビルドで使う共有手検索ルーチン内の3箇所について、fighter kindで検索する `GET_HAND` を
通常のプレイヤースロットから取得する `Player_GetEntity` に差し替える。

- Crazy Handの検索引数：fighter kind 28 → P4 slot 3
- Master Handの検索引数：fighter kind 27 → P3 slot 2
- US 1.00のPlayer_GetEntity呼び出し先：`0x80034090`
- CPU側の要求値380（`Squeezing1`）と、人間操作側の要求値383（`Slam`）を分離。手動版の開始条件は383を確認する。

CPU用通常版・確認版の検索処理と開始条件は変えない。手動版の修正は開始前の要求値チェックだけで、
技のアクションID（MH=385、CH=380）、投げ212フレーム、掴み・握り・投げ・音・衝突処理は変更しない。

## 原因と今回の修正

CPUの選択処理は `Squeezing1` を `x2250` に格納する一方、Human入力の4P Y＋十字左は `Slam` を格納する。旧手動版はCPUと同じ380を照合していたため、Master側から開始処理へ入っても `start_pair` が `start_cancel` へ進んでいた。手動版だけ照合値を383へ変更し、CPU版の380は維持する。

## 静的確認と制限

既存のv5手動Geckoテキストを基に、共有検索呼び出し3箇所の引数とPlayer_GetEntityの呼び出し先だけを差し替えた。
圧縮後のランタイムを再展開してバイト列が一致すること、C2ブロックのペア数、Geckoコード領域のサイズを確認した。

これは命令・ファイル構造の静的確認であり、Dolphin上の通常Versus実プレイ確認ではない。
P3にMaster Hand、P4にCrazy Handが存在する設定を前提とする。
両手が目的の技を再生するか、Dolphinでの発動から投げまでを確認する必要がある。
