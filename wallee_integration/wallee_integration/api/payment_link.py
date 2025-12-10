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


def create_payment_link(name, amount, currency, **kwargs):
	"""
	Create a payment link for invoicing

	Args:
		name: Name/description for the payment link
		amount: Amount to charge
		currency: Currency code
		**kwargs: Additional parameters (customer_id, email, etc.)

	Returns:
		Payment link object with URL
	"""
	from wallee.service.payment_links_service import PaymentLinksService
	from wallee.models import PaymentLinkCreate, LineItemCreate

	config = get_wallee_client()
	space_id = get_space_id()
	service = PaymentLinksService(config)

	line_item = LineItemCreate(
		name=name,
		quantity=1,
		amount_including_tax=amount,
		unique_id=frappe.generate_hash()[:8],
		type="PRODUCT"
	)

	link_create = PaymentLinkCreate(
		name=name,
		line_items=[line_item],
		currency=currency,
		external_id=kwargs.get("external_id", frappe.generate_hash()[:16]),
	)

	# Set optional parameters
	if kwargs.get("billing_address"):
		link_create.billing_address = kwargs["billing_address"]

	try:
		response = service.create(space_id, link_create)
		log_api_call("POST", "payment-links", link_create.to_dict(), response.to_dict())
		return {
			"id": response.id,
			"name": response.name,
			"url": response.url,
			"state": response.state.value if response.state else None,
			"external_id": response.external_id,
		}
	except Exception as e:
		log_api_call("POST", "payment-links", link_create.to_dict(), error=e)
		raise


def get_payment_link(link_id):
	"""Get payment link details"""
	from wallee.service.payment_links_service import PaymentLinksService

	config = get_wallee_client()
	space_id = get_space_id()
	service = PaymentLinksService(config)

	try:
		response = service.read(space_id, link_id)
		log_api_call("GET", f"payment-links/{link_id}", response_data=response.to_dict())
		return {
			"id": response.id,
			"name": response.name,
			"url": response.url,
			"state": response.state.value if response.state else None,
			"external_id": response.external_id,
		}
	except Exception as e:
		log_api_call("GET", f"payment-links/{link_id}", error=e)
		raise


def update_payment_link(link_id, **kwargs):
	"""Update a payment link"""
	from wallee.service.payment_links_service import PaymentLinksService
	from wallee.models import PaymentLinkUpdate

	config = get_wallee_client()
	space_id = get_space_id()
	service = PaymentLinksService(config)

	# First, read the current link
	current = service.read(space_id, link_id)

	link_update = PaymentLinkUpdate(
		id=link_id,
		version=current.version,
		name=kwargs.get("name", current.name),
	)

	try:
		response = service.update(space_id, link_update)
		log_api_call("PUT", f"payment-links/{link_id}", link_update.to_dict(), response.to_dict())
		return response
	except Exception as e:
		log_api_call("PUT", f"payment-links/{link_id}", link_update.to_dict(), error=e)
		raise


@frappe.whitelist()
def create_payment_link_for_invoice(sales_invoice):
	"""Create a payment link for a Sales Invoice"""
	if isinstance(sales_invoice, str):
		invoice = frappe.get_doc("Sales Invoice", sales_invoice)
	else:
		invoice = sales_invoice

	settings = frappe.get_single("Wallee Settings")
	if not settings.enabled:
		frappe.throw(_("Wallee Integration is not enabled"))

	result = create_payment_link(
		name=f"Invoice {invoice.name}",
		amount=invoice.grand_total,
		currency=invoice.currency,
		external_id=invoice.name,
	)

	# Create transaction record
	from wallee_integration.wallee_integration.doctype.wallee_transaction.wallee_transaction import (
		create_transaction_record
	)

	create_transaction_record(
		transaction_id=result["id"],
		amount=invoice.grand_total,
		currency=invoice.currency,
		transaction_type="Payment Link",
		reference_doctype="Sales Invoice",
		reference_name=invoice.name,
		customer=invoice.customer,
		merchant_reference=invoice.name
	)

	return result
