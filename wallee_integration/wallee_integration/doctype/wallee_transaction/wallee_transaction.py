# -*- coding: utf-8 -*-
# Copyright (c) 2024, Neoservice and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime


class WalleeTransaction(Document):
    def before_insert(self):
        if not self.merchant_reference:
            self.merchant_reference = self.name

    @frappe.whitelist()
    def sync_status(self):
        """Sync transaction status from Wallee"""
        sync_transaction_status(self.name)

    @frappe.whitelist()
    def capture(self):
        """Capture an authorized transaction"""
        from wallee_integration.wallee_integration.api.transaction import capture_transaction

        if self.status != "Authorized":
            frappe.throw(_("Only authorized transactions can be captured"))

        try:
            result = capture_transaction(self.transaction_id)
            self.reload()
            frappe.msgprint(_("Transaction captured successfully"), indicator="green")
            return result
        except Exception as e:
            frappe.throw(_("Failed to capture transaction: {0}").format(str(e)))

    @frappe.whitelist()
    def void(self):
        """Void an authorized transaction"""
        from wallee_integration.wallee_integration.api.transaction import void_transaction

        if self.status not in ["Authorized", "Pending"]:
            frappe.throw(_("Only authorized or pending transactions can be voided"))

        try:
            result = void_transaction(self.transaction_id)
            self.reload()
            frappe.msgprint(_("Transaction voided successfully"), indicator="green")
            return result
        except Exception as e:
            frappe.throw(_("Failed to void transaction: {0}").format(str(e)))

    @frappe.whitelist()
    def refund(self, amount=None):
        """Refund a completed transaction"""
        from wallee_integration.wallee_integration.api.refund import create_refund

        if self.status not in ["Completed", "Partially Refunded", "Fulfill"]:
            frappe.throw(_("Only completed transactions can be refunded"))

        refund_amount = amount or self.refund_amount or self.amount

        if refund_amount > (self.amount - (self.refunded_amount or 0)):
            frappe.throw(_("Refund amount exceeds available amount"))

        try:
            result = create_refund(self.transaction_id, refund_amount, self.refund_reason)
            self.reload()
            frappe.msgprint(_("Refund processed successfully"), indicator="green")
            return result
        except Exception as e:
            frappe.throw(_("Failed to process refund: {0}").format(str(e)))


def sync_transaction_status(transaction_name):
    """Sync a single transaction status from Wallee"""
    from wallee_integration.wallee_integration.api.transaction import get_full_transaction

    doc = frappe.get_doc("Wallee Transaction", transaction_name)

    if not doc.transaction_id:
        return

    try:
        wallee_data = get_full_transaction(doc.transaction_id)
        if wallee_data:
            update_transaction_from_wallee(doc, wallee_data)
    except Exception as e:
        frappe.log_error(
            message=str(e),
            title=f"Wallee Sync Error: {transaction_name}"
        )


# Mapping of Wallee states to local states
STATUS_MAP = {
    "PENDING": "Pending",
    "CONFIRMED": "Confirmed",
    "PROCESSING": "Processing",
    "AUTHORIZED": "Authorized",
    "COMPLETED": "Completed",
    "FULFILL": "Fulfill",
    "DECLINE": "Decline",
    "FAILED": "Failed",
    "VOIDED": "Voided",
}


