# Authority Review Workflow

`authority/body-inventory.snapshot.json`のraw anchorは、`scripts/generate_authority_review_queue.py`でstable IDを変えずに全件Review Queueへ割り当てます。priority、cluster、batchはReview順序を補助するmachine proposalであり、意味分類ではありません。Queue件数はSemantic Surface、Atomic behavior、Depth達成へ算入しません。

Review前に対象の固定commit、tree、locatorを一次資料で確認します。`authority/reviews/decisions.json`へdecisionを追加する場合は、human reviewer、ISO date-time、40文字以上の理由、`manual-primary-source`方式、source/tool digest、locator、旧anchorから新itemへのmapping、result itemを記録します。`include`、`exclude`、`merge`、`split`のmapping規則はVerifierが検査します。

Semantic SurfaceまたはAtomic behaviorへ昇格するitemは、`authority/reviews/promotions.json`へdecision IDとともに記録し、実際の`mastery.yaml`または`surface.inventory.yaml`への追加と一致させます。decision・mapping・result・promotion実体のどれかが欠ける場合はGateが失敗します。

Source stateがstaleになったdocumentはQueue対象から外して`stale_holds`へ移し、Lock更新と再抽出が終わるまでReview・昇格しません。

```bash
python3 scripts/generate_authority_review_queue.py
python3 scripts/test_authority_review_queue.py
python3 scripts/verify_authority_review_queue.py
```
