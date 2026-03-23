# -*- coding: utf-8 -*-
# Copyright (c) 2024, Neoservice and contributors
# For license information, please see license.txt

import re
import frappe
from frappe import _


def get_taxes_for_line_items(reference_doctype=None, reference_name=None):
	"""
	Extract tax rates from an ERPNext document for use in Wallee LineItemCreate.

	Handles both standard ERPNext taxes (rate field populated) and Swiss-style
	taxes where rate=0 and included_in_print_rate=1 (rate inferred from
	description or calculated from amounts).

	Args:
		reference_doctype: Document type (POS Invoice, Sales Invoice, Sales Order, Quotation)
		reference_name: Document name

	Returns:
		list of dicts: [{"title": "TVA 8.1%", "rate": 8.1}, ...]
	"""
	if not reference_doctype or not reference_name:
		return []

	supported_doctypes = ["POS Invoice", "Sales Invoice", "Sales Order", "Quotation"]
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

	Handles Swiss ERPNext pattern where:
	- charge_type = "On Net Total" with included_in_print_rate = 1
	- rate field is 0 (rate is in the Item Tax Template, not the row)
	- The actual rate must be inferred from the description (e.g. "TVA 8.1%")
	  or calculated from tax_amount / base_net_total

	Only extracts percentage-based taxes (On Net Total, On Previous Row Total),
	not "Actual" charges (shipping, fixed fees).

	Args:
		doc: Frappe document with taxes child table

	Returns:
		list of dicts with title and rate
	"""
	taxes = []
	seen_rates = set()
	net_total = _get_field(doc, "net_total") or _get_field(doc, "base_net_total") or 0

	for tax_row in (doc.get("taxes") or []):
		charge_type = _get_field(tax_row, "charge_type")

		# Skip "Actual" charges (shipping, fixed fees) - not percentage-based taxes
		if charge_type == "Actual":
			continue

		rate = _get_field(tax_row, "rate") or 0
		tax_amount = _get_field(tax_row, "tax_amount") or 0
		description = _get_field(tax_row, "description") or ""

		# Skip rows with no tax impact
		if not rate and not tax_amount:
			continue

		# If rate is 0 (Swiss pattern), try to infer it
		if not rate and tax_amount and net_total:
			# Method 1: Parse rate from description (e.g. "TVA 8.1% - Due")
			rate = _parse_rate_from_description(description)

			# Method 2: Calculate from amounts
			if not rate:
				rate = round((tax_amount / net_total) * 100, 2)

		if rate and rate not in seen_rates:
			seen_rates.add(rate)
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
		charge_type = _get_field(tax_row, "charge_type")

		# Skip "Actual" charges
		if charge_type == "Actual":
			continue

		rate = _get_field(tax_row, "rate") or 0
		description = _get_field(tax_row, "description") or ""

		# If rate is 0, try to parse from description
		if not rate:
			rate = _parse_rate_from_description(description)

		if rate and rate not in seen_rates:
			seen_rates.add(rate)
			title = _sanitize_tax_title(description, rate)
			taxes.append({"title": title, "rate": float(rate)})

	return taxes


def _parse_rate_from_description(description):
	"""
	Parse a tax rate from a description string.

	Handles patterns like:
	- "TVA 8.1% - Due"
	- "TVA 8.1%"
	- "VAT 7.7%"
	- "MwSt 8.1%"
	- "PostPack - TVA 8.1% - Due (8.1%)"

	Args:
		description: Tax description string

	Returns:
		float: Parsed rate, or 0 if not found
	"""
	if not description:
		return 0

	# Match percentage patterns like "8.1%", "7.7%", "2.6%"
	matches = re.findall(r'(\d+(?:\.\d+)?)\s*%', description)
	if matches:
		# Take the last match (handles "PostPack - TVA 8.1% - Due (8.1%)")
		try:
			return float(matches[-1])
		except (ValueError, IndexError):
			pass

	return 0


def _get_field(obj, field):
	"""
	Safely get a field value from an object or dict.
	"""
	if isinstance(obj, dict):
		return obj.get(field)
	return getattr(obj, field, None)


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
