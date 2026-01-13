# Wallee Integration - Claude Code Instructions

## Project Overview

Wallee Payment Integration for ERPNext/Frappe/Webshop. This app provides payment processing capabilities for:
- **Webshop**: Online payments with redirect flow
- **POS Terminal**: Physical payment terminal integration for Point of Sale
- **Payment Links**: Generate payment links for invoices

## Technology Stack

- **Framework**: Frappe Framework v15
- **ERP**: ERPNext v15
- **Payment SDK**: wallee-python-sdk v6.2.0
- **Language**: Python 3.11+, JavaScript

## Project Structure

```
wallee_integration/
├── setup.py                    # Package setup
├── pyproject.toml              # Project configuration
├── requirements.txt            # Dependencies (wallee>=6.2.0)
├── wallee_integration/
│   ├── __init__.py             # Version: 0.0.1
│   ├── api.py                  # Main API endpoints (webhook, webshop payment)
│   ├── hooks.py                # Frappe app hooks
│   ├── install.py              # Post-install setup
│   ├── tasks.py                # Scheduled tasks (sync, cleanup)
│   ├── modules.txt             # Module: "Wallee Integration"
│   ├── patches.txt             # Database patches
│   ├── config/
│   │   └── desktop.py          # Desk module config
│   ├── public/
│   │   └── js/
│   │       ├── wallee_terminal.js    # Terminal JS class
│   │       └── pos_wallee_payment.js # POS integration
│   ├── templates/
│   ├── www/
│   │   ├── wallee_success.html/.py   # Success page
│   │   └── wallee_failed.html/.py    # Failed page
│   └── wallee_integration/           # Module directory
│       ├── api/
│       │   ├── client.py         # Wallee API client singleton
│       │   ├── transaction.py    # Create, capture, void transactions
│       │   ├── terminal.py       # Terminal operations
│       │   ├── refund.py         # Refund processing
│       │   ├── payment_link.py   # Payment link generation
│       │   └── pos.py            # POS-specific endpoints
│       └── doctype/
│           ├── wallee_settings/           # Single DocType - API config
│           ├── wallee_payment_terminal/   # Terminal management
│           └── wallee_transaction/        # Transaction records
```

## DocTypes

