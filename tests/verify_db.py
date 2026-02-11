import asyncio
import logging
import sys
from bot import db, config

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def run_verification():
    cfg = config.load_config()
    logger.info("Connecting to DB at %s...", cfg.database_url)
    
    await db.create_pool(cfg.database_url, min_size=1, max_size=1)
    
    try:
        # Test 1: List Tables
        print("\n--- Testing get_tables ---")
        tables = await db.get_tables()
        print(f"Found {len(tables)} tables: {tables}")
        
        if not tables:
            print("No tables found! Skipping further tests.")
            return

        target_table = tables[0]
        
        # Test 2: List Columns
        print(f"\n--- Testing get_table_columns({target_table}) ---")
        columns = await db.get_table_columns(target_table)
        for col in columns:
            print(f"  - {col['name']} ({col['type']}) nullable={col['is_nullable']}")

        # Test 3: Get Primary Key
        print(f"\n--- Testing get_primary_key({target_table}) ---")
        pk = await db.get_primary_key(target_table)
        print(f"Primary Key: {pk}")

        # Test 4: Count Rows
        print(f"\n--- Testing get_row_count({target_table}) ---")
        count = await db.get_row_count(target_table)
        print(f"Row count: {count}")

        # Test 5: Get Rows
        print(f"\n--- Testing get_rows({target_table}, limit=3) ---")
        rows = await db.get_rows(target_table, limit=3)
        for i, row in enumerate(rows):
            print(f"Row {i+1}: {dict(row)}")

    finally:
        await db.close_pool()

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run_verification())
