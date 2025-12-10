// Wallee Terminal Integration for POS
// Copyright (c) 2024, Neoservice

frappe.provide("wallee_integration");

wallee_integration.WalleeTerminal = class WalleeTerminal {
	constructor(options = {}) {
		this.terminal = options.terminal || null;
		this.polling_interval = options.polling_interval || 2000;
		this.max_polling_attempts = options.max_polling_attempts || 60;
		this.on_success = options.on_success || (() => {});
		this.on_failure = options.on_failure || (() => {});
		this.on_status_change = options.on_status_change || (() => {});

		this.current_transaction = null;
		this.polling_timer = null;
		this.polling_attempts = 0;
	}

	async initiate_payment(amount, currency, pos_invoice = null, customer = null) {
		this.current_transaction = null;
		this.polling_attempts = 0;

		try {
			const response = await frappe.call({
				method: "wallee_integration.wallee_integration.api.pos.initiate_terminal_payment",
				args: {
					amount: amount,
					currency: currency,
					terminal: this.terminal,
					pos_invoice: pos_invoice,
					customer: customer
				}
			});

			if (response.message && response.message.success) {
				this.current_transaction = response.message.transaction_name;
				this.on_status_change("processing", response.message);
				this.start_polling();
				return response.message;
			} else {
				throw new Error(response.message?.message || __("Failed to initiate payment"));
			}
		} catch (error) {
			this.on_failure(error);
			throw error;
		}
	}

	start_polling() {
		if (this.polling_timer) {
			clearInterval(this.polling_timer);
		}

		this.polling_timer = setInterval(() => {
			this.check_status();
		}, this.polling_interval);
	}

	stop_polling() {
		if (this.polling_timer) {
			clearInterval(this.polling_timer);
			this.polling_timer = null;
		}
	}

	async check_status() {
		if (!this.current_transaction) {
			this.stop_polling();
			return;
		}

		this.polling_attempts++;

		if (this.polling_attempts > this.max_polling_attempts) {
			this.stop_polling();
			this.on_failure(new Error(__("Payment timeout - please check the terminal")));
			return;
		}

		try {
			const response = await frappe.call({
				method: "wallee_integration.wallee_integration.api.pos.check_terminal_payment_status",
				args: {
					transaction_name: this.current_transaction
				}
			});

			const result = response.message;

			if (result.completed) {
				this.stop_polling();
				this.on_success(result);
			} else if (result.failed) {
				this.stop_polling();
				this.on_failure(new Error(result.failure_reason || __("Payment failed")));
			} else {
				this.on_status_change(result.status, result);
			}
		} catch (error) {
			console.error("Error checking payment status:", error);
		}
	}

	async cancel_payment() {
		if (!this.current_transaction) {
			return { success: false, message: __("No active transaction") };
		}

		this.stop_polling();

		try {
			const response = await frappe.call({
				method: "wallee_integration.wallee_integration.api.pos.cancel_terminal_payment",
				args: {
					transaction_name: this.current_transaction
				}
			});

			this.current_transaction = null;
			return response.message;
		} catch (error) {
			throw error;
		}
	}

	async get_terminals() {
		const response = await frappe.call({
			method: "wallee_integration.wallee_integration.api.pos.get_available_terminals"
		});
		return response.message || [];
	}
};

// Dialog for terminal payment
wallee_integration.show_terminal_payment_dialog = function(options) {
	const {
		amount,
		currency,
		pos_invoice,
		customer,
		terminal,
		on_success,
		on_failure
	} = options;

	const dialog = new frappe.ui.Dialog({
		title: __("Terminal Payment"),
		fields: [
			{
				fieldtype: "HTML",
				fieldname: "status_html",
				options: `
					<div class="wallee-terminal-status text-center">
						<div class="payment-icon mb-3">
							<i class="fa fa-credit-card fa-3x text-primary"></i>
						</div>
						<h4 class="payment-amount">${format_currency(amount, currency)}</h4>
						<p class="payment-status text-muted">${__("Initiating payment...")}</p>
						<div class="payment-spinner mt-3">
							<i class="fa fa-spinner fa-spin fa-2x"></i>
						</div>
					</div>
				`
			}
		],
		primary_action_label: __("Cancel"),
		primary_action: async () => {
			try {
				await wallee_terminal.cancel_payment();
				dialog.hide();
				if (on_failure) on_failure(new Error(__("Payment cancelled by user")));
			} catch (error) {
				frappe.msgprint(__("Failed to cancel payment: {0}", [error.message]));
			}
		}
	});

	const update_status = (status, data) => {
		const status_element = dialog.$wrapper.find(".payment-status");
		const status_messages = {
			"processing": __("Please complete payment on terminal..."),
			"Pending": __("Waiting for terminal..."),
			"Processing": __("Processing payment..."),
			"Authorized": __("Payment authorized, completing...")
		};
		status_element.text(status_messages[status] || status);
	};

	const wallee_terminal = new wallee_integration.WalleeTerminal({
		terminal: terminal,
		on_success: (result) => {
			dialog.$wrapper.find(".payment-spinner").html(`
				<i class="fa fa-check-circle fa-3x text-success"></i>
			`);
			dialog.$wrapper.find(".payment-status").text(__("Payment completed!"));

			setTimeout(() => {
				dialog.hide();
				if (on_success) on_success(result);
			}, 1500);
		},
		on_failure: (error) => {
			dialog.$wrapper.find(".payment-spinner").html(`
				<i class="fa fa-times-circle fa-3x text-danger"></i>
			`);
			dialog.$wrapper.find(".payment-status").text(error.message || __("Payment failed"));

			setTimeout(() => {
				dialog.hide();
				if (on_failure) on_failure(error);
			}, 2000);
		},
		on_status_change: update_status
	});

	dialog.show();

	// Start payment
	wallee_terminal.initiate_payment(amount, currency, pos_invoice, customer).catch(error => {
		dialog.$wrapper.find(".payment-spinner").html(`
			<i class="fa fa-times-circle fa-3x text-danger"></i>
		`);
		dialog.$wrapper.find(".payment-status").text(error.message || __("Failed to start payment"));
	});

	return dialog;
};
