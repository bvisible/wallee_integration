# -*- coding: utf-8 -*-
# Copyright (c) 2024, Neoservice and contributors
# For license information, please see license.txt

import frappe
from frappe import _
import json


@frappe.whitelist()
def get_configurations():
	"""Get all Wallee Terminal Configurations"""
	return frappe.get_all(
		"Wallee Terminal Configuration",
		fields=["name", "configuration_name", "wallee_configuration_id",
				"wallee_configuration_version_id", "is_default", "description"]
	)


@frappe.whitelist()
def get_locations():
	"""Get all Wallee Locations with version IDs"""
	return frappe.get_all(
		"Wallee Location",
		filters={"is_active": 1},
		fields=["name", "location_name", "wallee_location_id",
				"wallee_location_version_id", "is_default", "city", "country"]
	)


@frappe.whitelist()
def sync_configurations_from_wallee():
	"""
	Fetch configuration and location version IDs from existing terminals in Wallee.
	Creates Wallee Terminal Configuration records from discovered configurations.
	"""
	try:
		from wallee_integration.wallee_integration.api.terminal import get_existing_configurations

		data = get_existing_configurations()
		configs_created = 0

		for config in data.get("configurations", []):
			config_id = config.get("id")
			config_name = config.get("name", f"Configuration {config_id}")

			# Check if already exists
			existing = frappe.db.exists(
				"Wallee Terminal Configuration",
				{"wallee_configuration_version_id": str(config_id)}
			)

			if not existing:
				doc = frappe.new_doc("Wallee Terminal Configuration")
				doc.configuration_name = config_name
				doc.wallee_configuration_version_id = str(config_id)
				doc.last_sync = frappe.utils.now_datetime()
				doc.insert(ignore_permissions=True)
				configs_created += 1

		frappe.db.commit()
		return {
			"success": True,
			"message": _("{0} configurations synced").format(configs_created)
		}

	except Exception as e:
		frappe.log_error(
			title="Wallee Config Sync Error",
			message=f"Error syncing configurations from Wallee: {e}"
		)
		return {
			"success": False,
			"error": str(e)
		}


@frappe.whitelist()
def sync_locations_from_wallee():
	"""
	Fetch location version IDs from existing terminals in Wallee.
	Updates Wallee Location records with version IDs.
	"""
	try:
		from wallee_integration.wallee_integration.api.terminal import get_existing_configurations

		data = get_existing_configurations()
		locations_updated = 0

		for loc in data.get("locations", []):
			loc_id = loc.get("id")
			loc_name = loc.get("name", f"Location {loc_id}")

			# Check if we have a location that matches by name or create new
			existing = frappe.db.get_value(
				"Wallee Location",
				{"location_name": loc_name},
				"name"
			)

			if existing:
				frappe.db.set_value(
					"Wallee Location",
					existing,
					{
						"wallee_location_version_id": str(loc_id),
						"last_sync": frappe.utils.now_datetime()
					}
				)
				locations_updated += 1
			else:
				# Create new location entry
				doc = frappe.new_doc("Wallee Location")
				doc.location_name = loc_name
				doc.wallee_location_version_id = str(loc_id)
				doc.city = "Unknown"
				doc.country = "Switzerland"
				doc.last_sync = frappe.utils.now_datetime()
				doc.insert(ignore_permissions=True)
				locations_updated += 1

		frappe.db.commit()
		return {
			"success": True,
			"message": _("{0} locations updated").format(locations_updated)
		}

	except Exception as e:
		frappe.log_error(
			title="Wallee Location Sync Error",
			message=f"Error syncing locations from Wallee: {e}"
		)
		return {
			"success": False,
			"error": str(e)
		}


@frappe.whitelist()
def create_configuration(configuration_name, wallee_configuration_id=None,
						 wallee_configuration_version_id=None):
	"""Create a new Wallee Terminal Configuration"""
	doc = frappe.new_doc("Wallee Terminal Configuration")
	doc.configuration_name = configuration_name
	doc.wallee_configuration_id = wallee_configuration_id
	doc.wallee_configuration_version_id = wallee_configuration_version_id
	doc.insert(ignore_permissions=True)
	frappe.db.commit()

	return {
		"name": doc.name,
		"configuration_name": doc.configuration_name
	}


