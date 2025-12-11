# -*- coding: utf-8 -*-
# Copyright (c) 2024, bVisible and contributors
# For license information, please see license.txt

import frappe
from frappe import _
import json


@frappe.whitelist()
def get_current_settings():
    """Get current Wallee settings if any"""
    settings = frappe.get_single("Wallee Settings")
    return {
        "user_id": settings.user_id or "",
        "space_id": settings.space_id or "",
        "has_auth_key": bool(settings.authentication_key),
        "enabled": settings.enabled,
        "enable_webshop": settings.enable_webshop,
        "enable_pos_terminal": settings.enable_pos_terminal
    }


@frappe.whitelist()
def save_credentials(user_id, authentication_key, space_id):
    """Save Wallee API credentials"""
    settings = frappe.get_single("Wallee Settings")
    settings.user_id = user_id
    settings.authentication_key = authentication_key
    settings.space_id = space_id
    settings.enabled = 1
    settings.save(ignore_permissions=True)
    frappe.db.commit()

    return {"success": True}


@frappe.whitelist()
def test_connection():
    """Test Wallee API connection"""
    try:
        from wallee import TransactionsService
        from wallee.configuration import Configuration

        settings = frappe.get_single("Wallee Settings")

        if not settings.user_id or not settings.authentication_key or not settings.space_id:
            return {
                "success": False,
                "error": _("Missing credentials. Please complete all fields.")
            }

        config = Configuration(
            user_id=int(settings.user_id),
            authentication_key=settings.get_password("authentication_key")
        )

        service = TransactionsService(config)
        space_id = int(settings.space_id)

        # Test by listing transactions
        service.get_payment_transactions(space_id)

        return {
            "success": True,
            "space_id": space_id,
            "user_id": settings.user_id
        }
    except Exception as e:
        error_msg = str(e)

        # Parse common errors
        if "access_denied" in error_msg.lower() or "403" in error_msg:
            return {
                "success": False,
                "error": _("Permission denied. Please check that your Application User has the required permissions."),
                "error_type": "permission"
            }
        elif "space_missing" in error_msg.lower():
            return {
                "success": False,
                "error": _("Space not found. Please verify the Space ID."),
                "error_type": "space"
            }
        elif "authentication" in error_msg.lower() or "401" in error_msg:
            return {
                "success": False,
                "error": _("Authentication failed. Please check your User ID and Authentication Key."),
                "error_type": "auth"
            }
        else:
            return {
                "success": False,
                "error": error_msg,
                "error_type": "unknown"
            }


@frappe.whitelist()
def test_transaction_creation():
    """Test creating a transaction (validates write permissions)"""
    try:
        from wallee import TransactionsService, LineItemCreate, TransactionCreate, LineItemType
        from wallee.configuration import Configuration

        settings = frappe.get_single("Wallee Settings")

        config = Configuration(
            user_id=int(settings.user_id),
            authentication_key=settings.get_password("authentication_key")
        )

        service = TransactionsService(config)
        space_id = int(settings.space_id)

        # Create a test transaction
        line_item = LineItemCreate(
            name="Test Item",
            quantity=1,
            amount_including_tax=1.0,
            unique_id=f"test-{frappe.generate_hash()[:8]}",
            type=LineItemType.PRODUCT
        )

        tx = TransactionCreate(
            line_items=[line_item],
            currency="CHF",
            auto_confirmation_enabled=True
        )

        result = service.post_payment_transactions(space_id, tx)

        # Get payment URL to verify full flow
        payment_url = service.get_payment_transactions_id_payment_page_url(result.id, space_id)

        return {
            "success": True,
            "transaction_id": result.id,
            "payment_url": payment_url,
            "state": result.state.value if result.state else None
        }
    except Exception as e:
        error_msg = str(e)

        if "access_denied" in error_msg.lower() or "403" in error_msg:
            # Extract permission details if available
            if "Transaction >> Create" in error_msg:
                return {
                    "success": False,
                    "error": _("Your Application User lacks 'Transaction >> Create' permission. Please add the 'Account Admin' role."),
                    "error_type": "permission"
                }
            return {
                "success": False,
                "error": _("Permission denied for transaction creation. Please verify your Application User has write permissions."),
                "error_type": "permission"
            }
        else:
            return {
                "success": False,
                "error": error_msg,
                "error_type": "unknown"
            }


@frappe.whitelist()
def setup_webshop(currency="CHF", payment_account=None):
    """Setup webshop integration"""
    try:
        from wallee_integration.wallee_integration.api.client import setup_webshop_integration

        result = setup_webshop_integration(
            currency=currency,
            payment_account=payment_account,
            checkout_title="Wallee",
            checkout_description=_("Pay securely with credit card")
        )

        if result.get("success"):
            # Update settings
            settings = frappe.get_single("Wallee Settings")
            settings.enable_webshop = 1
            settings.save(ignore_permissions=True)
            frappe.db.commit()

        return result
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@frappe.whitelist()
def get_payment_accounts():
    """Get list of bank/cash accounts for payment configuration"""
    accounts = frappe.get_all(
        "Account",
        filters={
            "account_type": ["in", ["Bank", "Cash"]],
            "is_group": 0,
            "disabled": 0
        },
        fields=["name", "account_name", "account_type", "company"],
        order_by="account_name"
    )
    return accounts


@frappe.whitelist()
def get_currencies():
    """Get list of enabled currencies"""
    currencies = frappe.get_all(
        "Currency",
        filters={"enabled": 1},
        fields=["name", "currency_name"],
        order_by="name"
    )
    return currencies
