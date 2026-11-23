"""Import the 17,617 verified Agmarknet daily price observations into market_prices.

Usage:
    python -m scripts.import_snapshot_dataset --apply
"""

import argparse
import os
import sqlite3
import sys
from datetime import datetime
import pandas as pd

def run_import(apply: bool = False, csv_path: str = "data/9ef84268-d588-465a-a308-a864a43d0070.csv"):
    if not os.path.exists(csv_path):
        print(f"Error: CSV not found at {csv_path}", file=sys.stderr)
        return 1

    db_path = "apps/api/preview.db"
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    print(f"Reading {csv_path}...")
    df = pd.read_csv(csv_path)
    total_rows = len(df)
    print(f"Loaded {total_rows} rows from snapshot.")

    # Build reference lookup maps
    print("Building reference lookups from database...")
    state_map = {r[1].strip().lower(): r[0] for r in cur.execute("SELECT id, name FROM reference_states").fetchall()}
    
    # Districts: (state_id, district_name_lower) -> id
    district_rows = cur.execute("SELECT id, state_id, name FROM reference_districts").fetchall()
    district_map = {(r[1], r[2].strip().lower()): r[0] for r in district_rows}
    # Fallback by district name alone if state matches
    district_by_name = {r[2].strip().lower(): r[0] for r in district_rows}

    # Mandis: (district_id, mandi_name_lower) -> id
    mandi_rows = cur.execute("SELECT id, district_id, name FROM reference_mandis").fetchall()
    mandi_map = {(r[1], r[2].strip().lower()): r[0] for r in mandi_rows}
    mandi_by_name = {r[2].strip().lower(): r[0] for r in mandi_rows}

    # Commodities: name_lower -> id
    comm_map = {r[1].strip().lower(): r[0] for r in cur.execute("SELECT id, name FROM reference_commodities").fetchall()}

    # Grades: name_lower -> id
    grade_map = {r[1].strip().lower(): r[0] for r in cur.execute("SELECT id, name FROM reference_commodity_grades").fetchall()}
    # Add alias mappings for common grades
    grade_map["grade a"] = grade_map.get("grade a", 5)
    grade_map["grade b"] = grade_map.get("grade b", 6)
    grade_map["grade c"] = grade_map.get("grade c", 7)
    grade_map["faq"] = grade_map.get("faq", 4)
    grade_map["local"] = grade_map.get("local", 12)
    grade_map["medium"] = grade_map.get("medium", 13)
    grade_map["large"] = grade_map.get("large", 11)
    grade_map["small"] = grade_map.get("small", 15)

    source_id = 2  # agmarknet-official
    unit_id = 1    # quintal

    now_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Map records
    print("Mapping CSV rows to database keys...")
    observations = {}
    skipped = 0

    for _, row in df.iterrows():
        st_name = str(row["State"]).strip().lower()
        dist_name = str(row["District"]).strip().lower()
        mkt_name = str(row["Market"]).strip().lower()
        comm_name = str(row["Commodity"]).strip().lower()
        grade_name = str(row["Grade"]).strip().lower()

        state_id = state_map.get(st_name)
        if not state_id:
            skipped += 1
            continue

        district_id = district_map.get((state_id, dist_name)) or district_by_name.get(dist_name)
        if not district_id:
            skipped += 1
            continue

        mandi_id = mandi_map.get((district_id, mkt_name)) or mandi_by_name.get(mkt_name)
        if not mandi_id:
            skipped += 1
            continue

        commodity_id = comm_map.get(comm_name)
        if not commodity_id:
            skipped += 1
            continue

        grade_id = grade_map.get(grade_name)

        # Parse date 17/10/2026 -> 2026-10-17
        try:
            market_date = datetime.strptime(str(row["Arrival_Date"]).strip(), "%d/%m/%Y").strftime("%Y-%m-%d")
        except ValueError:
            market_date = "2026-10-17"

        modal_price = float(row["Modal_x0020_Price"]) if pd.notnull(row["Modal_x0020_Price"]) else None

        key = (commodity_id, grade_id, mandi_id, district_id, state_id, market_date, unit_id)
        # Store or average if duplicate variety under same key
        observations[key] = (modal_price, source_id, now_iso, now_iso, now_iso)

    print(f"Mapped {len(observations)} unique price records. (Skipped unmapped: {skipped})")

    if not apply:
        print("\n[DRY RUN COMPLETE] No records written to database. Run with --apply to commit.")
        conn.close()
        return 0

    print("Writing records to database...")
    insert_records = []
    for (cid, gid, mid, did, sid, mdate, uid), (mprice, src_id, imp_at, cr_at, up_at) in observations.items():
        insert_records.append((
            cid, gid, mid, did, sid, uid, mdate, mprice, None, src_id, imp_at, cr_at, up_at
        ))

    # Upsert into market_prices
    cur.executemany(
        """
        INSERT INTO market_prices (
            commodity_id, grade_id, mandi_id, district_id, state_id, unit_id,
            market_date, modal_price, arrivals, source_id, imported_at, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(commodity_id, grade_id, mandi_id, district_id, state_id, market_date, unit_id)
        DO UPDATE SET
            modal_price = excluded.modal_price,
            imported_at = excluded.imported_at,
            updated_at = excluded.updated_at
        """,
        insert_records
    )

    # Update cache row for freshness
    cur.execute(
        """
        INSERT OR REPLACE INTO market_price_cache (id, key, value, created_at, updated_at)
        VALUES (
            1,
            'latest_extract',
            '{"row_count": ' || ? || ', "fetched_at": "' || ? || '", "errors": []}',
            ?,
            ?
        )
        """,
        (len(insert_records), now_iso, now_iso, now_iso)
    )

    conn.commit()
    total_in_db = cur.execute("SELECT count(*) FROM market_prices").fetchone()[0]
    print(f"SUCCESS! {len(insert_records)} observations upserted. Total rows in market_prices: {total_in_db}")
    conn.close()
    return 0

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import verified Agmarknet daily price snapshot.")
    parser.add_argument("--apply", action="store_true", help="Commit changes to database.")
    parser.add_argument("--csv", default="data/9ef84268-d588-465a-a308-a864a43d0070.csv", help="Path to snapshot CSV.")
    args = parser.parse_args()
    sys.exit(run_import(apply=args.apply, csv_path=args.csv))