@frappe.whitelist()
def create_location(location_name, wallee_location_id=None,
					wallee_location_version_id=None, city="Unknown"):
	"""Create a new Wallee Location"""
	doc = frappe.new_doc("Wallee Location")
	doc.location_name = location_name
	doc.wallee_location_id = wallee_location_id
	doc.wallee_location_version_id = wallee_location_version_id
	doc.city = city
	doc.country = "Switzerland"
	doc.insert(ignore_permissions=True)
	frappe.db.commit()

	return {
		"name": doc.name,
		"location_name": doc.location_name
	}


@frappe.whitelist()
def create_terminals(terminals, configuration, location):
	"""
	Create multiple terminals in Wallee.

	Args:
		terminals: JSON string or list of [{name, serial_number, pos_profile, warehouse}, ...]
		configuration: Wallee Terminal Configuration name
		location: Wallee Location name

	Returns:
		List of [{name, terminal_id, success, error}, ...]
	"""
	from wallee_integration.wallee_integration.api.terminal import (
		create_terminal,
		link_terminal_device,
		PHYSICAL_TERMINAL_TYPE_ID
	)

	# Parse terminals if string
	if isinstance(terminals, str):
		terminals = json.loads(terminals)

	# Get configuration and location version IDs
	config_doc = frappe.get_doc("Wallee Terminal Configuration", configuration)
	location_doc = frappe.get_doc("Wallee Location", location)

	config_version_id = config_doc.wallee_configuration_version_id
	location_version_id = location_doc.wallee_location_version_id

	if not config_version_id:
		return [{
			"name": t.get("name"),
			"success": False,
			"error": _("Configuration Version ID is missing")
		} for t in terminals]

	results = []

	for terminal_data in terminals:
		terminal_name = terminal_data.get("name")
		serial_number = terminal_data.get("serial_number")
		pos_profile = terminal_data.get("pos_profile")
		warehouse = terminal_data.get("warehouse")

		try:
			# Create terminal in Wallee
			result = create_terminal(
				name=terminal_name,
				terminal_type_id=PHYSICAL_TERMINAL_TYPE_ID,
				configuration_version=config_version_id,
				location_version=location_version_id
			)

			terminal_id = result.get("id")

			# Link device if serial number provided
			# Note: Device linking only works when terminal is ACTIVE
			# If terminal is not active yet, we skip linking - user can link later
			device_linked = False
			if serial_number and terminal_id:
				terminal_state = result.get("state", "")
				if terminal_state == "ACTIVE":
					try:
						link_terminal_device(terminal_id, serial_number)
						device_linked = True
					except Exception as link_error:
						frappe.log_error(
							title="Wallee Device Link Error",
							message=f"Failed to link device to terminal {terminal_id}: {link_error}"
						)
				else:
					# Terminal not active yet - device will need to be linked manually later
					frappe.log_error(
						title="Wallee Device Link Skipped",
						message=f"Terminal {terminal_id} is in state '{terminal_state}', not ACTIVE. Device linking skipped. Serial: {serial_number}"
					)

			# Create local DocType record
			doc = frappe.new_doc("Wallee Payment Terminal")
			doc.terminal_name = terminal_name
			doc.terminal_id = terminal_id
			doc.identifier = result.get("identifier")
			doc.terminal_type_id = str(PHYSICAL_TERMINAL_TYPE_ID)
			doc.terminal_configuration = configuration
			doc.wallee_location = location
			doc.device_serial_number = serial_number
			doc.configuration_version = config_version_id
			doc.location_version = location_version_id
			doc.status = "Active" if result.get("state") == "ACTIVE" else "Inactive"
			# Set registration status based on whether device was actually linked
			if device_linked:
				doc.registration_status = "Linked"
			elif serial_number:
				# Serial provided but not linked (terminal not active yet)
				doc.registration_status = "Created"
			else:
				doc.registration_status = "Created"
			doc.default_currency = result.get("default_currency", "CHF")

			if pos_profile:
				doc.pos_profile = pos_profile
			if warehouse:
				doc.warehouse = warehouse

			doc.insert(ignore_permissions=True)

			results.append({
				"name": terminal_name,
				"terminal_id": terminal_id,
				"identifier": result.get("identifier"),
				"serial_number": serial_number,
				"success": True
			})

		except Exception as e:
			frappe.log_error(
				title="Wallee Terminal Creation Error",
				message=f"Error creating terminal '{terminal_name}': {e}"
			)
			results.append({
				"name": terminal_name,
				"success": False,
				"error": str(e)
			})

	frappe.db.commit()
	return results


