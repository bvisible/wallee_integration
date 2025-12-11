# -*- coding: utf-8 -*-
import frappe
from frappe import _

no_cache = 1


def get_context(context):
    """
    Handle Wallee payment failed redirect.

    URL: /wallee/failed?payment_request=ACC-PRQ-XXX
    """
    payment_request_name = frappe.form_dict.get("payment_request")

    # Initialize context
    context.transaction = None
    context.payment_request = None
    context.failure_reason = None

    if not payment_request_name:
        context.failure_reason = _("Missing payment request reference")
        return context

    try:
        # Get Payment Request
        if frappe.db.exists("Payment Request", payment_request_name):
            context.payment_request = frappe.get_doc("Payment Request", payment_request_name)

        # Find linked Wallee Transaction
        wallee_tx_name = frappe.db.get_value(
            "Wallee Transaction",
            {"payment_request": payment_request_name},
            "name"
        )

        if wallee_tx_name:
            context.transaction = frappe.get_doc("Wallee Transaction", wallee_tx_name)

            # Sync status from Wallee API
            try:
                context.transaction.sync_status()
                context.transaction.reload()
            except Exception as e:
                frappe.log_error(f"Error syncing Wallee transaction: {str(e)}", "Wallee Failed Page")

            context.failure_reason = context.transaction.failure_reason

        if not context.failure_reason:
            context.failure_reason = _("Payment was declined or cancelled")

    except Exception as e:
        frappe.log_error(f"Wallee failed page error: {str(e)}", "Wallee Failed Page")
        context.failure_reason = _("An error occurred while retrieving payment information")

    return context
