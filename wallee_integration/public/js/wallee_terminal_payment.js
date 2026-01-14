/**
 * Wallee Terminal Payment Dialog
 *
 * A reusable payment dialog component for Wallee terminal payments.
 * Can be used from any DocType or module (POS Next, Sales Invoice, etc.)
 *
 * Usage:
 *   wallee_integration.show_terminal_payment({
 *       amount: 100.00,
 *       currency: 'CHF',
 *       pos_profile: 'Main POS',  // Optional - auto-selects default terminal
 *       max_amount: 500.00,       // Optional - limit amount
 *       on_success: (result) => { console.log('Payment successful', result); },
 *       on_failure: (error) => { console.log('Payment failed', error); },
 *       on_cancel: () => { console.log('Payment cancelled'); }
 *   });
 */

window.wallee_integration = window.wallee_integration || {};

/**
 * Show the Wallee terminal payment dialog
 * @param {Object} options - Configuration options
 * @param {number} options.amount - Initial amount (default: 0)
 * @param {string} options.currency - Currency code (default: 'CHF')
 * @param {string} options.pos_profile - POS Profile to get default terminal
 * @param {number} options.max_amount - Maximum allowed amount
 * @param {string} options.reference_doctype - Reference document type
 * @param {string} options.reference_name - Reference document name
 * @param {Function} options.on_success - Callback on successful payment
 * @param {Function} options.on_failure - Callback on failed payment
 * @param {Function} options.on_cancel - Callback on cancelled payment
 */
