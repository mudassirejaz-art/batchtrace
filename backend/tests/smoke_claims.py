"""Step 12 local-only claim allocation, state machine and tenant isolation integration smoke."""
import asyncio
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import httpx
from sqlalchemy import func, select, text, update

from app.db.session import AsyncSessionLocal, engine
from app.features.claims.model import ReturnClaim, ClaimEvent
from app.features.organizations.membership_model import OrganizationMembership
from app.features.imports.model import InventorySnapshotRow
from app.main import app


async def expect(client, method, path, status, **kwargs):
    response = await client.request(method, path, **kwargs)
    assert response.status_code == status, (method, path, status, response.status_code, response.text)
    return response


async def register(client, suffix):
    email = f"claim-{suffix}@example.com"
    password = "ClaimsLocalTest2026#"
    created = await expect(client, "POST", "/api/v1/auth/register", 201, json={
        "email": email, "password": password,
        "organization_name": f"Claims org {suffix}",
        "organization_slug": f"claims-org-{suffix}",
    })
    token = await expect(client, "POST", "/api/v1/auth/login", 200, json={
        "email": email, "password": password,
    })
    return created.json()["organization_id"], created.json()["user_id"], {
        "Authorization": "Bearer " + token.json()["access_token"],
    }


async def import_lot(client, base, auth, day, batch, expiry, quantity):
    csv = ("product_sku,supplier_code,batch_number,expiry_date,quantity\n"
           f"CLAIM-SKU,CLAIM-SUP,{batch},{expiry.isoformat()},{quantity}\n").encode()
    form = {"observed_on": day.isoformat()}
    files = {"file": ("claims.csv", csv, "text/csv")}
    preview = await expect(client, "POST", base + "/imports/preview", 200,
                           headers=auth, data=form, files=files)
    assert preview.json()["valid"], preview.text
    committed = await expect(client, "POST", base + "/imports/commit", 201,
                             headers=auth, data={**form, "preview_fingerprint": preview.json()["fingerprint"]},
                             files=files)
    return committed.json()["id"]


async def verified_lot(client, base, auth, reviewer_auth, suffix, today, expiry,
                       supplier, product, count, observed):
    lot = (await expect(client, "POST", base + "/lots", 201, headers=auth, json={
        "supplier_id": supplier, "product_id": product,
        "batch_number": suffix, "expiry_date": expiry.isoformat(),
    })).json()["id"]
    imported = await import_lot(client, base, auth, today, suffix, expiry, observed)
    verification = (await expect(client, "POST", base + "/recovery/verifications", 201,
                                 headers={**auth, "Idempotency-Key": "v-" + uuid4().hex}, json={
        "lot_id": lot, "import_id": imported, "counted_quantity": count,
        "note": f"Counted warehouse cartons for batch {suffix} manually.",
    })).json()
    reviewed = await expect(client, "POST", base + "/recovery/verifications/" + verification["id"] + "/review",
                            200, headers=reviewer_auth, json={
        "decision": "approved", "reason": "Cross-checked verified physical quantity manually.",
    })
    assert reviewed.json()["verification"]["status"] == "approved"
    return verification


