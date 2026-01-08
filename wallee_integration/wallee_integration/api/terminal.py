# -*- coding: utf-8 -*-
# Copyright (c) 2024, Neoservice and contributors
# For license information, please see license.txt

import frappe
from frappe import _
import uuid
from wallee_integration.wallee_integration.api.client import (
	get_wallee_client,
	get_space_id,
	log_api_call
)

# Wallee Terminal Type IDs
# These IDs are fixed by Wallee and identify the terminal type
PHYSICAL_TERMINAL_TYPE_ID = 1568379599819
SIMULATOR_TERMINAL_TYPE_ID = None  # To be determined if needed


@frappe.whitelist()
def get_wallee_terminal_settings():
	"""
	Get terminal configuration settings from Wallee Settings DocType.
	These are required to create terminals via API.

	Returns:
		dict with configuration_version, location_version, and terminal_type_id
	"""
	settings = frappe.get_single("Wallee Settings")
	return {
		"configuration_version": settings.get("terminal_configuration_version"),
		"location_version": settings.get("terminal_location_version"),
		"terminal_type_id": PHYSICAL_TERMINAL_TYPE_ID,
		"space_id": settings.space_id
	}


@frappe.whitelist()
def get_existing_configurations():
	"""
	Get configuration and location version IDs from existing terminals.
	Useful when setting up the integration - extracts IDs from terminals created via UI.

	Returns:
		dict with unique configurations and locations found
	"""
	terminals = get_terminals()
	configs = {}
	locations = {}

	for terminal in terminals:
		if terminal.configuration_version and hasattr(terminal.configuration_version, 'id'):
			config_id = terminal.configuration_version.id
			config_name = terminal.configuration_version.configuration.name if (
				terminal.configuration_version.configuration and
				hasattr(terminal.configuration_version.configuration, 'name')
			) else f"Configuration {config_id}"
			configs[config_id] = {"id": config_id, "name": config_name}

		if terminal.location_version and hasattr(terminal.location_version, 'id'):
			loc_id = terminal.location_version.id
			loc_name = terminal.location_version.location.name if (
				terminal.location_version.location and
				hasattr(terminal.location_version.location, 'name')
			) else f"Location {loc_id}"
			locations[loc_id] = {"id": loc_id, "name": loc_name}

	return {
		"configurations": list(configs.values()),
		"locations": list(locations.values())
	}


def get_terminals():
	"""Get all payment terminals from Wallee (SDK 6.3.0+)"""
	from wallee.service.payment_terminals_service import PaymentTerminalsService

	config = get_wallee_client()
	space_id = get_space_id()
	service = PaymentTerminalsService(config)

	try:
		# SDK 6.3.0: get_payment_terminals returns TerminalListResponse with .data property
		response = service.get_payment_terminals(space_id)
		terminals = response.data if response.data else []
		log_api_call("GET", "payment-terminals", response_data=[t.to_dict() for t in terminals])
		return terminals
	except Exception as e:
		log_api_call("GET", "payment-terminals", error=e)
		raise


def get_terminal_details(terminal_id):
	"""Get details of a specific terminal"""
	from wallee.service.payment_terminals_service import PaymentTerminalsService

	config = get_wallee_client()
	space_id = get_space_id()
	service = PaymentTerminalsService(config)

	try:
		# SDK 6.3.0: Use get_payment_terminals_id instead of read
		response = service.get_payment_terminals_id(int(terminal_id), space_id)
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


@frappe.whitelist()
def get_terminal_types():
	"""
	Get available terminal types from existing terminals.
	Since SDK doesn't have a dedicated endpoint, we extract types from existing terminals.
	Returns list of unique terminal types found.

	Note: If no terminals exist in Wallee, this returns an empty list.
	Terminal Type IDs must be obtained from the Wallee portal in that case.
	"""
	try:
		terminals = get_terminals()
		types = {}
		for terminal in terminals:
			if terminal.type and terminal.type.id:
				type_info = terminal.type
				types[type_info.id] = {
					"id": type_info.id,
					"name": type_info.name if isinstance(type_info.name, str) else (
						type_info.name.get("en-US") or list(type_info.name.values())[0] if type_info.name else f"Type {type_info.id}"
					)
				}
		return list(types.values())
	except Exception as e:
		frappe.log_error("Terminal types error", str(e))
		return []


