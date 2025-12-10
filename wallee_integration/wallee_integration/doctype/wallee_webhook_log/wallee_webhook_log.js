// Copyright (c) 2024, Neoservice and contributors
// For license information, please see license.txt

frappe.ui.form.on('Wallee Webhook Log', {
    refresh: function(frm) {
        // Status indicator
        frm.page.set_indicator(
            frm.doc.processing_status || 'Unknown',
            get_log_status_color(frm.doc.processing_status)
        );

        // Make all fields read-only (log entries should not be edited)
        frm.disable_save();

        // Link to transaction if available
        if (frm.doc.linked_transaction) {
            frm.add_custom_button(__('View Transaction'), function() {
                frappe.set_route('Form', 'Wallee Transaction', frm.doc.linked_transaction);
            });
        }

        // Reprocess button for failed webhooks
        if (frm.doc.processing_status === 'Failed') {
            frm.add_custom_button(__('Reprocess'), function() {
                reprocess_webhook(frm);
            }, __('Actions'));
        }

        // Format JSON fields for better display
        format_json_fields(frm);
    }
});

function get_log_status_color(status) {
    const colors = {
        'Received': 'blue',
        'Processed': 'green',
        'Failed': 'red',
        'Ignored': 'grey'
    };
    return colors[status] || 'grey';
}

function reprocess_webhook(frm) {
    frappe.confirm(
        __('Are you sure you want to reprocess this webhook?'),
        function() {
            frappe.call({
                method: 'wallee_integration.api.reprocess_webhook',
                args: {
                    log_name: frm.doc.name
                },
                freeze: true,
                freeze_message: __('Reprocessing webhook...'),
                callback: function(r) {
                    if (r.message && r.message.success) {
                        frappe.show_alert({
                            message: __('Webhook reprocessed successfully'),
                            indicator: 'green'
                        });
                        frm.reload_doc();
                    } else {
                        frappe.msgprint({
                            title: __('Reprocess Failed'),
                            indicator: 'red',
                            message: r.message ? r.message.error : __('Failed to reprocess webhook')
                        });
                    }
                }
            });
        }
    );
}

function format_json_fields(frm) {
    // Format JSON fields for better readability
    ['request_headers', 'request_payload', 'response_payload'].forEach(function(field) {
        if (frm.doc[field] && frm.fields_dict[field]) {
            try {
                let data = frm.doc[field];
                if (typeof data === 'string') {
                    data = JSON.parse(data);
                }
                // Pretty print with indentation
                let formatted = JSON.stringify(data, null, 2);
                frm.fields_dict[field].$wrapper.find('.like-disabled-input').css({
                    'white-space': 'pre-wrap',
                    'font-family': 'monospace',
                    'font-size': '12px'
                });
            } catch (e) {
                // Leave as-is if not valid JSON
            }
        }
    });
}
