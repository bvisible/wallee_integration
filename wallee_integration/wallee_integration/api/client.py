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
	Test connection to Wallee API by listing transactions

	Returns:
		dict: {success: bool, space_id: int, error: str}
	"""
	try:
		from wallee import TransactionsService

		config = get_wallee_client()
		space_id = get_space_id()

		# Test connection by listing transactions (will fail if credentials are invalid)
		service = TransactionsService(config)

		# This will throw an exception if credentials are invalid
		service.get_payment_transactions(space_id)

		log_api_call("GET", "payment/transactions", {"test": True}, {"success": True})

		return {
			"success": True,
			"space_id": space_id
		}
	except Exception as e:
		log_api_call("GET", "payment/transactions", {"test": True}, error=e)
		return {
			"success": False,
			"error": str(e)
		}


@frappe.whitelist()
def get_available_payment_methods():
	"""
	Get available payment method configurations from Wallee Space.
	These can be used to create separate Payment Gateway Accounts (Card, TWINT, etc.)

	Returns:
		dict: {success: bool, methods: list, error: str}
	"""
	try:
		from wallee.service.payment_method_configurations_service import PaymentMethodConfigurationsService

		config = get_wallee_client()
		space_id = get_space_id()

		service = PaymentMethodConfigurationsService(config)
		response = service.get_all_payment_method_configurations(space_id)

		# Extract method list from response
		methods_list = getattr(response, 'data', None) or getattr(response, 'items', None) or response or []

		methods = []
		for method in methods_list:
			# Handle both object and dict formats
			if hasattr(method, 'id'):
				method_id = method.id
				method_name = method.name
				resolved_title = method.resolved_title if hasattr(method, 'resolved_title') else None
				state = method.state if hasattr(method, 'state') else None
			else:
				method_id = method.get('id')
				method_name = method.get('name')
				resolved_title = method.get('resolved_title')
				state = method.get('state')

			# Only include active methods
			if state and str(state).upper() != 'ACTIVE':
				continue

			# Extract localized title
			title = method_name
			if resolved_title:
				if isinstance(resolved_title, dict):
					title = resolved_title.get('fr-FR') or resolved_title.get('en-US') or resolved_title.get('de-DE') or list(resolved_title.values())[0] if resolved_title else method_name
				else:
					title = str(resolved_title)

			methods.append({
				"id": method_id,
				"name": method_name,
				"title": title
			})

		return {
			"success": True,
			"methods": methods
		}

	except Exception as e:
		frappe.log_error("Wallee payment methods error", f"Failed to get payment methods: {str(e)}")
		return {
			"success": False,
			"methods": [],
			"error": str(e)
		}


@frappe.whitelist()
def setup_webshop_integration(currency="CHF", payment_account=None, checkout_title="Wallee", checkout_description=None, payment_method_id=None, payment_method_name=None):
	"""
	Setup complete webshop integration for Wallee.
	Creates Payment Gateway, Payment Gateway Account, and adds to Webshop Settings.

	Args:
		currency: Currency code (default: CHF)
		payment_account: Bank/Cash account for payments
		checkout_title: Title shown at checkout
		checkout_description: Description shown at checkout
		payment_method_id: Wallee Payment Method Configuration ID (optional)
		payment_method_name: Name suffix for the gateway account (e.g., "Card", "TWINT")

	Returns:
		dict: {success: bool, payment_gateway: str, payment_gateway_account: str, error: str}
	"""
	try:
		# Step 1: Ensure Payment Gateway exists
		if not frappe.db.exists("Payment Gateway", "Wallee"):
			gateway = frappe.get_doc({
				"doctype": "Payment Gateway",
				"gateway": "Wallee",
				"gateway_settings": "Wallee Settings"
			})
			gateway.insert(ignore_permissions=True)
			frappe.db.commit()

		# Step 2: Find or create Payment Gateway Account
		# If payment_method_id is provided, search by that too for uniqueness
		filters = {"payment_gateway": "Wallee", "currency": currency}

		if payment_method_id:
			# Check if account with this specific method ID exists
			existing_pga = frappe.db.get_value(
				"Payment Gateway Account",
				{"payment_gateway": "Wallee", "currency": currency, "wallee_payment_method_id": payment_method_id},
				"name"
			)
		else:
			# Search by payment_gateway and currency (name may have suffix)
			existing_pga = frappe.db.get_value(
				"Payment Gateway Account",
				filters,
				"name"
			)

		if existing_pga:
			# Update existing
			pga = frappe.get_doc("Payment Gateway Account", existing_pga)
			if payment_account:
				pga.payment_account = payment_account
			if checkout_title:
				pga.checkout_title = checkout_title
			if checkout_description:
				pga.checkout_description = checkout_description
			if payment_method_id:
				pga.wallee_payment_method_id = int(payment_method_id)
			pga.save(ignore_permissions=True)
			frappe.db.commit()
			account_name = existing_pga
		else:
			# Build account name with method suffix if provided
			account_title = checkout_title or "Wallee"
			if payment_method_name:
				account_title = f"Wallee - {payment_method_name}"

			# Create new
			pga_data = {
				"doctype": "Payment Gateway Account",
				"payment_gateway": "Wallee",
				"currency": currency,
				"payment_account": payment_account,
				"checkout_title": account_title,
				"checkout_description": checkout_description or _("Pay securely with credit card"),
				"is_default": 0
			}

			if payment_method_id:
				pga_data["wallee_payment_method_id"] = int(payment_method_id)

			pga = frappe.get_doc(pga_data)
			pga.insert(ignore_permissions=True)
			frappe.db.commit()
			account_name = pga.name

		# Step 3: Add to Webshop Settings payment methods
		if frappe.db.exists("DocType", "Webshop Settings"):
			webshop_settings = frappe.get_single("Webshop Settings")

			# Check if Wallee is already in payment methods (by actual account name)
			existing = False
			for method in webshop_settings.payment_methods:
				if method.payment_gateway_account == account_name:
					existing = True
					break

			if not existing:
				webshop_settings.append("payment_methods", {
					"payment_gateway_account": account_name
				})
				webshop_settings.save(ignore_permissions=True)
				frappe.db.commit()

		return {
			"success": True,
			"payment_gateway": "Wallee",
			"payment_gateway_account": account_name
		}

	except Exception as e:
		frappe.log_error("Wallee setup error", f"Failed to setup webshop integration: {str(e)}")
		return {
			"success": False,
			"error": str(e)
		}