wallee_integration.show_terminal_payment = async function(options = {}) {
    const config = {
        amount: options.amount || 0,
        currency: options.currency || 'CHF',
        pos_profile: options.pos_profile || null,
        max_amount: options.max_amount || null,
        reference_doctype: options.reference_doctype || null,
        reference_name: options.reference_name || null,
        on_success: options.on_success || function() {},
        on_failure: options.on_failure || function() {},
        on_cancel: options.on_cancel || function() {}
    };

    // Load terminals
    const terminals = await wallee_integration.get_available_terminals();

    if (!terminals || terminals.length === 0) {
        frappe.msgprint({
            title: __('No Terminal Available'),
            indicator: 'red',
            message: __('No active Wallee terminal found. Please configure a terminal in Wallee Settings.')
        });
        return;
    }

    // Get default terminal from POS Profile or last used
    let default_terminal = await wallee_integration.get_default_terminal(config.pos_profile);

    // Create the dialog
    const d = new frappe.ui.Dialog({
        title: __('Terminal Payment'),
        size: 'large',
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'terminal_container',
                options: `
                    <div class="wallee-terminal-container">
                        <div class="wallee-terminal-header">
                            <div class="wallee-terminal-title">
                                <i class="fa fa-credit-card"></i> ${__('Terminal')}
                            </div>
                            <div class="wallee-terminal-select"></div>
                            <button class="btn btn-xs btn-default wallee-toggle-info">
                                <i class="fa fa-chevron-down"></i>
                            </button>
                        </div>
                        <div class="wallee-terminal-info" style="display: none;">
                            <div class="wallee-terminal-info-grid">
                                <div class="wallee-terminal-info-item">
                                    <span class="label">${__('Status')}:</span>
                                    <span class="wallee-terminal-status">
                                        <span class="indicator-pill gray">${__('Unknown')}</span>
                                    </span>
                                </div>
                                <div class="wallee-terminal-info-item">
                                    <span class="label">${__('Terminal ID')}:</span>
                                    <span class="wallee-terminal-id-value">--</span>
                                </div>
                            </div>
                        </div>
                    </div>
                `
            },
            {
                fieldtype: 'Select',
                fieldname: 'terminal',
                label: __('Terminal'),
                reqd: 1,
                options: terminals.map(t => ({
                    value: t.name,
                    label: t.terminal_name || t.name
                }))
            },
            {
                fieldtype: 'HTML',
                fieldname: 'amount_display',
                options: `
                    <div class="wallee-amount-container">
                        <span class="wallee-amount-currency">${config.currency}</span>
                        <input type="text" class="wallee-amount-input"
                               value="${parseFloat(config.amount).toFixed(2)}"
                               inputmode="decimal" readonly />
                    </div>
                `
            },
            {
                fieldtype: 'HTML',
                fieldname: 'numpad',
                options: `
                    <div class="wallee-numpad">
                        <div class="wallee-numpad-row">
                            <button class="wallee-numpad-btn" data-value="7">7</button>
                            <button class="wallee-numpad-btn" data-value="8">8</button>
                            <button class="wallee-numpad-btn" data-value="9">9</button>
                        </div>
                        <div class="wallee-numpad-row">
                            <button class="wallee-numpad-btn" data-value="4">4</button>
                            <button class="wallee-numpad-btn" data-value="5">5</button>
                            <button class="wallee-numpad-btn" data-value="6">6</button>
                        </div>
                        <div class="wallee-numpad-row">
                            <button class="wallee-numpad-btn" data-value="1">1</button>
                            <button class="wallee-numpad-btn" data-value="2">2</button>
                            <button class="wallee-numpad-btn" data-value="3">3</button>
                        </div>
                        <div class="wallee-numpad-row">
                            <button class="wallee-numpad-btn" data-value="0">0</button>
                            <button class="wallee-numpad-btn" data-value="00">00</button>
                            <button class="wallee-numpad-btn wallee-numpad-backspace" data-value="backspace">
                                <i class="fa fa-arrow-left"></i>
                            </button>
                        </div>
                        <div class="wallee-numpad-row">
                            <button class="wallee-numpad-btn wallee-numpad-clear" data-value="clear">C</button>
                            <button class="wallee-numpad-btn wallee-numpad-max" data-value="max">${__('Max')}</button>
                            <button class="wallee-numpad-btn" data-value=".">.</button>
                        </div>
                    </div>
                `
            },
            {
                fieldtype: 'HTML',
                fieldname: 'status_display',
                options: `<div class="wallee-payment-status" style="display: none;"></div>`
            }
        ],
        primary_action_label: __('Send to Terminal'),
        primary_action: async function() {
            const values = d.get_values();
            if (!values) return;

            const terminal = values.terminal;
            const amount = parseFloat(d.$wrapper.find('.wallee-amount-input').val()) || 0;

            if (amount <= 0) {
                frappe.show_alert({
                    message: __('Please enter a valid amount'),
                    indicator: 'red'
                });
                return;
            }

            // Process payment
            await wallee_integration.process_terminal_payment(d, terminal, amount, config);
        },
        secondary_action_label: __('Cancel'),
        secondary_action: function() {
            config.on_cancel();
            d.hide();
        }
    });

    // Add custom class for styling
    d.$wrapper.find('.modal-dialog').addClass('wallee-terminal-payment-dialog');
    d.$wrapper.find('.modal-content').addClass('wallee-payment-dialog');

    // Move terminal field into custom container
    const terminalField = d.get_field('terminal');
    const terminalSelect = d.$wrapper.find('.wallee-terminal-select');

    const wrapper = $(`
        <div class="wallee-terminal-select-wrapper">
            <div class="wallee-terminal-status-dot gray"></div>
            <div class="wallee-terminal-field"></div>
        </div>
    `);

    wrapper.find('.wallee-terminal-field').append(terminalField.$wrapper);
    terminalSelect.empty().append(wrapper);

    // Hide the original label
    terminalField.$wrapper.find('.control-label').hide();
    terminalField.$wrapper.find('.frappe-control').css('margin-bottom', '0');

    // Set default terminal
    if (default_terminal) {
        terminalField.set_value(default_terminal);
    } else if (terminals.length > 0) {
        terminalField.set_value(terminals[0].name);
    }

    // Terminal change handler
    terminalField.$input.on('change', function() {
        const terminalName = $(this).val();
        wallee_integration.update_terminal_info(d, terminalName);
        // Save last used terminal
        localStorage.setItem('wallee_last_terminal', terminalName);
    });

    // Toggle info panel
    d.$wrapper.find('.wallee-toggle-info').on('click', function() {
        const infoPanel = d.$wrapper.find('.wallee-terminal-info');
        infoPanel.slideToggle(200);
        $(this).find('i').toggleClass('fa-chevron-down fa-chevron-up');

        if (infoPanel.is(':visible')) {
            wallee_integration.update_terminal_info(d, terminalField.get_value());
        }
    });

    // Numpad handling
    d.$wrapper.on('click', '.wallee-numpad-btn', function(e) {
        e.preventDefault();
        e.stopPropagation();

        const $input = d.$wrapper.find('.wallee-amount-input');
        const value = $(this).data('value');
        let currentValue = parseFloat($input.val().replace(/[^\d.]/g, '')) || 0;

        if (value === 'backspace') {
            // Remove last digit (cash register style)
            currentValue = Math.floor(currentValue * 10) / 100;
        } else if (value === 'clear') {
            currentValue = 0;
        } else if (value === 'max' && config.max_amount) {
            currentValue = config.max_amount;
        } else if (value === '.') {
            // Already handled by cash register style
        } else if (value === '00') {
            currentValue = currentValue * 100;
        } else {
            // Cash register style: shift digits left
            currentValue = (currentValue * 1000 + parseInt(value)) / 100;
        }

        // Limit to max amount if specified
        if (config.max_amount && currentValue > config.max_amount) {
            currentValue = config.max_amount;
        }

        $input.val(currentValue.toFixed(2));
    });

    // Initial terminal info update
    setTimeout(() => {
        wallee_integration.update_terminal_info(d, terminalField.get_value());
    }, 100);

    // Inject styles
    wallee_integration.inject_payment_styles();

    // Show dialog
    d.show();

    return d;
};

