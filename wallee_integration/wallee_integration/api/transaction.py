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


def create_transaction(line_items, currency, **kwargs):
	"""
	Create a new Wallee transaction

	Args:
		line_items: List of line items (name, quantity, unit_price, etc.)
		currency: Currency code (e.g., 'CHF', 'EUR')
		**kwargs: Additional transaction parameters

	Returns:
		Transaction object from Wallee
	"""
	from wallee.service.transactions_service import TransactionsService
	from wallee.models import LineItemCreate, TransactionCreate

	config = get_wallee_client()
	space_id = get_space_id()
	service = TransactionsService(config)

	# Build line items
	wallee_line_items = []
	for item in line_items:
		line_item = LineItemCreate(
			name=item.get("name"),
			quantity=item.get("quantity", 1),
			amount_including_tax=item.get("amount"),
			unique_id=item.get("unique_id", str(frappe.generate_hash()[:8])),
			type="PRODUCT"
		)
		wallee_line_items.append(line_item)

	# Create transaction
	transaction_create = TransactionCreate(
		line_items=wallee_line_items,
		currency=currency,
		auto_confirmation_enabled=kwargs.get("auto_confirm", True),
		merchant_reference=kwargs.get("merchant_reference"),
		customer_id=kwargs.get("customer_id"),
		customer_email_address=kwargs.get("email"),
		success_url=kwargs.get("success_url"),
		failed_url=kwargs.get("failed_url")
	)

	try:
		response = service.create(space_id, transaction_create)
		log_api_call("POST", "transactions", transaction_create.to_dict(), response.to_dict())
		return response
	except Exception as e:
		log_api_call("POST", "transactions", transaction_create.to_dict(), error=e)
		raise


def get_transaction_status(transaction_id):
	"""Get transaction status from Wallee"""
	from wallee.service.transactions_service import TransactionsService

	config = get_wallee_client()
	space_id = get_space_id()
	service = TransactionsService(config)

	try:
		response = service.read(space_id, transaction_id)
		log_api_call("GET", f"transactions/{transaction_id}", response_data=response.to_dict())
		return {
			"id": response.id,
			"state": response.state.value if response.state else None,
			"authorized_amount": response.authorized_amount,
			"completed_amount": response.completed_amount,
			"refunded_amount": response.refunded_amount,
			"failure_reason": response.failure_reason.description if response.failure_reason else None,
			"payment_connector_configuration": response.payment_connector_configuration,
		}
	except Exception as e:
		log_api_call("GET", f"transactions/{transaction_id}", error=e)
		raise


def complete_transaction_online(transaction_id):
	"""Complete an online transaction (capture)"""
	from wallee.service.transactions_service import TransactionsService

	config = get_wallee_client()
	space_id = get_space_id()
	service = TransactionsService(config)

	try:
		response = service.complete_online(space_id, transaction_id)
		log_api_call("POST", f"transactions/{transaction_id}/complete-online", response_data=response.to_dict())
		return response
	except Exception as e:
		log_api_call("POST", f"transactions/{transaction_id}/complete-online", error=e)
		raise


def capture_transaction(transaction_id):
	"""Capture an authorized transaction"""
	return complete_transaction_online(transaction_id)


def void_transaction(transaction_id):
	"""Void a pending or authorized transaction"""
	from wallee.service.transactions_service import TransactionsService

	config = get_wallee_client()
	space_id = get_space_id()
	service = TransactionsService(config)

	try:
		response = service.complete_offline(space_id, transaction_id)
		log_api_call("POST", f"transactions/{transaction_id}/void", response_data=response.to_dict())
		return response
	except Exception as e:
		log_api_call("POST", f"transactions/{transaction_id}/void", error=e)
		raise


def get_payment_page_url(transaction_id):
	"""Get the payment page URL for a transaction"""
	from wallee.service.transactions_service import TransactionsService

	config = get_wallee_client()
	space_id = get_space_id()
	service = TransactionsService(config)

	try:
		response = service.build_payment_page_url(space_id, transaction_id)
		log_api_call("GET", f"transactions/{transaction_id}/payment-page-url", response_data=response)
		return response
	except Exception as e:
		log_api_call("GET", f"transactions/{transaction_id}/payment-page-url", error=e)
		raise


def search_transactions(filters=None, page=0, size=20):
	"""Search transactions with filters"""
	from wallee.service.transactions_service import TransactionsService
	from wallee.models import EntityQuery, EntityQueryFilter

	config = get_wallee_client()
	space_id = get_space_id()
	service = TransactionsService(config)

	query = EntityQuery(
		number_of_entities=size,
		start_position=page * size
	)

	if filters:
		query.filter = EntityQueryFilter(**filters)

	try:
		response = service.search(space_id, query)
		log_api_call("POST", "transactions/search", query.to_dict(), [t.to_dict() for t in response])
		return response
	except Exception as e:
		log_api_call("POST", "transactions/search", query.to_dict(), error=e)
		raise