@frappe.whitelist()
def create_terminal(name, terminal_type_id, configuration_version=None, location_version=None):
	"""
	Create a new terminal in Wallee.

	Args:
		name: Terminal display name
		terminal_type_id: Wallee terminal type ID (e.g., A77 type ID)
		configuration_version: Optional configuration version ID
		location_version: Optional location version ID

	Returns:
		Created terminal data
	"""
	from wallee.service.payment_terminals_service import PaymentTerminalsService
	from wallee.models import PaymentTerminalCreate

	config = get_wallee_client()
	space_id = get_space_id()
	service = PaymentTerminalsService(config)

	terminal_create = PaymentTerminalCreate(
		name=name,
		external_id=str(uuid.uuid4()),
		type=int(terminal_type_id),
		configuration_version=int(configuration_version) if configuration_version else None,
		location_version=int(location_version) if location_version else None
	)

	try:
		response = service.post_payment_terminals(space=space_id, payment_terminal_create=terminal_create)
		result = {
			"id": response.id,
			"name": response.name,
			"identifier": response.identifier,
			"external_id": response.external_id,
			"state": response.state.value if response.state else None,
			"default_currency": response.default_currency,
		}
		log_api_call(
			"POST",
			"payment-terminals",
			{"name": name, "type": terminal_type_id},
			result
		)
		return result
	except Exception as e:
		log_api_call("POST", "payment-terminals", {"name": name, "type": terminal_type_id}, error=e)
		raise


@frappe.whitelist()
def link_terminal_device(terminal_id, serial_number):
	"""
	Link a terminal to a physical device using its serial number.

	Args:
		terminal_id: Wallee Terminal ID
		serial_number: Physical device serial number

	Returns:
		Updated terminal data after linking
	"""
	from wallee.service.payment_terminals_service import PaymentTerminalsService

	config = get_wallee_client()
	space_id = get_space_id()
	service = PaymentTerminalsService(config)

	try:
		# Link returns 204 No Content, so we fetch the terminal after linking
		service.post_payment_terminals_id_link(
			id=int(terminal_id),
			serial_number=serial_number,
			space=space_id
		)
		log_api_call(
			"POST",
			f"payment-terminals/{terminal_id}/link",
			{"serial_number": serial_number},
			{"status": "success"}
		)
		# Return updated terminal data
		return get_terminal_details(terminal_id)
	except Exception as e:
		log_api_call(
			"POST",
			f"payment-terminals/{terminal_id}/link",
			{"serial_number": serial_number},
			error=e
		)
		raise


@frappe.whitelist()
def unlink_terminal_device(terminal_id):
	"""
	Unlink a terminal from its physical device.

	Args:
		terminal_id: Wallee Terminal ID

	Returns:
		Updated terminal data after unlinking
	"""
	from wallee.service.payment_terminals_service import PaymentTerminalsService

	config = get_wallee_client()
	space_id = get_space_id()
	service = PaymentTerminalsService(config)

	try:
		# Unlink returns 204 No Content, so we fetch the terminal after unlinking
		service.post_payment_terminals_id_unlink(
			id=int(terminal_id),
			space=space_id
		)
		log_api_call(
			"POST",
			f"payment-terminals/{terminal_id}/unlink",
			response_data={"status": "success"}
		)
		# Return updated terminal data
		return get_terminal_details(terminal_id)
	except Exception as e:
		log_api_call("POST", f"payment-terminals/{terminal_id}/unlink", error=e)
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
		# SDK 6.3.0: Use post_payment_terminals_id_perform_transaction
		response = service.post_payment_terminals_id_perform_transaction(
			int(terminal_id),
			int(transaction_id),
			space_id
		)
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
		# SDK 6.3.0: Use post_payment_terminals_id_trigger_final_balance
		response = service.post_payment_terminals_id_trigger_final_balance(
			int(terminal_id),
			space_id
		)
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
		# SDK 6.3.0: Use get_payment_terminals_id_till_connection_credentials
		response = service.get_payment_terminals_id_till_connection_credentials(
			int(terminal_id),
			space_id
		)
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

		# Extract terminal type name from type object
		if terminal.type:
			if isinstance(terminal.type.name, dict):
				doc.terminal_type = terminal.type.name.get("en-US") or list(terminal.type.name.values())[0]
			else:
				doc.terminal_type = terminal.type.name or f"Type {terminal.type.id}"
			doc.terminal_type_id = str(terminal.type.id)
		else:
			doc.terminal_type = None
			doc.terminal_type_id = None

		doc.default_currency = terminal.default_currency

		# Extract version IDs from version objects and link to configuration/location records
		if terminal.configuration_version:
			config_version_id = str(terminal.configuration_version.id) if hasattr(terminal.configuration_version, 'id') else str(terminal.configuration_version)
			doc.configuration_version = config_version_id
			# Find and link the configuration record
			config_name = frappe.db.get_value(
				"Wallee Terminal Configuration",
				{"wallee_configuration_version_id": config_version_id},
				"name"
			)
			if config_name:
				doc.terminal_configuration = config_name

		if terminal.location_version:
			location_version_id = str(terminal.location_version.id) if hasattr(terminal.location_version, 'id') else str(terminal.location_version)
			doc.location_version = location_version_id
			# Find and link the location record
			location_name = frappe.db.get_value(
				"Wallee Location",
				{"wallee_location_version_id": location_version_id},
				"name"
			)
			if location_name:
				doc.wallee_location = location_name

		# Map Wallee state to DocType status (Wallee uses uppercase)
		wallee_state = terminal.state.value if terminal.state else "INACTIVE"
		state_mapping = {
			"ACTIVE": "Active",
			"INACTIVE": "Inactive",
			"PROCESSING": "Processing",
			"DELETED": "Deleted"
		}
		doc.status = state_mapping.get(wallee_state.upper(), "Inactive")
		doc.last_sync = frappe.utils.now_datetime()

		# Update registration status based on terminal state
		if terminal.device_serial_number:
			doc.registration_status = "Linked"
		elif terminal.id:
			doc.registration_status = "Created"
		else:
			doc.registration_status = "Not Created"

		doc.save(ignore_permissions=True)
		synced += 1

	frappe.db.commit()
	frappe.msgprint(_("{0} terminals synced from Wallee").format(synced))
	return synced


