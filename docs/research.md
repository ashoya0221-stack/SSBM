# Tagtsukamu 予備調査

## 対象と調査資料の違い

ユーザーの対象は **US版1.00 / Dolphin**。
以下は doldecomp/melee の **US版1.02** 向け解析コードから確認した情報である。
1.00の実行ファイル・キャラクターデータ・参考動画との照合は未実施。
ここに記した関数名末尾のアドレスを1.00用コードとして使用してはいけない。

参照コミット：`2f8eab8ebd7a2d25541e125abfa246defe1bacec`

資料のバージョン根拠：
[upstream README](https://github.com/doldecomp/melee/blob/2f8eab8ebd7a2d25541e125abfa246defe1bacec/.github/README.md)
はビルド対象を1.02と記載している。

## 確認できた処理（1.02）

### クレイジーハンドが連携技を要求する

[ftcrazyhandwait10.c](https://github.com/doldecomp/melee/blob/2f8eab8ebd7a2d25541e125abfa246defe1bacec/src/melee/ft/kinds/ftCrazyHand/ftcrazyhandwait10.c)
の `ftCh_Wait1_0_Anim` は行動候補を選び、`u.ch.x2250` に保存する。
連携技のグループは `{15, 3}`。18要素の `states` の末尾には
`ftMh_MS_Squeezing1`、`ftMh_MS_Squeeze`、`ftMh_MS_Throw` の3候補だけがある。

同じ選択処理には4つ目に相当する `case ftMh_MS_Slam` が残っているが、
座標を設定して `break` するだけで、移動・待機を開始する
`ftCh_GrabUnk1_8015BA34` を呼ばない。
手動操作の Y＋十字左の分岐には、この呼び出しが残っている。

**候補数を3から4に変えるだけでは足りない。**
現状の `x48[18]` は0なので、そのまま4候補目を選ぶと期待した新候補を参照しない。
初期検証では既存の連携候補1つを一時的に差し替える方法も検討できる。

### マスターハンドが要求を受け取る

[ftmasterhandwait10.c](https://github.com/doldecomp/melee/blob/2f8eab8ebd7a2d25541e125abfa246defe1bacec/src/melee/ft/kinds/ftMasterHand/ftmasterhandwait10.c)
の `ftMh_Wait1_0_Anim` は、クレイジーハンドの motion ID が
`ftMh_MS_TagRockPaper` のときに `ftBossLib_8015C4C4()` で要求内容を取得する。

最初の3候補には、移動と開始コールバックの登録を行う
`ftMh_MS_389_80150DC4` の呼び出しがある。
4つ目の `case ftMh_MS_Slam` には座標設定しかない。
手動操作側の対応分岐も同様に開始処理を呼ばない。

### 関連するモーション処理も存在する

[ftmasterhandtagrockpaper.c](https://github.com/doldecomp/melee/blob/2f8eab8ebd7a2d25541e125abfa246defe1bacec/src/melee/ft/kinds/ftMasterHand/ftmasterhandtagrockpaper.c)
には `ftMh_TagGrab_Anim`、`ftMh_TagSqueeze_Anim`、失敗・キャンセル時の処理がある。
掴まれた相手への参照を扱うため、モーションIDを強制するだけでは
必要な初期化を満たさない可能性がある。

[ftcrazyhandslam.c](https://github.com/doldecomp/melee/blob/2f8eab8ebd7a2d25541e125abfa246defe1bacec/src/melee/ft/kinds/ftCrazyHand/ftcrazyhandslam.c)
にも連携終了・失敗時と関連する処理が残っている。

## まだ確定していないこと

- 上記の4つ目の分岐と、動画の `Tagtsukamu` が同じ技か。
- US版1.00にも同じ分岐・モーション・掴み判定があるか。
- 1.00での正確なアドレスと、開始時に必要な両手・被掴み側の初期化。
- アニメーションだけでなく、掴み・ダメージ・解放まで動作するか。

解析コードの関数名・列挙子名を、そのままDAT内の技名と同一視しない。
特にクレイジーハンドにも `ftMh_` の列挙子が使われており、
名前だけではマスターハンドと同じ動作とは判断できない。

## 次の確認

1. 動画の動きと、両手のアニメーション・アクションの対応を確認する。
2. US版1.00の `main.dol` を調べ、対応する選択処理と開始処理を特定する。
   必要になったら `PlMh.dat`、`PlCh.dat`、`PlMhAJ.dat`、`PlChAJ.dat` も照合する。
3. まず両手が生存する場面で強制発動を検証する。
4. 掴み成功・空振り・片手の死亡・終了後の通常行動への復帰を確認する。
5. 動作を確認後、既存の連携技に加えてCPUが選ぶようにする。

現時点で動作保証のあるGeckoコード・パッチはない。
