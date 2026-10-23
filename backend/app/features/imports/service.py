"""Strict CSV validation + content-addressed, immutable historical snapshots.

No source-system synchronization, stock reservation, or available-to-sell assertions.
"""
import csv
import hashlib
import io
import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.imports.model import InventoryImport, InventorySnapshotRow
from app.features.imports.schema import PreviewResponse, RowError
from app.features.lots.model import Lot
from app.features.products.model import Product
from app.features.suppliers.model import Supplier

MAX_BYTES = 2 * 1024 * 1024
MAX_ROWS = 500
CSV_FIELDS = ["product_sku", "supplier_code", "batch_number", "expiry_date", "quantity"]
CODE_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9._-]*$")
QUANTITY_PATTERN = re.compile(r"^(?:0|[1-9][0-9]{0,8})$")
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class CsvInvalid(Exception):
    def __init__(self, message: str):
        self.message = message


class PreviewMismatch(Exception):
    pass


class ImportAlreadyExists(Exception):
    pass


@dataclass(frozen=True)
class ValidRow:
    line: int
    product_sku: str
    supplier_code: str
    batch_number: str
    expiry_date: date
    quantity: int
    lot_id: UUID | None = None


def read_csv(blob: bytes) -> tuple[list[ValidRow], list[RowError]]:
    if not blob or len(blob) > MAX_BYTES or b"\x00" in blob:
        raise CsvInvalid("File must be a nonempty CSV of at most 2 MiB")
    try:
        content = blob.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CsvInvalid("CSV must be UTF-8 encoded") from exc

    errors: list[RowError] = []
    parsed: list[ValidRow] = []
    try:
        reader = csv.DictReader(io.StringIO(content, newline=""), strict=True)
        if reader.fieldnames != CSV_FIELDS:
            raise CsvInvalid("CSV header must be exactly: " + ",".join(CSV_FIELDS))
        seen = set()
        for line_no, row in enumerate(reader, start=2):
            if line_no > MAX_ROWS + 1:
                raise CsvInvalid(f"Maximum {MAX_ROWS} data rows per file")
            if None in row or any(value is None for value in row.values()):
                errors.append(RowError(line=line_no, code="column_count", message="Expected five columns"))
                continue
            sku = row["product_sku"].strip().upper()
            supplier = row["supplier_code"].strip().upper()
            batch = row["batch_number"].strip().upper()
            expires = row["expiry_date"].strip()
            quantity_text = row["quantity"].strip()
            if not (1 <= len(sku) <= 80 and CODE_PATTERN.fullmatch(sku)):
                errors.append(RowError(line=line_no, code="product_sku", message="Invalid product SKU"))
                continue
            if not (1 <= len(supplier) <= 50 and CODE_PATTERN.fullmatch(supplier)):
                errors.append(RowError(line=line_no, code="supplier_code", message="Invalid supplier code"))
                continue
            if not (1 <= len(batch) <= 100):
                errors.append(RowError(line=line_no, code="batch_number", message="Invalid batch number"))
                continue
            if not DATE_PATTERN.fullmatch(expires):
                errors.append(RowError(line=line_no, code="expiry_date", message="Use YYYY-MM-DD"))
                continue
            try:
                expiry_date = date.fromisoformat(expires)
            except ValueError:
                errors.append(RowError(line=line_no, code="expiry_date", message="Invalid calendar date"))
                continue
            if not QUANTITY_PATTERN.fullmatch(quantity_text):
                errors.append(RowError(line=line_no, code="quantity", message="Quantity must be a nonnegative integer <=999999999"))
                continue
            identity = (sku, supplier, batch, expiry_date)
            if identity in seen:
                errors.append(RowError(line=line_no, code="duplicate_row", message="Duplicate lot identity in same CSV"))
                continue
            seen.add(identity)
            parsed.append(ValidRow(
                line=line_no, product_sku=sku, supplier_code=supplier,
                batch_number=batch, expiry_date=expiry_date, quantity=int(quantity_text),
            ))
    except csv.Error as exc:
        raise CsvInvalid("Malformed CSV structure") from exc

    if not parsed and not errors:
        raise CsvInvalid("CSV contains no data rows")
    return parsed, errors


