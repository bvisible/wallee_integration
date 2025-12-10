# -*- coding: utf-8 -*-
import frappe
from frappe import _


def after_install():
	"""Create default Wallee Settings and Payment Gateway"""
	# Create Wallee Settings if not exists
	if not frappe.db.exists("Wallee Settings", "Wallee Settings"):
		doc = frappe.new_doc("Wallee Settings")
		doc.enabled = 0
		doc.insert(ignore_permissions=True)
		frappe.db.commit()

	# Create Payment Gateway for Wallee
	create_payment_gateway()

	frappe.msgprint(_("Wallee Integration installed successfully. Please configure your Wallee settings."))


def create_payment_gateway():
	"""Create Wallee Payment Gateway if not exists"""
	if not frappe.db.exists("Payment Gateway", "Wallee"):
		gateway = frappe.get_doc({
			"doctype": "Payment Gateway",
			"gateway": "Wallee",
			"gateway_controller": "Wallee Settings"
		})
		gateway.insert(ignore_permissions=True)
		frappe.db.commit()
		frappe.logger().info("Created Payment Gateway: Wallee")
