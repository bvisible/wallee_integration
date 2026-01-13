// Copyright (c) 2024, Neoservice and contributors
// For license information, please see license.txt

frappe.ui.form.on('Wallee Settings', {
    refresh: function(frm) {
        // Check if credentials are missing - redirect to setup wizard
        if (!frm.doc.space_id || frm.doc.space_id === 0 ||
            !frm.doc.user_id || frm.doc.user_id === 0 ||
            !frm.doc.authentication_key) {

            frm.set_intro(`
                <div class="alert alert-warning" style="margin-bottom: 0;">
                    <strong>${__('Configuration Required')}</strong><br>
                    ${__('Wallee Integration needs to be configured before use.')}
                    <div style="margin-top: 10px;">
                        <button class="btn btn-primary btn-sm" onclick="frappe.set_route('wallee-setup-wizard')">
                            ${__('Open Setup Wizard')} →
                        </button>
                    </div>
                </div>
            `, 'yellow');

            // Add wizard button
            frm.add_custom_button(__('Setup Wizard'), function() {
                frappe.set_route('wallee-setup-wizard');
            }).addClass('btn-primary');

            return;
        }

        // Normal view - credentials configured
        // Test Connection button
        frm.add_custom_button(__('Test Connection'), function() {
            test_wallee_connection(frm);
        });

        // Setup Webshop Integration button
        if (frm.doc.enable_webshop) {
            frm.add_custom_button(__('Setup Webshop'), function() {
                setup_webshop_integration(frm);
            }, __('Actions'));
        }

        // Sync Terminals button
        if (frm.doc.enable_pos_terminal) {
            frm.add_custom_button(__('Sync Terminals'), function() {
                sync_terminals();
            }, __('Actions'));

            frm.add_custom_button(__('Terminal Wizard'), function() {
                frappe.set_route('wallee-terminal-wizard');
            }, __('Actions'));

            frm.add_custom_button(__('Test Terminal Transaction'), function() {
                show_test_terminal_dialog(frm);
            }, __('Actions'));
        }

        // Display connection status
        frm.set_intro(__('Wallee credentials configured. Click "Test Connection" to verify.'), 'blue');

        // Test mode warning
        if (frm.doc.test_mode) {
            frm.dashboard.add_comment(__('Test Mode is enabled. No real payments will be processed.'), 'yellow', true);
        }
    },

    space_id: function(frm) {
        // When space_id changes, update the application user link
        update_application_user_link(frm);
    },

    test_mode: function(frm) {
        if (frm.doc.test_mode) {
            frappe.show_alert({
                message: __('Test Mode enabled - transactions will use sandbox'),
                indicator: 'yellow'
            });
        }
    }
});

// Setup wizard moved to dedicated page: wallee-setup-wizard

function update_application_user_link(frm) {
    // Update description with direct link when space_id changes
    if (frm.doc.space_id && frm.doc.space_id > 0) {
        const url = `https://app-wallee.com/s/${frm.doc.space_id}/application-user/list`;
        frm.set_df_property('user_id', 'description',
            `${__('Your Application User ID.')} <a href="${url}" target="_blank">${__('Manage Application Users')}</a>`
        );
    }
}

