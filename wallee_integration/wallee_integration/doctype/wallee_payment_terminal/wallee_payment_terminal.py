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
