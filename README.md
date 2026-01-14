# Wallee Integration

Wallee Payment Integration for ERPNext, Frappe, and Webshop.

## Features

- **Webshop Payments**: Online payment processing for Frappe Webshop
- **POS Terminal**: Payment terminal integration for Point of Sale
- **Transaction Management**: Track and manage all Wallee transactions
- **Refunds**: Process refunds directly from ERPNext
- **Payment Links**: Generate payment links for Sales Invoices
- **Setup Wizard**: Guided configuration with connection testing

## Installation

```bash
bench get-app https://github.com/bvisible/wallee_integration
bench --site your-site install-app wallee_integration
```

## Configuration

### Using the Setup Wizard (Recommended)

1. Go to **Wallee Settings** in the ERPNext desk
2. Click the **Setup Wizard** button
3. Follow the guided steps:
   - Enter your Wallee credentials (Space ID, User ID, Authentication Key)
   - Test the connection
   - Sync and configure your payment terminals

### Manual Configuration

1. Go to **Wallee Settings**
2. Enter your Wallee credentials:
   - User ID
   - Authentication Key
   - Space ID
3. Enable the features you need (Webshop, POS Terminal)
4. Configure your payment terminals if using POS

## Terminal Payment Dialog

The integration provides a reusable payment dialog component for terminal payments that can be called from anywhere in your Frappe/ERPNext application.

### Basic Usage

```javascript
wallee_integration.show_terminal_payment({
    amount: 100.00,
    currency: 'CHF',
    on_success: function(result) {
        console.log('Payment successful', result);
        // result contains: transaction_name, amount, currency, status
    },
    on_failure: function(error) {
        console.log('Payment failed', error);
    },
    on_cancel: function() {
        console.log('Payment cancelled');
    }
});
```

### Quick Payment

For simple use cases, use the shorthand function:

```javascript
// Simple payment with callback
wallee_integration.pay(100, 'CHF', function(result) {
    console.log('Paid!', result);
});
```

### Full Options

```javascript
wallee_integration.show_terminal_payment({
    // Amount and currency
    amount: 100.00,              // Initial amount (default: 0)
    currency: 'CHF',             // Currency code (default: 'CHF')
    max_amount: 500.00,          // Maximum allowed amount (optional)

    // Terminal selection
    pos_profile: 'Main POS',     // POS Profile to get default terminal (optional)

    // Reference document (optional)
    reference_doctype: 'Sales Invoice',
    reference_name: 'SINV-00001',

    // Callbacks
    on_success: function(result) {
        // Called when payment is successful
        // result = { transaction_name, amount, currency, status }
    },
    on_failure: function(error) {
        // Called when payment fails
        // error = { transaction_name, status, reason }
    },
    on_cancel: function() {
        // Called when user cancels the payment
    }
});
```

### Dialog Features

- **Terminal Selection**: Choose from available terminals
- **Numpad**: Easy amount entry with numpad interface
- **Real-time Status**: Live payment status updates
- **Cancel Support**: Cancel payment from dialog or terminal
- **WebSocket Integration**: Real-time terminal communication via Till SDK

### Example: Custom Payment Button

```javascript
// Add a payment button to a form
frappe.ui.form.on('Sales Invoice', {
    refresh: function(frm) {
        if (frm.doc.docstatus === 1 && frm.doc.outstanding_amount > 0) {
            frm.add_custom_button(__('Pay with Terminal'), function() {
                wallee_integration.show_terminal_payment({
                    amount: frm.doc.outstanding_amount,
                    currency: frm.doc.currency,
                    reference_doctype: frm.doctype,
                    reference_name: frm.docname,
                    on_success: function(result) {
                        frappe.show_alert({
                            message: __('Payment received!'),
                            indicator: 'green'
                        });
                        frm.reload_doc();
                    }
                });
            }, __('Payments'));
        }
    }
});
```

### Example: Standalone Payment Page

```javascript
// In a custom page or script
frappe.ready(function() {
    $('#pay-button').click(function() {
        const amount = parseFloat($('#amount').val());

        wallee_integration.pay(amount, 'CHF', function(result) {
            window.location.href = '/payment-success?tx=' + result.transaction_name;
        });
    });
});
```

## API Endpoints

### Terminal Operations

```python
# Get available terminals
frappe.call({
    method: 'wallee_integration.wallee_integration.api.pos.get_available_terminals',
    callback: function(r) {
        console.log(r.message);  // List of terminals
    }
});

# Initiate terminal payment
frappe.call({
    method: 'wallee_integration.wallee_integration.api.pos.initiate_terminal_payment',
    args: {
        amount: 100,
        currency: 'CHF',
        terminal: 'Terminal Name',
        pos_invoice: 'POS-INV-001'  // optional
    }
});

# Check payment status
frappe.call({
    method: 'wallee_integration.wallee_integration.api.pos.check_terminal_payment_status',
    args: {
        transaction_name: 'WALLEE-TXN-00001'
    }
});

# Cancel payment
frappe.call({
    method: 'wallee_integration.wallee_integration.api.pos.cancel_terminal_payment',
    args: {
        transaction_name: 'WALLEE-TXN-00001'
    }
});
```

### Sync Terminals

```python
# Sync terminals from Wallee
frappe.call({
    method: 'wallee_integration.wallee_integration.api.terminal.sync_terminals_from_wallee'
});
```

## DocTypes

- **Wallee Settings**: Main configuration (credentials, features)
- **Wallee Payment Terminal**: Terminal configuration and status
- **Wallee Transaction**: Transaction records with full lifecycle tracking

## License

MIT