function test_wallee_connection(frm) {
    if (!frm.doc.user_id || !frm.doc.authentication_key || !frm.doc.space_id) {
        frappe.msgprint(__('Please fill in User ID, Authentication Key, and Space ID before testing connection.'));
        return;
    }

    frappe.call({
        method: 'wallee_integration.wallee_integration.api.client.test_connection',
        freeze: true,
        freeze_message: __('Testing Wallee connection...'),
        callback: function(r) {
            if (r.message && r.message.success) {
                frappe.show_alert({
                    message: __('Connection successful!'),
                    indicator: 'green'
                });

                // Show success dialog
                frappe.msgprint({
                    title: __('✓ Wallee Connection Verified'),
                    indicator: 'green',
                    message: `
                        <p><strong>${__('Space ID')}:</strong> ${frm.doc.space_id}</p>
                        <p><strong>${__('Status')}:</strong> ${__('Connected')}</p>
                        <hr>
                        <p>${__('You can now:')}</p>
                        <ul>
                            <li>${__('Enable Webshop payments')}</li>
                            <li>${__('Enable POS Terminal payments')}</li>
                            <li>${__('Sync terminals from Wallee')}</li>
                        </ul>
                    `
                });

                frm.reload_doc();
            } else {
                frappe.msgprint({
                    title: __('Connection Failed'),
                    indicator: 'red',
                    message: `
                        <p>${__('Unable to connect to Wallee API')}</p>
                        <p><strong>${__('Error')}:</strong> ${r.message ? r.message.error : __('Unknown error')}</p>
                        <hr>
                        <p>${__('Please verify:')}</p>
                        <ul>
                            <li>${__('Space ID is correct')}</li>
                            <li>${__('User ID is correct')}</li>
                            <li>${__('Authentication Key is correct and not expired')}</li>
                        </ul>
                    `
                });
            }
        }
    });
}

function sync_terminals() {
    frappe.call({
        method: 'wallee_integration.wallee_integration.api.terminal.sync_terminals_from_wallee',
        freeze: true,
        freeze_message: __('Syncing terminals from Wallee...'),
        callback: function(r) {
            if (!r.exc) {
                let msg = __('Terminals synced successfully');
                if (r.message) {
                    msg += ': ' + r.message.created + __(' created, ') + r.message.updated + __(' updated');
                }
                frappe.show_alert({
                    message: msg,
                    indicator: 'green'
                });
            }
        }
    });
}

function setup_webshop_integration(frm) {
    // Show dialog to configure webshop integration
    let d = new frappe.ui.Dialog({
        title: __('Setup Webshop Integration'),
        size: 'large',
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'intro_html',
                options: `
                    <div class="alert alert-info">
                        <strong>${__('Automatic Configuration')}</strong><br>
                        ${__('This will create the necessary Payment Gateway Account and add Wallee to your Webshop payment methods.')}
                    </div>
                `
            },
            {
                fieldtype: 'Section Break',
                label: __('Payment Gateway Account')
            },
            {
                label: __('Currency'),
                fieldname: 'currency',
                fieldtype: 'Link',
                options: 'Currency',
                reqd: 1,
                default: 'CHF',
                description: __('Currency for this payment gateway account')
            },
            {
                fieldtype: 'Column Break'
            },
            {
                label: __('Payment Account'),
                fieldname: 'payment_account',
                fieldtype: 'Link',
                options: 'Account',
                description: __('Bank/Payment account for received payments'),
                get_query: function() {
                    return {
                        filters: {
                            'account_type': ['in', ['Bank', 'Cash']],
                            'is_group': 0
                        }
                    };
                }
            },
            {
                fieldtype: 'Section Break',
                label: __('Display Settings')
            },
            {
                label: __('Checkout Title'),
                fieldname: 'checkout_title',
                fieldtype: 'Data',
                default: 'Wallee',
                description: __('Title shown at checkout')
            },
            {
                fieldtype: 'Column Break'
            },
            {
                label: __('Checkout Description'),
                fieldname: 'checkout_description',
                fieldtype: 'Small Text',
                default: __('Pay securely with credit card'),
                description: __('Description shown at checkout')
            }
        ],
        primary_action_label: __('Create & Configure'),
        primary_action: function(values) {
            frappe.call({
                method: 'wallee_integration.wallee_integration.api.client.setup_webshop_integration',
                args: {
                    currency: values.currency,
                    payment_account: values.payment_account,
                    checkout_title: values.checkout_title,
                    checkout_description: values.checkout_description
                },
                freeze: true,
                freeze_message: __('Setting up Webshop integration...'),
                callback: function(r) {
                    d.hide();
                    if (r.message && r.message.success) {
                        frappe.msgprint({
                            title: __('✓ Webshop Integration Configured'),
                            indicator: 'green',
                            message: `
                                <p>${__('The following items were created/configured:')}</p>
                                <ul>
                                    <li><strong>${__('Payment Gateway')}:</strong> ${r.message.payment_gateway || 'Wallee'}</li>
                                    <li><strong>${__('Payment Gateway Account')}:</strong> ${r.message.payment_gateway_account}</li>
                                    <li><strong>${__('Webshop Payment Method')}:</strong> ${__('Added to Webshop Settings')}</li>
                                </ul>
                                <hr>
                                <p class="text-success">
                                    <strong>✓ ${__('Wallee is now available as a payment option in your webshop!')}</strong>
                                </p>
                            `
                        });
                        frm.reload_doc();
                    } else {
                        frappe.msgprint({
                            title: __('Setup Failed'),
                            indicator: 'red',
                            message: r.message ? r.message.error : __('Unknown error occurred')
                        });
                    }
                }
            });
        }
    });

    d.show();
}

