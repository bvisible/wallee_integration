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

    # Debug log - use print which goes to web server logs
    def debug_log(msg):
        print(f"[Wallee Success] {msg}")
        frappe.log_error(msg, "Wallee Debug")

    debug_log(f"START - payment_request={payment_request_name}")

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
        frappe.logger().info(f"[Wallee Success] PR status={context.payment_request.status}, ref={context.payment_request.reference_doctype}/{context.payment_request.reference_name}")

        # Check if already paid - redirect directly
        if context.payment_request.status in ["Paid", "Completed"] and context.payment_request.reference_doctype == "Sales Order":
            frappe.logger().info(f"[Wallee Success] Already paid, redirecting to {context.payment_request.reference_name}")
            frappe.local.flags.redirect_location = f"/thank_you?sales_order={context.payment_request.reference_name}"
            raise frappe.Redirect

        # Find linked Wallee Transaction
        wallee_tx_name = frappe.db.get_value(
            "Wallee Transaction",
            {"payment_request": payment_request_name},
            "name"
        )
        frappe.logger().info(f"[Wallee Success] Wallee TX={wallee_tx_name}")

        if wallee_tx_name:
            context.transaction = frappe.get_doc("Wallee Transaction", wallee_tx_name)
            frappe.logger().info(f"[Wallee Success] TX status BEFORE sync={context.transaction.status}")

            # Sync status from Wallee API
            try:
                context.transaction.sync_status()
                context.transaction.reload()
                frappe.logger().info(f"[Wallee Success] TX status AFTER sync={context.transaction.status}")
            except Exception as e:
                frappe.log_error(f"Error syncing Wallee transaction: {str(e)}", "Wallee Success Page")

            # Check if payment is successful
            if context.transaction.status in ["Completed", "Fulfill", "Authorized"]:
                context.status = "success"
                frappe.logger().info(f"[Wallee Success] Payment successful, calling handle_payment_success")

                # Call webshop payment handler to create Sales Order
                try:
                    from webshop.controllers.payment_handler import handle_payment_success
                    result = handle_payment_success(payment_request_id=payment_request_name)

                    frappe.logger().info(f"[Wallee Success] handle_payment_success result={result}")

                    if result and result.get("status") == "success":
                        redirect_url = result.get("redirect_to")
                        if redirect_url:
                            frappe.logger().info(f"[Wallee Success] Redirecting to {redirect_url}")
                            # Redirect to thank you page
                            frappe.local.flags.redirect_location = redirect_url
                            raise frappe.Redirect
                        else:
                            # Success but no redirect URL - find Sales Order from Payment Request
                            pr = frappe.get_doc("Payment Request", payment_request_name)
                            if pr.reference_doctype == "Sales Order":
                                frappe.logger().info(f"[Wallee Success] Fallback redirect to {pr.reference_name}")
                                frappe.local.flags.redirect_location = f"/thank_you?sales_order={pr.reference_name}"
                                raise frappe.Redirect
                    else:
                        # Payment handler returned error
                        error_msg = result.get("message") if result else _("Error processing payment")
                        frappe.logger().error(f"[Wallee Success] Payment handler error: {error_msg}")
                        context.error = error_msg

                except frappe.Redirect:
                    raise  # Re-raise redirect exception
                except Exception as e:
                    frappe.log_error(f"Error in handle_payment_success: {str(e)}\n{frappe.get_traceback()}", "Wallee Success Page")
                    frappe.logger().error(f"[Wallee Success] Exception: {str(e)}")
                    context.error = _("Error creating order. Please contact support.")

            elif context.transaction.status in ["Failed", "Decline", "Voided"]:
                context.status = "failed"
                context.error = context.transaction.failure_reason or _("Payment was declined")
                frappe.logger().info(f"[Wallee Success] Payment failed: {context.error}")

            else:
                # Payment still pending
                context.status = "pending"
                frappe.logger().info(f"[Wallee Success] Payment pending, status={context.transaction.status}")
        else:
            context.error = _("Transaction record not found")
            frappe.logger().error(f"[Wallee Success] No Wallee Transaction found for {payment_request_name}")

    except frappe.Redirect:
        frappe.logger().info(f"[Wallee Success] Redirect raised")
        raise  # Re-raise redirect
    except Exception as e:
        frappe.log_error(f"Wallee success page error: {str(e)}", "Wallee Success Page")
        frappe.logger().error(f"[Wallee Success] Exception: {str(e)}")
        context.error = _("An error occurred while processing your payment")

    frappe.logger().info(f"[Wallee Success] END - status={context.status}, error={context.error}")
    return context
