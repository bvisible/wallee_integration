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

    # Set default URLs if not already set
    site_url = frappe.utils.get_url()
    if not settings.success_url:
        settings.success_url = f"{site_url}/wallee/success"
    if not settings.failed_url:
        settings.failed_url = f"{site_url}/wallee/failed"

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
def get_wallee_payment_methods():
    """Get available payment methods from Wallee"""
    try:
        from wallee_integration.wallee_integration.api.client import get_available_payment_methods
        return get_available_payment_methods()
    except Exception as e:
        return {
            "success": False,
            "methods": [],
            "error": str(e)
        }


@frappe.whitelist()
def setup_webshop(currency="CHF", payment_account=None, payment_methods=None):
    """Setup webshop integration with selected payment methods"""
    try:
        from wallee_integration.wallee_integration.api.client import setup_webshop_integration

        # Parse payment_methods if it's a string
        if isinstance(payment_methods, str):
            payment_methods = json.loads(payment_methods)

        created_accounts = []

        if payment_methods and len(payment_methods) > 0:
            # Create a Payment Gateway Account for each selected method
            for method in payment_methods:
                method_id = method.get("id")
                method_title = method.get("title") or method.get("name")

                result = setup_webshop_integration(
                    currency=currency,
                    payment_account=payment_account,
                    checkout_title=f"Wallee - {method_title}",
                    checkout_description=_("Pay with {0}").format(method_title),
                    payment_method_id=method_id,
                    payment_method_name=method_title
                )

                if result.get("success"):
                    created_accounts.append({
                        "name": result.get("payment_gateway_account"),
                        "method_id": method_id,
                        "method_title": method_title
                    })
        else:
            # No specific methods - create generic Wallee account
            result = setup_webshop_integration(
                currency=currency,
                payment_account=payment_account,
                checkout_title="Wallee",
                checkout_description=_("Pay securely with credit card")
            )

            if result.get("success"):
                created_accounts.append({
                    "name": result.get("payment_gateway_account"),
                    "method_id": None,
                    "method_title": "All methods"
                })

        if created_accounts:
            # Update settings
            settings = frappe.get_single("Wallee Settings")
            settings.enable_webshop = 1
            settings.save(ignore_permissions=True)
            frappe.db.commit()

            return {
                "success": True,
                "payment_gateway": "Wallee",
                "accounts": created_accounts
            }
        else:
            return {
                "success": False,
                "error": _("No payment gateway accounts were created")
            }

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


@frappe.whitelist()
def save_features(enable_webshop=False, enable_pos_terminal=False):
    """Save feature flags"""
    settings = frappe.get_single("Wallee Settings")
    settings.enable_webshop = 1 if enable_webshop else 0
    settings.enable_pos_terminal = 1 if enable_pos_terminal else 0
    settings.save(ignore_permissions=True)
    frappe.db.commit()
    return {"success": True}


