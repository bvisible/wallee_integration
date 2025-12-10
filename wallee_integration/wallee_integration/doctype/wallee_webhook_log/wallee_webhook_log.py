# Copyright (c) 2024, Your Company and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class WalleeWebhookLog(Document):
    """Wallee Webhook Log for audit trail of webhook events."""

    pass


def create_webhook_log(
    event_type,
    entity_type=None,
    entity_id=None,
    space_id=None,
    listener_entity_id=None,
    request_headers=None,
    request_payload=None,
    processing_status="Received",
    http_status=None,
    error_message=None,
    linked_transaction=None
):
    """
    Create a webhook log entry.

    Args:
        event_type: Type of webhook event (e.g., "transaction.completed")
        entity_type: Type of entity (Transaction, Refund, Terminal, etc.)
        entity_id: Wallee ID of the entity
        space_id: Wallee Space ID
        listener_entity_id: Webhook listener ID
        request_headers: HTTP headers as dict
        request_payload: Request body as dict
        processing_status: Received/Processed/Failed/Ignored
        http_status: HTTP response code
        error_message: Error message if failed
        linked_transaction: Link to Wallee Transaction document

    Returns:
        WalleeWebhookLog: The created log document
    """
    log = frappe.new_doc("Wallee Webhook Log")
    log.event_type = event_type
    log.entity_type = entity_type
    log.entity_id = str(entity_id) if entity_id else None
    log.space_id = space_id
    log.listener_entity_id = str(listener_entity_id) if listener_entity_id else None
    log.request_headers = frappe.as_json(request_headers) if request_headers else None
    log.request_payload = frappe.as_json(request_payload) if request_payload else None
    log.processing_status = processing_status
    log.http_status = http_status
    log.error_message = error_message
    log.linked_transaction = linked_transaction

    log.flags.ignore_permissions = True
    log.insert()

    return log


def update_webhook_log(
    log_name,
    processing_status=None,
    http_status=None,
    error_message=None,
    response_payload=None,
    linked_transaction=None
):
    """
    Update an existing webhook log entry.

    Args:
        log_name: Name of the webhook log document
        processing_status: New status
        http_status: HTTP response code
        error_message: Error message if failed
        response_payload: Response sent back
        linked_transaction: Link to transaction

    Returns:
        WalleeWebhookLog: The updated log document
    """
    log = frappe.get_doc("Wallee Webhook Log", log_name)

    if processing_status:
        log.processing_status = processing_status
    if http_status:
        log.http_status = http_status
    if error_message:
        log.error_message = error_message
    if response_payload:
        log.response_payload = frappe.as_json(response_payload)
    if linked_transaction:
        log.linked_transaction = linked_transaction

    log.flags.ignore_permissions = True
    log.save()

    return log


def cleanup_old_logs(days=90):
    """
    Delete webhook logs older than specified days.

    Args:
        days: Number of days to keep logs (default 90)

    Returns:
        int: Number of logs deleted
    """
    from frappe.utils import add_days, nowdate

    cutoff_date = add_days(nowdate(), -days)

    old_logs = frappe.get_all(
        "Wallee Webhook Log",
        filters={"timestamp": ["<", cutoff_date]},
        pluck="name"
    )

    for log_name in old_logs:
        frappe.delete_doc("Wallee Webhook Log", log_name, ignore_permissions=True)

    frappe.db.commit()

    return len(old_logs)
