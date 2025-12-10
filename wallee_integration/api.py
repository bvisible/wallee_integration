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
	try:
		data = frappe.request.get_data(as_text=True)
		signature = frappe.request.headers.get("X-Signature")

		settings = frappe.get_single("Wallee Settings")

		# Verify webhook signature if secret is configured
		if settings.webhook_secret:
			if not verify_webhook_signature(data, signature, settings.get_password("webhook_secret")):
				frappe.throw(_("Invalid webhook signature"), frappe.AuthenticationError)

		payload = json.loads(data)

		# Process based on event type
		entity_id = payload.get("entityId")
		listener_entity_technical_name = payload.get("listenerEntityTechnicalName")

		if listener_entity_technical_name == "Transaction":
			handle_transaction_webhook(entity_id, payload)
		elif listener_entity_technical_name == "Refund":
			handle_refund_webhook(entity_id, payload)
		elif listener_entity_technical_name == "PaymentTerminal":
			handle_terminal_webhook(entity_id, payload)

		return {"status": "success"}

	except Exception as e:
		frappe.log_error(
			message=str(e),
			title="Wallee Webhook Error"
		)
		raise


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
	"""Handle transaction status update from webhook"""
	from wallee_integration.wallee_integration.api.transaction import get_transaction_status
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
		status_data = get_transaction_status(transaction_id)
		update_transaction_from_wallee(doc, status_data)


def handle_refund_webhook(refund_id, payload):
	"""Handle refund status update from webhook"""
	from wallee_integration.wallee_integration.api.refund import get_refund_status

	status = get_refund_status(refund_id)

	if status and status.get("transaction_id"):
		# Update the related transaction
		handle_transaction_webhook(status["transaction_id"], payload)


def handle_terminal_webhook(terminal_id, payload):
	"""Handle terminal status update from webhook"""
	from wallee_integration.wallee_integration.api.terminal import get_terminal_details

	terminal = frappe.db.get_value(
		"Wallee Payment Terminal",
		{"terminal_id": terminal_id},
		"name"
	)

	if terminal:
		doc = frappe.get_doc("Wallee Payment Terminal", terminal)
		doc.sync_from_wallee()


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