@frappe.whitelist()
def create_dedicated_users(enable_webshop=False, enable_pos_terminal=False):
    """Create dedicated Application Users for Webshop and/or POS with Account Admin role"""
    from wallee import (
        Configuration,
        ApplicationUsersService,
        ApplicationUserCreate,
        ApplicationUsersRolesService,
        AccountsService
    )

    settings = frappe.get_single("Wallee Settings")

    if not settings.user_id or not settings.authentication_key:
        return {
            "success": False,
            "error": _("Admin credentials not configured. Please complete Step 3 first.")
        }

    config = Configuration(
        user_id=int(settings.user_id),
        authentication_key=settings.get_password("authentication_key")
    )

    results = {
        "success": True,
        "webshop": None,
        "pos": None
    }

    try:
        # Get Account ID
        acc_service = AccountsService(config)
        accounts = acc_service.get_accounts(limit=1)
        if not accounts.data:
            return {"success": False, "error": _("No Wallee account found")}

        account_id = accounts.data[0].id
        space_id = int(settings.space_id)

        # Save account_id to settings
        settings.account_id = account_id

        # Account Admin role ID (standard Wallee role with full permissions)
        ACCOUNT_ADMIN_ROLE_ID = 2

        user_service = ApplicationUsersService(config)
        role_assign_service = ApplicationUsersRolesService(config)

        # Create Webshop User if enabled
        if enable_webshop:
            # Check if webshop user already exists
            if settings.webshop_user_id:
                results["webshop"] = {
                    "status": "exists",
                    "user_id": settings.webshop_user_id
                }
            else:
                try:
                    # Create unique name with site identifier
                    site_name = frappe.local.site.replace('.', '_')
                    webshop_user = ApplicationUserCreate(
                        name=f"webshop_{site_name}",
                        primary_account=account_id
                    )

                    created_user = user_service.post_application_users(webshop_user)

                    # Assign Account Admin role at Account level for full permissions
                    role_assign_service.post_application_users_user_id_account_roles(
                        user_id=created_user.id,
                        role_id=ACCOUNT_ADMIN_ROLE_ID,
                        account=account_id
                    )

                    # Save credentials to settings
                    settings.webshop_user_id = created_user.id
                    settings.webshop_authentication_key = created_user.mac_key

                    results["webshop"] = {
                        "status": "created",
                        "user_id": created_user.id,
                        "name": created_user.name,
                        "role_assigned": True
                    }
                except Exception as e:
                    results["webshop"] = {
                        "status": "error",
                        "error": str(e)
                    }
                    results["success"] = False

        # Create POS User if enabled
        if enable_pos_terminal:
            # Check if POS user already exists
            if settings.pos_user_id:
                results["pos"] = {
                    "status": "exists",
                    "user_id": settings.pos_user_id
                }
            else:
                try:
                    site_name = frappe.local.site.replace('.', '_')
                    pos_user = ApplicationUserCreate(
                        name=f"pos_{site_name}",
                        primary_account=account_id
                    )

                    created_user = user_service.post_application_users(pos_user)

                    # Assign Account Admin role at Account level for full permissions
                    role_assign_service.post_application_users_user_id_account_roles(
                        user_id=created_user.id,
                        role_id=ACCOUNT_ADMIN_ROLE_ID,
                        account=account_id
                    )

                    # Save credentials to settings
                    settings.pos_user_id = created_user.id
                    settings.pos_authentication_key = created_user.mac_key

                    results["pos"] = {
                        "status": "created",
                        "user_id": created_user.id,
                        "name": created_user.name,
                        "role_assigned": True
                    }
                except Exception as e:
                    results["pos"] = {
                        "status": "error",
                        "error": str(e)
                    }
                    results["success"] = False

        # Save all changes to settings
        settings.save(ignore_permissions=True)
        frappe.db.commit()

        return results

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@frappe.whitelist()
def fix_user_permissions():
    """Add Account Admin role to existing users that may be missing permissions"""
    from wallee import (
        Configuration,
        ApplicationUsersRolesService,
        AccountsService
    )

    settings = frappe.get_single("Wallee Settings")

    if not settings.user_id or not settings.authentication_key:
        return {
            "success": False,
            "error": _("Admin credentials not configured.")
        }

    config = Configuration(
        user_id=int(settings.user_id),
        authentication_key=settings.get_password("authentication_key")
    )

    ACCOUNT_ADMIN_ROLE_ID = 2

    try:
        # Get Account ID
        acc_service = AccountsService(config)
        accounts = acc_service.get_accounts(limit=1)
        if not accounts.data:
            return {"success": False, "error": _("No Wallee account found")}

        account_id = accounts.data[0].id
        role_assign_service = ApplicationUsersRolesService(config)

        results = {"success": True, "users_updated": []}

        # Update main user
        try:
            role_assign_service.post_application_users_user_id_account_roles(
                user_id=int(settings.user_id),
                role_id=ACCOUNT_ADMIN_ROLE_ID,
                account=account_id
            )
            results["users_updated"].append(f"Main user {settings.user_id}")
        except Exception as e:
            # May already have the role
            pass

        # Update webshop user if exists
        if settings.webshop_user_id:
            try:
                role_assign_service.post_application_users_user_id_account_roles(
                    user_id=int(settings.webshop_user_id),
                    role_id=ACCOUNT_ADMIN_ROLE_ID,
                    account=account_id
                )
                results["users_updated"].append(f"Webshop user {settings.webshop_user_id}")
            except Exception as e:
                pass

        # Update POS user if exists
        if settings.pos_user_id:
            try:
                role_assign_service.post_application_users_user_id_account_roles(
                    user_id=int(settings.pos_user_id),
                    role_id=ACCOUNT_ADMIN_ROLE_ID,
                    account=account_id
                )
                results["users_updated"].append(f"POS user {settings.pos_user_id}")
            except Exception as e:
                pass

        return results

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
