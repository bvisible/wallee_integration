# -*- coding: utf-8 -*-
# Copyright (c) 2024, Neoservice and contributors
# For license information, please see license.txt

import frappe
from frappe import _
import json
import hmac
import hashlib


@frappe.whitelist(allow_guest=True)
def webhook():
    """Handle Wallee webhook notifications"""
    webhook_log = None
    try:
        data = frappe.request.get_data(as_text=True)
        signature = frappe.request.headers.get("X-Signature")
        headers = dict(frappe.request.headers)

        settings = frappe.get_single("Wallee Settings")

        # Parse payload early for logging
        payload = json.loads(data) if data else {}

        # Create webhook log entry
        webhook_log = _create_webhook_log(
            payload=payload,
            headers=headers,
            processing_status="Received"
        )

        # Verify webhook signature if secret is configured
        if settings.webhook_secret:
            if not verify_webhook_signature(data, signature, settings.get_password("webhook_secret")):
                _update_webhook_log(
                    webhook_log,
                    processing_status="Failed",
                    http_status=401,
                    error_message=_("Invalid webhook signature")
                )
                frappe.throw(_("Invalid webhook signature"), frappe.AuthenticationError)

        # Process based on event type
        entity_id = payload.get("entityId")
        listener_entity_technical_name = payload.get("listenerEntityTechnicalName")
        space_id = payload.get("spaceId")

        linked_transaction = None

        if listener_entity_technical_name == "Transaction":
            linked_transaction = handle_transaction_webhook(entity_id, payload)
        elif listener_entity_technical_name == "Refund":
            linked_transaction = handle_refund_webhook(entity_id, payload)
        elif listener_entity_technical_name == "PaymentTerminal":
            handle_terminal_webhook(entity_id, payload)
        elif listener_entity_technical_name == "TransactionCompletion":
            linked_transaction = handle_completion_webhook(entity_id, payload)

        # Update webhook log as processed
        _update_webhook_log(
            webhook_log,
            processing_status="Processed",
            http_status=200,
            linked_transaction=linked_transaction,
            response_payload={"status": "success"}
        )

        return {"status": "success"}

    except Exception as e:
        frappe.log_error(
            message=str(e),
            title="Wallee Webhook Error"
        )

        if webhook_log:
            _update_webhook_log(
                webhook_log,
                processing_status="Failed",
                http_status=500,
                error_message=str(e)
            )

        raise


def _create_webhook_log(payload, headers, processing_status="Received"):
    """
    Create a webhook log entry.

    Args:
        payload: Webhook payload dict
        headers: HTTP headers dict
        processing_status: Initial status

    Returns:
        str: Name of the created webhook log document
    """
    from wallee_integration.wallee_integration.doctype.wallee_webhook_log.wallee_webhook_log import (
        create_webhook_log
    )

    entity_id = payload.get("entityId")
    listener_entity_technical_name = payload.get("listenerEntityTechnicalName", "")
    space_id = payload.get("spaceId")
    listener_entity_id = payload.get("listenerEntityId")

    # Determine entity type
    entity_type_map = {
        "Transaction": "Transaction",
        "Refund": "Refund",
        "PaymentTerminal": "Terminal",
        "TransactionCompletion": "Completion",
    }
    entity_type = entity_type_map.get(listener_entity_technical_name, "Other")

    # Build event type string
    state = payload.get("state", "")
    if hasattr(state, "value"):
        state = state.value
    event_type = f"{listener_entity_technical_name.lower()}.{state.lower()}" if state else listener_entity_technical_name.lower()

    log = create_webhook_log(
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        space_id=space_id,
        listener_entity_id=listener_entity_id,
        request_headers=headers,
        request_payload=payload,
        processing_status=processing_status
    )

    return log.name


def _update_webhook_log(log_name, **kwargs):
    """Update webhook log entry."""
    from wallee_integration.wallee_integration.doctype.wallee_webhook_log.wallee_webhook_log import (
        update_webhook_log
    )
    update_webhook_log(log_name, **kwargs)


