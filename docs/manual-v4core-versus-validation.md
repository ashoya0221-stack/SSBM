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

CPU用通常版・確認版の検索処理は変えない。手動版も技のアクションID（MH=385、CH=380）、
掴み・握り・投げ・音・衝突処理は変更しない。

## 静的確認と制限

既存のv5手動Geckoテキストを基に、共有検索呼び出し3箇所の引数とPlayer_GetEntityの呼び出し先だけを差し替えた。
圧縮後のランタイムを再展開してバイト列が一致すること、C2ブロックのペア数、Geckoコード領域のサイズを確認した。

これは命令・ファイル構造の静的確認であり、Dolphin上の通常Versus実プレイ確認ではない。
P3にMaster Hand、P4にCrazy Handが存在する設定を前提とする。
両手が目的の技を再生するか、Dolphinでの発動から投げまでを確認する必要がある。
