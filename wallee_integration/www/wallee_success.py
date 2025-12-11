# -*- coding: utf-8 -*-
import frappe
from frappe import _

no_cache = 1


def get_context(context):
    """
    Handle Wallee payment success redirect.

    URL: /wallee/success?payment_request=ACC-PRQ-XXX

    Flow:
    1. Get payment_request from URL
    2. Find linked Wallee Transaction
    3. Sync status from Wallee API
    4. If payment completed, create Sales Order and redirect to /thank_you
    5. If payment pending/failed, show status page
    """
    payment_request_name = frappe.form_dict.get("payment_request")

    # Initialize context
    context.transaction = None
    context.payment_request = None
    context.sales_order = None
    context.error = None
    context.status = "pending"

    if not payment_request_name:
        context.error = _("Missing payment request reference")
        return context

    try:
        # Get Payment Request
        if not frappe.db.exists("Payment Request", payment_request_name):
            context.error = _("Payment request not found")
            return context

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
                frappe.log_error(f"Error syncing Wallee transaction: {str(e)}", "Wallee Success Page")

            # Check if payment is successful
            if context.transaction.status in ["Completed", "Fulfill", "Authorized"]:
                context.status = "success"

                # Call webshop payment handler to create Sales Order
                try:
                    from webshop.controllers.payment_handler import handle_payment_success
                    result = handle_payment_success(payment_request_id=payment_request_name)

                    frappe.log_error(f"handle_payment_success result: {result}", "Wallee Debug")

                    if result and result.get("status") == "success":
                        redirect_url = result.get("redirect_to")
                        if redirect_url:
                            # Redirect to thank you page
                            frappe.local.flags.redirect_location = redirect_url
                            raise frappe.Redirect
                        else:
                            # Success but no redirect URL - find Sales Order from Payment Request
                            pr = frappe.get_doc("Payment Request", payment_request_name)
                            if pr.reference_doctype == "Sales Order":
                                frappe.local.flags.redirect_location = f"/thank_you?sales_order={pr.reference_name}"
                                raise frappe.Redirect
                    else:
                        # Payment handler returned error
                        context.error = result.get("message") if result else _("Error processing payment")

                except frappe.Redirect:
                    raise  # Re-raise redirect exception
                except Exception as e:
                    frappe.log_error(f"Error in handle_payment_success: {str(e)}\n{frappe.get_traceback()}", "Wallee Success Page")
                    context.error = _("Error creating order. Please contact support.")

            elif context.transaction.status in ["Failed", "Decline", "Voided"]:
                context.status = "failed"
                context.error = context.transaction.failure_reason or _("Payment was declined")

            else:
                # Payment still pending
                context.status = "pending"
        else:
            context.error = _("Transaction record not found")

    except frappe.Redirect:
        raise  # Re-raise redirect
    except Exception as e:
        frappe.log_error(f"Wallee success page error: {str(e)}", "Wallee Success Page")
        context.error = _("An error occurred while processing your payment")

    return context
