// Wallee POS Payment Integration
// Copyright (c) 2024, Neoservice

frappe.provide("erpnext.PointOfSale");

// Extend the POS Payment component to add Wallee terminal payment
$(document).ready(function() {
	// Wait for POS to be loaded
	if (typeof erpnext !== "undefined" && erpnext.PointOfSale) {
		// Hook into the payment section
		frappe.ui.form.on("POS Invoice", {
			refresh: function(frm) {
				if (frm.doc.docstatus === 0) {
					add_wallee_payment_button(frm);
				}
			}
		});
	}
});

function add_wallee_payment_button(frm) {
	// Check if Wallee is enabled
	frappe.call({
		method: "frappe.client.get_single_value",
		args: {
			doctype: "Wallee Settings",
			field: "enable_pos_terminal"
		},
		async: false,
		callback: function(r) {
			if (r.message) {
				frm.add_custom_button(__("Pay with Terminal"), function() {
					initiate_wallee_payment(frm);
				}, __("Payment"));
			}
		}
	});
}

function initiate_wallee_payment(frm) {
	if (!frm.doc.grand_total || frm.doc.grand_total <= 0) {
		frappe.msgprint(__("Please add items to the invoice first"));
		return;
	}

	// Get available terminals
	frappe.call({
		method: "wallee_integration.wallee_integration.api.pos.get_available_terminals",
		callback: function(r) {
			const terminals = r.message || [];

			if (terminals.length === 0) {
				frappe.msgprint(__("No payment terminals configured"));
				return;
			}

			// If only one terminal, use it directly
			if (terminals.length === 1) {
				start_terminal_payment(frm, terminals[0].name);
			} else {
				// Show terminal selection dialog
				show_terminal_selection(frm, terminals);
			}
		}
	});
}

function show_terminal_selection(frm, terminals) {
	const terminal_options = terminals.map(t => ({
		label: t.terminal_name + (t.is_default ? " (Default)" : ""),
		value: t.name
	}));

	const dialog = new frappe.ui.Dialog({
		title: __("Select Terminal"),
		fields: [
			{
				fieldname: "terminal",
				fieldtype: "Select",
				label: __("Payment Terminal"),
				options: terminal_options,
				default: terminal_options.find(t => t.label.includes("Default"))?.value || terminal_options[0].value,
				reqd: 1
			}
		],
		primary_action_label: __("Start Payment"),
		primary_action: function(values) {
			dialog.hide();
			start_terminal_payment(frm, values.terminal);
		}
	});

	dialog.show();
}

function start_terminal_payment(frm, terminal) {
	wallee_integration.show_terminal_payment_dialog({
		amount: frm.doc.grand_total,
		currency: frm.doc.currency,
		pos_invoice: frm.doc.name,
		customer: frm.doc.customer,
		terminal: terminal,
		on_success: function(result) {
			frappe.show_alert({
				message: __("Payment successful!"),
				indicator: "green"
			});

			// Add payment entry
			add_payment_to_invoice(frm, result);
		},
		on_failure: function(error) {
			frappe.show_alert({
				message: error.message || __("Payment failed"),
				indicator: "red"
			});
		}
	});
}

function add_payment_to_invoice(frm, payment_result) {
	// Add a payment row to the POS Invoice
	const row = frm.add_child("payments");
	row.mode_of_payment = "Card"; // Assumes "Card" mode of payment exists
	row.amount = payment_result.amount;

	// Add custom reference
	if (frm.doc.wallee_transaction) {
		frm.set_value("wallee_transaction", payment_result.transaction_name);
	}

	frm.refresh_field("payments");

	// Link the payment to the invoice
	frappe.call({
		method: "wallee_integration.wallee_integration.api.pos.link_payment_to_invoice",
		args: {
			transaction_name: payment_result.transaction_name,
			pos_invoice: frm.doc.name
		},
		callback: function(r) {
			if (r.message && r.message.success) {
				frm.reload_doc();
			}
		}
	});
}
