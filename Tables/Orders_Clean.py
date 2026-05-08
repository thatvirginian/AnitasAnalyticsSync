# -*- coding: utf-8 -*-
from sqlalchemy import text
import logging

logger = logging.getLogger("Orders_Clean")


def upsert_orders(conn, orders_list):
    """
    Upgraded for Azure PostgresSQL via SQLAlchemy.
    Maintains the 4-Tier Hierarchy and strictly follows:
    'If a GUID is already present, it should not be added again.'
    """
    stats = {"orders_updated": 0, "items_added": 0}

    if not orders_list:
        return stats

    # Prepare lists of DICTIONARIES for SQLAlchemy batched execution
    tier1_head = []
    tier2_checks = []
    tier3_items = []
    tier4_mods = []

    # 1. Extraction and Transformation
    for order in orders_list:
        if not isinstance(order, dict) or not order.get('guid'):
            continue

        o_guid = order.get('guid')

        # --- TIER 1: Header ---
        d_opt = order.get('diningOption') or {}
        table_obj = order.get('table') or {}
        s_area = table_obj.get('serviceArea') or {}
        service = order.get('restaurantService') or {}
        rev_ctr = order.get('revenueCenter') or {}
        server_obj = order.get('server') or {}

        tier1_head.append({
            "order_guid": o_guid,
            "location_id": order.get('location_id'),
            "order_number": order.get('displayNumber'),
            "fire_date": order.get('openedDate'),
            "promised_date": order.get('promisedDate'),
            "created_date": order.get('createdDate'),
            "closed_date": order.get('closedDate'),
            "paid_date": order.get('paidDate'),
            "modified_date": order.get('modifiedDate'),
            "deleted_date": order.get('deletedDate'),
            "estimated_fulfillment_date": order.get('estimatedFulfillmentDate'),
            "business_date": order.get('businessDate'),
            "required_prep_time": order.get('requiredPrepTime'),
            "number_of_guests": order.get('numberOfGuests'),
            "approval_status": order.get('approvalStatus'),
            "deleted": order.get('voided', False),  # Mapping Toast 'voided' to your DB 'deleted'
            "source": order.get('source'),
            "dining_option_guid": d_opt.get('guid'),
            "service_area_guid": s_area.get('guid'),
            "restaurant_service_daypart": service.get('guid'),
            "revenue_center_guid": rev_ctr.get('guid'),
            "server_guid": server_obj.get('guid')
        })

        # --- TIER 2: Checks ---
        for check in [c for c in order.get('checks', []) if isinstance(c, dict) and c.get('guid')]:
            c_guid = check.get('guid')
            cust = check.get('customer') or {}

            tier2_checks.append({
                "check_guid": c_guid,
                "order_guid": o_guid,
                "payment_status": check.get('paymentStatus'),
                "tax_exempt": check.get('taxExempt', False),
                "total_amount": check.get('totalAmount'),
                "tax_amount": check.get('taxAmount'),
                "net_amount": check.get('amount'),
                "tab_name": check.get('tabName'),
                "customer_first": cust.get('firstName'),
                "customer_last": cust.get('lastName'),
                "customer_phone": cust.get('phone'),
                "customer_email": cust.get('email'),
                "opened_date": check.get('openedDate'),
                "closed_date": check.get('closedDate'),
                "voided": check.get('voided', False)
            })

            # --- TIER 3: Items ---
            for sel in [s for s in check.get('selections', []) if isinstance(s, dict) and s.get('guid')]:
                s_guid = sel.get('guid')
                item_ref = sel.get('item') or {}
                sales_cat = sel.get('salesCategory') or {}
                item_group_ref = sel.get('itemGroup') or {}
                
                tier3_items.append({
                    "selection_guid": s_guid,
                    "check_guid": c_guid,
                    "item_guid": item_ref.get('guid'),
                    "item_name": sel.get('displayName'),
                    "quantity": sel.get('quantity'),
                    "unit_price": sel.get('receiptLinePrice'),
                    "net_price": sel.get('price'),
                    "deferred": sel.get('deferred', False),
                    "tax_amount": sel.get('tax'),
                    "voided": sel.get('voided', False),
                    "fulfillment_status": sel.get('fulfillmentStatus'),
                    "plu": sel.get('plu'),
                    "sales_category_guid": sales_cat.get('guid'),
                    "item_group_guid": item_group_ref.get('guid')
                })
                stats["items_added"] += 1

                # --- TIER 4: Modifiers ---
                for mod in [m for m in sel.get('modifiers', []) if isinstance(m, dict) and m.get('guid')]:
                    m_item = mod.get('item') or {}
                    tier4_mods.append({
                        "modifier_guid": mod.get('guid'),
                        "selection_guid": s_guid,
                        "item_guid": m_item.get('guid'),
                        "mod_name": mod.get('displayName'),
                        "quantity": mod.get('quantity'),
                        "mod_unit_price": mod.get('receiptLinePrice'),
                        "mod_net_price": mod.get('price'),
                        "deferred": mod.get('deferred', False),
                        "voided": mod.get('voided', False)
                    })

        stats["orders_updated"] += 1

    # 2. Batch Execution Phase
    # SQLAlchemy's conn.execute(text(sql), list_of_dicts) handles the batching automatically.
    try:
        if tier1_head:
            conn.execute(text("""
                INSERT INTO orders_head (
                    order_guid, location_id, order_number, fire_date, promised_date,
                    created_date, closed_date, paid_date, modified_date, deleted_date,
                    estimated_fulfillment_date, business_date, required_prep_time,
                    number_of_guests, approval_status, deleted, source,
                    dining_option_guid, service_area_guid, restaurant_service_daypart, 
                    revenue_center_guid, server_guid
                ) VALUES (
                    :order_guid, :location_id, :order_number, :fire_date, :promised_date,
                    :created_date, :closed_date, :paid_date, :modified_date, :deleted_date,
                    :estimated_fulfillment_date, :business_date, :required_prep_time,
                    :number_of_guests, :approval_status, :deleted, :source,
                    :dining_option_guid, :service_area_guid, :restaurant_service_daypart, 
                    :revenue_center_guid, :server_guid
                ) 
                ON CONFLICT (order_guid) DO UPDATE SET 
                    deleted = EXCLUDED.deleted,
                    modified_date = EXCLUDED.modified_date;
            """), tier1_head)

        if tier2_checks:
            conn.execute(text("""
                INSERT INTO order_checks (
                    check_guid, order_guid, payment_status, tax_exempt, total_amount,
                    tax_amount, net_amount, tab_name, customer_first, customer_last,
                    customer_phone, customer_email, opened_date, closed_date, voided
                ) VALUES (
                    :check_guid, :order_guid, :payment_status, :tax_exempt, :total_amount,
                    :tax_amount, :net_amount, :tab_name, :customer_first, :customer_last,
                    :customer_phone, :customer_email, :opened_date, :closed_date, :voided
                ) ON CONFLICT (check_guid) DO NOTHING;
            """), tier2_checks)

        if tier3_items:
            conn.execute(text("""
                INSERT INTO order_items (
                    selection_guid, check_guid, item_guid, item_name, quantity,
                    unit_price, net_price, deferred, tax_amount, voided,
                    fulfillment_status, plu, sales_category_guid
                ) VALUES (
                    :selection_guid, :check_guid, :item_guid, :item_name, :quantity,
                    :unit_price, :net_price, :deferred, :tax_amount, :voided,
                    :fulfillment_status, :plu, :sales_category_guid
                ) ON CONFLICT (selection_guid) DO NOTHING;
            """), tier3_items)

        if tier4_mods:
            conn.execute(text("""
                INSERT INTO item_modifiers (
                    modifier_guid, selection_guid, item_guid, mod_name,
                    quantity, mod_unit_price, mod_net_price, deferred, voided
                ) VALUES (
                    :modifier_guid, :selection_guid, :item_guid, :mod_name,
                    :quantity, :mod_unit_price, :mod_net_price, :deferred, :voided
                ) ON CONFLICT (modifier_guid) DO NOTHING;
            """), tier4_mods)

    except Exception as e:
        # In SQLAlchemy's with engine.begin() block, an error here automatically triggers conn.rollback()
        logger.error(f"Error during Orders_Clean batch insert: {e}")
        raise e

    return stats