@frappe.whitelist()
def delete_terminal(terminal_id):
	"""
	Delete a terminal from Wallee.

	Args:
		terminal_id: Wallee Terminal ID

	Returns:
		Success status
	"""
	from wallee.service.payment_terminals_service import PaymentTerminalsService

	config = get_wallee_client()
	space_id = get_space_id()
	service = PaymentTerminalsService(config)

	try:
		service.delete_payment_terminals_id(
			id=int(terminal_id),
			space=space_id
		)
		log_api_call(
			"DELETE",
			f"payment-terminals/{terminal_id}",
			response_data={"status": "deleted"}
		)
		return {"success": True, "terminal_id": terminal_id}
	except Exception as e:
		log_api_call("DELETE", f"payment-terminals/{terminal_id}", error=e)
		raise


@frappe.whitelist()
def delete_all_terminals():
	"""
	Delete ALL terminals from Wallee and ERPNext.
	Use with caution!

	Returns:
		Dict with deleted counts
	"""
	terminals = get_terminals()
	deleted_wallee = 0
	errors = []

	for terminal in terminals:
		try:
			delete_terminal(terminal.id)
			deleted_wallee += 1
		except Exception as e:
			errors.append({"id": terminal.id, "name": terminal.name, "error": str(e)})

	# Delete all ERPNext records
	deleted_erpnext = frappe.db.count("Wallee Payment Terminal")
	frappe.db.delete("Wallee Payment Terminal")
	frappe.db.commit()

	return {
		"deleted_wallee": deleted_wallee,
		"deleted_erpnext": deleted_erpnext,
		"errors": errors
	}


