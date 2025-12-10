# -*- coding: utf-8 -*-
# Copyright (c) 2024, Neoservice and contributors
# For license information, please see license.txt

import frappe
from frappe import _


_wallee_client = None


def get_wallee_client():
	"""Get configured Wallee API client singleton"""
	global _wallee_client

	if _wallee_client is not None:
		return _wallee_client

	settings = frappe.get_single("Wallee Settings")

	if not settings.enabled:
		frappe.throw(_("Wallee Integration is not enabled"))

	if not all([settings.user_id, settings.authentication_key, settings.space_id]):
		frappe.throw(_("Wallee credentials are not configured"))

	try:
		from wallee.configuration import Configuration

		host = settings.api_host or "https://app-wallee.com/api/v2.0"

		_wallee_client = Configuration(
			user_id=settings.user_id,
			authentication_key=settings.get_password("authentication_key"),
			host=host
		)

		return _wallee_client
	except ImportError:
		frappe.throw(_("Wallee Python SDK is not installed. Please run: pip install wallee"))
	except Exception as e:
		frappe.throw(_("Failed to initialize Wallee client: {0}").format(str(e)))


def get_space_id():
	"""Get the configured Wallee Space ID"""
	settings = frappe.get_single("Wallee Settings")
	return settings.space_id


def log_api_call(method, endpoint, request_data=None, response_data=None, error=None):
	"""Log API calls if logging is enabled"""
	settings = frappe.get_single("Wallee Settings")

	if not settings.log_api_calls:
		return

	frappe.get_doc({
		"doctype": "Error Log",
		"method": f"Wallee API: {method} {endpoint}",
		"error": frappe.as_json({
			"request": request_data,
			"response": response_data,
			"error": str(error) if error else None
		})
	}).insert(ignore_permissions=True)


def reset_client():
	"""Reset the cached client (useful after settings change)"""
	global _wallee_client
	_wallee_client = None


@frappe.whitelist()
def test_connection():
	"""
	Test connection to Wallee API

	Returns:
		dict: {success: bool, space_name: str, space_info: dict, error: str}
	"""
	try:
		from wallee.service.account_service import AccountService

		config = get_wallee_client()
		space_id = get_space_id()

		# Try to read the space to verify connection
		service = AccountService(config)
		space = service.read(space_id)

		space_info = {}
		if space:
			space_info = {
				"id": space.id,
				"name": getattr(space, "name", None),
				"state": getattr(space, "state", {}).value if hasattr(getattr(space, "state", None), "value") else str(getattr(space, "state", "Unknown"))
			}

		log_api_call("GET", f"account/{space_id}", response_data=space_info)

		return {
			"success": True,
			"space_name": space_info.get("name"),
			"space_info": space_info
		}
	except Exception as e:
		log_api_call("GET", "account/test", error=e)
		return {
			"success": False,
			"error": str(e)
		}
