import os
import logging
from datetime import datetime, timedelta
# Import get_engine instead of the old get_db_connection
from src.database_setup import get_engine
from Tables.Orders_Clean import upsert_orders
from src.order_pull import fetch_all_bulk_orders
from src.utils import load_locations

# Logger configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("sync_history.log"),
        logging.StreamHandler()
    ]
)


def run_order_update(target_date=None):
    print(">>> RUN_ORDER_UPDATE ENTERED <<<")
    """
    Orchestrates pulling orders from Toast API and pushing to Azure Postgres.
    Now optimized with SQLAlchemy for stable Azure performance.
    """
    # 1. Date Logic
    if target_date is None:
        # Default to yesterday for the daily automated sync
        target_date = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")

    logging.info(f"--- STARTING AZURE SYNC FOR BUSINESS DATE: {target_date} ---")

    # 2. Load Anita's Store List
    try:
        locations = load_locations()
    except Exception as e:
        logging.error(f"CRITICAL ERROR: Could not load locations.json: {e}")
        return

    # 3. Get the SQLAlchemy Engine
    engine = get_engine()
    global_stats = {"orders_updated": 0, "items_added": 0}

    # 4. Open a single transaction for the entire sync
    # 'engine.begin()' starts a transaction and automatically commits at the end of the block.
    try:
        with engine.begin() as conn:
            for entry in locations:
                loc_name = entry.get('location_name', 'Unnamed Store')
                loc_guid = entry.get('store_guid')

                if not loc_guid:
                    logging.warning(f"Skipping {loc_name}: No store_guid found.")
                    continue

                logging.info(f"[{loc_name}] Fetching from Toast API...")

                try:
                    # Pull raw data from Toast
                    orders_data = fetch_all_bulk_orders(business_date=target_date, location_id=loc_guid)

                    if not orders_data:
                        logging.info(f" ! No orders found for {loc_name} on {target_date}.")
                        continue

                    # Pass the SQLAlchemy connection 'conn' to your tiered upsert logic
                    change_log = upsert_orders(conn, orders_data)

                    # Accumulate stats
                    global_stats["orders_updated"] += change_log.get("orders_updated", 0)
                    global_stats["items_added"] += change_log.get("items_added", 0)

                    logging.info(f" > Success: {len(orders_data)} orders processed for {loc_name}.")

                except Exception as e:
                    logging.error(f"FAILED SYNC for {loc_name}: {e}", exc_info=True)
                    # We continue to the next store so one failure doesn't stop the whole fleet
                    continue

    except Exception as e:
        logging.error(f"CRITICAL DATABASE ERROR: {e}")
        return

    logging.info("--- AZURE SYNC COMPLETE ---")
    logging.info(f"Total Orders Synced: {global_stats['orders_updated']} | Total Items: {global_stats['items_added']}")


if __name__ == "__main__":
    # You can pass a specific date here for manual backfills, e.g., run_order_update("20260101")
    run_order_update()