@frappe.whitelist()
def get_existing_wallee_terminals():
	"""
	Get terminals from Wallee that are not yet imported to ERPNext.

	Returns:
		List of terminals available for import
	"""
	from wallee_integration.wallee_integration.api.terminal import get_terminals

	try:
		wallee_terminals = get_terminals()

		# Get terminal IDs already in ERPNext
		existing_ids = set(
			frappe.get_all(
				"Wallee Payment Terminal",
				pluck="terminal_id"
			)
		)

		# Filter out already imported terminals
		available_terminals = []
		for terminal in wallee_terminals:
			if str(terminal.id) not in existing_ids:
				# Extract configuration and location info
				config_name = None
				location_name = None

				if terminal.configuration_version:
					if hasattr(terminal.configuration_version, 'configuration') and terminal.configuration_version.configuration:
						config_name = terminal.configuration_version.configuration.name
					elif hasattr(terminal.configuration_version, 'id'):
						config_name = f"Configuration {terminal.configuration_version.id}"

				if terminal.location_version:
					if hasattr(terminal.location_version, 'location') and terminal.location_version.location:
						location_name = terminal.location_version.location.name
					elif hasattr(terminal.location_version, 'id'):
						location_name = f"Location {terminal.location_version.id}"

				# Extract terminal type name
				terminal_type = None
				terminal_type_id = None
				if terminal.type:
					if isinstance(terminal.type.name, dict):
						terminal_type = terminal.type.name.get("en-US") or list(terminal.type.name.values())[0]
					else:
						terminal_type = terminal.type.name or f"Type {terminal.type.id}"
					terminal_type_id = str(terminal.type.id)

				available_terminals.append({
					"id": terminal.id,
					"name": terminal.name,
					"identifier": terminal.identifier,
					"state": terminal.state.value if terminal.state else "INACTIVE",
					"device_serial_number": terminal.device_serial_number,
					"default_currency": terminal.default_currency,
					"configuration_name": config_name,
					"location_name": location_name,
					"terminal_type": terminal_type,
					"terminal_type_id": terminal_type_id,
					"configuration_version_id": str(terminal.configuration_version.id) if terminal.configuration_version and hasattr(terminal.configuration_version, 'id') else None,
					"location_version_id": str(terminal.location_version.id) if terminal.location_version and hasattr(terminal.location_version, 'id') else None
				})

		return {
			"success": True,
			"terminals": available_terminals
		}

	except Exception as e:
		frappe.log_error(
			title="Wallee Terminal Fetch Error",
			message=f"Error fetching existing terminals from Wallee: {e}"
		)
		return {
			"success": False,
			"error": str(e),
			"terminals": []
		}


