# -*- coding: utf-8 -*-
# Copyright (c) 2024, Neoservice and contributors
# Test file for terminal payment cancellation

"""
Terminal Payment Cancel Test

This file tests different methods to cancel a terminal transaction.

According to Wallee documentation:
- REST API `perform_transaction` is synchronous and has NO cancel mechanism
- To cancel, you need to use the WebSocket Till Connection with `tillConnection.cancel()`
- The `void_online` only works for AUTHORIZED transactions, not PENDING

Options explored:
1. void_online - Only works for AUTHORIZED state
2. charge_flow_cancel - For charge flow transactions only
3. Till WebSocket Connection - Real-time control with cancel() method
4. Terminal credentials - Get WebSocket URL for till connection
"""

import frappe
from frappe import _


def test_get_terminal_credentials(terminal_id, transaction_id):
    """
    Get the WebSocket credentials for a terminal's till connection.
    These credentials are needed to establish a real-time connection
    that supports cancellation.

    NOTE: This requires an ACTIVE transaction on the terminal.
    The credentials are transaction-specific.
    """
    from wallee_integration.wallee_integration.api.client import get_wallee_client, get_space_id
    from wallee.service.payment_terminals_service import PaymentTerminalsService

    if not terminal_id or not transaction_id:
        frappe.throw(_("Both terminal_id and transaction_id are required"))

    config = get_wallee_client()
    space_id = get_space_id()
    service = PaymentTerminalsService(config)

    try:
        # Get till connection credentials
        # This returns WebSocket URL and auth tokens needed for real-time connection
        # Signature: (id, transaction_id, space, language=None)
        credentials = service.get_payment_terminals_id_till_connection_credentials(
            int(terminal_id),
            int(transaction_id),
            space_id
        )

        result = {
            "terminal_id": terminal_id,
            "transaction_id": transaction_id,
            "credentials_type": type(credentials).__name__,
        }

        # The credentials should be a string (WebSocket URL with auth token)
        if isinstance(credentials, str):
            result["websocket_url"] = credentials
        elif hasattr(credentials, 'to_dict'):
            result["credentials"] = credentials.to_dict()
        elif hasattr(credentials, '__dict__'):
            result["credentials"] = {k: v for k, v in credentials.__dict__.items() if not k.startswith('_')}
        else:
            result["credentials"] = str(credentials)

        frappe.log_error("Terminal Credentials", frappe.as_json(result))
        return result

    except Exception as e:
        frappe.log_error("Credentials Error", str(e))
        raise


def test_transaction_states(transaction_id):
    """
    Get the current state of a transaction and check what operations are possible.
    """
    from wallee_integration.wallee_integration.api.transaction import get_full_transaction

    try:
        tx = get_full_transaction(transaction_id)

        state = tx.state.value if tx.state else "Unknown"

        result = {
            "transaction_id": transaction_id,
            "state": state,
            "can_void": state == "AUTHORIZED",
            "can_complete": state == "AUTHORIZED",
            "is_terminal": tx.user_interface_type.value == "TERMINAL" if tx.user_interface_type else False,
            "terminal_id": tx.terminal.id if tx.terminal else None,
        }

        # Check what the failure reason is if any
        if tx.failure_reason:
            if hasattr(tx.failure_reason, 'description'):
                result["failure_reason"] = tx.failure_reason.description
            else:
                result["failure_reason"] = str(tx.failure_reason)

        frappe.log_error("Transaction State Test", frappe.as_json(result))
        return result

    except Exception as e:
        frappe.log_error("State Check Error", str(e))
        raise


def test_charge_flow_cancel(transaction_id):
    """
    Try to cancel using charge flow cancel.
    This is typically for charge flow transactions, not terminal.
    """
    from wallee_integration.wallee_integration.api.client import get_wallee_client, get_space_id
    from wallee import TransactionsService

    config = get_wallee_client()
    space_id = get_space_id()
    service = TransactionsService(config)

    try:
        # Try charge flow cancel
        response = service.post_payment_transactions_id_charge_flow_cancel(
            int(transaction_id),
            space_id
        )

        result = {
            "success": True,
            "response": response.to_dict() if hasattr(response, 'to_dict') else str(response)
        }

        frappe.log_error("Charge Flow Cancel Test", frappe.as_json(result))
        return result

    except Exception as e:
        error_msg = str(e)
        frappe.log_error("Charge Flow Cancel Error", error_msg)
        return {
            "success": False,
            "error": error_msg
        }


def test_void_offline(transaction_id):
    """
    Try void offline - might work differently than void online.
    """
    from wallee_integration.wallee_integration.api.client import get_wallee_client, get_space_id
    from wallee import TransactionsService

    config = get_wallee_client()
    space_id = get_space_id()
    service = TransactionsService(config)

    try:
        response = service.post_payment_transactions_id_void_offline(
            int(transaction_id),
            space_id
        )

        result = {
            "success": True,
            "response": response.to_dict() if hasattr(response, 'to_dict') else str(response)
        }

        frappe.log_error("Void Offline Test", frappe.as_json(result))
        return result

    except Exception as e:
        error_msg = str(e)
        frappe.log_error("Void Offline Error", error_msg)
        return {
            "success": False,
            "error": error_msg
        }


