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


def get_terminals():
	"""Get all payment terminals from Wallee"""
	from wallee.service.payment_terminals_service import PaymentTerminalsService
	from wallee.models import EntityQuery

	config = get_wallee_client()
	space_id = get_space_id()
	service = PaymentTerminalsService(config)

	query = EntityQuery(number_of_entities=100)

	try:
		response = service.search(space_id, query)
		log_api_call("POST", "payment-terminals/search", response_data=[t.to_dict() for t in response])
		return response
	except Exception as e:
		log_api_call("POST", "payment-terminals/search", error=e)
		raise


def get_terminal_details(terminal_id):
	"""Get details of a specific terminal"""
	from wallee.service.payment_terminals_service import PaymentTerminalsService

	config = get_wallee_client()
	space_id = get_space_id()
	service = PaymentTerminalsService(config)

	try:
		response = service.read(space_id, terminal_id)
		log_api_call("GET", f"payment-terminals/{terminal_id}", response_data=response.to_dict())
		return {
			"id": response.id,
			"identifier": response.identifier,
			"name": response.name,
			"state": response.state.value if response.state else "Inactive",
			"type": response.type,
			"default_currency": response.default_currency,
			"configuration_version": response.configuration_version,
			"location_version": response.location_version,
			"device_serial_number": response.device_serial_number,
		}
	except Exception as e:
		log_api_call("GET", f"payment-terminals/{terminal_id}", error=e)
		raise


def initiate_terminal_transaction(terminal_id, transaction_id):
	"""
	Initiate a payment on a terminal

	Args:
		terminal_id: Wallee Terminal ID
		transaction_id: Wallee Transaction ID to process

	Returns:
		Terminal transaction result
	"""
	from wallee.service.payment_terminals_service import PaymentTerminalsService

	config = get_wallee_client()
	space_id = get_space_id()
	service = PaymentTerminalsService(config)

	try:
		response = service.perform_transaction(space_id, terminal_id, transaction_id)
		log_api_call(
			"POST",
			f"payment-terminals/{terminal_id}/perform-transaction",
			{"transaction_id": transaction_id},
			response.to_dict() if hasattr(response, "to_dict") else str(response)
		)
		return response
	except Exception as e:
		log_api_call(
			"POST",
			f"payment-terminals/{terminal_id}/perform-transaction",
			{"transaction_id": transaction_id},
			error=e
		)
		raise


def trigger_terminal_balance(terminal_id):
	"""Trigger final balance/settlement on a terminal"""
	from wallee.service.payment_terminals_service import PaymentTerminalsService

	config = get_wallee_client()
	space_id = get_space_id()
	service = PaymentTerminalsService(config)

	try:
		response = service.trigger_final_balance(space_id, terminal_id)
		log_api_call(
			"POST",
			f"payment-terminals/{terminal_id}/trigger-final-balance",
			response_data=response.to_dict() if hasattr(response, "to_dict") else str(response)
		)
		return response
	except Exception as e:
		log_api_call("POST", f"payment-terminals/{terminal_id}/trigger-final-balance", error=e)
		raise


def get_terminal_credentials(terminal_id):
	"""Get terminal connection credentials (for direct integration)"""
	from wallee.service.payment_terminals_service import PaymentTerminalsService

	config = get_wallee_client()
	space_id = get_space_id()
	service = PaymentTerminalsService(config)

	try:
		response = service.till_connection_credentials(space_id, terminal_id)
		log_api_call(
			"GET",
			f"payment-terminals/{terminal_id}/credentials",
			response_data=response.to_dict() if hasattr(response, "to_dict") else str(response)
		)
		return response
	except Exception as e:
		log_api_call("GET", f"payment-terminals/{terminal_id}/credentials", error=e)
		raise


@frappe.whitelist()
def sync_terminals_from_wallee():
	"""Sync all terminals from Wallee to ERPNext"""
	terminals = get_terminals()

	synced = 0
	for terminal in terminals:
		terminal_name = terminal.name or terminal.identifier

		if frappe.db.exists("Wallee Payment Terminal", {"terminal_id": terminal.id}):
			# Update existing
			doc = frappe.get_doc("Wallee Payment Terminal", {"terminal_id": terminal.id})
		else:
			# Create new
			doc = frappe.new_doc("Wallee Payment Terminal")
			doc.terminal_name = terminal_name

		doc.terminal_id = terminal.id
		doc.identifier = terminal.identifier
		doc.device_serial_number = terminal.device_serial_number
		doc.terminal_type = terminal.type
		doc.default_currency = terminal.default_currency
		doc.configuration_version = terminal.configuration_version
		doc.location_version = terminal.location_version
		doc.status = terminal.state.value if terminal.state else "Inactive"
		doc.last_sync = frappe.utils.now_datetime()

		doc.save(ignore_permissions=True)
		synced += 1

	frappe.db.commit()
	frappe.msgprint(_("{0} terminals synced from Wallee").format(synced))
	return synced
