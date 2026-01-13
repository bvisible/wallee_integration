# -*- coding: utf-8 -*-
# Copyright (c) 2024, Neoservice and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from wallee_integration.wallee_integration.api.client import (
    get_wallee_client,
    get_space_id,
    log_api_call
)


def create_transaction(amount=None, line_items=None, currency=None, **kwargs):
    """
    Create a new Wallee transaction and return payment URL

    Args:
        amount: Total amount (used if line_items not provided)
        line_items: List of line items (name, quantity, amount_including_tax, type, sku)
        currency: Currency code (e.g., 'CHF', 'EUR')
        **kwargs: Additional transaction parameters:
            - merchant_reference: Reference ID
            - customer_id: Customer identifier
            - customer_email: Customer email address
            - success_url: URL to redirect on success
            - failed_url: URL to redirect on failure
            - auto_confirm: Auto confirm transaction (default True)
            - billing_address: dict with given_name, family_name, email_address, street, city, postcode, country

    Returns:
        dict: {transaction_id, payment_url, state}
    """
    from wallee import TransactionsService, LineItemCreate, TransactionCreate, LineItemType, AddressCreate

    config = get_wallee_client()
    space_id = get_space_id()
    service = TransactionsService(config)

    # Build line items
    wallee_line_items = []

    if line_items:
        for item in line_items:
            # Map item type
            item_type = LineItemType.PRODUCT
            type_str = item.get("type", "PRODUCT").upper()
            if type_str == "SHIPPING":
                item_type = LineItemType.SHIPPING
            elif type_str == "DISCOUNT":
                item_type = LineItemType.DISCOUNT
            elif type_str == "FEE":
                item_type = LineItemType.FEE

            # Support both "amount_including_tax" and "amount" as field names
            item_amount = item.get("amount_including_tax") or item.get("amount", 0)

            line_item = LineItemCreate(
                name=item.get("name"),
                quantity=float(item.get("quantity", 1)),
                amount_including_tax=float(item_amount),
                unique_id=item.get("unique_id") or item.get("sku") or str(frappe.generate_hash()[:8]),
                type=item_type,
                sku=item.get("sku")
            )
            wallee_line_items.append(line_item)
    elif amount:
        # Create single line item for total amount
        line_item = LineItemCreate(
            name=kwargs.get("merchant_reference") or _("Payment"),
            quantity=1,
            amount_including_tax=float(amount),
            unique_id=str(frappe.generate_hash()[:8]),
            type=LineItemType.PRODUCT
        )
        wallee_line_items.append(line_item)
    else:
        frappe.throw(_("Either amount or line_items must be provided"))

    # Build billing address if provided
    wallee_billing_address = None
    billing_addr = kwargs.get("billing_address")
    if billing_addr:
        wallee_billing_address = AddressCreate(
            given_name=billing_addr.get("given_name"),
            family_name=billing_addr.get("family_name"),
            email_address=billing_addr.get("email_address"),
            street=billing_addr.get("street"),
            city=billing_addr.get("city"),
            postcode=billing_addr.get("postcode"),
            country=billing_addr.get("country")
        )

    # Create transaction
    transaction_create = TransactionCreate(
        line_items=wallee_line_items,
        currency=currency,
        auto_confirmation_enabled=kwargs.get("auto_confirm", True),
        merchant_reference=kwargs.get("merchant_reference"),
        customer_id=kwargs.get("customer_id"),
        customer_email_address=kwargs.get("customer_email"),
        success_url=kwargs.get("success_url"),
        failed_url=kwargs.get("failed_url"),
        billing_address=wallee_billing_address
    )

    try:
        # Create the transaction
        response = service.post_payment_transactions(space_id, transaction_create)
        log_api_call("POST", "payment/transactions", transaction_create.to_dict(), response.to_dict())

        transaction_id = response.id

        # Get payment page URL (note: method signature is id, space - not space, id)
        payment_url = service.get_payment_transactions_id_payment_page_url(transaction_id, space_id)
        log_api_call("GET", f"payment/transactions/{transaction_id}/payment-page-url", response_data=payment_url)

        return {
            "transaction_id": transaction_id,
            "payment_url": payment_url,
            "state": response.state.value if response.state else None
        }
    except Exception as e:
        log_api_call("POST", "payment/transactions", transaction_create.to_dict() if transaction_create else {}, error=e)
        raise