def update_transaction_from_wallee(doc, tx):
    """
    Update transaction document from Wallee API response.

    Args:
        doc: Wallee Transaction document
        tx: Full transaction object from Wallee API (Transaction object, NOT dict)
             Note: SDK to_dict() truncates data, so we access attributes directly
    """
    # Helper to safely get attribute from object or dict
    def get_attr(obj, attr, default=None):
        if obj is None:
            return default
        if hasattr(obj, attr):
            return getattr(obj, attr, default)
        elif isinstance(obj, dict):
            return obj.get(attr, default)
        return default

    # Helper to get enum value
    def get_enum_value(val):
        if val is None:
            return None
        if hasattr(val, "value"):
            return val.value
        return str(val)

    # Helper to convert timezone-aware datetime to naive (MariaDB compatible)
    def to_naive_datetime(dt):
        if dt is None:
            return None
        if hasattr(dt, "replace") and hasattr(dt, "tzinfo") and dt.tzinfo is not None:
            return dt.replace(tzinfo=None)
        return dt

    # Update status - access state attribute directly
    wallee_status = ""
    state = get_attr(tx, "state")
    if state:
        wallee_status = get_enum_value(state).upper() if state else ""

    new_status = STATUS_MAP.get(wallee_status, doc.status)

    # Handle refund status
    refunded_amount = get_attr(tx, "refunded_amount") or 0
    if refunded_amount > 0:
        authorized = get_attr(tx, "authorization_amount") or doc.amount
        if refunded_amount >= authorized:
            new_status = "Refunded"
        else:
            new_status = "Partially Refunded"

    doc.status = new_status

    # Update amounts - access attributes directly
    doc.authorized_amount = get_attr(tx, "authorization_amount")
    doc.captured_amount = get_attr(tx, "completed_amount")
    doc.refunded_amount = refunded_amount

    # Update failure reason
    failure_reason = get_attr(tx, "failure_reason")
    if failure_reason:
        if isinstance(failure_reason, dict):
            doc.failure_reason = failure_reason.get("description") or str(failure_reason)
        elif hasattr(failure_reason, "description"):
            doc.failure_reason = failure_reason.description
        else:
            doc.failure_reason = str(failure_reason)

    # Update fees and settlement
    doc.wallee_fee = get_attr(tx, "total_applied_fees")
    doc.settlement_amount = get_attr(tx, "total_settled_amount")
    if doc.captured_amount and doc.wallee_fee:
        doc.net_amount = doc.captured_amount - doc.wallee_fee

    # Update authorization environment
    auth_env = get_attr(tx, "authorization_environment")
    if auth_env:
        doc.authorization_environment = get_enum_value(auth_env)

    # Update payment connector info
    payment_connector = get_attr(tx, "payment_connector_configuration")
    if payment_connector:
        connector_id = get_attr(payment_connector, "id")
        connector_name = get_attr(payment_connector, "name")
        doc.payment_connector = connector_name or (f"Connector #{connector_id}" if connector_id else None)

    # Update terminal info
    terminal_obj = get_attr(tx, "terminal")
    if terminal_obj:
        terminal_id = get_attr(terminal_obj, "id")
        if terminal_id:
            doc.terminal_id = int(terminal_id)
        terminal_name = get_attr(terminal_obj, "name") or get_attr(terminal_obj, "device_name")
        if terminal_name and not doc.terminal:
            # Try to find matching terminal in our system
            existing_terminal = frappe.db.get_value(
                "Wallee Payment Terminal",
                {"terminal_id": terminal_id},
                "name"
            )
            if existing_terminal:
                doc.terminal = existing_terminal

    # Update user interface type (Terminal, Payment Page, etc.)
    ui_type = get_attr(tx, "user_interface_type")
    if ui_type:
        ui_value = get_enum_value(ui_type)
        if ui_value == "TERMINAL":
            doc.is_terminal_transaction = 1
            if doc.transaction_type != "Terminal":
                doc.transaction_type = "Terminal"

    # Update customer info
    customer_email = get_attr(tx, "customer_email_address")
    if customer_email:
        doc.email = customer_email

    # Update merchant reference if not set
    merchant_ref = get_attr(tx, "merchant_reference")
    if merchant_ref and not doc.merchant_reference:
        doc.merchant_reference = merchant_ref

    # Update external ID
    external_id = get_attr(tx, "meta_data")
    if external_id and isinstance(external_id, dict):
        doc.external_id = external_id.get("externalId") or external_id.get("external_id")

    # Update card details from payment method data
    _update_card_details(doc, tx)

    # Update completion details
    _update_completion_details(doc, tx)

    # Update line items
    _update_line_items(doc, tx)

    # Update timestamps from Wallee (more accurate than local time)
    authorized_on = get_attr(tx, "authorized_on")
    if authorized_on and (new_status == "Authorized" or doc.authorized_amount):
        doc.authorized_on = to_naive_datetime(authorized_on)

    completed_on = get_attr(tx, "completed_on")
    if completed_on and new_status in ["Completed", "Fulfill"]:
        doc.completed_on = to_naive_datetime(completed_on)

    if new_status == "Voided" and not doc.voided_on:
        doc.voided_on = now_datetime()

    # Store comprehensive raw data for debugging
    raw_data = {
        "id": get_attr(tx, "id"),
        "state": get_enum_value(get_attr(tx, "state")),
        "authorization_amount": get_attr(tx, "authorization_amount"),
        "completed_amount": get_attr(tx, "completed_amount"),
        "refunded_amount": get_attr(tx, "refunded_amount"),
        "total_applied_fees": get_attr(tx, "total_applied_fees"),
        "total_settled_amount": get_attr(tx, "total_settled_amount"),
        "authorization_environment": get_enum_value(get_attr(tx, "authorization_environment")),
        "user_interface_type": get_enum_value(get_attr(tx, "user_interface_type")),
        "customers_presence": get_enum_value(get_attr(tx, "customers_presence")),
        "merchant_reference": get_attr(tx, "merchant_reference"),
        "invoice_merchant_reference": get_attr(tx, "invoice_merchant_reference"),
        "currency": get_attr(tx, "currency"),
        "created_on": str(get_attr(tx, "created_on")) if get_attr(tx, "created_on") else None,
        "authorized_on": str(get_attr(tx, "authorized_on")) if get_attr(tx, "authorized_on") else None,
        "completed_on": str(get_attr(tx, "completed_on")) if get_attr(tx, "completed_on") else None,
        "terminal_id": get_attr(get_attr(tx, "terminal"), "id") if get_attr(tx, "terminal") else None,
        "payment_connector_id": get_attr(get_attr(tx, "payment_connector_configuration"), "id") if get_attr(tx, "payment_connector_configuration") else None,
        "version": get_attr(tx, "version"),
    }

    # Add token/card details if available
    token = get_attr(tx, "token")
    if token:
        tokenized_pm = get_attr(token, "tokenized_payment_method")
        if tokenized_pm:
            raw_data["card"] = {
                "brand": get_attr(tokenized_pm, "brand") or get_attr(tokenized_pm, "payment_method_brand"),
                "last_digits": get_attr(tokenized_pm, "last_digits"),
                "masked_number": get_attr(tokenized_pm, "masked_card_number"),
                "holder_name": get_attr(tokenized_pm, "holder_name"),
                "expiry_month": get_attr(tokenized_pm, "expiry_month"),
                "expiry_year": get_attr(tokenized_pm, "expiry_year"),
            }

    # Add line items if available
    line_items = get_attr(tx, "line_items")
    if line_items:
        raw_data["line_items"] = []
        for item in line_items:
            raw_data["line_items"].append({
                "name": get_attr(item, "name"),
                "unique_id": get_attr(item, "unique_id"),
                "sku": get_attr(item, "sku"),
                "quantity": get_attr(item, "quantity"),
                "amount": get_attr(item, "amount_including_tax"),
            })

    # Add completion info if available
    completions = get_attr(tx, "completions")
    if completions:
        raw_data["completions"] = []
        for comp in completions:
            raw_data["completions"].append({
                "id": get_attr(comp, "id"),
                "state": get_enum_value(get_attr(comp, "state")),
                "amount": get_attr(comp, "amount"),
            })

    doc.wallee_data = frappe.as_json(raw_data)

    doc.flags.ignore_validate = True
    doc.save(ignore_permissions=True)
    frappe.db.commit()


