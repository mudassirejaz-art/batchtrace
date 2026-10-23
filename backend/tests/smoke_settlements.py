"""Local-only integration smoke: approved claims -> reviewed recorded credits.

Writes isolated test data to LOCAL batchtrace_db. Does not delete existing data.
"""
import asyncio
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import httpx
from sqlalchemy import select, text

from app.db.session import AsyncSessionLocal, engine
from app.features.organizations.membership_model import OrganizationMembership
from app.features.settlements.model import ClaimCreditTerms, CreditReceipt, CreditReceiptReview
from app.main import app
from smoke_claims import expect, register, verified_lot


async def main():
    if (engine.url.host not in {"127.0.0.1", "localhost", "::1"}
            or engine.url.database != "batchtrace_db"
            or engine.url.username != "batchtrace_dev"):
        raise SystemExit("STOP: Local BatchTrace database required")
    async with engine.connect() as conn:
        assert await conn.scalar(text("SELECT current_database()")) == "batchtrace_db"
        assert await conn.scalar(text("SELECT version_num FROM alembic_version")) == "d6f20a718c43"
    print("PASS: Local DB and Step 13 migration guard")

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        token = uuid4().hex[:12]
        org, creator, creator_auth = await register(client, token + "a")
        _, reviewer, reviewer_auth = await register(client, token + "b")
        _, viewer, viewer_auth = await register(client, token + "c")
        _, outsider, outsider_auth = await register(client, token + "d")
        base = "/api/v1/organizations/" + org
        async with AsyncSessionLocal() as db:
            db.add_all([
                OrganizationMembership(organization_id=UUID(org), user_id=UUID(reviewer), role="admin"),
                OrganizationMembership(organization_id=UUID(org), user_id=UUID(viewer), role="viewer"),
            ])
            await db.commit()

        supplier = (await expect(client, "POST", base + "/suppliers", 201, headers=creator_auth,
                                 json={"code": "CLAIM-SUP", "name": "Credit supplier"})).json()["id"]
        product = (await expect(client, "POST", base + "/products", 201, headers=creator_auth,
                                json={"sku": "CLAIM-SKU", "name": "Credit product"})).json()["id"]
        today = datetime.now(timezone.utc).date()
        expiry = today + timedelta(days=10)
        await expect(client, "POST", base + "/return-policies", 201, headers=creator_auth, json={
            "supplier_id": supplier, "days_before_expiry": 45, "days_after_expiry": 15,
            "effective_from": (today - timedelta(days=5)).isoformat(),
        })
        verified = await verified_lot(client, base, creator_auth, reviewer_auth, "CREDIT-" + token,
                                     today, expiry, supplier, product, 15, 20)
        claim_endpoint = base + "/recovery/claims"
        claim = (await expect(client, "POST", claim_endpoint, 201,
                              headers={**creator_auth, "Idempotency-Key": "credit-claim-" + token},
                              json={"verification_id": verified["id"], "quantity": 10,
                                    "note": "Ten counted units submitted to supplier for credit."})).json()
        path = claim_endpoint + "/" + claim["id"]
        terms_url = path + "/credit-terms"
        summary_url = path + "/credit-summary"
        receipts_url = path + "/credit-receipts"

        await expect(client, "GET", summary_url, 401)
        await expect(client, "GET", summary_url, 404, headers=outsider_auth)
        await expect(client, "GET", summary_url, 404, headers=creator_auth)
        await expect(client, "POST", terms_url, 403, headers=viewer_auth,
                     json={"currency": "PKR", "unit_price_minor": 12345,
                           "note": "Quoted price from manual credit terms."})
        await expect(client, "POST", terms_url, 409, headers=reviewer_auth,
                     json={"currency": "PKR", "unit_price_minor": 12345,
                           "note": "Quoted price from manual credit terms."})
        print("PASS: Authentication, tenant, RBAC and pre-supplier-outcome guards")

        await expect(client, "POST", path + "/approve", 200, headers=reviewer_auth,
                     json={"note": "Independent approval after physical stock review."})
        await expect(client, "POST", path + "/dispatch", 200, headers=creator_auth,
                     json={"note": "Ten cartons recorded as dispatched for supplier return."})
        await expect(client, "POST", path + "/supplier-response", 200, headers=reviewer_auth,
                     json={"accepted_quantity": 7, "rejected_quantity": 3,
                           "note": "Supplier outcome reported by authorized warehouse staff."})
        await expect(client, "POST", terms_url, 422, headers=reviewer_auth,
                     json={"currency": "pkr", "unit_price_minor": 12345,
                           "note": "Invalid lowercase currency must be rejected."})
        data = {"currency": "PKR", "unit_price_minor": 12345,
                "note": "Supplier terms transcribed from signed credit quotation."}
        terms = (await expect(client, "POST", terms_url, 201, headers=reviewer_auth, json=data)).json()
        assert terms["accepted_quantity"] == 7
        assert terms["expected_minor"] == 7 * 12345
        assert terms["externally_verified"] is False
        repeated = (await expect(client, "POST", terms_url, 201, headers=reviewer_auth, json=data)).json()
        assert repeated["id"] == terms["id"]
        await expect(client, "POST", terms_url, 409, headers=reviewer_auth,
                     json={**data, "unit_price_minor": 12000})
        print("PASS: Supplier outcome, immutable terms, exact integer minor-unit arithmetic")

        before = (await expect(client, "GET", summary_url, 200, headers=creator_auth)).json()
        assert before["expected_minor"] == 86415 and before["approved_recorded_minor"] == 0
        assert before["outstanding_unapproved_minor"] == 86415
        assert before["is_bank_verified"] is False
        first_payload = {"amount_minor": 30000, "reference": "MANUAL-NOTE-001",
                         "note": "Potential credit note recorded from warehouse paperwork."}
        h1 = {**creator_auth, "Idempotency-Key": "credit-r1-" + token}
        rejected = (await expect(client, "POST", receipts_url, 201,
                                 headers=h1, json=first_payload)).json()
        assert rejected["status"] == "pending" and rejected["is_bank_confirmed"] is False
        retry = (await expect(client, "POST", receipts_url, 201, headers=h1, json=first_payload)).json()
        assert retry["id"] == rejected["id"]
        await expect(client, "POST", receipts_url, 409, headers=h1,
                     json={**first_payload, "amount_minor": 25000})
        pending_summary = (await expect(client, "GET", summary_url, 200, headers=viewer_auth)).json()
        assert pending_summary["pending_review_minor"] == 30000
        assert pending_summary["approved_recorded_minor"] == 0
        await expect(client, "POST", receipts_url, 403,
                     headers={**viewer_auth, "Idempotency-Key": "viewer-" + token}, json=first_payload)
        await expect(client, "POST", receipts_url, 409,
                     headers={**creator_auth, "Idempotency-Key": "overspend-" + token},
                     json={**first_payload, "amount_minor": 60000})
        print("PASS: Receipt idempotency, viewer permissions, pending does not count as recovered")

        review1 = receipts_url + "/" + rejected["id"] + "/review"
        await expect(client, "POST", review1, 403, headers=creator_auth,
                     json={"decision": "approved", "reason": "Cannot review own submission."})
        result = (await expect(client, "POST", review1, 200, headers=reviewer_auth,
                               json={"decision": "rejected", "reason": "No supplier evidence for this credit entry."})).json()
        assert result["status"] == "rejected"
        await expect(client, "POST", review1, 409, headers=reviewer_auth,
                     json={"decision": "approved", "reason": "Repeat review must be rejected."})
        after_reject = (await expect(client, "GET", summary_url, 200, headers=creator_auth)).json()
        assert after_reject["remaining_unrecorded_minor"] == 86415
        print("PASS: Independent review, immutable rejection, rejected entry releases capacity")

        second = (await expect(client, "POST", receipts_url, 201,
                               headers={**creator_auth, "Idempotency-Key": "credit-r2-" + token}, json={
            "amount_minor": 40000, "reference": "MANUAL-NOTE-002",
            "note": "Partial credit evidence submitted for independent approval.",
        })).json()
        approved = (await expect(client, "POST", receipts_url + "/" + second["id"] + "/review", 200,
                                 headers=reviewer_auth, json={
            "decision": "approved", "reason": "Matched internal credit note against paper evidence.",
        })).json()
        assert approved["status"] == "approved"
        partially = (await expect(client, "GET", summary_url, 200, headers=creator_auth)).json()
        assert partially["approved_recorded_minor"] == 40000
        assert partially["remaining_unrecorded_minor"] == 46415
        assert partially["reconciliation_status"] == "partially_reconciled"
        print("PASS: Approved recorded credit updates outstanding, no bank verification claim")

        async def try_submit(k):
            return await client.post(receipts_url, headers={**creator_auth, "Idempotency-Key": k}, json={
                "amount_minor": 46415, "reference": "MANUAL-" + k,
                "note": "Simultaneous recorded supplier credit for remaining amount.",
            })
        a, b = await asyncio.gather(try_submit("race-a-" + token), try_submit("race-b-" + token))
        assert sorted([a.status_code, b.status_code]) == [201, 409], (a.text, b.text)
        winning = (a if a.status_code == 201 else b).json()
        await expect(client, "POST", receipts_url + "/" + winning["id"] + "/review", 200,
                     headers=reviewer_auth, json={
                         "decision": "approved", "reason": "Independent review of final credit evidence.",
                     })
        summary = (await expect(client, "GET", summary_url, 200, headers=creator_auth)).json()
        assert summary["approved_recorded_minor"] == 86415
        assert summary["outstanding_unapproved_minor"] == 0
        assert summary["reconciliation_status"] == "fully_reconciled_internal"
        await expect(client, "POST", receipts_url, 409,
                     headers={**creator_auth, "Idempotency-Key": "exceed-" + token}, json=first_payload)
        listed = (await expect(client, "GET", receipts_url, 200, headers=viewer_auth)).json()
        assert len(listed) == 3  # one race loser is never inserted
        assert sum(r["amount_minor"] for r in listed if r["status"] == "approved") == 86415
        await expect(client, "GET", receipts_url, 422, headers=creator_auth, params={"limit": 0})
        await expect(client, "GET", receipts_url, 404, headers=outsider_auth)
        print("PASS: Concurrent allocation serialized, accounting ceiling, tenant reads")

        async with AsyncSessionLocal() as db:
            entry = await db.scalar(select(ClaimCreditTerms).where(ClaimCreditTerms.id == UUID(terms["id"])))
            assert entry.expected_minor == 86415
            rows = (await db.scalars(select(CreditReceipt).where(CreditReceipt.terms_id == entry.id))).all()
            reviews = (await db.scalars(select(CreditReceiptReview).where(
                CreditReceiptReview.receipt_id.in_([r.id for r in rows]),
            ))).all()
            assert len(rows) == 3 and len(reviews) == 3
            assert sum(r.amount_minor for r in rows if r.status == "approved") == 86415
        print("PASS: Immutable terms, receipts and review evidence preserved")
        print("PASS: Step 13 credit reconciliation integration smoke completed")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