/**
 * Get available terminals
 */
wallee_integration.get_available_terminals = async function() {
    try {
        const result = await frappe.call({
            method: 'wallee_integration.wallee_integration.api.pos.get_available_terminals'
        });
        return result.message || [];
    } catch (error) {
        console.error('Error loading terminals:', error);
        return [];
    }
};

/**
 * Get default terminal from POS Profile or last used
 */
wallee_integration.get_default_terminal = async function(pos_profile) {
    // First, try to get from POS Profile
    if (pos_profile) {
        try {
            const result = await frappe.db.get_value('POS Profile', pos_profile, 'wallee_default_terminal');
            if (result.message && result.message.wallee_default_terminal) {
                return result.message.wallee_default_terminal;
            }
        } catch (e) {
            // Field might not exist yet
        }
    }

    // Try Wallee Settings default
    try {
        const settings = await frappe.db.get_single_value('Wallee Settings', 'default_terminal');
        if (settings) {
            return settings;
        }
    } catch (e) {
        // Ignore
    }

    // Fall back to last used terminal from localStorage
    return localStorage.getItem('wallee_last_terminal') || null;
};

/**
 * Update terminal info in dialog
 */
wallee_integration.update_terminal_info = async function(dialog, terminalName) {
    if (!terminalName) return;

    try {
        const terminalDoc = await frappe.db.get_doc('Wallee Payment Terminal', terminalName);

        if (terminalDoc) {
            const isActive = terminalDoc.status === 'Active';

            // Update status indicator
            dialog.$wrapper.find('.wallee-terminal-status-dot')
                .removeClass('green red gray')
                .addClass(isActive ? 'green' : 'red');

            dialog.$wrapper.find('.wallee-terminal-status .indicator-pill')
                .removeClass('green red gray')
                .addClass(isActive ? 'green' : 'red')
                .text(isActive ? __('Active') : __('Inactive'));

            // Update terminal ID
            dialog.$wrapper.find('.wallee-terminal-id-value')
                .text(terminalDoc.terminal_id || '--');
        }
    } catch (error) {
        console.error('Error updating terminal info:', error);
    }
};

/**
 * Extract clean error message from API error
 */
wallee_integration.extract_error_message = function(error) {
    if (!error) return __('Unknown error');

    let msg = error.message || String(error);

    // Try to extract the message from Wallee API error format
    // Example: "message='Terminal transaction canceled.'"
    const messageMatch = msg.match(/message='([^']+)'/);
    if (messageMatch) {
        return messageMatch[1];
    }

    // Try to extract from "The terminal is not available" type errors
    if (msg.includes('terminal')) {
        const terminalMatch = msg.match(/(The terminal[^.]+\.)/i) ||
                              msg.match(/(Terminal[^.]+\.)/i);
        if (terminalMatch) {
            return terminalMatch[1];
        }
    }

    // If message is too long (API dump), truncate it
    if (msg.length > 200) {
        // Try to find a meaningful part
        if (msg.includes('Reason:')) {
            const reasonMatch = msg.match(/Reason:\s*([^H]+)/);
            if (reasonMatch) {
                return reasonMatch[1].trim();
            }
        }
        return __('Payment failed. Please try again.');
    }

    return msg;
};

