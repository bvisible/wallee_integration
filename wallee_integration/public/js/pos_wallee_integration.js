/**
 * Wallee POS Integration for ERPNext Standard POS (/point-of-sale)
 *
 * Intercepts Mode of Payment clicks when the payment mode is configured
 * as the Wallee terminal payment mode in POS Profile.
 */

frappe.provide('wallee_integration.pos');

wallee_integration.pos = {
    walleePaymentMode: null,
    posProfile: null,
    lockedPayments: {},
    initialized: false,

    /**
     * Initialize the Wallee POS integration
     */
    init: async function() {
        if (this.initialized) return;

        // Wait for POS to be ready
        await this.waitForPOS();

        // Get POS Profile
        this.posProfile = await this.getPOSProfile();
        if (!this.posProfile) {
            console.warn('Wallee POS: No POS Profile found');
            return;
        }

        // Load Wallee payment mode setting
        await this.loadWalleePaymentMode();
        if (!this.walleePaymentMode) {
            return;
        }

        // Hook into payment method clicks
        this.hookPaymentMethods();

        // Restore any captured payments
        this.restoreCapturedPayments();

        this.initialized = true;
    },

    /**
     * Wait for the POS page to be fully loaded
     */
    waitForPOS: function() {
        return new Promise((resolve) => {
            const check = () => {
                // Check for erpnext.PointOfSale.Controller
                if (window.cur_pos || (window.erpnext && erpnext.PointOfSale && erpnext.PointOfSale.Controller)) {
                    setTimeout(resolve, 500); // Extra delay for DOM to be ready
                } else {
                    setTimeout(check, 200);
                }
            };
            check();
        });
    },

    /**
     * Get the current POS Profile
     */
    getPOSProfile: async function() {
        try {
            // Try to get from cur_pos
            if (window.cur_pos && cur_pos.pos_profile) {
                return cur_pos.pos_profile;
            }

            // Try from frm
            if (window.cur_pos && cur_pos.frm && cur_pos.frm.pos_profile) {
                return cur_pos.frm.pos_profile;
            }

            // Get from settings
            const result = await frappe.xcall(
                'erpnext.selling.page.point_of_sale.point_of_sale.get_pos_profile_data'
            );
            return result?.name || null;
        } catch (e) {
            console.warn('Wallee POS: Could not get POS Profile', e);
            return null;
        }
    },

    /**
     * Load the Wallee payment mode setting from POS Profile
     */
    loadWalleePaymentMode: async function() {
        if (!this.posProfile) return;

        try {
            const result = await frappe.db.get_value(
                'POS Profile',
                this.posProfile,
                'wallee_terminal_payment_mode'
            );
            this.walleePaymentMode = result?.message?.wallee_terminal_payment_mode || null;
        } catch (e) {
            console.warn('Wallee POS: Could not load payment mode setting', e);
        }
    },

    /**
     * Hook into payment method clicks
     */
    hookPaymentMethods: function() {
        if (!this.walleePaymentMode) return;

        const self = this;

        // Wait for payment section to be rendered
        const observePaymentSection = () => {
            const $paymentSection = $('.payment-modes, .mode-of-payment-control');

            if ($paymentSection.length === 0) {
                setTimeout(observePaymentSection, 500);
                return;
            }

            // Use event delegation to catch clicks on payment modes
            $(document).off('click.walleePos').on('click.walleePos', '.mode-of-payment', function(e) {
                const $mode = $(this);
                const modeName = $mode.attr('data-mode') || $mode.find('.mode-of-payment-label, .payment-mode-label').text().trim();

                // Check if this is the Wallee payment mode
                if (self.isWalleePaymentMode(modeName)) {
                    e.preventDefault();
                    e.stopImmediatePropagation();
                    self.openWalleeDialog();
                    return false;
                }
            });
        };

        observePaymentSection();
    },

    /**
     * Check if a mode name matches the Wallee payment mode
     */
    isWalleePaymentMode: function(modeName) {
        if (!this.walleePaymentMode || !modeName) return false;

        // Normalize for comparison
        const normalize = (str) => str.toLowerCase().replace(/[^a-z0-9]/g, '');
        return normalize(this.walleePaymentMode) === normalize(modeName);
    },

    /**
     * Get the current invoice reference
     */
    getInvoiceReference: function() {
        if (window.cur_pos && cur_pos.frm && cur_pos.frm.doc) {
            return cur_pos.frm.doc.name || `draft_${this.posProfile}_${Date.now()}`;
        }
        return `draft_${this.posProfile}_${Date.now()}`;
    },

    /**
     * Get the remaining amount to pay
     */
    getRemainingAmount: function() {
        if (!window.cur_pos || !cur_pos.frm || !cur_pos.frm.doc) {
            return 0;
        }

        const doc = cur_pos.frm.doc;
        const grandTotal = flt(frappe.sys_defaults.disable_rounded_total ?
            doc.grand_total : doc.rounded_total);
        const paidAmount = flt(doc.paid_amount || 0);

        return grandTotal - paidAmount;
    },

    /**
     * Open the Wallee terminal payment dialog
     */
    openWalleeDialog: function() {
        const remaining = this.getRemainingAmount();

        if (remaining <= 0) {
            frappe.show_alert({
                message: __('No remaining amount to pay'),
                indicator: 'orange'
            });
            return;
        }

        const invoiceRef = this.getInvoiceReference();
        const currency = cur_pos?.frm?.doc?.currency || 'CHF';
        const self = this;

        wallee_integration.show_terminal_payment({
            amount: remaining,
            currency: currency,
            pos_profile: this.posProfile,
            max_amount: remaining,
            invoice_reference: invoiceRef,
            mode_of_payment: this.walleePaymentMode,
            on_success: function(result) {
                self.handlePaymentSuccess(result);
            },
            on_failure: function(error) {
                frappe.show_alert({
                    message: error.reason || __('Payment failed'),
                    indicator: 'red'
                });
            },
            on_cancel: function() {
                // Do nothing on cancel
            }
        });
    },

    /**
     * Handle successful payment
     */
    handlePaymentSuccess: function(result) {
        const frm = cur_pos?.frm;
        if (!frm) return;

        const modeName = this.walleePaymentMode;

        // Find or add the payment row
        let paymentRow = (frm.doc.payments || []).find(p => p.mode_of_payment === modeName);

        if (!paymentRow) {
            paymentRow = frm.add_child('payments', {
                mode_of_payment: modeName,
                amount: 0
            });
        }

        // Set amount (this will be locked)
        paymentRow.amount = result.amount;

        // Mark as locked in our tracking
        this.lockedPayments[modeName] = {
            amount: result.amount,
            transaction_name: result.transaction_name,
            is_locked: true
        };

        // Refresh display
        frm.refresh_field('payments');

        // Update totals if available
        if (cur_pos.payment && cur_pos.payment.update_totals_section) {
            cur_pos.payment.update_totals_section(frm.doc);
        }

        // Add visual lock indicator
        this.addLockIndicator(modeName);

        frappe.show_alert({
            message: __('Payment of {0} captured', [format_currency(result.amount, frm.doc.currency)]),
            indicator: 'green'
        });
    },

    /**
     * Add a lock indicator to the payment mode button
     */
    addLockIndicator: function(modeName) {
        const self = this;

        // Find the payment mode element
        $('.mode-of-payment').each(function() {
            const $mode = $(this);
            const elementMode = $mode.attr('data-mode') || $mode.find('.mode-of-payment-label, .payment-mode-label').text().trim();

            if (self.isWalleePaymentMode(elementMode)) {
                // Add lock icon if not already present
                if (!$mode.find('.wallee-lock-icon').length) {
                    $mode.addClass('wallee-locked');
                    $mode.find('.pay-amount, .mode-of-payment-amount').before(`
                        <span class="wallee-lock-icon" title="${__('Payment captured via Wallee terminal')}">
                            <svg style="width:16px;height:16px;fill:currentColor;margin-right:4px;" viewBox="0 0 20 20">
                                <path fill-rule="evenodd" d="M5 9V7a5 5 0 0110 0v2a2 2 0 012 2v5a2 2 0 01-2 2H5a2 2 0 01-2-2v-5a2 2 0 012-2zm8-2v2H7V7a3 3 0 016 0z"/>
                            </svg>
                        </span>
                    `);
                }

                // Update displayed amount
                const lockedPayment = self.lockedPayments[self.walleePaymentMode];
                if (lockedPayment) {
                    const $amount = $mode.find('.pay-amount, .mode-of-payment-amount');
                    if ($amount.length) {
                        $amount.text(format_currency(lockedPayment.amount, cur_pos?.frm?.doc?.currency || 'CHF'));
                    }
                }
            }
        });
    },

    /**
     * Restore captured payments from localStorage
     */
    restoreCapturedPayments: function() {
        const invoiceRef = this.getInvoiceReference();

        if (!invoiceRef || !wallee_integration.captured_payments) return;

        const captured = wallee_integration.captured_payments.get(invoiceRef);
        if (!captured) return;

        // Wait a bit for POS to fully initialize then restore
        const self = this;
        setTimeout(() => {
            self.handlePaymentSuccess({
                amount: captured.amount,
                transaction_name: captured.transaction_name,
                mode_of_payment: captured.mode_of_payment
            });
        }, 1000);
    },

    /**
     * Clear locked payments (called when invoice is submitted)
     */
    clearLockedPayments: function() {
        const invoiceRef = this.getInvoiceReference();

        if (invoiceRef && wallee_integration.captured_payments) {
            wallee_integration.captured_payments.remove(invoiceRef);
        }

        this.lockedPayments = {};
    },

    /**
     * Check if a payment mode is locked
     */
    isLocked: function(modeName) {
        return this.lockedPayments.hasOwnProperty(modeName);
    }
};

// Initialize when POS page loads
$(document).on('page-change', function() {
    if (frappe.get_route_str() === 'point-of-sale') {
        // Reset state for new POS session
        wallee_integration.pos.initialized = false;
        wallee_integration.pos.lockedPayments = {};

        // Initialize after a short delay
        setTimeout(() => {
            wallee_integration.pos.init();
        }, 1000);
    }
});

// Also try to initialize on document ready (for direct navigation)
$(document).ready(function() {
    if (frappe.get_route_str() === 'point-of-sale') {
        setTimeout(() => {
            wallee_integration.pos.init();
        }, 2000);
    }
});

// Add CSS for lock indicator
$(`
    <style>
        .mode-of-payment.wallee-locked {
            position: relative;
        }
        .mode-of-payment.wallee-locked::after {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 128, 0, 0.05);
            pointer-events: none;
            border-radius: inherit;
        }
        .wallee-lock-icon {
            display: inline-flex;
            align-items: center;
            color: var(--green-500, #22c55e);
        }
    </style>
`).appendTo('head');
