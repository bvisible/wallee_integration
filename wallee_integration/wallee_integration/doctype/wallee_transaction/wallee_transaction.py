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


def update_transaction_from_wallee(doc, data):
    """
    Update transaction document from Wallee API response.

    Args:
        doc: Wallee Transaction document
        data: Full transaction data from Wallee API (dict or object)
    """
    # Convert object to dict if needed
    if hasattr(data, "to_dict"):
        data = data.to_dict()

    # Update status
    wallee_status = ""
    if data.get("state"):
        if hasattr(data["state"], "value"):
            wallee_status = data["state"].value.upper()
        else:
            wallee_status = str(data["state"]).upper()

    new_status = STATUS_MAP.get(wallee_status, doc.status)

    # Handle refund status
    refunded_amount = data.get("refunded_amount") or data.get("refundedAmount") or 0
    if refunded_amount > 0:
        if refunded_amount >= (data.get("authorized_amount") or data.get("authorizedAmount") or doc.amount):
            new_status = "Refunded"
        else:
            new_status = "Partially Refunded"

    doc.status = new_status

    # Update amounts
    doc.authorized_amount = data.get("authorized_amount") or data.get("authorizedAmount")
    doc.captured_amount = data.get("completed_amount") or data.get("completedAmount")
    doc.refunded_amount = refunded_amount

    # Update failure reason
    failure_reason = data.get("failure_reason") or data.get("failureReason")
    if failure_reason:
        if isinstance(failure_reason, dict):
            doc.failure_reason = failure_reason.get("description") or str(failure_reason)
        elif hasattr(failure_reason, "description"):
            doc.failure_reason = failure_reason.description
        else:
            doc.failure_reason = str(failure_reason)

    # Update fees and settlement
    doc.wallee_fee = data.get("total_applied_fees") or data.get("totalAppliedFees")
    doc.settlement_amount = data.get("total_settled_amount") or data.get("totalSettledAmount")
    if doc.captured_amount and doc.wallee_fee:
        doc.net_amount = doc.captured_amount - doc.wallee_fee

    # Update authorization environment
    auth_env = data.get("authorization_environment") or data.get("authorizationEnvironment")
    if auth_env:
        doc.authorization_environment = str(auth_env.value if hasattr(auth_env, "value") else auth_env)

    # Update payment method info
    payment_connector = data.get("payment_connector_configuration") or data.get("paymentConnectorConfiguration")
    if payment_connector:
        if isinstance(payment_connector, dict):
            doc.payment_connector = payment_connector.get("name")
        elif hasattr(payment_connector, "name"):
            doc.payment_connector = payment_connector.name

    # Update card details from payment method data
    _update_card_details(doc, data)

    # Update completion details
    _update_completion_details(doc, data)

    # Update line items
    _update_line_items(doc, data)

    # Update timestamps
    if new_status == "Authorized" and not doc.authorized_on:
        doc.authorized_on = now_datetime()
    elif new_status in ["Completed", "Fulfill"] and not doc.completed_on:
        completed_on = data.get("completed_on") or data.get("completedOn")
        doc.completed_on = completed_on or now_datetime()
    elif new_status == "Voided" and not doc.voided_on:
        doc.voided_on = now_datetime()

    # Store raw data
    doc.wallee_data = frappe.as_json(data)

    doc.flags.ignore_validate = True
    doc.save(ignore_permissions=True)
    frappe.db.commit()


def _update_card_details(doc, data):
    """Extract and update card details from transaction data."""
    # Try to get payment method details
    # Wallee stores this in different places depending on the payment method

    # Check for token data
    token = data.get("token")
    if token:
        if isinstance(token, dict):
            token_data = token
        elif hasattr(token, "to_dict"):
            token_data = token.to_dict()
        else:
            token_data = {}

        if token_data.get("tokenizedPaymentMethod"):
            pm = token_data["tokenizedPaymentMethod"]
            doc.card_brand = pm.get("brand") or pm.get("paymentMethodBrand")
            doc.card_last_four = pm.get("lastDigits") or pm.get("maskedCardNumber", "")[-4:]
            doc.card_holder_name = pm.get("holderName")
            doc.card_expiry_month = pm.get("expiryMonth")
            doc.card_expiry_year = pm.get("expiryYear")

    # Check for allowed payment method brands
    brands = data.get("allowed_payment_method_brands") or data.get("allowedPaymentMethodBrands")
    if brands and not doc.payment_method_brand:
        if isinstance(brands, list) and len(brands) > 0:
            brand = brands[0]
            if isinstance(brand, dict):
                doc.payment_method_brand = brand.get("name")
            elif hasattr(brand, "name"):
                doc.payment_method_brand = brand.name
            else:
                doc.payment_method_brand = str(brand)


def _update_completion_details(doc, data):
    """Update completion/capture details."""
    # Completion data might be in completions array or as single completion
    completions = data.get("completions") or []

    if completions:
        # Get the last successful completion
        for completion in reversed(completions):
            if isinstance(completion, dict):
                comp_data = completion
            elif hasattr(completion, "to_dict"):
                comp_data = completion.to_dict()
            else:
                continue

            state = comp_data.get("state")
            if state:
                state_value = state.value if hasattr(state, "value") else str(state)
                if state_value.upper() == "SUCCESSFUL":
                    doc.completion_id = str(comp_data.get("id", ""))
                    doc.completion_state = "Successful"
                    doc.completion_amount = comp_data.get("amount")
                    doc.statement_descriptor = comp_data.get("statement_descriptor") or comp_data.get("statementDescriptor")
                    doc.processor_reference = comp_data.get("processor_reference") or comp_data.get("processorReference")
                    break


def _update_line_items(doc, data):
    """Update line items from transaction data."""
    line_items = data.get("line_items") or data.get("lineItems") or []

    if not line_items:
        return

    # Clear existing items
    doc.items = []

    for item in line_items:
        if isinstance(item, dict):
            item_data = item
        elif hasattr(item, "to_dict"):
            item_data = item.to_dict()
        else:
            continue

        # Determine item type
        item_type = item_data.get("type")
        if item_type:
            item_type = item_type.value if hasattr(item_type, "value") else str(item_type)
        else:
            item_type = "PRODUCT"

        doc.append("items", {
            "item_name": item_data.get("name", _("Unknown Item")),
            "unique_id": item_data.get("unique_id") or item_data.get("uniqueId"),
            "sku": item_data.get("sku"),
            "quantity": item_data.get("quantity", 1),
            "unit_price": item_data.get("unit_price_including_tax") or item_data.get("unitPriceIncludingTax"),
            "amount_including_tax": item_data.get("amount_including_tax") or item_data.get("amountIncludingTax"),
            "tax_amount": item_data.get("tax_amount") or item_data.get("taxAmount"),
            "discount_amount": item_data.get("discount_including_tax") or item_data.get("discountIncludingTax"),
            "item_type": item_type.upper() if item_type else "PRODUCT",
            "attributes": frappe.as_json(item_data.get("attributes")) if item_data.get("attributes") else None
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
