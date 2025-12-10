// Copyright (c) 2024, Neoservice and contributors
// For license information, please see license.txt

frappe.ui.form.on('Wallee Location', {
    refresh: function(frm) {
        // Status indicator
        frm.page.set_indicator(
            frm.doc.is_active ? __('Active') : __('Inactive'),
            frm.doc.is_active ? 'green' : 'grey'
        );

        // Show linked terminals count
        if (!frm.is_new()) {
            frappe.call({
                method: 'frappe.client.get_count',
                args: {
                    doctype: 'Wallee Payment Terminal',
                    filters: {
                        wallee_location: frm.doc.name
                    }
                },
                callback: function(r) {
                    if (r.message) {
                        frm.set_intro(__('Terminals at this location: {0}', [r.message]), 'blue');
                    }
                }
            });
        }

        // View Terminals button
        if (!frm.is_new()) {
            frm.add_custom_button(__('View Terminals'), function() {
                frappe.set_route('List', 'Wallee Payment Terminal', {
                    wallee_location: frm.doc.name
                });
            });
        }
    }
});