// Button field handler
frappe.ui.form.on('Wallee Settings', {
    btn_terminal_wizard: function(frm) {
        frappe.set_route('wallee-terminal-wizard');
    }
});

function show_test_terminal_dialog(frm) {
    // Dialog to test terminal transaction
    let d = new frappe.ui.Dialog({
        title: __('Test Terminal Transaction'),
        size: 'small',
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'intro_html',
                options: `
                    <div class="alert alert-info" style="margin-bottom: 15px;">
                        <strong>${__('Debug Terminal Test Amounts')}</strong><br>
                        <small>
                            ${__('3.00-9.00 CHF = Approved')}<br>
                            ${__('1.00-2.00 CHF = Declined')}<br>
                            ${__('Use 5.00 CHF for a successful test')}
                        </small>
                    </div>
                `
            },
            {
                label: __('Terminal'),
                fieldname: 'terminal',
                fieldtype: 'Link',
                options: 'Wallee Payment Terminal',
                reqd: 1,
                default: frm.doc.default_terminal,
                get_query: function() {
                    return {
                        filters: {
                            'status': 'Active'
                        }
                    };
                }
            },
            {
                label: __('Amount'),
                fieldname: 'amount',
                fieldtype: 'Currency',
                reqd: 1,
                default: 5.00,
                description: __('Use 5.00 for approved, 1.00 for declined')
            },
            {
                label: __('Currency'),
                fieldname: 'currency',
                fieldtype: 'Link',
                options: 'Currency',
                default: 'CHF',
                reqd: 1
            },
            {
                fieldtype: 'Section Break'
            },
            {
                fieldtype: 'HTML',
                fieldname: 'status_html',
                options: '<div id="terminal-test-status"></div>'
            }
        ],
        primary_action_label: __('Send to Terminal'),
        primary_action: function(values) {
            initiate_test_terminal_transaction(d, values);
        }
    });

    d.show();
}

