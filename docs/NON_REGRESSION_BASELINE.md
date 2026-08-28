# 公開main非後退Baseline

## 正本

公開済み`main`のcommit `e42f23d616b9172bddc0a35679f111d4aab7e43b`を、Definitive深掘りで縮小してはならない下限として固定します。機械可読正本は`baseline/public-main-v0.2.0.json`、実行Gateは`scripts/verify_non_regression.py`、結果は`evidence/artifacts/non-regression.json`です。

Baselineは28 Target、13 Target Set、23 Capability、25 Claim、27 Proof Obligation、24 Evidence、8 Source、18 Skill Eval case、9 Lab module、34実行Test case、56 Assertion、2 CI Jobを含みます。

## 禁止する後退

- Test／Lab／Target／Claim／Proof／Evidence／Source／Skill Eval／CI Jobの削除
- `required`の格下げ、既存`covered`の`partial`／`planned`／`excluded`／`infeasible`化
- 新しい`excluded`／`infeasible`によるScope外退避
- Testのskip／disabled化、Test数またはAssertion数の縮小
- JVM／JS／Wasm／Native compile task、固定Version、CI runner／toolchainの縮小
- 既存Evidence commandのmock／static／fixture／compile-onlyへの置換
- 失敗Evidenceを削除してpass扱いにすること

既存IDやProofを置換する場合は、Baselineの`replacements`へ旧ID、新ID、理由、Migration Evidence、同等以上のProof IDを追加する必要があります。Mappingがない変更はGateで失敗します。
