/**
 * Wallee Captured Payments Manager
 *
 * Manages localStorage persistence for captured terminal payments.
 * Allows payment state to survive page reloads.
 * Works in both Frappe and standalone (POSNext) environments.
 */

// Create wallee_integration namespace (works with or without frappe)
if (typeof window.wallee_integration === 'undefined') {
    window.wallee_integration = {};
}

wallee_integration.captured_payments = {
    STORAGE_KEY: 'wallee_captured_payments',
    TTL_HOURS: 24,

    /**
     * Save a captured payment for an invoice
     * @param {string} invoiceRef - Invoice reference (e.g., "POS-INV-001" or draft ID)
     * @param {Object} data - Payment data to store
     */
    save: function(invoiceRef, data) {
        if (!invoiceRef) return;

        const payments = this.getAll();
        payments[invoiceRef] = {
            transaction_name: data.transaction_name,
            amount: data.amount,
            currency: data.currency || 'CHF',
            status: data.status || 'Completed',
            terminal: data.terminal || null,
            pos_profile: data.pos_profile || null,
            mode_of_payment: data.mode_of_payment || null,
            captured_at: new Date().toISOString()
        };

        try {
            localStorage.setItem(this.STORAGE_KEY, JSON.stringify(payments));
        } catch (e) {
            console.warn('Failed to save Wallee payment to localStorage:', e);
        }
    },

    /**
     * Get captured payment for an invoice
     * @param {string} invoiceRef - Invoice reference
     * @returns {Object|null} - Payment data or null if not found/expired
     */
    get: function(invoiceRef) {
        if (!invoiceRef) return null;

        const payments = this.getAll();
        const payment = payments[invoiceRef];

        if (payment && this.isValid(payment)) {
            return payment;
        }

        // Clean up expired entry
        if (payment) {
            this.remove(invoiceRef);
        }

        return null;
    },

    /**
     * Get all captured payments
     * @returns {Object} - Map of invoice references to payment data
     */
    getAll: function() {
        try {
            return JSON.parse(localStorage.getItem(this.STORAGE_KEY) || '{}');
        } catch (e) {
            console.warn('Failed to parse Wallee payments from localStorage:', e);
            return {};
        }
    },

    /**
     * Remove a captured payment
     * @param {string} invoiceRef - Invoice reference to remove
     */
    remove: function(invoiceRef) {
        if (!invoiceRef) return;

        const payments = this.getAll();
        delete payments[invoiceRef];

        try {
            localStorage.setItem(this.STORAGE_KEY, JSON.stringify(payments));
        } catch (e) {
            console.warn('Failed to remove Wallee payment from localStorage:', e);
        }
    },

    /**
     * Check if a payment is still valid (within TTL)
     * @param {Object} payment - Payment data with captured_at timestamp
     * @returns {boolean} - True if valid, false if expired
     */
    isValid: function(payment) {
        if (!payment || !payment.captured_at) return false;

        const capturedAt = new Date(payment.captured_at);
        const now = new Date();
        const ttlMs = this.TTL_HOURS * 60 * 60 * 1000;

        return (now - capturedAt) < ttlMs;
    },

    /**
     * Clean up all expired payments
     */
    cleanupExpired: function() {
        const payments = this.getAll();
        const cleaned = {};
        let removedCount = 0;

        for (const [key, payment] of Object.entries(payments)) {
            if (this.isValid(payment)) {
                cleaned[key] = payment;
            } else {
                removedCount++;
            }
        }

        if (removedCount > 0) {
            try {
                localStorage.setItem(this.STORAGE_KEY, JSON.stringify(cleaned));
                console.log(`Cleaned up ${removedCount} expired Wallee payment(s)`);
            } catch (e) {
                console.warn('Failed to cleanup expired Wallee payments:', e);
            }
        }
    },

    /**
     * Check if there's a captured payment for an invoice
     * @param {string} invoiceRef - Invoice reference
     * @returns {boolean} - True if payment exists and is valid
     */
    has: function(invoiceRef) {
        return this.get(invoiceRef) !== null;
    },

    /**
     * Get the captured amount for an invoice
     * @param {string} invoiceRef - Invoice reference
     * @returns {number} - Captured amount or 0
     */
    getAmount: function(invoiceRef) {
        const payment = this.get(invoiceRef);
        return payment ? payment.amount : 0;
    }
};

// Clean up expired entries on load (works with or without jQuery)
(function() {
    function init() {
        if (wallee_integration.captured_payments) {
            wallee_integration.captured_payments.cleanupExpired();
        }
    }

    if (typeof $ !== 'undefined' && $.fn) {
        $(document).ready(init);
    } else if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
