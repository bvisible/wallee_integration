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


def get_transaction_invoice(transaction_id):
	"""
	Find the TransactionInvoice linked to a given transaction.

	Args:
		transaction_id: Wallee transaction ID

	Returns:
		TransactionInvoice object or None
	"""
	from wallee.service.transaction_invoices_service import TransactionInvoicesService

	config = get_wallee_client()
	space_id = get_space_id()
	service = TransactionInvoicesService(config)

	try:
		response = service.get_payment_transactions_invoices(space_id, limit=100)
		log_api_call("GET", "payment/transactions/invoices", {"transaction_id": transaction_id})

		# Response is InvoiceListResponse - extract the list of invoices
		invoices = getattr(response, "data", None) or getattr(response, "items", None) or []
		if isinstance(response, list):
			invoices = response

		for invoice in invoices:
			linked_tx = getattr(invoice, "linked_transaction", None)
			if linked_tx and int(linked_tx) == int(transaction_id):
				return invoice

	except Exception as e:
		log_api_call("GET", "payment/transactions/invoices", {"transaction_id": transaction_id}, error=e)
		frappe.log_error("Wallee Invoice Search Error", f"TX {transaction_id}: {str(e)}")

	return None


def replace_invoice(invoice_id, line_items, sent_to_customer=False,
					external_id=None, merchant_reference=None, billing_address=None):
	"""
	Replace a transaction invoice with updated data.

	Args:
		invoice_id: Wallee invoice ID
		line_items: List of LineItemCreate objects
		sent_to_customer: Whether to email the invoice to customer
		external_id: Idempotency key (required, auto-generated if not provided)
		merchant_reference: Optional merchant reference
		billing_address: Optional AddressCreate object

	Returns:
		TransactionInvoice object
	"""
	from wallee.service.transaction_invoices_service import TransactionInvoicesService
	from wallee.models.transaction_invoice_replacement import TransactionInvoiceReplacement

	config = get_wallee_client()
	space_id = get_space_id()
	service = TransactionInvoicesService(config)

	if not external_id:
		external_id = f"inv-replace-{invoice_id}-{frappe.generate_hash()[:8]}"

	replacement = TransactionInvoiceReplacement(
		line_items=line_items,
		external_id=external_id,
		sent_to_customer=sent_to_customer,
		merchant_reference=merchant_reference,
		billing_address=billing_address
	)

	try:
		response = service.post_payment_transactions_invoices_id_replace(
			invoice_id,
			space_id,
			transaction_invoice_replacement=replacement
		)
		log_api_call(
			"POST",
			f"payment/transactions/invoices/{invoice_id}/replace",
			{"sent_to_customer": sent_to_customer},
			{"id": getattr(response, "id", None)}
		)
		return response
	except Exception as e:
		log_api_call(
			"POST",
			f"payment/transactions/invoices/{invoice_id}/replace",
			{"sent_to_customer": sent_to_customer},
			error=e
		)
		raise


def manage_invoice_after_completion(transaction_id, local_transaction_name=None):
	"""
	Manage invoice after a transaction completes.

	Called as a background job after transaction status transitions to Completed/Fulfill.
	Controls whether the invoice is sent to the customer based on Wallee Settings.
	Also rebuilds line items with proper tax information from the reference document.

	Args:
		transaction_id: Wallee transaction ID
		local_transaction_name: Local Wallee Transaction document name
	"""
	from wallee import LineItemCreate, LineItemType, TaxCreate

	try:
		settings = frappe.get_single("Wallee Settings")
		send_to_customer = bool(settings.get("send_invoice_to_customer"))

		# Find the invoice for this transaction
		invoice = get_transaction_invoice(transaction_id)

		if not invoice:
			# Invoice may not be ready yet - log and return silently
			frappe.log_error(
				"Wallee Invoice Not Found",
				f"No invoice found for TX {transaction_id}. It may not be generated yet."
			)
			return

		invoice_id = getattr(invoice, "id", None)
		if not invoice_id:
			return

		# Get the original line items from the invoice
		original_line_items = getattr(invoice, "line_items", None) or []

		# Try to rebuild line items with proper tax info from reference document
		rebuilt_line_items = _rebuild_line_items_with_taxes(
			original_line_items, local_transaction_name
		)

		if not rebuilt_line_items:
			# Fallback: convert original line items to LineItemCreate
			rebuilt_line_items = _convert_to_line_item_creates(original_line_items)

		if not rebuilt_line_items:
			frappe.log_error(
				"Wallee Invoice No Items",
				f"No line items to replace for TX {transaction_id}, invoice {invoice_id}"
			)
			return

		# Replace the invoice
		merchant_ref = getattr(invoice, "merchant_reference", None)
		replace_invoice(
			invoice_id=invoice_id,
			line_items=rebuilt_line_items,
			sent_to_customer=send_to_customer,
			merchant_reference=merchant_ref
		)

	except Exception as e:
		frappe.log_error(
			"Wallee Invoice Management Error",
			f"TX {transaction_id}: {str(e)}"
		)


