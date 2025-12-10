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


def create_refund(transaction_id, amount, external_id=None):
	"""
	Create a refund for a transaction

	Args:
		transaction_id: Wallee Transaction ID
		amount: Amount to refund
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
		amount=amount,
		external_id=external_id or frappe.generate_hash()[:16],
		type="MERCHANT_INITIATED_ONLINE"
	)

	try:
		response = service.refund(space_id, refund_create)
		log_api_call("POST", "refunds", refund_create.to_dict(), response.to_dict())

		# Update local transaction record
		update_transaction_after_refund(transaction_id, amount)

		return response
	except Exception as e:
		log_api_call("POST", "refunds", refund_create.to_dict(), error=e)
		raise


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


def update_transaction_after_refund(transaction_id, refund_amount):
	"""Update local transaction record after refund"""
	wallee_transaction = frappe.db.get_value(
		"Wallee Transaction",
		{"transaction_id": str(transaction_id)},
		"name"
	)

	if wallee_transaction:
		doc = frappe.get_doc("Wallee Transaction", wallee_transaction)
		current_refunded = doc.refunded_amount or 0
		doc.refunded_amount = current_refunded + refund_amount

		if doc.refunded_amount >= doc.amount:
			doc.status = "Refunded"
		else:
			doc.status = "Partially Refunded"

		doc.refunded_on = frappe.utils.now_datetime()
		doc.save(ignore_permissions=True)
		frappe.db.commit()
