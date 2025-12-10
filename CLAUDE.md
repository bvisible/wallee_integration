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

## Important Notes

1. **Credentials Security**: Authentication key is stored as Password field (encrypted)
2. **Transaction States**: Map Wallee states to local states in `update_transaction_from_wallee()`
3. **Webhook Verification**: Uses HMAC-SHA256 signature verification
4. **Error Logging**: Enable `log_api_calls` in settings for debugging
5. **Dependencies**: wallee SDK has version conflicts with Frappe - minor version mismatches are acceptable

## Related Projects

- **wallee-python-sdk**: `/Users/jeremy/GitHub/wallee-python-sdk`
- **neopay_integration**: Similar integration for Stripe (reference implementation)
- **twint_integration**: TWINT payment integration

## Repository

- **GitHub**: https://github.com/bvisible/wallee_integration
- **Local**: /Users/jeremy/GitHub/wallee_integration
- **Symlink**: /Users/jeremy/GitHub/frappe-bench/apps/wallee_integration
