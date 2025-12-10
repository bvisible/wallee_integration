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
def create_refund(transaction_id, amount, reason=None, external_id=None):
	"""
	Create a refund for a transaction

	Args:
		transaction_id: Wallee Transaction ID
		amount: Amount to refund
		reason: Reason for refund
		external_id: Optional external reference ID

	Returns:
		Refund object from Wallee
	"""
	from wallee.service.refunds_service import RefundsService
	from wallee.models import RefundCreate

	config = get_wallee_client()
	space_id = get_space_id()
	service = RefundsService(config)

	refund_create = RefundCreate(
		transaction=transaction_id,
		amount=float(amount),
		external_id=external_id or frappe.generate_hash()[:16],
		type="MERCHANT_INITIATED_ONLINE"
	)

	try:
		response = service.refund(space_id, refund_create)
		response_dict = response.to_dict() if hasattr(response, "to_dict") else {}
		log_api_call("POST", "refunds", refund_create.to_dict(), response_dict)

		# Update local transaction record with new refund fields
		update_transaction_after_refund(transaction_id, response, reason)

		return response_dict
	except Exception as e:
		log_api_call("POST", "refunds", refund_create.to_dict(), error=e)
		frappe.throw(_("Failed to create refund: {0}").format(str(e)))


def get_refund_status(refund_id):
	"""Get refund status from Wallee"""
	from wallee.service.refunds_service import RefundsService

	config = get_wallee_client()
	space_id = get_space_id()
	service = RefundsService(config)

	try:
		response = service.read(space_id, refund_id)
		log_api_call("GET", f"refunds/{refund_id}", response_data=response.to_dict())
		return {
			"id": response.id,
			"state": response.state.value if response.state else None,
			"amount": response.amount,
			"transaction_id": response.transaction.id if response.transaction else None,
		}
	except Exception as e:
		log_api_call("GET", f"refunds/{refund_id}", error=e)
		raise


def search_refunds(transaction_id=None, page=0, size=20):
	"""Search refunds with filters"""
	from wallee.service.refunds_service import RefundsService
	from wallee.models import EntityQuery, EntityQueryFilter, EntityQueryFilterType

	config = get_wallee_client()
	space_id = get_space_id()
	service = RefundsService(config)

	query = EntityQuery(
		number_of_entities=size,
		start_position=page * size
	)

	if transaction_id:
		query.filter = EntityQueryFilter(
			type=EntityQueryFilterType.LEAF,
			field_name="transaction",
			operator="EQUALS",
			value=transaction_id
		)

	try:
		response = service.search(space_id, query)
		log_api_call("POST", "refunds/search", query.to_dict(), [r.to_dict() for r in response])
		return response
	except Exception as e:
		log_api_call("POST", "refunds/search", query.to_dict(), error=e)
		raise


def update_transaction_after_refund(transaction_id, refund_response, reason=None):
	"""
	Update local transaction record after refund with new fields

	Args:
		transaction_id: Wallee Transaction ID
		refund_response: Refund response object from Wallee API
		reason: Refund reason provided by user
	"""
	wallee_transaction = frappe.db.get_value(
		"Wallee Transaction",
		{"transaction_id": str(transaction_id)},
		"name"
	)

	if not wallee_transaction:
		return

	doc = frappe.get_doc("Wallee Transaction", wallee_transaction)

	# Extract refund data from response
	refund_id = getattr(refund_response, "id", None)
	refund_amount = getattr(refund_response, "amount", 0) or 0
	refund_state = getattr(refund_response, "state", None)
	processor_ref = getattr(refund_response, "processor_reference", None)
	succeeded_on = getattr(refund_response, "succeeded_on", None)

	# Convert state enum to string
	if refund_state and hasattr(refund_state, "value"):
		refund_state = refund_state.value

	# Map Wallee refund states to our states
	state_map = {
		"CREATED": "Pending",
		"SCHEDULED": "Pending",
		"PENDING": "Pending",
		"MANUAL_CHECK": "Manual Check",
		"FAILED": "Failed",
		"SUCCESSFUL": "Successful"
	}
	mapped_state = state_map.get(refund_state, refund_state)

	# Update refund fields
	doc.refund_id = str(refund_id) if refund_id else None
	doc.refund_state = mapped_state
	doc.refund_amount = (doc.refund_amount or 0) + float(refund_amount)
	doc.refund_reason = reason
	doc.refund_processor_reference = processor_ref

	if succeeded_on:
		doc.refund_date = succeeded_on
	else:
		doc.refund_date = frappe.utils.now_datetime()

	# Also update legacy fields for compatibility
	doc.refunded_amount = doc.refund_amount
	doc.refunded_on = doc.refund_date

	# Update transaction status
	if doc.refund_amount >= doc.amount:
		doc.status = "Refunded"
	else:
		doc.status = "Partially Refunded"

	doc.save(ignore_permissions=True)
	frappe.db.commit()
