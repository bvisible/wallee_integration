# -*- coding: utf-8 -*-
import frappe

no_cache = 1


def get_context(context):
	transaction_id = frappe.form_dict.get("transaction_id")

	context.transaction = None

	if transaction_id:
		# Find local transaction
		transaction_name = frappe.db.get_value(
			"Wallee Transaction",
			{"transaction_id": str(transaction_id)},
			"name"
		)

		if transaction_name:
			context.transaction = frappe.get_doc("Wallee Transaction", transaction_name)

			# Sync status
			context.transaction.sync_status()
			context.transaction.reload()

	return context