/**
 * Process terminal payment
 */
wallee_integration.process_terminal_payment = async function(dialog, terminal, amount, config) {
    const statusDiv = dialog.$wrapper.find('.wallee-payment-status');

    // Store current transaction for cancellation
    dialog.wallee_current_transaction = null;
    dialog.wallee_polling_active = true;

    // Show status
    statusDiv.show().html(`
        <div class="alert alert-info">
            <i class="fa fa-spinner fa-spin"></i>
            ${__('Initiating payment on terminal...')}
        </div>
    `);

    // Disable primary button and change Cancel to "Cancel Payment"
    dialog.disable_primary_action();

    try {
        // Call API to initiate payment
        const result = await frappe.call({
            method: 'wallee_integration.wallee_integration.api.pos.initiate_terminal_payment',
            args: {
                amount: amount,
                currency: config.currency,
                terminal: terminal,
                pos_invoice: config.reference_name || null,
                customer: null
            }
        });

        if (result.exc) {
            throw new Error(result.exc);
        }

        if (result.message && result.message.transaction_name) {
            const transactionName = result.message.transaction_name;
            dialog.wallee_current_transaction = transactionName;

            statusDiv.html(`
                <div class="alert alert-warning">
                    <i class="fa fa-spinner fa-spin"></i>
                    ${__('Waiting for payment on terminal...')}<br>
                    <small>${__('Transaction')}: ${transactionName}</small>
                    <div class="wallee-cancel-container" style="margin-top: 10px;">
                        <button class="btn btn-sm btn-danger wallee-cancel-payment">
                            <i class="fa fa-times"></i> ${__('Cancel Payment')}
                        </button>
                    </div>
                </div>
            `);

            // Add cancel button handler
            statusDiv.find('.wallee-cancel-payment').on('click', async function() {
                $(this).prop('disabled', true).html(`<i class="fa fa-spinner fa-spin"></i> ${__('Cancelling...')}`);
                dialog.wallee_polling_active = false;

                try {
                    await frappe.call({
                        method: 'wallee_integration.wallee_integration.api.pos.cancel_terminal_payment',
                        args: { transaction_name: transactionName }
                    });

                    statusDiv.html(`
                        <div class="alert alert-warning">
                            <i class="fa fa-ban"></i>
                            ${__('Payment cancelled')}
                        </div>
                    `);
                    dialog.enable_primary_action();
                    config.on_cancel();
                } catch (cancelError) {
                    statusDiv.html(`
                        <div class="alert alert-danger">
                            <i class="fa fa-exclamation-triangle"></i>
                            ${__('Could not cancel payment. Please check the terminal.')}
                        </div>
                    `);
                    dialog.enable_primary_action();
                }
            });

            // Start polling for status
            await wallee_integration.poll_payment_status(dialog, transactionName, config);
        } else if (result.message && result.message.error) {
            throw new Error(result.message.error);
        }
    } catch (error) {
        console.error('Payment error:', error);
        const cleanError = wallee_integration.extract_error_message(error);

        statusDiv.html(`
            <div class="alert alert-danger">
                <i class="fa fa-times"></i>
                <strong>${__('Error')}</strong><br>
                ${cleanError}
            </div>
        `);
        dialog.enable_primary_action();
        config.on_failure({ error: cleanError });
    }
};

/**
 * Poll for payment status
 */
