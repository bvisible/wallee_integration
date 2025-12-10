# -*- coding: utf-8 -*-
import frappe
from frappe import _


def after_install():
	"""Create default Wallee Settings if not exists"""
	if not frappe.db.exists("Wallee Settings", "Wallee Settings"):
		doc = frappe.new_doc("Wallee Settings")
		doc.enabled = 0
		doc.insert(ignore_permissions=True)
		frappe.db.commit()

	frappe.msgprint(_("Wallee Integration installed successfully. Please configure your Wallee settings."))
