# -*- coding: utf-8 -*-
# Copyright (c) 2024, Neoservice and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime


class WalleeTransaction(Document):
	def before_insert(self):
		if not self.merchant_reference:
			self.merchant_reference = self.name

	@frappe.whitelist()
	def sync_status(self):
		"""Sync transaction status from Wallee"""
		sync_transaction_status(self.name)

	@frappe.whitelist()
	def capture(self):
		"""Capture an authorized transaction"""
		from wallee_integration.wallee_integration.api.transaction import capture_transaction

		if self.status != "Authorized":
			frappe.throw(_("Only authorized transactions can be captured"))

		try:
			result = capture_transaction(self.transaction_id)
			self.reload()
			frappe.msgprint(_("Transaction captured successfully"), indicator="green")
			return result
		except Exception as e:
			frappe.throw(_("Failed to capture transaction: {0}").format(str(e)))

	@frappe.whitelist()
	def void(self):
		"""Void an authorized transaction"""
		from wallee_integration.wallee_integration.api.transaction import void_transaction

		if self.status not in ["Authorized", "Pending"]:
			frappe.throw(_("Only authorized or pending transactions can be voided"))

		try:
			result = void_transaction(self.transaction_id)
			self.reload()
			frappe.msgprint(_("Transaction voided successfully"), indicator="green")
			return result
		except Exception as e:
			frappe.throw(_("Failed to void transaction: {0}").format(str(e)))

	@frappe.whitelist()
	def refund(self, amount=None):
		"""Refund a completed transaction"""
		from wallee_integration.wallee_integration.api.refund import create_refund

		if self.status not in ["Completed", "Partially Refunded"]:
			frappe.throw(_("Only completed transactions can be refunded"))

		refund_amount = amount or self.amount

		if refund_amount > (self.amount - (self.refunded_amount or 0)):
			frappe.throw(_("Refund amount exceeds available amount"))

		try:
			result = create_refund(self.transaction_id, refund_amount)
			self.reload()
			frappe.msgprint(_("Refund processed successfully"), indicator="green")
			return result
		except Exception as e:
			frappe.throw(_("Failed to process refund: {0}").format(str(e)))


def sync_transaction_status(transaction_name):
	"""Sync a single transaction status from Wallee"""
	from wallee_integration.wallee_integration.api.transaction import get_transaction_status

	doc = frappe.get_doc("Wallee Transaction", transaction_name)

	if not doc.transaction_id:
		return

	try:
		status_data = get_transaction_status(doc.transaction_id)
		if status_data:
			update_transaction_from_wallee(doc, status_data)
	except Exception as e:
		frappe.log_error(
			message=str(e),
			title=f"Wallee Sync Error: {transaction_name}"
		)


def update_transaction_from_wallee(doc, data):
	"""Update transaction document from Wallee API response"""
	status_map = {
		"PENDING": "Pending",
		"PROCESSING": "Processing",
		"AUTHORIZED": "Authorized",
		"COMPLETED": "Completed",
		"FULFILL": "Completed",
		"FAILED": "Failed",
		"VOIDED": "Voided",
		"DECLINE": "Failed",
	}

	wallee_status = data.get("state", "").upper()
	new_status = status_map.get(wallee_status, doc.status)

	doc.status = new_status
	doc.authorized_amount = data.get("authorized_amount")
	doc.captured_amount = data.get("completed_amount")
	doc.refunded_amount = data.get("refunded_amount")

	if data.get("failure_reason"):
		doc.failure_reason = str(data.get("failure_reason"))

	if new_status == "Authorized" and not doc.authorized_on:
		doc.authorized_on = now_datetime()
	elif new_status == "Completed" and not doc.completed_on:
		doc.completed_on = now_datetime()
	elif new_status == "Voided" and not doc.voided_on:
		doc.voided_on = now_datetime()

	doc.wallee_data = frappe.as_json(data)
	doc.save(ignore_permissions=True)
	frappe.db.commit()


def create_transaction_record(
	transaction_id,
	amount,
	currency,
	transaction_type="Online",
	reference_doctype=None,
	reference_name=None,
	customer=None,
	terminal=None,
	**kwargs
):
	"""Create a new Wallee Transaction record"""
	doc = frappe.new_doc("Wallee Transaction")
	doc.transaction_id = str(transaction_id)
	doc.amount = amount
	doc.currency = currency
	doc.transaction_type = transaction_type
	doc.reference_doctype = reference_doctype
	doc.reference_name = reference_name
	doc.customer = customer
	doc.status = "Pending"

	if terminal:
		doc.terminal = terminal
		doc.is_terminal_transaction = 1
		doc.transaction_type = "Terminal"

	for key, value in kwargs.items():
		if hasattr(doc, key):
			setattr(doc, key, value)

	doc.insert(ignore_permissions=True)
	frappe.db.commit()

	return doc
