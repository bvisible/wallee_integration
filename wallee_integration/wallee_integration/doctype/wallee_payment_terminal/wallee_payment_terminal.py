# -*- coding: utf-8 -*-
# Copyright (c) 2024, Neoservice and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime


class WalleePaymentTerminal(Document):
	def validate(self):
		if self.is_default:
			self.unset_other_defaults()

	def unset_other_defaults(self):
		"""Ensure only one terminal is marked as default"""
		frappe.db.sql("""
			UPDATE `tabWallee Payment Terminal`
			SET is_default = 0
			WHERE name != %s AND is_default = 1
		""", self.name)

	@frappe.whitelist()
	def sync_from_wallee(self):
		"""Sync terminal data from Wallee API"""
		from wallee_integration.wallee_integration.api.client import get_wallee_client
		from wallee_integration.wallee_integration.api.terminal import get_terminal_details

		if not self.terminal_id:
			frappe.throw(_("Terminal ID is required to sync from Wallee"))

		try:
			terminal_data = get_terminal_details(self.terminal_id)
			if terminal_data:
				self.identifier = terminal_data.get("identifier")
				self.device_serial_number = terminal_data.get("device_serial_number")
				self.terminal_type = terminal_data.get("type")
				self.default_currency = terminal_data.get("default_currency")
				self.configuration_version = terminal_data.get("configuration_version")
				self.location_version = terminal_data.get("location_version")
				self.status = terminal_data.get("state", "Inactive")
				self.last_sync = now_datetime()
				self.save()
				frappe.msgprint(_("Terminal synced successfully"), indicator="green")
		except Exception as e:
			frappe.throw(_("Failed to sync terminal: {0}").format(str(e)))

	@frappe.whitelist()
	def trigger_balance(self):
		"""Trigger final balance/settlement on terminal"""
		from wallee_integration.wallee_integration.api.terminal import trigger_terminal_balance

		if not self.terminal_id:
			frappe.throw(_("Terminal ID is required"))

		try:
			result = trigger_terminal_balance(self.terminal_id)
			frappe.msgprint(_("Balance triggered successfully"), indicator="green")
			return result
		except Exception as e:
			frappe.throw(_("Failed to trigger balance: {0}").format(str(e)))

	@frappe.whitelist()
	def create_in_wallee(self):
		"""Create this terminal in Wallee API"""
		from wallee_integration.wallee_integration.api.terminal import create_terminal

		if self.terminal_id:
			frappe.throw(_("Terminal already exists in Wallee (ID: {0})").format(self.terminal_id))

		if not self.terminal_type_id:
			frappe.throw(_("Terminal Type ID is required to create a terminal"))

		try:
			result = create_terminal(
				name=self.terminal_name,
				terminal_type_id=self.terminal_type_id,
				configuration_version=self.configuration_version if self.configuration_version else None,
				location_version=self.location_version if self.location_version else None
			)

			self.terminal_id = result.get("id")
			self.identifier = result.get("identifier")
			self.registration_status = "Created"
			self.last_sync = now_datetime()
			self.save()

			frappe.msgprint(
				_("Terminal created in Wallee with ID: {0}").format(self.terminal_id),
				indicator="green"
			)
			return result
		except Exception as e:
			frappe.throw(_("Failed to create terminal in Wallee: {0}").format(str(e)))

	@frappe.whitelist()
	def link_device(self, serial_number):
		"""Link this terminal to a physical device using its serial number"""
		from wallee_integration.wallee_integration.api.terminal import link_terminal_device

		if not self.terminal_id:
			frappe.throw(_("Terminal must be created in Wallee first"))

		if not serial_number:
			frappe.throw(_("Serial number is required"))

		try:
			result = link_terminal_device(self.terminal_id, serial_number)

			self.device_serial_number = serial_number
			# The identifier after linking contains the activation code
			self.activation_code = result.get("identifier")
			self.registration_status = "Linked"
			self.last_sync = now_datetime()
			self.save()

			frappe.msgprint(
				_("Terminal linked successfully. Activation code: {0}").format(self.activation_code),
				indicator="green",
				alert=True
			)
			return {
				"success": True,
				"activation_code": self.activation_code,
				"message": _("Enter this code on your terminal to activate it")
			}
		except Exception as e:
			frappe.throw(_("Failed to link terminal: {0}").format(str(e)))

	@frappe.whitelist()
	def unlink_device(self):
		"""Unlink this terminal from its physical device"""
		from wallee_integration.wallee_integration.api.terminal import unlink_terminal_device

		if not self.terminal_id:
			frappe.throw(_("Terminal ID is required"))

		try:
			result = unlink_terminal_device(self.terminal_id)

			self.device_serial_number = None
			self.activation_code = None
			self.registration_status = "Created"
			self.last_sync = now_datetime()
			self.save()

			frappe.msgprint(_("Terminal unlinked successfully"), indicator="green")
			return result
		except Exception as e:
			frappe.throw(_("Failed to unlink terminal: {0}").format(str(e)))


def get_default_terminal():
	"""Get the default payment terminal"""
	terminal = frappe.db.get_value(
		"Wallee Payment Terminal",
		{"is_default": 1, "status": "Active"},
		"name"
	)
	if terminal:
		return frappe.get_doc("Wallee Payment Terminal", terminal)
	return None