wallee_integration.poll_payment_status = async function(dialog, transactionName, config, attempts = 0) {
    const maxAttempts = 90;  // 3 minutes with 2-second intervals
    const pollInterval = 2000;
    const statusDiv = dialog.$wrapper.find('.wallee-payment-status');

    // Check if polling was cancelled
    if (!dialog.wallee_polling_active) {
        return;
    }

    if (attempts >= maxAttempts) {
        statusDiv.html(`
            <div class="alert alert-warning">
                <i class="fa fa-clock-o"></i>
                <strong>${__('Timeout')}</strong><br>
                ${__('Payment is still processing. Please check the terminal.')}
            </div>
        `);
        dialog.enable_primary_action();
        dialog.set_primary_action(__('Close'), () => dialog.hide());
        return;
    }

    try {
        const result = await frappe.call({
            method: 'wallee_integration.wallee_integration.api.pos.check_terminal_payment_status',
            args: { transaction_name: transactionName }
        });

        if (result.message) {
            const status = result.message.status;
            const wallee_state = result.message.wallee_state;

            if (status === 'Completed' || status === 'Authorized' || status === 'Fulfill') {
                // Success!
                statusDiv.html(`
                    <div class="alert alert-success">
                        <i class="fa fa-check-circle"></i>
                        <strong>${__('Payment Successful!')}</strong><br>
                        ${__('Amount')}: ${config.currency} ${result.message.amount}<br>
                        ${__('Transaction')}: ${transactionName}
                    </div>
                `);
                dialog.set_primary_action(__('Close'), () => dialog.hide());

                // Call success callback
                config.on_success({
                    transaction_name: transactionName,
                    transaction_id: result.message.transaction_id,
                    amount: result.message.amount,
                    currency: config.currency,
                    status: status
                });
            } else if (status === 'Failed' || status === 'Decline' || status === 'Voided') {
                // Failed
                statusDiv.html(`
                    <div class="alert alert-danger">
                        <i class="fa fa-times-circle"></i>
                        <strong>${__('Payment Failed')}</strong><br>
                        ${result.message.failure_reason || __('The payment was declined or cancelled.')}
                    </div>
                `);
                dialog.enable_primary_action();
                config.on_failure({
                    transaction_name: transactionName,
                    status: status,
                    reason: result.message.failure_reason
                });
            } else {
                // Still processing
                statusDiv.html(`
                    <div class="alert alert-info">
                        <i class="fa fa-spinner fa-spin"></i>
                        ${__('Waiting for payment on terminal...')}<br>
                        <small>${__('Status')}: ${status || wallee_state || 'Processing'}</small>
                    </div>
                `);

                setTimeout(() => {
                    wallee_integration.poll_payment_status(dialog, transactionName, config, attempts + 1);
                }, pollInterval);
            }
        }
    } catch (error) {
        console.error('Status check error:', error);
        // Continue polling on error
        setTimeout(() => {
            wallee_integration.poll_payment_status(dialog, transactionName, config, attempts + 1);
        }, pollInterval);
    }
};

/**
 * Inject CSS styles for the payment dialog
 */
