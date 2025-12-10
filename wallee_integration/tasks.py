# -*- coding: utf-8 -*-
import frappe
from frappe import _


def sync_pending_transactions():
	"""Sync pending transactions with Wallee API"""
	from wallee_integration.wallee_integration.doctype.wallee_transaction.wallee_transaction import sync_transaction_status

	# Get all pending transactions
	pending_transactions = frappe.get_all(
		"Wallee Transaction",
		filters={"status": ["in", ["Pending", "Processing", "Authorized"]]},
		pluck="name"
	)

	for transaction_name in pending_transactions:
		try:
			sync_transaction_status(transaction_name)
		except Exception as e:
			frappe.log_error(
				message=str(e),
				title=f"Wallee Transaction Sync Error: {transaction_name}"
			)


def cleanup_old_transactions():
	"""Archive old completed/failed transactions"""
	# Keep transactions for 90 days
	frappe.db.sql("""
		UPDATE `tabWallee Transaction`
		SET archived = 1
		WHERE status IN ('Completed', 'Failed', 'Voided', 'Refunded')
		AND creation < DATE_SUB(NOW(), INTERVAL 90 DAY)
		AND archived = 0
	""")
	frappe.db.commit()