def _update_card_details(doc, tx):
    """Extract and update card details from transaction data."""
    # Helper to safely get attribute from object or dict
    def get_attr(obj, attr, default=None):
        if hasattr(obj, attr):
            return getattr(obj, attr, default)
        elif isinstance(obj, dict):
            return obj.get(attr, default)
        return default

    # Check for token data
    token = get_attr(tx, "token")
    if token:
        tokenized_pm = get_attr(token, "tokenized_payment_method")
        if tokenized_pm:
            doc.card_brand = get_attr(tokenized_pm, "brand") or get_attr(tokenized_pm, "payment_method_brand")
            last_digits = get_attr(tokenized_pm, "last_digits")
            masked = get_attr(tokenized_pm, "masked_card_number") or ""
            doc.card_last_four = last_digits or (masked[-4:] if masked else None)
            doc.card_holder_name = get_attr(tokenized_pm, "holder_name")
            doc.card_expiry_month = get_attr(tokenized_pm, "expiry_month")
            doc.card_expiry_year = get_attr(tokenized_pm, "expiry_year")

    # Check for allowed payment method brands
    brands = get_attr(tx, "allowed_payment_method_brands")
    if brands and not doc.payment_method_brand:
        if isinstance(brands, list) and len(brands) > 0:
            brand = brands[0]
            doc.payment_method_brand = get_attr(brand, "name") or str(brand)