def verify_observed_on(observed_on: date) -> None:
    if observed_on < date(2000, 1, 1) or observed_on > datetime.now(timezone.utc).date():
        raise CsvInvalid("observed_on must be between 2000-01-01 and today's UTC date")


async def evaluate_csv(
    db: AsyncSession, organization_id: UUID, observed_on: date, blob: bytes,
) -> tuple[PreviewResponse, list[ValidRow]]:
    verify_observed_on(observed_on)
    rows, errors = read_csv(blob)
    valid = []
    skus = {r.product_sku for r in rows}
    supplier_codes = {r.supplier_code for r in rows}
    products = {
        obj.sku: obj for obj in (await db.scalars(select(Product).where(
            Product.organization_id == organization_id, Product.sku.in_(skus)
        ))).all()
    } if skus else {}
    suppliers = {
        obj.code: obj for obj in (await db.scalars(select(Supplier).where(
            Supplier.organization_id == organization_id, Supplier.code.in_(supplier_codes)
        ))).all()
    } if supplier_codes else {}

    product_ids = {p.id for p in products.values()}
    supplier_ids = {s.id for s in suppliers.values()}
    batch_numbers = {r.batch_number for r in rows}
    lots = (await db.scalars(select(Lot).where(
        Lot.organization_id == organization_id,
        Lot.product_id.in_(product_ids),
        Lot.supplier_id.in_(supplier_ids),
        Lot.batch_number.in_(batch_numbers),
    ))).all() if product_ids and supplier_ids and batch_numbers else []
    lot_lookup = {
        (lot.product_id, lot.supplier_id, lot.batch_number, lot.expiry_date): lot.id
        for lot in lots
    }
    for row in rows:
        product = products.get(row.product_sku)
        supplier = suppliers.get(row.supplier_code)
        if product is None:
            errors.append(RowError(line=row.line, code="unknown_product", message="Product SKU not registered in organization"))
        if supplier is None:
            errors.append(RowError(line=row.line, code="unknown_supplier", message="Supplier code not registered in organization"))
        if product is None or supplier is None:
            continue
        lot_id = lot_lookup.get((product.id, supplier.id, row.batch_number, row.expiry_date))
        if lot_id is None:
            errors.append(RowError(line=row.line, code="unknown_lot", message="Lot does not match a registered batch and expiry"))
            continue
        valid.append(ValidRow(
            line=row.line, product_sku=row.product_sku, supplier_code=row.supplier_code,
            batch_number=row.batch_number, expiry_date=row.expiry_date,
            quantity=row.quantity, lot_id=lot_id,
        ))
    errors.sort(key=lambda err: (err.line, err.code))
    total = len(rows) + sum(1 for err in errors if err.code in {
        "column_count", "product_sku", "supplier_code", "batch_number", "expiry_date", "quantity", "duplicate_row"
    })
    # Canonical digest is row-order invariant. It is only available for fully valid CSVs.
    fingerprint = None
    if not errors and valid:
        payload = {
            "observed_on": observed_on.isoformat(),
            "rows": sorted((str(r.lot_id), r.quantity) for r in valid),
        }
        fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return PreviewResponse(
        valid=not errors and bool(valid), observed_on=observed_on,
        total_rows=total, valid_rows=len(valid), errors=errors,
        fingerprint=fingerprint,
    ), valid


async def commit_csv(
    db: AsyncSession, organization_id: UUID, observed_on: date,
    filename: str, blob: bytes, expected_fingerprint: str,
):
    preview, valid_rows = await evaluate_csv(db, organization_id, observed_on, blob)
    if not preview.valid:
        raise CsvInvalid("CSV contains invalid rows; preview and correct them before committing")
    if preview.fingerprint != expected_fingerprint:
        raise PreviewMismatch
    imported = InventoryImport(
        organization_id=organization_id, observed_on=observed_on,
        content_sha256=preview.fingerprint,
        original_file_sha256=hashlib.sha256(blob).hexdigest(),
        filename=filename,
        row_count=len(valid_rows),
    )
    db.add(imported)
    try:
        await db.flush()
        db.add_all([
            InventorySnapshotRow(
                import_id=imported.id, lot_id=row.lot_id,
                observed_quantity=row.quantity,
            ) for row in valid_rows
        ])
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        if getattr(exc.orig, "sqlstate", None) == "23505":
            raise ImportAlreadyExists from exc
        raise
    await db.refresh(imported)
    return imported