def get_transaction_status(transaction_id):
    """
    Get basic transaction status from Wallee.

    Args:
        transaction_id: Wallee transaction ID

    Returns:
        dict: Basic status information
    """
    from wallee import TransactionsService

    config = get_wallee_client()
    space_id = get_space_id()
    service = TransactionsService(config)

    try:
        # Note: method signature is (id, space) not (space, id)
        response = service.get_payment_transactions_id(transaction_id, space_id)
        log_api_call("GET", f"payment/transactions/{transaction_id}", response_data=response.to_dict())
        return {
            "id": response.id,
            "state": response.state.value if response.state else None,
            "authorized_amount": response.authorized_amount,
            "completed_amount": response.completed_amount,
            "refunded_amount": response.refunded_amount,
            "failure_reason": response.failure_reason.description if response.failure_reason else None,
            "payment_connector_configuration": response.payment_connector_configuration,
        }
    except Exception as e:
        log_api_call("GET", f"payment/transactions/{transaction_id}", error=e)
        raise


def get_full_transaction(transaction_id):
    """
    Get full transaction data from Wallee including line items, fees, etc.

    Args:
        transaction_id: Wallee transaction ID

    Returns:
        Transaction: Complete transaction object (not dict - SDK to_dict() truncates data)
    """
    from wallee import TransactionsService

    config = get_wallee_client()
    space_id = get_space_id()
    service = TransactionsService(config)

    try:
        # Note: method signature is (id, space) not (space, id)
        response = service.get_payment_transactions_id(int(transaction_id), space_id)
        log_api_call("GET", f"payment/transactions/{transaction_id}/full", response_data={"state": str(response.state)})

        # Return the full response object directly (NOT to_dict() which truncates data)
        return response
    except Exception as e:
        log_api_call("GET", f"payment/transactions/{transaction_id}/full", error=e)
        raise


def complete_transaction_online(transaction_id):
    """Complete an online transaction (capture)"""
    from wallee import TransactionsService

    config = get_wallee_client()
    space_id = get_space_id()
    service = TransactionsService(config)

    try:
        # Note: method signature is (id, space) not (space, id)
        response = service.post_payment_transactions_id_complete_online(transaction_id, space_id)
        log_api_call("POST", f"payment/transactions/{transaction_id}/complete-online", response_data=response.to_dict())
        return response
    except Exception as e:
        log_api_call("POST", f"payment/transactions/{transaction_id}/complete-online", error=e)
        raise


def capture_transaction(transaction_id):
    """Capture an authorized transaction"""
    return complete_transaction_online(transaction_id)


def void_transaction(transaction_id):
    """Void a pending or authorized transaction"""
    from wallee import TransactionsService

    config = get_wallee_client()
    space_id = get_space_id()
    service = TransactionsService(config)

    try:
        # Note: method signature is (id, space) not (space, id)
        response = service.post_payment_transactions_id_void_online(transaction_id, space_id)
        log_api_call("POST", f"payment/transactions/{transaction_id}/void", response_data=response.to_dict())
        return response
    except Exception as e:
        log_api_call("POST", f"payment/transactions/{transaction_id}/void", error=e)
        raise


def get_payment_page_url(transaction_id):
    """Get the payment page URL for a transaction (redirect mode)"""
    from wallee import TransactionsService

    config = get_wallee_client()
    space_id = get_space_id()
    service = TransactionsService(config)

    try:
        # Note: method signature is (id, space) not (space, id)
        response = service.get_payment_transactions_id_payment_page_url(transaction_id, space_id)
        log_api_call("GET", f"payment/transactions/{transaction_id}/payment-page-url", response_data=response)
        return response
    except Exception as e:
        log_api_call("GET", f"payment/transactions/{transaction_id}/payment-page-url", error=e)
        raise


def get_lightbox_javascript_url(transaction_id):
    """Get the Lightbox JavaScript URL for a transaction"""
    from wallee import TransactionsService

    config = get_wallee_client()
    space_id = get_space_id()
    service = TransactionsService(config)

    try:
        # Note: method signature is (id, space) not (space, id)
        response = service.get_payment_transactions_id_lightbox_javascript_url(transaction_id, space_id)
        log_api_call("GET", f"payment/transactions/{transaction_id}/lightbox-javascript-url", response_data=response)
        return response
    except Exception as e:
        log_api_call("GET", f"payment/transactions/{transaction_id}/lightbox-javascript-url", error=e)
        raise


def get_iframe_javascript_url(transaction_id):
    """Get the iFrame JavaScript URL for a transaction"""
    from wallee import TransactionsService

    config = get_wallee_client()
    space_id = get_space_id()
    service = TransactionsService(config)

    try:
        # Note: method signature is (id, space) not (space, id)
        response = service.get_payment_transactions_id_iframe_javascript_url(transaction_id, space_id)
        log_api_call("GET", f"payment/transactions/{transaction_id}/iframe-javascript-url", response_data=response)
        return response
    except Exception as e:
        log_api_call("GET", f"payment/transactions/{transaction_id}/iframe-javascript-url", error=e)
        raise


