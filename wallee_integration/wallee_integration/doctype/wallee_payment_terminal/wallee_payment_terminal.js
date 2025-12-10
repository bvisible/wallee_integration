// Copyright (c) 2024, Neoservice and contributors
// For license information, please see license.txt

frappe.ui.form.on('Wallee Payment Terminal', {
    refresh: function(frm) {
        // Status indicator
        frm.page.set_indicator(frm.doc.status || 'Unknown', get_terminal_status_color(frm.doc.status));

        // Sync from Wallee button
        if (frm.doc.terminal_id) {
            frm.add_custom_button(__('Sync from Wallee'), function() {
                sync_terminal(frm);
            }, __('Actions'));
        }

        // Test Terminal button - only for Active terminals
        if (frm.doc.status === 'Active' && frm.doc.terminal_id) {
            frm.add_custom_button(__('Test Terminal'), function() {
                test_terminal(frm);
            }, __('Actions'));
        }

        // Sync All Terminals button (on list or new form)
        if (!frm.is_new()) {
            frm.add_custom_button(__('Sync All Terminals'), function() {
                sync_all_terminals();
            });
        }

        // Show location info if linked
        if (frm.doc.wallee_location) {
            frm.set_intro(__('Location: ') + frm.doc.wallee_location, 'blue');
        }
    },

    onload: function(frm) {
        // Set query for wallee_location to show only active locations
        frm.set_query('wallee_location', function() {
            return {
                filters: {
                    is_active: 1
                }
            };
        });
    }
});

function get_terminal_status_color(status) {
    const colors = {
        'Active': 'green',
        'Inactive': 'grey',
        'Processing': 'yellow',
        'Deleted': 'red'
    };
    return colors[status] || 'grey';
}

function sync_terminal(frm) {
    frappe.call({
        method: 'wallee_integration.wallee_integration.api.terminal.sync_terminal',
        args: {
            terminal_name: frm.doc.name
        },
        freeze: true,
        freeze_message: __('Syncing terminal from Wallee...'),
        callback: function(r) {
            if (!r.exc) {
                frappe.show_alert({
                    message: __('Terminal synced successfully'),
                    indicator: 'green'
                });
                frm.reload_doc();
            }
        }
    });
}

function test_terminal(frm) {
    frappe.call({
        method: 'wallee_integration.wallee_integration.api.terminal.test_terminal',
        args: {
            terminal_id: frm.doc.terminal_id
        },
        freeze: true,
        freeze_message: __('Testing terminal connection...'),
        callback: function(r) {
            if (r.message && r.message.success) {
                frappe.show_alert({
                    message: __('Terminal is responding'),
                    indicator: 'green'
                });
            } else {
                frappe.msgprint({
                    title: __('Terminal Test Failed'),
                    indicator: 'red',
                    message: r.message ? r.message.error : __('Terminal not responding')
                });
            }
        }
    });
}

function sync_all_terminals() {
    frappe.call({
        method: 'wallee_integration.wallee_integration.api.terminal.sync_terminals_from_wallee',
        freeze: true,
        freeze_message: __('Syncing all terminals from Wallee...'),
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
                // Refresh list if on list view
                if (cur_list) {
                    cur_list.refresh();
                }
            }
        }
    });
}
