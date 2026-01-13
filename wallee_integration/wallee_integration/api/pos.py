# -*- coding: utf-8 -*-
# Copyright (c) 2024, Neoservice and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from wallee_integration.wallee_integration.api.client import (
	get_wallee_client,
	get_space_id,
	log_api_call
)


@frappe.whitelist()
def initiate_terminal_payment(amount, currency, terminal=None, pos_invoice=None, customer=None):
	"""
	Initiate a terminal payment for POS

	Args:
		amount: Amount to charge
		currency: Currency code
		terminal: Terminal name (uses default if not specified)
		pos_invoice: POS Invoice reference
		customer: Customer ID

	Returns:
		Transaction details and status
	"""
	from wallee_integration.wallee_integration.api.transaction import create_transaction
	from wallee_integration.wallee_integration.api.terminal import initiate_terminal_transaction
	from wallee_integration.wallee_integration.doctype.wallee_transaction.wallee_transaction import (
		create_transaction_record
	)
	from wallee_integration.wallee_integration.doctype.wallee_payment_terminal.wallee_payment_terminal import (
		get_default_terminal
	)

	settings = frappe.get_single("Wallee Settings")

	if not settings.enabled or not settings.enable_pos_terminal:
		frappe.throw(_("POS Terminal payments are not enabled"))

	# Get terminal
	if terminal:
		terminal_doc = frappe.get_doc("Wallee Payment Terminal", terminal)
	else:
		terminal_doc = get_default_terminal()

	if not terminal_doc:
		frappe.throw(_("No terminal configured. Please set up a payment terminal."))

	if terminal_doc.status != "Active":
		frappe.throw(_("Terminal {0} is not active").format(terminal_doc.terminal_name))

	# Create line item for the payment
	line_items = [{
		"name": f"POS Payment - {pos_invoice or 'Direct'}",
		"quantity": 1,
		"amount": float(amount),
		"unique_id": frappe.generate_hash()[:8]
	}]

	# Create transaction in Wallee
	# IMPORTANT: For terminal payments, auto_confirm must be False
	# The transaction needs to be in PENDING state for terminal processing
	transaction = create_transaction(
		line_items=line_items,
		currency=currency,
		merchant_reference=pos_invoice or frappe.generate_hash()[:16],
		auto_confirm=False
	)

	transaction_id = transaction.get("transaction_id")
	merchant_reference = pos_invoice or frappe.generate_hash()[:16]

	# Create local transaction record
	local_transaction = create_transaction_record(
		transaction_id=transaction_id,
		amount=amount,
		currency=currency,
		transaction_type="Terminal",
		terminal=terminal_doc.name,
		pos_invoice=pos_invoice,
		customer=customer,
		merchant_reference=merchant_reference
	)

	# Initiate payment on terminal
	try:
		result = initiate_terminal_transaction(terminal_doc.terminal_id, transaction_id)

		return {
			"success": True,
			"transaction_name": local_transaction.name,
			"transaction_id": transaction_id,
			"terminal": terminal_doc.terminal_name,
			"amount": amount,
			"currency": currency,
			"status": "Processing",
			"message": _("Payment initiated on terminal. Please complete on device.")
		}
	except Exception as e:
		# Update transaction status to failed
		local_transaction.status = "Failed"
		local_transaction.failure_reason = str(e)
		local_transaction.save(ignore_permissions=True)
		frappe.db.commit()

		frappe.throw(_("Failed to initiate terminal payment: {0}").format(str(e)))


@frappe.whitelist()
def check_terminal_payment_status(transaction_name):
	"""
	Check the status of a terminal payment

	Args:
		transaction_name: Local transaction name

	Returns:
		Current payment status
	"""
	from wallee_integration.wallee_integration.api.transaction import get_full_transaction
	from wallee_integration.wallee_integration.doctype.wallee_transaction.wallee_transaction import (
		update_transaction_from_wallee
	)

	doc = frappe.get_doc("Wallee Transaction", transaction_name)

	if not doc.transaction_id:
		return {
			"success": False,
			"status": doc.status,
			"message": _("Transaction not found in Wallee")
		}

	try:
		# Use get_full_transaction to get the complete Transaction object
		# (not get_transaction_status which returns a dict)
		wallee_tx = get_full_transaction(doc.transaction_id)
		update_transaction_from_wallee(doc, wallee_tx)
		doc.reload()

		return {
			"success": True,
			"transaction_name": doc.name,
			"transaction_id": doc.transaction_id,
			"status": doc.status,
			"wallee_state": str(wallee_tx.state.value) if wallee_tx.state else None,
			"amount": doc.amount,
			"currency": doc.currency,
			"completed": doc.status in ["Completed", "Fulfill"],
			"failed": doc.status in ["Failed", "Decline", "Voided"],
			"failure_reason": doc.failure_reason
		}
	except Exception as e:
		frappe.log_error("Terminal Status Check Error", f"Transaction: {transaction_name}, Error: {str(e)}")
		return {
			"success": False,
			"status": doc.status,
			"message": str(e)
		}


@frappe.whitelist()
def cancel_terminal_payment(transaction_name):
	"""
	Cancel a pending terminal payment

	Args:
		transaction_name: Local transaction name

	Returns:
		Cancellation result
	"""
	from wallee_integration.wallee_integration.api.transaction import void_transaction

	doc = frappe.get_doc("Wallee Transaction", transaction_name)

	if doc.status not in ["Pending", "Processing", "Authorized"]:
		frappe.throw(_("Only pending or authorized transactions can be cancelled"))

	try:
		void_transaction(doc.transaction_id)
		doc.status = "Voided"
		doc.voided_on = frappe.utils.now_datetime()
		doc.save(ignore_permissions=True)
		frappe.db.commit()

		return {
			"success": True,
			"transaction_name": doc.name,
			"status": "Voided",
			"message": _("Payment cancelled successfully")
		}
	except Exception as e:
		frappe.throw(_("Failed to cancel payment: {0}").format(str(e)))


@frappe.whitelist()
def get_available_terminals():
	"""Get list of available terminals for POS"""
	terminals = frappe.get_all(
		"Wallee Payment Terminal",
		filters={"status": "Active"},
		fields=["name", "terminal_name", "terminal_id", "is_default", "pos_profile", "warehouse"]
	)

	return terminals


@frappe.whitelist()
def link_payment_to_invoice(transaction_name, pos_invoice):
	"""Link a completed payment to a POS Invoice"""
	doc = frappe.get_doc("Wallee Transaction", transaction_name)

	if doc.status != "Completed":
		frappe.throw(_("Only completed transactions can be linked to invoices"))

	doc.pos_invoice = pos_invoice
	doc.reference_doctype = "POS Invoice"
	doc.reference_name = pos_invoice
	doc.save(ignore_permissions=True)
	frappe.db.commit()

	return {
		"success": True,
		"message": _("Payment linked to invoice {0}").format(pos_invoice)
	}