async def main():
    if (engine.url.host not in {"127.0.0.1", "localhost", "::1"}
            or engine.url.database != "batchtrace_db"
            or engine.url.username != "batchtrace_dev"):
        raise SystemExit("STOP: Local BatchTrace database required")
    async with engine.connect() as conn:
        assert await conn.scalar(text("SELECT current_database()")) == "batchtrace_db"
        assert await conn.scalar(text("SELECT version_num FROM alembic_version")) in {"c5e81d0a624f", "d6f20a718c43", "e7b54d260a91"}
    print("PASS: Local database and Step 12 migration guard")

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        suffix = uuid4().hex[:12]
        org, creator, creator_auth = await register(client, suffix + "a")
        _, reviewer, reviewer_auth = await register(client, suffix + "b")
        _, foreign, foreign_auth = await register(client, suffix + "c")
        base = "/api/v1/organizations/" + org
        endpoint = base + "/recovery/claims"
        await expect(client, "GET", endpoint, 401)
        await expect(client, "GET", endpoint, 404, headers=foreign_auth)
        assert (await expect(client, "GET", endpoint, 200, headers=creator_auth)).json() == []
        async with AsyncSessionLocal() as db:
            db.add(OrganizationMembership(organization_id=UUID(org), user_id=UUID(reviewer), role="admin"))
            db.add(OrganizationMembership(organization_id=UUID(org), user_id=UUID(foreign), role="viewer"))
            await db.commit()
        assert (await expect(client, "GET", endpoint, 200, headers=foreign_auth)).json() == []
        await expect(client, "POST", endpoint, 403, headers={
            **foreign_auth, "Idempotency-Key": "viewer-test-key"}, json={
            "verification_id": str(uuid4()), "quantity": 1, "note": "Attempt viewer create without permission",
        })
        print("PASS: Authentication, tenant isolation, viewer read-only")

        supplier = (await expect(client, "POST", base + "/suppliers", 201, headers=creator_auth,
                                 json={"code": "CLAIM-SUP", "name": "Claims supplier"})).json()["id"]
        product = (await expect(client, "POST", base + "/products", 201, headers=creator_auth,
                                json={"sku": "CLAIM-SKU", "name": "Claims product"})).json()["id"]
        today = datetime.now(timezone.utc).date()
        expiry = today + timedelta(days=10)
        await expect(client, "POST", base + "/return-policies", 201, headers=creator_auth, json={
            "supplier_id": supplier, "days_before_expiry": 45, "days_after_expiry": 15,
            "effective_from": (today - timedelta(days=5)).isoformat(),
        })
        verified = await verified_lot(client, base, creator_auth, reviewer_auth, "A", today, expiry,
                                     supplier, product, 20, 27)
        print("PASS: Approved verification with open return window")

        first = {"verification_id": verified["id"], "quantity": 13,
                 "note": "Request return of thirteen verified cartons."}
        key1 = {**creator_auth, "Idempotency-Key": "claim-a-" + suffix}
        await expect(client, "POST", endpoint, 422, headers=creator_auth, json=first)
        await expect(client, "POST", endpoint, 403, headers={**foreign_auth, "Idempotency-Key": "foreign-" + suffix},
                     json={**first, "verification_id": str(uuid4())})  # viewer cannot write
        record1 = (await expect(client, "POST", endpoint, 201, headers=key1, json=first)).json()
        assert record1["status"] == "draft" and record1["quantity"] == 13
        assert record1["is_external_supplier_confirmation"] is False
        repeated = (await expect(client, "POST", endpoint, 201, headers=key1, json=first)).json()
        assert repeated["id"] == record1["id"]
        await expect(client, "POST", endpoint, 409, headers=key1, json={**first, "quantity": 12})
        second = {"verification_id": verified["id"], "quantity": 7,
                  "note": "Request the remaining seven verified cartons."}
        record2 = (await expect(client, "POST", endpoint, 201, headers={
            **creator_auth, "Idempotency-Key": "claim-b-" + suffix}, json=second)).json()
        await expect(client, "POST", endpoint, 409, headers={
            **creator_auth, "Idempotency-Key": "claim-over-" + suffix}, json={**first, "quantity": 1})
        print("PASS: Drafts, idempotency and 20-unit allocation cap")

        await expect(client, "POST", endpoint + "/" + record1["id"] + "/approve", 403,
                     headers=creator_auth, json={"note": "Creator cannot approve this claim."})
        await expect(client, "POST", endpoint + "/" + record1["id"] + "/approve", 403,
                     headers=foreign_auth, json={"note": "Viewer cannot approve this claim."})
        approved = (await expect(client, "POST", endpoint + "/" + record1["id"] + "/approve", 200,
                                 headers=reviewer_auth, json={"note": "Reviewed counted quantity and supplier policy."})).json()
        assert approved["status"] == "approved"
        await expect(client, "POST", endpoint + "/" + record1["id"] + "/approve", 409,
                     headers=reviewer_auth, json={"note": "Cannot approve this twice."})
        dispatched = (await expect(client, "POST", endpoint + "/" + record1["id"] + "/dispatch", 200,
                                   headers=creator_auth, json={"note": "Warehouse dispatch slip checked and recorded."})).json()
        assert dispatched["status"] == "dispatched"
        await expect(client, "POST", endpoint + "/" + record1["id"] + "/supplier-response", 403,
                     headers=foreign_auth, json={"accepted_quantity": 10, "rejected_quantity": 3,
                                                "note": "Claim checked with supplier via staff report."})
        await expect(client, "POST", endpoint + "/" + record1["id"] + "/supplier-response", 409,
                     headers=reviewer_auth, json={"accepted_quantity": 10, "rejected_quantity": 2,
                                                 "note": "One carton has not been reconciled."})
        completed = (await expect(client, "POST", endpoint + "/" + record1["id"] + "/supplier-response", 200,
                                  headers=reviewer_auth, json={
            "accepted_quantity": 10, "rejected_quantity": 3,
            "note": "Staff recorded supplier response with partial acceptance.",
        })).json()
        assert completed["status"] == "partially_accepted"
        assert completed["accepted_quantity"] == 10 and completed["rejected_quantity"] == 3
        await expect(client, "POST", endpoint + "/" + record1["id"] + "/supplier-response", 409,
                     headers=reviewer_auth, json={"accepted_quantity": 13, "rejected_quantity": 0,
                                                 "note": "Cannot duplicate supplier response record."})
        detail = (await expect(client, "GET", endpoint + "/" + record1["id"], 200,
                               headers=creator_auth)).json()
        assert [e["event_type"] for e in detail["events"]] == [
            "created", "approved", "dispatched", "supplier_response_recorded",
        ]
        assert len((await expect(client, "GET", endpoint, 200, headers=creator_auth)).json()) == 2
        assert (await expect(client, "GET", endpoint + "/" + record1["id"], 200,
                             headers=foreign_auth)).json()["id"] == record1["id"]  # viewer can read
        print("PASS: Independent approval, dispatch, recorded partial outcome, append-only events")

        # Race two independent partial claims against the SAME approved verification.
        race_verified = await verified_lot(client, base, creator_auth, reviewer_auth, "R", today, expiry,
                                          supplier, product, 8, 9)
        race_payload = {"verification_id": race_verified["id"], "quantity": 6,
                        "note": "Six physically verified units claimed concurrently."}
        race = await asyncio.gather(
            client.post(endpoint, headers={**creator_auth, "Idempotency-Key": "race-1-" + suffix}, json=race_payload),
            client.post(endpoint, headers={**creator_auth, "Idempotency-Key": "race-2-" + suffix}, json=race_payload),
        )
        assert sorted(r.status_code for r in race) == [201, 409], [(r.status_code, r.text) for r in race]
        print("PASS: Concurrent claim allocation serialized; no oversubscription")

        # Source supersession blocks late approval of a draft.
        stale_verified = await verified_lot(client, base, creator_auth, reviewer_auth, "S", today, expiry,
                                           supplier, product, 5, 7)
        stale = (await expect(client, "POST", endpoint, 201,
                              headers={**creator_auth, "Idempotency-Key": "stale-" + suffix}, json={
            "verification_id": stale_verified["id"], "quantity": 4,
            "note": "Prepare verified cartons for supplier return.",
        })).json()
        await import_lot(client, base, creator_auth, today, "S", expiry, 8)
        await expect(client, "POST", endpoint + "/" + stale["id"] + "/approve", 409,
                     headers=reviewer_auth, json={"note": "Cannot approve a superseded source."})
        print("PASS: Superseded CSV blocks draft approval")

        async with AsyncSessionLocal() as db:
            committed = await db.scalar(select(func.coalesce(func.sum(ReturnClaim.quantity), 0)).where(
                ReturnClaim.verification_id == UUID(verified["id"])))
            event_count = await db.scalar(select(func.count()).select_from(ClaimEvent).where(
                ClaimEvent.claim_id == UUID(record1["id"])))
            physical_source = await db.scalar(select(InventorySnapshotRow.observed_quantity).where(
                InventorySnapshotRow.id == UUID(verified["snapshot_row_id"])))
        assert committed == 20 and event_count == 4 and physical_source == 27
        print("PASS: Sum allocations bounded, source observations unchanged")
        print("PASS: Step 12 internal return claim integration smoke completed")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