def verify_webhook_signature(payload, signature, secret):
    """Verify webhook signature"""
    if not signature or not secret:
        return False

    expected = hmac.new(
        secret.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(signature, expected)


def handle_transaction_webhook(transaction_id, payload):
    """
    Handle transaction status update from webhook.

    Returns:
        str: Linked transaction document name or None
    """
    from wallee_integration.wallee_integration.api.transaction import get_full_transaction
    from wallee_integration.wallee_integration.doctype.wallee_transaction.wallee_transaction import (
        update_transaction_from_wallee
    )

    # Find local transaction record
    local_transaction = frappe.db.get_value(
        "Wallee Transaction",
        {"transaction_id": str(transaction_id)},
        "name"
    )

    if local_transaction:
        doc = frappe.get_doc("Wallee Transaction", local_transaction)
        wallee_data = get_full_transaction(transaction_id)
        update_transaction_from_wallee(doc, wallee_data)
        return local_transaction

    return None


def handle_refund_webhook(refund_id, payload):
    """
    Handle refund status update from webhook.

    Returns:
        str: Linked transaction document name or None
    """
    from wallee_integration.wallee_integration.api.refund import get_refund_status
    from wallee_integration.wallee_integration.doctype.wallee_transaction.wallee_transaction import (
        update_refund_from_wallee
    )

    refund_data = get_refund_status(refund_id)

    if refund_data:
        # Get the transaction ID from the refund
        transaction_id = refund_data.get("transaction_id") or refund_data.get("transaction", {}).get("id")

        if transaction_id:
            local_transaction = frappe.db.get_value(
                "Wallee Transaction",
                {"transaction_id": str(transaction_id)},
                "name"
            )

            if local_transaction:
                doc = frappe.get_doc("Wallee Transaction", local_transaction)
                update_refund_from_wallee(doc, refund_data)
                return local_transaction

    return None


def handle_terminal_webhook(terminal_id, payload):
    """Handle terminal status update from webhook"""
    terminal = frappe.db.get_value(
        "Wallee Payment Terminal",
        {"terminal_id": terminal_id},
        "name"
    )

    if terminal:
        doc = frappe.get_doc("Wallee Payment Terminal", terminal)
        doc.sync_from_wallee()


def handle_completion_webhook(completion_id, payload):
    """
    Handle transaction completion webhook.

    Returns:
        str: Linked transaction document name or None
    """
    from wallee_integration.wallee_integration.api.transaction import get_full_transaction

    # Get transaction ID from payload
    transaction_id = payload.get("transactionId") or payload.get("transaction_id")

    # If not in payload, we might need to fetch the completion to get the transaction
    if not transaction_id:
        # The completion object should have a reference to the transaction
        # For now, skip if we can't determine the transaction
        return None

    local_transaction = frappe.db.get_value(
        "Wallee Transaction",
        {"transaction_id": str(transaction_id)},
        "name"
    )

    if local_transaction:
        from wallee_integration.wallee_integration.doctype.wallee_transaction.wallee_transaction import (
            update_transaction_from_wallee
        )

        doc = frappe.get_doc("Wallee Transaction", local_transaction)
        wallee_data = get_full_transaction(transaction_id)
        update_transaction_from_wallee(doc, wallee_data)
        return local_transaction

    return None


# Webshop Payment Controller Integration

@frappe.whitelist()
def create_webshop_payment(cart_items, currency, success_url=None, failed_url=None, customer=None):
    """
    Create a payment for webshop checkout

    Args:
        cart_items: List of cart items
        currency: Currency code
        success_url: Redirect URL after successful payment
        failed_url: Redirect URL after failed payment
        customer: Customer ID

    Returns:
        Payment page URL and transaction details
    """
    from wallee_integration.wallee_integration.api.transaction import (
        create_transaction,
        get_payment_page_url
    )
    from wallee_integration.wallee_integration.doctype.wallee_transaction.wallee_transaction import (
        create_transaction_record
    )

    settings = frappe.get_single("Wallee Settings")

    if not settings.enabled or not settings.enable_webshop:
        frappe.throw(_("Webshop payments are not enabled"))

    # Parse cart items
    if isinstance(cart_items, str):
        cart_items = json.loads(cart_items)

    # Build line items for Wallee
    line_items = []
    total_amount = 0

    for item in cart_items:
        amount = float(item.get("amount", 0))
        line_items.append({
            "name": item.get("name", item.get("item_code", "Item")),
            "quantity": item.get("qty", 1),
            "amount": amount,
            "unique_id": item.get("item_code", frappe.generate_hash()[:8])
        })
        total_amount += amount

    # Set URLs
    base_url = frappe.utils.get_url()
    success_url = success_url or settings.success_url or f"{base_url}/wallee/success"
    failed_url = failed_url or settings.failed_url or f"{base_url}/wallee/failed"

    # Create transaction in Wallee
    transaction = create_transaction(
        line_items=line_items,
        currency=currency,
        success_url=success_url,
        failed_url=failed_url,
        customer_id=customer,
        merchant_reference=frappe.generate_hash()[:16]
    )

    # Get payment page URL
    payment_url = get_payment_page_url(transaction.id)

    # Create local transaction record
    create_transaction_record(
        transaction_id=transaction.id,
        amount=total_amount,
        currency=currency,
        transaction_type="Online",
        customer=customer,
        merchant_reference=transaction.merchant_reference
    )

    return {
        "transaction_id": transaction.id,
        "payment_url": payment_url,
        "amount": total_amount,
        "currency": currency
    }


@frappe.whitelist()
def get_transaction_status(transaction_name):
    """Get status of a transaction"""
    doc = frappe.get_doc("Wallee Transaction", transaction_name)
    return {
        "name": doc.name,
        "transaction_id": doc.transaction_id,
        "status": doc.status,
        "amount": doc.amount,
        "currency": doc.currency
    }


@frappe.whitelist()
def sync_transaction(transaction_name):
    """Sync a transaction from Wallee"""
    doc = frappe.get_doc("Wallee Transaction", transaction_name)
    doc.sync_status()
    doc.reload()
    return {
        "name": doc.name,
        "status": doc.status
    }