function initiate_test_terminal_transaction(dialog, values) {
    // Get terminal_id from the selected terminal
    frappe.db.get_value('Wallee Payment Terminal', values.terminal, 'terminal_id')
        .then(r => {
            if (!r.message || !r.message.terminal_id) {
                frappe.msgprint(__('Terminal ID not found. Please sync terminals first.'));
                return;
            }

            const terminal_id = r.message.terminal_id;
            const status_div = dialog.$wrapper.find('#terminal-test-status');

            // Update status
            status_div.html(`
                <div class="alert alert-warning">
                    <i class="fa fa-spinner fa-spin"></i> ${__('Creating transaction...')}
                </div>
            `);

            // Disable primary button
            dialog.get_primary_btn().prop('disabled', true);

            // Call API to create and initiate terminal transaction
            frappe.call({
                method: 'wallee_integration.wallee_integration.api.pos.initiate_terminal_payment',
                args: {
                    amount: values.amount,
                    currency: values.currency,
                    terminal: values.terminal
                },
                callback: function(r) {
                    if (r.exc) {
                        status_div.html(`
                            <div class="alert alert-danger">
                                <strong>${__('Error')}</strong><br>
                                ${r.exc}
                            </div>
                        `);
                        dialog.get_primary_btn().prop('disabled', false);
                        return;
                    }

                    if (r.message && r.message.transaction_name) {
                        status_div.html(`
                            <div class="alert alert-info">
                                <i class="fa fa-spinner fa-spin"></i>
                                ${__('Transaction sent to terminal. Waiting for response...')}<br>
                                <small>Transaction: ${r.message.transaction_name}</small>
                            </div>
                        `);

                        // Start polling for status
                        poll_terminal_status(dialog, r.message.transaction_name, status_div);
                    } else if (r.message && r.message.error) {
                        status_div.html(`
                            <div class="alert alert-danger">
                                <strong>${__('Error')}</strong><br>
                                ${r.message.error}
                            </div>
                        `);
                        dialog.get_primary_btn().prop('disabled', false);
                    }
                },
                error: function(r) {
                    status_div.html(`
                        <div class="alert alert-danger">
                            <strong>${__('Error')}</strong><br>
                            ${__('Failed to initiate terminal transaction')}
                        </div>
                    `);
                    dialog.get_primary_btn().prop('disabled', false);
                }
            });
        });
}

function poll_terminal_status(dialog, transaction_name, status_div, attempts = 0) {
    const max_attempts = 60; // 2 minutes with 2-second interval
    const poll_interval = 2000;

    if (attempts >= max_attempts) {
        status_div.html(`
            <div class="alert alert-warning">
                <strong>${__('Timeout')}</strong><br>
                ${__('Transaction is still processing. Check the terminal.')}
            </div>
        `);
        dialog.get_primary_btn().prop('disabled', false);
        return;
    }

    frappe.call({
        method: 'wallee_integration.wallee_integration.api.pos.check_terminal_payment_status',
        args: {
            transaction_name: transaction_name
        },
        callback: function(r) {
            if (r.message) {
                const status = r.message.status;
                const wallee_state = r.message.wallee_state;

                if (status === 'Completed' || status === 'Authorized') {
                    status_div.html(`
                        <div class="alert alert-success">
                            <strong><i class="fa fa-check"></i> ${__('Success!')}</strong><br>
                            ${__('Transaction')}: ${transaction_name}<br>
                            ${__('Status')}: ${status}<br>
                            ${__('Amount')}: ${r.message.amount} ${r.message.currency}
                        </div>
                    `);
                    dialog.get_primary_btn().prop('disabled', false);
                    dialog.set_primary_action(__('Close'), () => dialog.hide());
                } else if (status === 'Failed' || status === 'Decline' || status === 'Voided') {
                    status_div.html(`
                        <div class="alert alert-danger">
                            <strong><i class="fa fa-times"></i> ${__('Transaction Failed')}</strong><br>
                            ${__('Status')}: ${status}<br>
                            ${r.message.failure_reason ? __('Reason') + ': ' + r.message.failure_reason : ''}
                        </div>
                    `);
                    dialog.get_primary_btn().prop('disabled', false);
                } else {
                    // Still processing - continue polling
                    status_div.html(`
                        <div class="alert alert-info">
                            <i class="fa fa-spinner fa-spin"></i>
                            ${__('Waiting for terminal response...')}<br>
                            <small>${__('Status')}: ${status || wallee_state || 'Processing'}</small>
                        </div>
                    `);
                    setTimeout(() => {
                        poll_terminal_status(dialog, transaction_name, status_div, attempts + 1);
                    }, poll_interval);
                }
            }
        },
        error: function() {
            // Continue polling on error
            setTimeout(() => {
                poll_terminal_status(dialog, transaction_name, status_div, attempts + 1);
            }, poll_interval);
        }
    });
}