wallee_integration.inject_payment_styles = function() {
    if ($('#wallee-payment-styles').length) return;

    $('<style id="wallee-payment-styles">').text(`
        .wallee-terminal-payment-dialog {
            max-width: 420px;
        }

        .wallee-terminal-payment-dialog .modal-body {
            padding: 15px;
        }

        .wallee-terminal-container {
            border: 1px solid var(--gray-300);
            border-radius: 8px;
            margin-bottom: 15px;
            overflow: hidden;
        }

        .wallee-terminal-header {
            display: flex;
            align-items: center;
            padding: 12px 15px;
            background-color: var(--gray-100);
            border-bottom: 1px solid var(--gray-300);
        }

        .wallee-terminal-title {
            font-weight: 600;
            flex: 0 0 auto;
            margin-right: 12px;
            color: var(--gray-700);
        }

        .wallee-terminal-title i {
            margin-right: 6px;
            color: var(--primary);
        }

        .wallee-terminal-select {
            flex: 1 1 auto;
        }

        .wallee-terminal-select-wrapper {
            display: flex;
            align-items: center;
        }

        .wallee-terminal-status-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            margin-right: 10px;
            flex-shrink: 0;
        }

        .wallee-terminal-status-dot.green {
            background-color: var(--green-500);
            box-shadow: 0 0 6px var(--green-300);
        }

        .wallee-terminal-status-dot.red {
            background-color: var(--red-500);
        }

        .wallee-terminal-status-dot.gray {
            background-color: var(--gray-400);
        }

        .wallee-terminal-field {
            flex: 1 1 auto;
        }

        .wallee-terminal-field .frappe-control {
            margin-bottom: 0 !important;
        }

        .wallee-terminal-info {
            padding: 12px 15px;
            background-color: var(--gray-50);
        }

        .wallee-terminal-info-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
        }

        .wallee-terminal-info-item {
            font-size: 12px;
        }

        .wallee-terminal-info-item .label {
            color: var(--gray-600);
        }

        .wallee-amount-container {
            display: flex;
            align-items: center;
            border: 2px solid var(--primary);
            border-radius: 8px;
            padding: 0 15px;
            margin-bottom: 15px;
            background-color: white;
        }

        .wallee-amount-currency {
            font-weight: 700;
            font-size: 18px;
            margin-right: 10px;
            color: var(--primary);
        }

        .wallee-amount-input {
            flex: 1 1 auto;
            border: none;
            background: transparent;
            font-size: 32px;
            padding: 15px 0;
            text-align: right;
            font-weight: 700;
            color: var(--gray-900);
            font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Fira Code', monospace;
        }

        .wallee-amount-input:focus {
            outline: none;
        }

        .wallee-numpad {
            display: flex;
            flex-direction: column;
            gap: 8px;
            margin-bottom: 15px;
        }

        .wallee-numpad-row {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 8px;
        }

        .wallee-numpad-btn {
            background-color: #d1d5db;
            border: 1px solid #9ca3af;
            border-radius: 8px;
            padding: 18px 0;
            font-size: 20px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.15s ease;
            color: #1f2937;
        }

        .wallee-numpad-btn:hover {
            background-color: #9ca3af;
            transform: translateY(-1px);
        }

        .wallee-numpad-btn:active {
            background-color: #6b7280;
            color: white;
            transform: translateY(0);
        }

        .wallee-numpad-backspace {
            background-color: #f87171;
            color: white;
            border-color: #ef4444;
        }

        .wallee-numpad-backspace:hover {
            background-color: #ef4444;
        }

        .wallee-numpad-clear {
            background-color: #fb923c;
            color: white;
            border-color: #f97316;
        }

        .wallee-numpad-clear:hover {
            background-color: #f97316;
        }

        .wallee-numpad-max {
            background-color: #60a5fa;
            color: white;
            border-color: #3b82f6;
            font-size: 14px;
        }

        .wallee-numpad-max:hover {
            background-color: #3b82f6;
        }

        .wallee-payment-status {
            margin-top: 10px;
        }

        .wallee-payment-status .alert {
            margin-bottom: 0;
            border-radius: 8px;
        }

        .wallee-payment-status .fa-spinner {
            margin-right: 8px;
        }

        .wallee-payment-status .fa-check-circle,
        .wallee-payment-status .fa-times-circle,
        .wallee-payment-status .fa-clock-o {
            margin-right: 8px;
            font-size: 18px;
        }

        /* Hide max button if no max_amount */
        .wallee-numpad-max[data-hide="true"] {
            visibility: hidden;
        }

        /* Dark mode support */
        [data-theme="dark"] .wallee-amount-container {
            background-color: #1f2937;
        }

        [data-theme="dark"] .wallee-numpad-btn {
            background-color: #374151;
            border-color: #4b5563;
            color: #e5e7eb;
        }

        [data-theme="dark"] .wallee-numpad-btn:hover {
            background-color: #4b5563;
        }

        [data-theme="dark"] .wallee-numpad-backspace {
            background-color: #7f1d1d;
            color: #fca5a5;
            border-color: #991b1b;
        }

        [data-theme="dark"] .wallee-numpad-clear {
            background-color: #78350f;
            color: #fcd34d;
            border-color: #92400e;
        }

        [data-theme="dark"] .wallee-numpad-max {
            background-color: #1e3a8a;
            color: #93c5fd;
            border-color: #1e40af;
        }
    `).appendTo('head');
};

/**
 * Quick function to show payment dialog from anywhere
 * Example: wallee_integration.pay(100, 'CHF', result => console.log(result));
 */
wallee_integration.pay = function(amount, currency, callback) {
    return wallee_integration.show_terminal_payment({
        amount: amount,
        currency: currency || 'CHF',
        on_success: callback || function() {},
        on_failure: function(error) {
            frappe.show_alert({
                message: error.reason || __('Payment failed'),
                indicator: 'red'
            });
        }
    });
};