@frappe.whitelist()
def reset_wallee_data(include_transactions=True, include_payment_gateway=True):
	"""
	Complete reset of ALL Wallee-related data.
	Use with EXTREME caution - this deletes everything!

	Args:
		include_transactions: Also delete Wallee Transaction records (default: True)
		include_payment_gateway: Also delete Payment Gateway, Account and Requests (default: True)

	Returns:
		Dict with detailed deletion report
	"""
	report = {
		"wallee_api": {},
		"erpnext": {},
		"errors": []
	}

	# 0. Delete Application Users from Wallee API (before credentials are cleared)
	try:
		settings = frappe.get_single("Wallee Settings")
		if settings.user_id and settings.authentication_key:
			from wallee import Configuration, ApplicationUsersService

			config = Configuration(
				user_id=int(settings.user_id),
				authentication_key=settings.get_password("authentication_key")
			)
			user_service = ApplicationUsersService(config)

			deleted_users = 0
			# Delete webshop user if exists
			if settings.webshop_user_id:
				try:
					user_service.delete_application_users_id(int(settings.webshop_user_id))
					deleted_users += 1
				except Exception as e:
					report["errors"].append({"type": "wallee_webshop_user", "error": str(e)})

			# Delete POS user if exists
			if settings.pos_user_id:
				try:
					user_service.delete_application_users_id(int(settings.pos_user_id))
					deleted_users += 1
				except Exception as e:
					report["errors"].append({"type": "wallee_pos_user", "error": str(e)})

			report["wallee_api"]["application_users"] = deleted_users
	except Exception as e:
		report["errors"].append({"type": "wallee_users", "error": str(e)})
		report["wallee_api"]["application_users"] = 0

	# 1. Delete all terminals from Wallee API
	try:
		terminals = get_terminals()
		deleted_wallee_terminals = 0
		for terminal in terminals:
			try:
				delete_terminal(terminal.id)
				deleted_wallee_terminals += 1
			except Exception as e:
				report["errors"].append({
					"type": "wallee_terminal",
					"id": terminal.id,
					"error": str(e)
				})
		report["wallee_api"]["terminals"] = deleted_wallee_terminals
	except Exception as e:
		report["errors"].append({"type": "wallee_api", "error": str(e)})
		report["wallee_api"]["terminals"] = 0

	# 2. Delete ERPNext Wallee Payment Terminal records
	count = frappe.db.count("Wallee Payment Terminal")
	if count > 0:
		frappe.db.delete("Wallee Payment Terminal")
	report["erpnext"]["Wallee Payment Terminal"] = count

	# 3. Delete ERPNext Wallee Terminal Configuration records
	count = frappe.db.count("Wallee Terminal Configuration")
	if count > 0:
		frappe.db.delete("Wallee Terminal Configuration")
	report["erpnext"]["Wallee Terminal Configuration"] = count

	# 4. Delete ERPNext Wallee Location records
	count = frappe.db.count("Wallee Location")
	if count > 0:
		frappe.db.delete("Wallee Location")
	report["erpnext"]["Wallee Location"] = count

	# 5. Delete Wallee Transactions (optional)
	if include_transactions:
		# Delete transaction items first (child table)
		count_items = frappe.db.count("Wallee Transaction Item")
		if count_items > 0:
			frappe.db.delete("Wallee Transaction Item")
		report["erpnext"]["Wallee Transaction Item"] = count_items

		count = frappe.db.count("Wallee Transaction")
		if count > 0:
			frappe.db.delete("Wallee Transaction")
		report["erpnext"]["Wallee Transaction"] = count

		# Delete webhook logs
		count = frappe.db.count("Wallee Webhook Log")
		if count > 0:
			frappe.db.delete("Wallee Webhook Log")
		report["erpnext"]["Wallee Webhook Log"] = count

	# 6. Delete Payment Gateway related (optional)
	if include_payment_gateway:
		# Delete Payment Requests linked to Wallee
		wallee_accounts = frappe.get_all(
			"Payment Gateway Account",
			filters={"payment_gateway": ["like", "%Wallee%"]},
			pluck="name"
		)

		if wallee_accounts:
			for account in wallee_accounts:
				count = frappe.db.count("Payment Request", {"payment_gateway_account": account})
				if count > 0:
					frappe.db.delete("Payment Request", {"payment_gateway_account": account})
				report["erpnext"][f"Payment Request ({account})"] = count

		# Delete Payment Gateway Accounts
		count = frappe.db.count("Payment Gateway Account", {"payment_gateway": ["like", "%Wallee%"]})
		if count > 0:
			frappe.db.delete("Payment Gateway Account", {"payment_gateway": ["like", "%Wallee%"]})
		report["erpnext"]["Payment Gateway Account (Wallee)"] = count

		# Delete Payment Gateway
		count = frappe.db.count("Payment Gateway", {"name": ["like", "%Wallee%"]})
		if count > 0:
			frappe.db.delete("Payment Gateway", {"name": ["like", "%Wallee%"]})
		report["erpnext"]["Payment Gateway (Wallee)"] = count

	# 7. Reset Wallee Settings - ALL fields (bypass validation with db_set)
	try:
		fields_to_reset = [
			"user_id", "space_id", "authentication_key", "account_id",
			"default_terminal", "enable_webshop", "enable_pos_terminal",
			"webshop_user_id", "webshop_authentication_key",
			"pos_user_id", "pos_authentication_key",
			"success_url", "failed_url"
		]
		for field in fields_to_reset:
			frappe.db.set_single_value("Wallee Settings", field, None)
		report["erpnext"]["Wallee Settings"] = "full reset (credentials + settings)"
	except Exception as e:
		report["errors"].append({"type": "wallee_settings", "error": str(e)})

	frappe.db.commit()

	return report