def test_all_cancel_methods(transaction_id):
    """
    Test all available cancel methods on a transaction.
    Run this while a terminal transaction is in PENDING/PROCESSING state.
    """
    results = {
        "transaction_id": transaction_id,
        "tests": {}
    }

    # 1. Check current state
    try:
        results["tests"]["state_check"] = test_transaction_states(transaction_id)
    except Exception as e:
        results["tests"]["state_check"] = {"error": str(e)}

    # 2. Try charge flow cancel
    try:
        results["tests"]["charge_flow_cancel"] = test_charge_flow_cancel(transaction_id)
    except Exception as e:
        results["tests"]["charge_flow_cancel"] = {"error": str(e)}

    # 3. Try void offline
    try:
        results["tests"]["void_offline"] = test_void_offline(transaction_id)
    except Exception as e:
        results["tests"]["void_offline"] = {"error": str(e)}

    frappe.log_error("All Cancel Tests", frappe.as_json(results))
    return results


@frappe.whitelist()
def run_cancel_test(transaction_name):
    """
    Whitelisted method to run cancel tests on a transaction.

    Usage:
        frappe.call({
            method: 'wallee_integration.wallee_integration.api.terminal_test.run_cancel_test',
            args: { transaction_name: 'WALLEE-TX-00001' }
        })
    """
    doc = frappe.get_doc("Wallee Transaction", transaction_name)

    if not doc.transaction_id:
        frappe.throw(_("Transaction has no Wallee transaction ID"))

    return test_all_cancel_methods(doc.transaction_id)


@frappe.whitelist()
def get_till_credentials(transaction_name):
    """
    Get WebSocket credentials for till connection during an active transaction.

    Usage:
        frappe.call({
            method: 'wallee_integration.wallee_integration.api.terminal_test.get_till_credentials',
            args: { transaction_name: 'WALLEE-TX-00001' }
        })

    Returns:
        dict with terminal_id, transaction_id, websocket_url (token)
        The websocket_url is a token to use with the Wallee Till JavaScript SDK
    """
    doc = frappe.get_doc("Wallee Transaction", transaction_name)

    if not doc.transaction_id:
        frappe.throw(_("Transaction has no Wallee transaction ID"))

    # Get terminal ID
    terminal_id = None
    if doc.terminal:
        terminal_doc = frappe.get_doc("Wallee Payment Terminal", doc.terminal)
        terminal_id = terminal_doc.terminal_id

    if not terminal_id:
        # Try to get from Wallee transaction data
        from wallee_integration.wallee_integration.api.transaction import get_full_transaction
        tx = get_full_transaction(doc.transaction_id)
        if tx.terminal:
            terminal_id = tx.terminal.id

    if not terminal_id:
        frappe.throw(_("Could not determine terminal ID for this transaction"))

    return test_get_terminal_credentials(terminal_id, doc.transaction_id)


@frappe.whitelist()
def get_till_websocket_info(transaction_name):
    """
    Get complete WebSocket info needed to establish a Till connection
    and potentially cancel the transaction.

    The Till connection uses STOMP over WebSocket.
    Base WebSocket URL: wss://app-wallee.com/api/terminal/till/stomp

    Usage:
        frappe.call({
            method: 'wallee_integration.wallee_integration.api.terminal_test.get_till_websocket_info',
            args: { transaction_name: 'WALLEE-TX-00001' }
        })
    """
    from wallee_integration.wallee_integration.api.client import get_space_id

    doc = frappe.get_doc("Wallee Transaction", transaction_name)

    if not doc.transaction_id:
        frappe.throw(_("Transaction has no Wallee transaction ID"))

    # Get terminal info
    terminal_id = None
    terminal_identifier = None

    if doc.terminal:
        terminal_doc = frappe.get_doc("Wallee Payment Terminal", doc.terminal)
        terminal_id = terminal_doc.terminal_id
        terminal_identifier = terminal_doc.identifier

    if not terminal_id:
        from wallee_integration.wallee_integration.api.transaction import get_full_transaction
        tx = get_full_transaction(doc.transaction_id)
        if tx.terminal:
            terminal_id = tx.terminal.id
            terminal_identifier = tx.terminal.identifier

    if not terminal_id:
        frappe.throw(_("Could not determine terminal ID for this transaction"))

    # Get credentials
    creds = test_get_terminal_credentials(terminal_id, doc.transaction_id)

    space_id = get_space_id()

    return {
        "transaction_name": transaction_name,
        "transaction_id": doc.transaction_id,
        "terminal_id": terminal_id,
        "terminal_identifier": terminal_identifier,
        "space_id": space_id,
        "websocket_base_url": "wss://app-wallee.com/api/terminal/till/stomp",
        "credentials_token": creds.get("websocket_url"),
        "stomp_headers": {
            "transactionId": doc.transaction_id,
            "spaceId": str(space_id),
        }
    }
