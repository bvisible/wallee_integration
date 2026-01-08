// Copyright (c) 2024, Neoservice and contributors
// For license information, please see license.txt

frappe.ui.form.on('Wallee Payment Terminal', {
    refresh: function(frm) {
        // Status indicator
        frm.page.set_indicator(frm.doc.status || 'Unknown', get_terminal_status_color(frm.doc.status));

        // Registration buttons based on status
        if (!frm.is_new()) {
            // Create in Wallee button - only when not yet created
            if (!frm.doc.terminal_id && frm.doc.terminal_type_id) {
                frm.add_custom_button(__('Create in Wallee'), function() {
                    create_terminal_in_wallee(frm);
                }, __('Registration'));
            }

            // Link Device button - only when created but not linked
            if (frm.doc.terminal_id && !frm.doc.device_serial_number) {
                frm.add_custom_button(__('Link Device'), function() {
                    show_link_device_dialog(frm);
                }, __('Registration'));
            }

            // Unlink Device button - only when linked
            if (frm.doc.terminal_id && frm.doc.device_serial_number) {
                frm.add_custom_button(__('Unlink Device'), function() {
                    unlink_terminal_device(frm);
                }, __('Registration'));
            }

            // Show Activation Code button - when code exists
            if (frm.doc.activation_code) {
                frm.add_custom_button(__('Show Activation Code'), function() {
                    show_activation_code_dialog(frm);
                }, __('Registration'));
            }
        }

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

        // Trigger Balance button - only for Active terminals
        if (frm.doc.status === 'Active' && frm.doc.terminal_id) {
            frm.add_custom_button(__('Trigger Balance'), function() {
                trigger_terminal_balance(frm);
            }, __('Actions'));
        }

        // Sync All Terminals button
        if (!frm.is_new()) {
            frm.add_custom_button(__('Sync All Terminals'), function() {
                sync_all_terminals();
            });
        }

        // Terminal Wizard button
        frm.add_custom_button(__('Terminal Wizard'), function() {
            frappe.set_route('wallee-terminal-wizard');
        });

        // Show location info if linked
        if (frm.doc.wallee_location) {
            frm.set_intro(__('Location: ') + frm.doc.wallee_location, 'blue');
        }

        // Show registration status info
        if (frm.doc.registration_status === 'Not Created' && !frm.doc.terminal_type_id) {
            frm.set_intro(__('Enter a Terminal Type ID to create this terminal in Wallee'), 'yellow');
        } else if (frm.doc.registration_status === 'Created') {
            frm.set_intro(__('Terminal created. Link a physical device to generate activation code.'), 'blue');
        } else if (frm.doc.registration_status === 'Linked' && frm.doc.activation_code) {
            frm.set_intro(__('Enter activation code on your terminal: ') + frm.doc.activation_code, 'green');
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

function create_terminal_in_wallee(frm) {
    frappe.confirm(
        __('This will create a new terminal in Wallee. Continue?'),
        function() {
            frm.call({
                doc: frm.doc,
                method: 'create_in_wallee',
                freeze: true,
                freeze_message: __('Creating terminal in Wallee...'),
                callback: function(r) {
                    if (!r.exc) {
                        frm.reload_doc();
                    }
                }
            });
        }
    );
}

function show_link_device_dialog(frm) {
    let d = new frappe.ui.Dialog({
        title: __('Link Physical Device'),
        fields: [
            {
                label: __('Serial Number'),
                fieldname: 'serial_number',
                fieldtype: 'Data',
                reqd: 1,
                description: __('Enter the serial number from the back of your terminal device')
            }
        ],
        primary_action_label: __('Link Device'),
        primary_action: function(values) {
            d.hide();
            frm.call({
                doc: frm.doc,
                method: 'link_device',
                args: {
                    serial_number: values.serial_number
                },
                freeze: true,
                freeze_message: __('Linking device...'),
                callback: function(r) {
                    if (!r.exc && r.message) {
                        // Show activation code in a prominent dialog
                        show_activation_code_result(r.message.activation_code);
                        frm.reload_doc();
                    }
                }
            });
        }
    });
    d.show();
}

function show_activation_code_result(activation_code) {
    let d = new frappe.ui.Dialog({
        title: __('Terminal Activation Code'),
        fields: [
            {
                fieldtype: 'HTML',
                options: `
                    <div style="text-align: center; padding: 20px;">
                        <p>${__('Enter this code on your terminal to activate it:')}</p>
                        <h1 style="font-size: 48px; font-weight: bold; color: var(--primary); letter-spacing: 8px; margin: 20px 0;">
                            ${activation_code}
                        </h1>
                        <p class="text-muted">${__('The terminal will automatically configure itself after activation.')}</p>
                    </div>
                `
            }
        ],
        primary_action_label: __('OK'),
        primary_action: function() {
            d.hide();
        }
    });
    d.show();
}

function show_activation_code_dialog(frm) {
    show_activation_code_result(frm.doc.activation_code);
}

function unlink_terminal_device(frm) {
    frappe.confirm(
        __('This will unlink the physical device from this terminal. The device will need to be re-activated. Continue?'),
        function() {
            frm.call({
                doc: frm.doc,
                method: 'unlink_device',
                freeze: true,
                freeze_message: __('Unlinking device...'),
                callback: function(r) {
                    if (!r.exc) {
                        frm.reload_doc();
                    }
                }
            });
        }
    );
}

function trigger_terminal_balance(frm) {
    frappe.confirm(
        __('This will trigger a final balance/settlement on the terminal. Continue?'),
        function() {
            frm.call({
                doc: frm.doc,
                method: 'trigger_balance',
                freeze: true,
                freeze_message: __('Triggering balance...'),
                callback: function(r) {
                    if (!r.exc) {
                        frappe.show_alert({
                            message: __('Balance triggered successfully'),
                            indicator: 'green'
                        });
                    }
                }
            });
        }
    );
}
