"""Select the latest observation per lot without modifying stock balances."""
from datetime import date
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.imports.model import InventoryImport, InventorySnapshotRow
from app.features.lots.model import Lot
from app.features.products.model import Product
from app.features.return_policies.model import ReturnPolicyVersion
from app.features.suppliers.model import Supplier


async def latest_observations(
    db: AsyncSession,
    organization_id: UUID,
    as_of: date,
    *,
    product_id: UUID | None,
    supplier_id: UUID | None,
    limit: int,
    offset: int,
):
    # Rank by OBSERVED day first, then by when the CSV was committed.
    # A late upload of an older physical observation must not replace newer data.
    ranked = (
        select(
            InventorySnapshotRow.lot_id.label("lot_id"),
            InventorySnapshotRow.observed_quantity.label("observed_quantity"),
            InventoryImport.id.label("import_id"),
            InventoryImport.observed_on.label("observed_on"),
            InventoryImport.created_at.label("imported_at"),
            func.row_number().over(
                partition_by=InventorySnapshotRow.lot_id,
                order_by=(
                    InventoryImport.observed_on.desc(),
                    InventoryImport.created_at.desc(),
                    InventoryImport.id.desc(),
                    InventorySnapshotRow.id.desc(),
                ),
            ).label("rank"),
        )
        .join(InventoryImport, InventorySnapshotRow.import_id == InventoryImport.id)
        .where(
            InventoryImport.organization_id == organization_id,
            InventoryImport.observed_on <= as_of,
        )
        .subquery("ranked_observations")
    )

    statement = (
        select(
            Lot, Product.sku, Supplier.code,
            ranked.c.observed_quantity, ranked.c.import_id,
            ranked.c.observed_on, ranked.c.imported_at,
        )
        .join(ranked, ranked.c.lot_id == Lot.id)
        .join(Product, and_(Product.id == Lot.product_id, Product.organization_id == organization_id))
        .join(Supplier, and_(Supplier.id == Lot.supplier_id, Supplier.organization_id == organization_id))
        .where(
            Lot.organization_id == organization_id,
            ranked.c.rank == 1,
        )
    )
    if product_id is not None:
        statement = statement.where(Lot.product_id == product_id)
    if supplier_id is not None:
        statement = statement.where(Lot.supplier_id == supplier_id)
    statement = statement.order_by(Lot.expiry_date, Lot.id).limit(limit).offset(offset)
    return (await db.execute(statement)).all()


async def policies_for_suppliers(
    db: AsyncSession, organization_id: UUID, as_of: date, supplier_ids: set[UUID],
) -> dict[UUID, ReturnPolicyVersion]:
    if not supplier_ids:
        return {}
    # Same semantics as Step 8 effective_policy: latest effective_from wins;
    # if it has expired, do not fall back to a superseded policy.
    result = await db.scalars(
        select(ReturnPolicyVersion)
        .where(
            ReturnPolicyVersion.organization_id == organization_id,
            ReturnPolicyVersion.supplier_id.in_(supplier_ids),
            ReturnPolicyVersion.effective_from <= as_of,
        )
        .order_by(
            ReturnPolicyVersion.supplier_id,
            ReturnPolicyVersion.effective_from.desc(),
            ReturnPolicyVersion.version.desc(),
        )
    )
    latest = {}
    for policy in result:
        latest.setdefault(policy.supplier_id, policy)
    return latest