def _update_completion_details(doc, tx):
    """Update completion/capture details."""
    # Helper to safely get attribute from object or dict
    def get_attr(obj, attr, default=None):
        if hasattr(obj, attr):
            return getattr(obj, attr, default)
        elif isinstance(obj, dict):
            return obj.get(attr, default)
        return default

    # Completion data might be in completions array
    completions = get_attr(tx, "completions") or []

    if completions:
        # Get the last successful completion
        for completion in reversed(completions):
            state = get_attr(completion, "state")
            if state:
                state_value = state.value if hasattr(state, "value") else str(state)
                if state_value.upper() == "SUCCESSFUL":
                    doc.completion_id = str(get_attr(completion, "id") or "")
                    doc.completion_state = "Successful"
                    doc.completion_amount = get_attr(completion, "amount")
                    doc.statement_descriptor = get_attr(completion, "statement_descriptor")
                    doc.processor_reference = get_attr(completion, "processor_reference")
                    break


def _update_line_items(doc, tx):
    """Update line items from transaction data."""
    # Helper to safely get attribute from object or dict
    def get_attr(obj, attr, default=None):
        if hasattr(obj, attr):
            return getattr(obj, attr, default)
        elif isinstance(obj, dict):
            return obj.get(attr, default)
        return default

    line_items = get_attr(tx, "line_items") or []

    if not line_items:
        return

    # Clear existing items
    doc.items = []

    for item in line_items:
        # Determine item type
        item_type = get_attr(item, "type")
        if item_type:
            item_type = item_type.value if hasattr(item_type, "value") else str(item_type)
        else:
            item_type = "PRODUCT"

        doc.append("items", {
            "item_name": get_attr(item, "name") or _("Unknown Item"),
            "unique_id": get_attr(item, "unique_id"),
            "sku": get_attr(item, "sku"),
            "quantity": get_attr(item, "quantity") or 1,
            "unit_price": get_attr(item, "unit_price_including_tax"),
            "amount_including_tax": get_attr(item, "amount_including_tax"),
            "tax_amount": get_attr(item, "tax_amount"),
            "discount_amount": get_attr(item, "discount_including_tax"),
            "item_type": item_type.upper() if item_type else "PRODUCT",
            "attributes": frappe.as_json(get_attr(item, "attributes")) if get_attr(item, "attributes") else None
        })


def update_refund_from_wallee(doc, refund_data):
    """
    Update transaction document with refund data from Wallee API.

    Args:
        doc: Wallee Transaction document
        refund_data: Refund data from Wallee API
    """
    if hasattr(refund_data, "to_dict"):
        refund_data = refund_data.to_dict()

    doc.refund_id = str(refund_data.get("id", ""))

    # Map refund state
    refund_state = refund_data.get("state")
    if refund_state:
        state_value = refund_state.value if hasattr(refund_state, "value") else str(refund_state)
        state_map = {
            "PENDING": "Pending",
            "SUCCESSFUL": "Successful",
            "FAILED": "Failed",
            "MANUAL_CHECK": "Manual Check",
        }
        doc.refund_state = state_map.get(state_value.upper(), state_value)

    doc.refunded_amount = refund_data.get("amount")
    doc.refund_processor_reference = refund_data.get("processor_reference") or refund_data.get("processorReference")

    succeeded_on = refund_data.get("succeeded_on") or refund_data.get("succeededOn")
    if succeeded_on:
        doc.refund_date = succeeded_on
        doc.refunded_on = succeeded_on

    # Update transaction status based on refund
    if doc.refund_state == "Successful":
        if doc.refunded_amount >= doc.amount:
            doc.status = "Refunded"
        else:
            doc.status = "Partially Refunded"

    doc.flags.ignore_validate = True
    doc.save(ignore_permissions=True)
    frappe.db.commit()


def create_transaction_record(
    transaction_id,
    amount,
    currency,
    transaction_type="Online",
    reference_doctype=None,
    reference_name=None,
    customer=None,
    terminal=None,
    **kwargs
):
    """Create a new Wallee Transaction record"""
    doc = frappe.new_doc("Wallee Transaction")
    doc.transaction_id = str(transaction_id)
    doc.amount = amount
    doc.currency = currency
    doc.transaction_type = transaction_type
    doc.reference_doctype = reference_doctype
    doc.reference_name = reference_name
    doc.customer = customer
    doc.status = "Pending"

    if terminal:
        doc.terminal = terminal
        doc.is_terminal_transaction = 1
        doc.transaction_type = "Terminal"

    for key, value in kwargs.items():
        if hasattr(doc, key):
            setattr(doc, key, value)

    doc.insert(ignore_permissions=True)
    frappe.db.commit()

    return doc