### Wallee Settings (Single)
Configuration for Wallee API connection:
- `user_id`: Wallee Application User ID
- `authentication_key`: API authentication key (Password field)
- `space_id`: Wallee Space ID
- `api_host`: API endpoint (default: https://app-wallee.com/api/v2.0)
- `enable_webshop`: Enable online payments
- `enable_pos_terminal`: Enable terminal payments
- `default_terminal`: Link to default terminal
- `webhook_secret`: For webhook signature verification
- `test_mode`: Sandbox mode flag

### Wallee Payment Terminal
Physical payment terminal configuration:
- `terminal_name`: Unique identifier
- `terminal_id`: Wallee Terminal ID
- `status`: Active/Inactive/Processing/Deleted
- `is_default`: Default terminal flag
- `pos_profile`: Link to POS Profile
- `warehouse`: Associated warehouse

### Wallee Transaction
Transaction records with full lifecycle:
- `transaction_id`: Wallee Transaction ID
- `status`: Pending/Processing/Authorized/Completed/Failed/Voided/Refunded
- `transaction_type`: Online/Terminal/Payment Link
- `amount`, `currency`: Payment amount
- `reference_doctype`, `reference_name`: Link to source document
- `pos_invoice`, `sales_invoice`, `sales_order`: Document links
- `terminal`: Link to terminal (for terminal transactions)
- `authorized_amount`, `captured_amount`, `refunded_amount`: Amount tracking
- `failure_reason`: Error details
- `wallee_data`: Raw JSON from Wallee API

## Key API Endpoints

### Whitelisted Methods

```python
# Webhook handler (allow_guest=True)
wallee_integration.api.webhook

# Webshop payment creation
wallee_integration.api.create_webshop_payment(cart_items, currency, success_url, failed_url, customer)

# Transaction status
wallee_integration.api.get_transaction_status(transaction_name)
wallee_integration.api.sync_transaction(transaction_name)

# POS Terminal
wallee_integration.wallee_integration.api.pos.initiate_terminal_payment(amount, currency, terminal, pos_invoice, customer)
wallee_integration.wallee_integration.api.pos.check_terminal_payment_status(transaction_name)
wallee_integration.wallee_integration.api.pos.cancel_terminal_payment(transaction_name)
wallee_integration.wallee_integration.api.pos.get_available_terminals()
wallee_integration.wallee_integration.api.pos.link_payment_to_invoice(transaction_name, pos_invoice)

# Terminal sync
wallee_integration.wallee_integration.api.terminal.sync_terminals_from_wallee()

# Payment links
wallee_integration.wallee_integration.api.payment_link.create_payment_link_for_invoice(sales_invoice)
```

## Wallee SDK Usage

The SDK is located at `/Users/jeremy/GitHub/wallee-python-sdk`. Key services used:

```python
from wallee.configuration import Configuration
from wallee.service.transactions_service import TransactionsService
from wallee.service.payment_terminals_service import PaymentTerminalsService
from wallee.service.refunds_service import RefundsService
from wallee.service.payment_links_service import PaymentLinksService
```

### Configuration Pattern
```python
from wallee_integration.wallee_integration.api.client import get_wallee_client, get_space_id

config = get_wallee_client()  # Returns Configuration singleton
space_id = get_space_id()     # Returns configured Space ID
```

## Scheduled Tasks

Defined in `hooks.py`:
- **Every 5 minutes**: `sync_pending_transactions` - Update pending transaction statuses
- **Daily**: `cleanup_old_transactions` - Archive transactions older than 90 days

## JavaScript Integration

### Terminal Class
```javascript
const terminal = new wallee_integration.WalleeTerminal({
    terminal: "Terminal Name",
    on_success: (result) => { /* handle success */ },
    on_failure: (error) => { /* handle failure */ },
    on_status_change: (status, data) => { /* handle status */ }
});

await terminal.initiate_payment(amount, currency, pos_invoice, customer);
```

### Payment Dialog
```javascript
wallee_integration.show_terminal_payment_dialog({
    amount: 100,
    currency: "CHF",
    pos_invoice: "POS-INV-001",
    customer: "CUST-001",
    terminal: "Terminal Name",
    on_success: (result) => {},
    on_failure: (error) => {}
});
```

## URL Routes

Defined in `hooks.py`:
- `/api/method/wallee_integration.api.webhook` - Webhook endpoint
- `/wallee/payment/<transaction_id>` - Payment page (not implemented yet)
- `/wallee/success` - Success redirect page
- `/wallee/failed` - Failed redirect page

## Development Commands

```bash
# Install app
bench get-app https://github.com/bvisible/wallee_integration
bench --site [site-name] install-app wallee_integration

# Migrate after changes
bench --site [site-name] migrate

# Build assets
bench build --app wallee_integration

# Clear cache
bench --site [site-name] clear-cache
```

## Testing Wallee Connection

```python
# In bench console
from wallee_integration.wallee_integration.api.client import get_wallee_client
from wallee.service.transactions_service import TransactionsService

config = get_wallee_client()
service = TransactionsService(config)
# Make test API call
```

## Terminal Payment Testing

### Debug/QAT Terminal Test Amounts
When using a **debug terminal** (QAT - Quality Assurance Test), the transaction result is controlled by the amount:

| Amount (CHF) | Result |
|--------------|--------|
| 1.00 | Declined |
| 2.00 | Declined |
| 1.01 | Card Error |
| 1.02 | Card Expired |
| 1.03 | Card Unknown |
| 1.09 | System Error |
| 1.28 | PIN Required |
| 11.30 | PIN Required, Restart |
| 6.66 | Declined, Autoreversal OK |
| 9.97 | Declined |
| 9.98-9.99 | Declined, Autoreversal OK |
| **3.00-9.00** | **Approved** |
| 20.15 | Confirm Amount, Approved |
| 20.16 | PIN Required, Cardholder ID |
| 20.17+ | Declined |

**Use amounts between 3.00 and 9.00 CHF for successful test transactions.**

### Terminal Transaction Flow
1. Create transaction with `auto_confirm=False` (required for terminal)
2. Call `initiate_terminal_transaction(terminal_id, transaction_id)`
3. Terminal displays payment screen
4. Customer presents card
5. Transaction state changes to AUTHORIZED → COMPLETED

### Line Items for Terminal Transactions
**IMPORTANT**: When creating line items, use `amount_including_tax`, not `amount`:

```python
# CORRECT
line_items = [{
    "name": "Product Name",
    "quantity": 1,
    "amount_including_tax": 5.00,  # ✓ Correct field name
    "unique_id": "unique-id-123"
}]

# WRONG - will result in 0.00 amount!
line_items = [{
    "name": "Product Name",
    "quantity": 1,
    "amount": 5.00,  # ✗ Wrong field name - defaults to 0
    "unique_id": "unique-id-123"
}]
```

### Testing Terminal Payment via API
```python
from wallee_integration.wallee_integration.api.transaction import create_transaction
from wallee_integration.wallee_integration.api.terminal import initiate_terminal_transaction

# Create transaction (use amount 5.00 for approved result on debug terminal)
line_items = [{
    "name": "Test Payment",
    "quantity": 1,
    "amount_including_tax": 5.00,
    "unique_id": "test-123"
}]

tx = create_transaction(
    line_items=line_items,
    currency="CHF",
    merchant_reference="TEST-001",
    auto_confirm=False  # Required for terminal!
)

# Send to terminal (use Terminal ID, not identifier)
result = initiate_terminal_transaction(304079, tx["transaction_id"])
# Terminal now displays payment screen
```

## Important Notes

1. **Credentials Security**: Authentication key is stored as Password field (encrypted)
2. **Transaction States**: Map Wallee states to local states in `update_transaction_from_wallee()`
3. **Webhook Verification**: Uses HMAC-SHA256 signature verification
4. **Error Logging**: Enable `log_api_calls` in settings for debugging
5. **Dependencies**: wallee SDK has version conflicts with Frappe - minor version mismatches are acceptable
6. **Terminal Transactions**: Must use `auto_confirm=False` when creating transactions for terminal processing
7. **Terminal ID vs Identifier**: Use `terminal_id` (e.g., 304079) not `identifier` (e.g., 32580758) for API calls
8. **Line Items**: Use `amount_including_tax` (or `amount` as alias) - the field name matters!

## Coding Conventions

### frappe.log_error Usage
**IMPORTANT**: Always use `title` as the FIRST argument when calling `frappe.log_error()`:
```python
# CORRECT - title first, then message
frappe.log_error(
    title="Short Error Title",  # Limited to 140 characters!
    message=f"Detailed error message: {error}"
)

# WRONG - don't put message first
frappe.log_error(
    message=f"...",
    title="..."
)
```
The `title` field in Error Log DocType is limited to **140 characters**. Keep titles short and descriptive.

## Dangerous Functions - ASK USER BEFORE RUNNING

### reset_wallee_data()
**Location:** `wallee_integration/wallee_integration/api/terminal.py`

**ALWAYS ASK USER CONFIRMATION BEFORE RUNNING THIS FUNCTION!**

Complete reset of ALL Wallee-related data. Deletes:
- All terminals from Wallee API (sets to DECOMMISSIONED state)
- ERPNext DocTypes: Wallee Payment Terminal, Terminal Configuration, Location
- Wallee Transaction and Transaction Item records
- Wallee Webhook Log records
- Payment Gateway, Payment Gateway Account (Wallee-related)
- Payment Requests linked to Wallee
- Resets ALL Wallee Settings fields (user_id, space_id, authentication_key, etc.)

```python
# Usage - ONLY after user confirmation
bench --site [site] execute wallee_integration.wallee_integration.api.terminal.reset_wallee_data

# Parameters:
# - include_transactions: Also delete Wallee Transaction records (default: True)
# - include_payment_gateway: Also delete Payment Gateway related (default: True)
```

**Note:** Wallee API terminals go to DECOMMISSIONED state (not truly deleted). They will be purged automatically by Wallee after the `planned_purge_date`. If using a NEW Wallee account with different credentials, update Wallee Settings first and the new space will be empty.

## Related Projects

- **wallee-python-sdk**: `/Users/jeremy/GitHub/wallee-python-sdk`
- **neopay_integration**: Similar integration for Stripe (reference implementation)
- **twint_integration**: TWINT payment integration

## Repository

- **GitHub**: https://github.com/bvisible/wallee_integration
- **Local**: /Users/jeremy/GitHub/wallee_integration
- **Symlink**: /Users/jeremy/GitHub/frappe-bench/apps/wallee_integration
