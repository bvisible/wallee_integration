# -*- coding: utf-8 -*-
# Copyright (c) 2024, Neoservice and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class WalleeLocation(Document):
	"""Wallee Location DocType for managing terminal locations."""

	def validate(self):
		"""Validate the location document."""
		self.validate_default()

	def validate_default(self):
		"""Ensure only one location is marked as default"""
		if self.is_default:
			frappe.db.set_value(
				"Wallee Location",
				{"is_default": 1, "name": ("!=", self.name)},
				"is_default",
				0
			)

	def on_trash(self):
		"""Handle deletion - check for linked terminals."""
		linked_terminals = frappe.get_all(
			"Wallee Payment Terminal",
			filters={"wallee_location": self.name},
			pluck="name"
		)
		if linked_terminals:
			frappe.throw(
				_("Cannot delete location. It is linked to terminals: {0}").format(
					", ".join(linked_terminals)
				)
			)


def get_active_locations():
	"""Get all active locations."""
	return frappe.get_all(
		"Wallee Location",
		filters={"is_active": 1},
		fields=["name", "location_name", "city", "country", "wallee_location_id",
				"wallee_location_version_id", "is_default"]
	)


def get_default_location():
	"""Get the default terminal location"""
	location = frappe.db.get_value(
		"Wallee Location",
		{"is_default": 1, "is_active": 1},
		["name", "location_name", "wallee_location_id", "wallee_location_version_id"],
		as_dict=True
	)
	return location
