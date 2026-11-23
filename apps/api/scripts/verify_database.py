"""Read-only verification of the configured database.

Run this BEFORE applying any migration. It answers: "which database am I about
to touch?" without printing the password, the full connection string, or any
row of user data.

Usage (from apps/api, with apps/api/.env present):

    python -m scripts.verify_database

Exit codes: 0 = reachable, 1 = not configured or unreachable.
"""

import asyncio
import sys

from sqlalchemy import text

from app.core.config import describe_database_target, get_settings
from app.core.database import check_connection, dispose_engine, init_engine


async def main() -> int:
    settings = get_settings()
    print("AgriPredict AI - database verification (read-only)")
    print("-" * 56)
    print(f"environment      : {settings.ENVIRONMENT}")
    print(f"database target  : {describe_database_target(settings)}")
    print("(host, port and database name only - credentials are never printed)")

    if settings.is_production:
        print("WARNING: you are pointed at a production environment.")
        answer = input("Type the database name to continue: ").strip()
        if answer != describe_database_target(settings).rsplit("/", 1)[-1]:
            print("Confirmation did not match. Nothing was connected.")
            return 1

    engine = init_engine(settings)
    if engine is None:
        print("result           : FAILED - no database configured")
        return 1

    ok, detail = await check_connection()
    if not ok:
        print(f"result           : FAILED - {detail}")
        await dispose_engine()
        return 1

    async with engine.connect() as connection:
        if engine.dialect.name == "sqlite":
            server_version = f"SQLite {(await connection.execute(text('SELECT sqlite_version()'))).scalar_one()}"
            db_name = describe_database_target(settings).rsplit("/", 1)[-1]
            schema = "main"
        else:
            server_version = (await connection.execute(text("SHOW server_version"))).scalar_one()
            db_name = (await connection.execute(text("SELECT current_database()"))).scalar_one()
            schema = (await connection.execute(text("SELECT current_schema()"))).scalar_one()

    print("result           : reachable")
    print(f"server version   : {server_version}")
    print(f"current database : {db_name}")
    print(f"current schema   : {schema}")
    print()
    print("Next step: run 'alembic current' to see applied migrations, then")
    print("'alembic upgrade head' to apply pending ones.")
    await dispose_engine()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))