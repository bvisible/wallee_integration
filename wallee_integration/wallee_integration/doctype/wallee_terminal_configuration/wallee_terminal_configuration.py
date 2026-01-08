# -*- coding: utf-8 -*-
# Copyright (c) 2024, Neoservice and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class WalleeTerminalConfiguration(Document):
	def validate(self):
		self.validate_default()

	def validate_default(self):
		"""Ensure only one configuration is marked as default"""
		if self.is_default:
			frappe.db.set_value(
				"Wallee Terminal Configuration",
				{"is_default": 1, "name": ("!=", self.name)},
				"is_default",
				0
			)


def get_default_configuration():
	"""Get the default terminal configuration"""
	config = frappe.db.get_value(
		"Wallee Terminal Configuration",
		{"is_default": 1},
		["name", "wallee_configuration_id", "wallee_configuration_version_id"],
		as_dict=True
	)
	return config


def get_all_configurations():
	"""Get all terminal configurations"""
	return frappe.get_all(
		"Wallee Terminal Configuration",
		fields=["name", "configuration_name", "wallee_configuration_id",
				"wallee_configuration_version_id", "is_default", "description"]
	)
