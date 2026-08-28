# Router modes

## design

Capabilityの`verdict`、Claim、設計上の境界を比較する。`default`以外は適用条件を必ず示す。

## implement

対応Labを最小再現として使い、対象Projectへ必要な部分だけ適用する。Lab全体を製品Codeへコピーしない。

## diagnose

ClaimのAcceptance CriteriaとTest oracleから仮説を作る。再現できない場合はEvidenceを`inconclusive`として扱う。

## migrate

`migrations/`とCoverageの`migration` Targetを確認する。旧仕様を現行推奨として残さない。

## review

変更差分をCapability、failure mode、相互運用境界、再現Commandに照らす。文体や好みではなくObservable Outcomeを指摘する。