def get_javascript_url(transaction_id, mode="Redirect"):
    """
    Get the appropriate URL based on payment mode.

    Args:
        transaction_id: Wallee transaction ID
        mode: Payment mode - "Redirect", "Lightbox", or "iFrame"

    Returns:
        dict: {url, mode, transaction_id}
            - For Redirect: url is the payment page URL
            - For Lightbox/iFrame: url is the JavaScript URL to include
    """
    if mode == "Lightbox":
        url = get_lightbox_javascript_url(transaction_id)
    elif mode == "iFrame":
        url = get_iframe_javascript_url(transaction_id)
    else:
        url = get_payment_page_url(transaction_id)

    return {
        "url": url,
        "mode": mode,
        "transaction_id": transaction_id
    }


def get_payment_method_configurations(transaction_id, integration_mode="IFRAME"):
    """
    Get available payment method configurations for a transaction.

    Args:
        transaction_id: Wallee transaction ID
        integration_mode: IFRAME, LIGHTBOX, or PAYMENT_PAGE

    Returns:
        list: List of payment method configurations with id and name
    """
    from wallee import TransactionsService

    config = get_wallee_client()
    space_id = get_space_id()
    service = TransactionsService(config)

    try:
        response = service.get_payment_transactions_id_payment_method_configurations(
            transaction_id,
            integration_mode,
            space_id
        )
        log_api_call(
            "GET",
            f"payment/transactions/{transaction_id}/payment-method-configurations",
            {"integration_mode": integration_mode},
            response.to_dict() if hasattr(response, 'to_dict') else str(response)
        )

        # Extract payment methods from response
        methods = []
        # Response is PaymentMethodConfigurationListResponse with .data attribute
        data_list = getattr(response, 'data', None) or getattr(response, 'items', None) or []
        if isinstance(response, list):
            data_list = response

        for m in data_list:
            methods.append({
                "id": m.id,
                "name": getattr(m, 'name', None),
                "resolved_title": getattr(m, 'resolved_title', None),
                "resolved_description": getattr(m, 'resolved_description', None),
                "image_url": getattr(m, 'resolved_image_url', None)
            })
        return methods
    except Exception as e:
        log_api_call(
            "GET",
            f"payment/transactions/{transaction_id}/payment-method-configurations",
            {"integration_mode": integration_mode},
            error=e
        )
        raise


def search_transactions(filters=None, page=0, size=20):
    """Search transactions with filters - returns list of transactions"""
    from wallee import TransactionsService

    config = get_wallee_client()
    space_id = get_space_id()
    service = TransactionsService(config)

    try:
        # Use simple list endpoint with pagination
        response = service.get_payment_transactions(space_id)
        log_api_call("GET", "payment/transactions", {}, [t.to_dict() for t in response] if response else [])
        return response
    except Exception as e:
        log_api_call("GET", "payment/transactions", {}, error=e)
        raise


def debug_transaction_attributes(transaction_id):
    """
    Debug function to log all transaction attributes from Wallee API.
    """
    from wallee import TransactionsService

    config = get_wallee_client()
    space_id = get_space_id()
    service = TransactionsService(config)

    tx = service.get_payment_transactions_id(int(transaction_id), space_id)

    attrs = {}
    for attr in sorted(dir(tx)):
        if not attr.startswith('_'):
            val = getattr(tx, attr, None)
            if val is not None and not callable(val):
                # Convert to string representation
                val_str = repr(val)
                if len(val_str) > 500:
                    val_str = val_str[:500] + "..."
                attrs[attr] = val_str

    import json
    result = json.dumps(attrs, indent=2, default=str)
    frappe.log_error("Wallee TX Debug", result[:10000])
    return attrs


def get_transaction_completions(transaction_id):
    """
    Get completions for a transaction.

    Args:
        transaction_id: Wallee transaction ID

    Returns:
        list: List of completion objects
    """
    from wallee import TransactionCompletionService

    config = get_wallee_client()
    space_id = get_space_id()
    service = TransactionCompletionService(config)

    try:
        # Get completions for transaction
        response = service.get_payment_transaction_completion(space_id)
        # Filter by transaction_id
        completions = [c for c in response if c.line_item_version and
                       c.line_item_version.transaction and
                       c.line_item_version.transaction.id == int(transaction_id)]
        log_api_call(
            "GET",
            f"payment/transaction-completion",
            {"transaction_id": transaction_id},
            [c.to_dict() for c in completions]
        )
        return completions
    except Exception as e:
        log_api_call("GET", f"payment/transaction-completion", {"transaction_id": transaction_id}, error=e)
        raise
