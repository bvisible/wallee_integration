# -*- coding: utf-8 -*-
# Copyright (c) 2024, Neoservice and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def get_taxes_for_line_items(reference_doctype=None, reference_name=None):
	"""
	Extract tax rates from an ERPNext document for use in Wallee LineItemCreate.

	Args:
		reference_doctype: Document type (POS Invoice, Sales Invoice, Sales Order)
		reference_name: Document name

	Returns:
		list of dicts: [{"title": "TVA 8.1%", "rate": 8.1}, ...]
	"""
	if not reference_doctype or not reference_name:
		return []

	supported_doctypes = ["POS Invoice", "Sales Invoice", "Sales Order"]
	if reference_doctype not in supported_doctypes:
		return []

	try:
		if not frappe.db.exists(reference_doctype, reference_name):
			return []

		doc = frappe.get_doc(reference_doctype, reference_name)
		return _extract_taxes_from_doc(doc)
	except Exception:
		return []


def get_taxes_from_pos_profile(pos_profile_name):
	"""
	Extract default tax rates from a POS Profile's tax template.

	Args:
		pos_profile_name: POS Profile name

	Returns:
		list of dicts: [{"title": "TVA 8.1%", "rate": 8.1}, ...]
	"""
	if not pos_profile_name:
		return []

	try:
		profile = frappe.get_doc("POS Profile", pos_profile_name)
		if profile.taxes_and_charges:
			template = frappe.get_doc(
				"Sales Taxes and Charges Template",
				profile.taxes_and_charges
			)
			return _extract_taxes_from_template(template)
	except Exception:
		pass

	return []


def _extract_taxes_from_doc(doc):
	"""
	Extract unique tax rates from a document with a taxes table.

	Args:
		doc: Frappe document with taxes child table

	Returns:
		list of dicts with title and rate
	"""
	taxes = []
	seen_rates = set()

	for tax_row in (doc.get("taxes") or []):
		rate = tax_row.get("rate") if isinstance(tax_row, dict) else getattr(tax_row, "rate", None)
		if rate and rate not in seen_rates:
			seen_rates.add(rate)
			description = (
				tax_row.get("description") if isinstance(tax_row, dict)
				else getattr(tax_row, "description", None)
			)
			title = _sanitize_tax_title(description, rate)
			taxes.append({"title": title, "rate": float(rate)})

	return taxes


def _extract_taxes_from_template(template):
	"""
	Extract unique tax rates from a Sales Taxes and Charges Template.

	Args:
		template: Sales Taxes and Charges Template document

	Returns:
		list of dicts with title and rate
	"""
	taxes = []
	seen_rates = set()

	for tax_row in (template.get("taxes") or []):
		rate = tax_row.get("rate") if isinstance(tax_row, dict) else getattr(tax_row, "rate", None)
		if rate and rate not in seen_rates:
			seen_rates.add(rate)
			description = (
				tax_row.get("description") if isinstance(tax_row, dict)
				else getattr(tax_row, "description", None)
			)
			title = _sanitize_tax_title(description, rate)
			taxes.append({"title": title, "rate": float(rate)})

	return taxes


def _sanitize_tax_title(description, rate):
	"""
	Sanitize tax title for Wallee TaxCreate (min 2, max 40 chars).

	Args:
		description: Tax description string
		rate: Tax rate

	Returns:
		str: Sanitized title
	"""
	title = description or f"Tax {rate}%"
	if len(title) < 2:
		title = f"Tax {rate}%"
	elif len(title) > 40:
		title = title[:40]
	return title
