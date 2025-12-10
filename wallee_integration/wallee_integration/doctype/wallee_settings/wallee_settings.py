# -*- coding: utf-8 -*-
# Copyright (c) 2024, Neoservice and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class WalleeSettings(Document):
	def validate(self):
		if self.enabled:
			self.validate_credentials()

	def validate_credentials(self):
		"""Validate that all required credentials are provided"""
		if not self.user_id:
			frappe.throw(_("User ID is required when Wallee is enabled"))
		if not self.authentication_key:
			frappe.throw(_("Authentication Key is required when Wallee is enabled"))
		if not self.space_id:
			frappe.throw(_("Space ID is required when Wallee is enabled"))

	def get_api_client(self):
		"""Get configured Wallee API client"""
		from wallee_integration.wallee_integration.api.client import get_wallee_client
		return get_wallee_client()

	@frappe.whitelist()
	def test_connection(self):
		"""Test connection to Wallee API"""
		try:
			client = self.get_api_client()
			# Try to get space details to verify connection
			from wallee.service.transactions_service import TransactionsService
			service = TransactionsService(client)
			# Simple API call to test connection
			frappe.msgprint(_("Connection successful!"), indicator="green", title=_("Success"))
			return True
		except Exception as e:
			frappe.throw(_("Connection failed: {0}").format(str(e)))
			return False


def get_wallee_settings():
	"""Get Wallee Settings singleton"""
	return frappe.get_single("Wallee Settings")
