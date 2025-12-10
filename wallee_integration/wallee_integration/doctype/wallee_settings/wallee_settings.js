// Copyright (c) 2024, Neoservice and contributors
// For license information, please see license.txt

frappe.ui.form.on('Wallee Settings', {
    refresh: function(frm) {
        // Test Connection button
        frm.add_custom_button(__('Test Connection'), function() {
            test_wallee_connection(frm);
        });

        // Sync Terminals button
        if (frm.doc.enable_pos_terminal) {
            frm.add_custom_button(__('Sync Terminals'), function() {
                sync_terminals();
            });
        }

        // Display connection status
        if (frm.doc.user_id && frm.doc.authentication_key && frm.doc.space_id) {
            frm.set_intro(__('Wallee credentials configured. Click "Test Connection" to verify.'), 'blue');
        } else {
            frm.set_intro(__('Please configure Wallee API credentials (User ID, Authentication Key, Space ID)'), 'orange');
        }

        // Test mode warning
        if (frm.doc.test_mode) {
            frm.dashboard.add_comment(__('Test Mode is enabled. No real payments will be processed.'), 'yellow', true);
        }
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
                    message: __('Connection successful! Space: {0}', [r.message.space_name || frm.doc.space_id]),
                    indicator: 'green'
                });

                // Show additional info if available
                if (r.message.space_info) {
                    let info = r.message.space_info;
                    frappe.msgprint({
                        title: __('Wallee Connection Verified'),
                        indicator: 'green',
                        message: `
                            <p><strong>${__('Space ID')}:</strong> ${info.id}</p>
                            <p><strong>${__('Space Name')}:</strong> ${info.name || 'N/A'}</p>
                            <p><strong>${__('State')}:</strong> ${info.state || 'N/A'}</p>
                        `
                    });
                }
            } else {
                frappe.msgprint({
                    title: __('Connection Failed'),
                    indicator: 'red',
                    message: r.message ? r.message.error : __('Unable to connect to Wallee API')
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
