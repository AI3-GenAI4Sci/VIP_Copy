"""Single-request CSV preprocessing for the workspace harness."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, OrderedDict
from pathlib import Path
from typing import Any, Sequence

from seers_harness.intake.categories import TARGET_CATEGORIES, row_category
from seers_harness.intake.features import (
    REQUEST_ID_FIELDS,
    build_derived_features,
    parse_field,
    product_from_row,
    resolve_first,
    stable_product_key,
    user_state_from_row,
)


def preprocess_request_from_csv(
    csv_path: str | Path,
    *,
    request_id: str,
    brand_level_index: dict[str, str] | None = None,
    cat3_cat1_index: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Read one request from raw CSV and return a workflow-ready scenario dict."""
    rows = list(read_request_rows(csv_path, request_id=request_id))
    return scenario_from_request_rows(
        request_id=request_id,
        rows=rows,
        brand_level_index=brand_level_index,
        cat3_cat1_index=cat3_cat1_index,
    )


def preprocess_requests_from_csv(
    csv_path: str | Path,
    *,
    request_ids: Sequence[str],
    brand_level_index: dict[str, str] | None = None,
    cat3_cat1_index: dict[str, str] | None = None,
) -> dict[str, dict[str, Any]]:
    """Read several requests with one CSV scan and return scenarios by id."""
    grouped_rows = read_selected_request_rows(csv_path, request_ids=request_ids)
    return {
        request_id: scenario_from_request_rows(
            request_id=request_id,
            rows=grouped_rows.get(request_id, []),
            brand_level_index=brand_level_index,
            cat3_cat1_index=cat3_cat1_index,
        )
        for request_id in request_ids
    }


def scenario_from_request_rows(
    *,
    request_id: str,
    rows: list[dict[str, Any]],
    brand_level_index: dict[str, str] | None = None,
    cat3_cat1_index: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build a workflow-ready scenario from already selected CSV rows."""
    if not rows:
        raise ValueError(f"request_id not found: {request_id}")

    first = rows[0]["row"]
    products_by_key: OrderedDict[str, dict[str, Any]] = OrderedDict()
    derived_by_product: dict[str, dict[str, Any]] = {}
    source_categories: Counter[str] = Counter()
    skipped_categories: Counter[str] = Counter()

    for item in rows:
        row = item["row"]
        category = row_category(row)
        raw_cat3 = str(row.get("item_cat3_name") or row.get("item_cat3") or "").strip()
        if raw_cat3:
            source_categories[raw_cat3] += 1
        if category is None:
            if raw_cat3:
                skipped_categories[raw_cat3] += 1
            continue

        product = product_from_row(row, category=category, line_no=int(item["line_no"]))
        key = stable_product_key(row)
        existing = products_by_key.get(key)
        if existing and _position(existing) <= _position(product):
            continue
        products_by_key[key] = product
        derived_by_product[product["product_id"]] = build_derived_features(
            user_row=first,
            product_row=row,
            category=category,
            brand_level_index=brand_level_index,
            cat3_cat1_index=cat3_cat1_index,
        )

    products = sorted(products_by_key.values(), key=_position)
    active_product_ids = {str(product["product_id"]) for product in products}
    derived_by_product = {
        product_id: features
        for product_id, features in derived_by_product.items()
        if product_id in active_product_ids
    }

    return {
        "scenario_id": request_id,
        "request_id": request_id,
        "minimum_semantic_unit": "request/list_group",
        "user_state": user_state_from_row(first),
        "products": products,
        "target_products": products,
        "target_product_count": len(products),
        "derived_features_by_product": derived_by_product,
        "list_context": {
            "target_categories": list(TARGET_CATEGORIES),
            "source_category_counts": dict(source_categories),
            "skipped_category_counts": dict(skipped_categories),
        },
    }


def read_request_rows(csv_path: str | Path, *, request_id: str) -> list[dict[str, Any]]:
    return read_selected_request_rows(csv_path, request_ids=[request_id]).get(
        request_id, []
    )


def read_selected_request_rows(
    csv_path: str | Path,
    *,
    request_ids: Sequence[str],
) -> dict[str, list[dict[str, Any]]]:
    path = Path(csv_path)
    delimiter = detect_delimiter(path)
    wanted = {str(request_id) for request_id in request_ids}
    out: dict[str, list[dict[str, Any]]] = {request_id: [] for request_id in wanted}
    if not wanted:
        return out
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f, delimiter=delimiter)
        try:
            header = next(reader)
        except StopIteration as exc:
            raise ValueError(f"CSV is empty: {path}") from exc
        for line_no, values in enumerate(reader, start=2):
            fixed = fix_row_length(values, header, delimiter)
            if fixed is None:
                continue
            row = {key: parse_field(key, value) for key, value in zip(header, fixed)}
            row_request_id = resolve_first(row, REQUEST_ID_FIELDS)
            if row_request_id in wanted:
                out.setdefault(row_request_id, []).append(
                    {"line_no": line_no, "row": row}
                )
    return out


def detect_delimiter(path: Path) -> str:
    with path.open("r", encoding="utf-8", newline="") as f:
        header = f.readline()
    counts = {delimiter: header.count(delimiter) for delimiter in ("#", ",", "\t", "|")}
    best = max(counts, key=counts.get)
    return best if counts[best] else ","


def fix_row_length(row: list[str], header: list[str], delimiter: str) -> list[str] | None:
    expected = len(header)
    if len(row) == expected:
        return row
    if len(row) < expected:
        return None
    extra = len(row) - expected
    for text_field in ("item_name", "item_spu_title"):
        if text_field not in header:
            continue
        idx = header.index(text_field)
        tail_start = idx + extra + 1
        merged = row[:idx] + [delimiter.join(row[idx:tail_start])] + row[tail_start:]
        if len(merged) == expected:
            return merged
    return None


def _position(product: dict[str, Any]) -> int:
    return int((product.get("observed") or {}).get("goods_seq") or 0)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Preprocess one VIP COPY request from a raw CSV.")
    parser.add_argument("--csv", required=True, help="Raw CSV path.")
    parser.add_argument("--request-id", required=True, help="Request id to extract.")
    parser.add_argument("--out", default="-", help="Output JSON path, or '-' for stdout.")
    args = parser.parse_args(argv)

    scenario = preprocess_request_from_csv(args.csv, request_id=args.request_id)
    payload = json.dumps(scenario, ensure_ascii=False, indent=2, sort_keys=True)
    if args.out == "-":
        print(payload)
    else:
        Path(args.out).write_text(payload + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