@frappe.whitelist()
def import_terminals(terminals):
	"""
	Import existing terminals from Wallee into ERPNext.

	Args:
		terminals: JSON string or list of [{id, pos_profile, warehouse}, ...]

	Returns:
		List of [{name, terminal_id, success, error}, ...]
	"""
	from wallee_integration.wallee_integration.api.terminal import get_terminal_details

	# Parse terminals if string
	if isinstance(terminals, str):
		terminals = json.loads(terminals)

	results = []

	for terminal_data in terminals:
		terminal_id = terminal_data.get("id")
		pos_profile = terminal_data.get("pos_profile")
		warehouse = terminal_data.get("warehouse")

		try:
			# Check if already exists
			if frappe.db.exists("Wallee Payment Terminal", {"terminal_id": str(terminal_id)}):
				results.append({
					"name": terminal_data.get("name", f"Terminal {terminal_id}"),
					"terminal_id": terminal_id,
					"success": False,
					"error": _("Terminal already exists in ERPNext")
				})
				continue

			# Get full terminal details from Wallee
			details = get_terminal_details(terminal_id)

			# Create local DocType record
			doc = frappe.new_doc("Wallee Payment Terminal")
			doc.terminal_name = details.get("name") or details.get("identifier")
			doc.terminal_id = terminal_id
			doc.identifier = details.get("identifier")
			doc.device_serial_number = terminal_data.get("device_serial_number") or details.get("device_serial_number")
			doc.default_currency = details.get("default_currency", "CHF")

			# Extract terminal type info
			if terminal_data.get("terminal_type"):
				doc.terminal_type = terminal_data.get("terminal_type")
			if terminal_data.get("terminal_type_id"):
				doc.terminal_type_id = terminal_data.get("terminal_type_id")

			# Extract version IDs and link to configuration/location records
			config_version_id = terminal_data.get("configuration_version_id")
			location_version_id = terminal_data.get("location_version_id")

			if config_version_id:
				doc.configuration_version = config_version_id
				# Find and link the configuration record
				config_name = frappe.db.get_value(
					"Wallee Terminal Configuration",
					{"wallee_configuration_version_id": str(config_version_id)},
					"name"
				)
				if config_name:
					doc.terminal_configuration = config_name

			if location_version_id:
				doc.location_version = location_version_id
				# Find and link the location record
				location_name = frappe.db.get_value(
					"Wallee Location",
					{"wallee_location_version_id": str(location_version_id)},
					"name"
				)
				if location_name:
					doc.wallee_location = location_name

			# Map state to status
			wallee_state = details.get("state", "INACTIVE")
			state_mapping = {
				"ACTIVE": "Active",
				"INACTIVE": "Inactive",
				"PROCESSING": "Processing",
				"DELETED": "Deleted"
			}
			doc.status = state_mapping.get(wallee_state.upper(), "Inactive")

			# Set registration status
			if doc.device_serial_number:
				doc.registration_status = "Linked"
			else:
				doc.registration_status = "Created"

			# Optional fields
			if pos_profile:
				doc.pos_profile = pos_profile
			if warehouse:
				doc.warehouse = warehouse

			doc.last_sync = frappe.utils.now_datetime()
			doc.insert(ignore_permissions=True)

			results.append({
				"name": doc.terminal_name,
				"terminal_id": terminal_id,
				"identifier": details.get("identifier"),
				"success": True
			})

		except Exception as e:
			frappe.log_error(
				title="Wallee Terminal Import Error",
				message=f"Error importing terminal '{terminal_id}': {e}"
			)
			results.append({
				"name": terminal_data.get("name", f"Terminal {terminal_id}"),
				"terminal_id": terminal_id,
				"success": False,
				"error": str(e)
			})

	frappe.db.commit()
	return results


@frappe.whitelist()
def get_wizard_defaults():
	"""Get default configuration and location if set"""
	settings = frappe.get_single("Wallee Settings")

	default_config = None
	default_location = None

	if settings.get("default_terminal_configuration"):
		default_config = settings.default_terminal_configuration

	if settings.get("default_terminal_location"):
		default_location = settings.default_terminal_location

	# Fallback to is_default flags
	if not default_config:
		default_config = frappe.db.get_value(
			"Wallee Terminal Configuration",
			{"is_default": 1},
			"name"
		)

	if not default_location:
		default_location = frappe.db.get_value(
			"Wallee Location",
			{"is_default": 1, "is_active": 1},
			"name"
		)

	return {
		"configuration": default_config,
		"location": default_location
	}