def _rebuild_line_items_with_taxes(original_line_items, local_transaction_name):
	"""
	Rebuild line items from the reference ERPNext document with proper tax info.

	Args:
		original_line_items: Original LineItem objects from Wallee invoice
		local_transaction_name: Local Wallee Transaction document name

	Returns:
		list of LineItemCreate objects, or None if no reference document
	"""
	from wallee import LineItemCreate, LineItemType, TaxCreate
	from wallee_integration.wallee_integration.api.tax_utils import get_taxes_for_line_items

	if not local_transaction_name:
		return None

	try:
		doc = frappe.get_doc("Wallee Transaction", local_transaction_name)
	except Exception:
		return None

	ref_doctype = doc.reference_doctype
	ref_name = doc.reference_name

	if not ref_doctype or not ref_name:
		return None

	# Get taxes from the reference document
	taxes_data = get_taxes_for_line_items(ref_doctype, ref_name)

	wallee_taxes = None
	if taxes_data:
		wallee_taxes = [
			TaxCreate(rate=float(t["rate"]), title=t["title"])
			for t in taxes_data
		]

	# Rebuild line items from originals, adding tax info
	rebuilt = []
	for item in original_line_items:
		item_type = LineItemType.PRODUCT
		orig_type = getattr(item, "type", None)
		if orig_type:
			type_val = orig_type.value if hasattr(orig_type, "value") else str(orig_type)
			type_val = type_val.upper()
			if type_val == "SHIPPING":
				item_type = LineItemType.SHIPPING
			elif type_val == "DISCOUNT":
				item_type = LineItemType.DISCOUNT
			elif type_val == "FEE":
				item_type = LineItemType.FEE

		line_item = LineItemCreate(
			name=getattr(item, "name", None) or _("Item"),
			quantity=float(getattr(item, "quantity", 1)),
			amount_including_tax=float(getattr(item, "amount_including_tax", 0)),
			unique_id=getattr(item, "unique_id", None) or str(frappe.generate_hash()[:8]),
			type=item_type,
			sku=getattr(item, "sku", None),
			taxes=wallee_taxes
		)
		rebuilt.append(line_item)

	return rebuilt if rebuilt else None


def _convert_to_line_item_creates(original_line_items):
	"""
	Convert original LineItem objects to LineItemCreate objects (without tax changes).

	Args:
		original_line_items: List of LineItem objects from Wallee

	Returns:
		list of LineItemCreate objects
	"""
	from wallee import LineItemCreate, LineItemType

	items = []
	for item in original_line_items:
		item_type = LineItemType.PRODUCT
		orig_type = getattr(item, "type", None)
		if orig_type:
			type_val = orig_type.value if hasattr(orig_type, "value") else str(orig_type)
			type_val = type_val.upper()
			if type_val == "SHIPPING":
				item_type = LineItemType.SHIPPING
			elif type_val == "DISCOUNT":
				item_type = LineItemType.DISCOUNT
			elif type_val == "FEE":
				item_type = LineItemType.FEE

		line_item = LineItemCreate(
			name=getattr(item, "name", None) or _("Item"),
			quantity=float(getattr(item, "quantity", 1)),
			amount_including_tax=float(getattr(item, "amount_including_tax", 0)),
			unique_id=getattr(item, "unique_id", None) or str(frappe.generate_hash()[:8]),
			type=item_type,
			sku=getattr(item, "sku", None)
		)
		items.append(line_item)

	return items if items else None
