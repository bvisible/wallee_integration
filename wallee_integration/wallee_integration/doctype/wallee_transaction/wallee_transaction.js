// Copyright (c) 2024, Neoservice and contributors
// For license information, please see license.txt

frappe.ui.form.on('Wallee Transaction', {
    refresh: function(frm) {
        // Set read-only fields (all data comes from Wallee API)
        const readOnlyFields = [
            'transaction_id', 'status', 'amount', 'currency',
            'authorized_amount', 'captured_amount', 'refunded_amount',
            'completion_id', 'completion_state', 'completion_amount',
            'statement_descriptor', 'processor_reference',
            'wallee_fee', 'net_amount', 'settlement_amount', 'settlement_date', 'settlement_state',
            'card_brand', 'card_last_four', 'card_expiry_month', 'card_expiry_year',
            'card_holder_name', 'authentication_indicator',
            'refund_id', 'refund_state', 'refund_amount', 'refund_date', 'refund_processor_reference',
            'failure_reason', 'wallee_data'
        ];

        readOnlyFields.forEach(field => {
            if (frm.fields_dict[field]) {
                frm.set_df_property(field, 'read_only', 1);
            }
        });

        // Status indicator colors
        frm.page.set_indicator(get_status_indicator(frm.doc.status), get_status_color(frm.doc.status));

        // Sync from Wallee button - always available if transaction_id exists
        if (frm.doc.transaction_id) {
            frm.add_custom_button(__('Sync from Wallee'), function() {
                sync_transaction(frm);
            }, __('Actions'));
        }

        // Capture button - only for Authorized transactions
        if (frm.doc.status === 'Authorized' && frm.doc.transaction_id) {
            frm.add_custom_button(__('Capture Payment'), function() {
                capture_payment(frm);
            }, __('Actions'));
        }

        // Void button - only for Authorized transactions
        if (frm.doc.status === 'Authorized' && frm.doc.transaction_id) {
            frm.add_custom_button(__('Void Payment'), function() {
                void_payment(frm);
            }, __('Actions'));
        }

        // Refund button - only for Completed transactions without existing refund
        if (frm.doc.status === 'Completed' && frm.doc.transaction_id && !frm.doc.refund_id) {
            frm.add_custom_button(__('Refund'), function() {
                show_refund_dialog(frm);
            }, __('Actions'));
        }

        // Display transaction state info
        if (frm.doc.status === 'Failed' && frm.doc.failure_reason) {
            frm.set_intro(__('Transaction failed: ') + frm.doc.failure_reason, 'red');
        }

        if (frm.doc.refund_state) {
            let refund_msg = __('Refund Status: ') + frm.doc.refund_state;
            if (frm.doc.refund_amount) {
                refund_msg += ' (' + format_currency(frm.doc.refund_amount, frm.doc.currency) + ')';
            }
            frm.set_intro(refund_msg, frm.doc.refund_state === 'Successful' ? 'green' : 'orange');
        }
    }
});

function get_status_indicator(status) {
    return status || 'Unknown';
}

function get_status_color(status) {
    const colors = {
        'Pending': 'orange',
        'Processing': 'yellow',
        'Authorized': 'blue',
        'Completed': 'green',
        'Fulfill': 'green',
        'Failed': 'red',
        'Decline': 'red',
        'Voided': 'grey',
        'Refunded': 'purple',
        'Partially Refunded': 'purple'
    };
    return colors[status] || 'grey';
}

function sync_transaction(frm) {
    frappe.call({
        method: 'wallee_integration.api.sync_transaction',
        args: {
            transaction_name: frm.doc.name
        },
        freeze: true,
        freeze_message: __('Syncing from Wallee...'),
        callback: function(r) {
            if (r.message && r.message.success) {
                frappe.show_alert({
                    message: __('Transaction synced successfully'),
                    indicator: 'green'
                });
                frm.reload_doc();
            } else {
                frappe.msgprint({
                    title: __('Sync Error'),
                    indicator: 'red',
                    message: r.message ? r.message.error : __('Unknown error occurred')
                });
            }
        }
    });
}

function capture_payment(frm) {
    frappe.confirm(
        __('Are you sure you want to capture this payment of {0} {1}?',
            [format_currency(frm.doc.authorized_amount || frm.doc.amount, frm.doc.currency), frm.doc.currency]),
        function() {
            frappe.call({
                method: 'wallee_integration.wallee_integration.api.transaction.complete_transaction',
                args: {
                    transaction_id: frm.doc.transaction_id
                },
                freeze: true,
                freeze_message: __('Capturing payment...'),
                callback: function(r) {
                    if (!r.exc) {
                        frappe.show_alert({
                            message: __('Payment captured successfully'),
                            indicator: 'green'
                        });
                        // Wait a moment then sync
                        setTimeout(() => sync_transaction(frm), 1500);
                    }
                }
            });
        }
    );
}

function void_payment(frm) {
    frappe.confirm(
        __('Are you sure you want to void this authorized payment?'),
        function() {
            frappe.call({
                method: 'wallee_integration.wallee_integration.api.transaction.void_transaction',
                args: {
                    transaction_id: frm.doc.transaction_id
                },
                freeze: true,
                freeze_message: __('Voiding payment...'),
                callback: function(r) {
                    if (!r.exc) {
                        frappe.show_alert({
                            message: __('Payment voided successfully'),
                            indicator: 'orange'
                        });
                        setTimeout(() => sync_transaction(frm), 1500);
                    }
                }
            });
        }
    );
}

function show_refund_dialog(frm) {
    let max_refund = frm.doc.captured_amount || frm.doc.amount;

    let d = new frappe.ui.Dialog({
        title: __('Refund Transaction'),
        fields: [
            {
                label: __('Available Amount'),
                fieldname: 'available_amount',
                fieldtype: 'Currency',
                read_only: 1,
                default: max_refund
            },
            {
                label: __('Refund Amount'),
                fieldname: 'amount',
                fieldtype: 'Currency',
                default: max_refund,
                reqd: 1,
                description: __('Enter amount to refund (max: {0})', [format_currency(max_refund, frm.doc.currency)])
            },
            {
                label: __('Reason'),
                fieldname: 'reason',
                fieldtype: 'Small Text',
                reqd: 1
            }
        ],
        primary_action_label: __('Refund'),
        primary_action(values) {
            if (values.amount > max_refund) {
                frappe.msgprint(__('Refund amount cannot exceed {0}', [format_currency(max_refund, frm.doc.currency)]));
                return;
            }

            frappe.call({
                method: 'wallee_integration.wallee_integration.api.refund.create_refund',
                args: {
                    transaction_id: frm.doc.transaction_id,
                    amount: values.amount,
                    reason: values.reason
                },
                freeze: true,
                freeze_message: __('Processing refund...'),
                callback: function(r) {
                    if (!r.exc) {
                        d.hide();
                        frappe.show_alert({
                            message: __('Refund initiated successfully'),
                            indicator: 'green'
                        });
                        // Wait for Wallee to process, then sync
                        setTimeout(() => sync_transaction(frm), 2000);
                    }
                }
            });
        }
    });
    d.show();
}
