// Copyright (c) 2024, Neoservice and contributors
// For license information, please see license.txt

frappe.ui.form.on('Wallee Settings', {
    refresh: function(frm) {
        // Check if credentials are missing - show setup wizard
        if (!frm.doc.space_id || frm.doc.space_id === 0) {
            show_setup_wizard(frm, 'space_id');
            return;
        }

        if (!frm.doc.user_id || frm.doc.user_id === 0 || !frm.doc.authentication_key) {
            show_setup_wizard(frm, 'credentials');
            return;
        }

        // Normal view - credentials configured
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
        frm.set_intro(__('Wallee credentials configured. Click "Test Connection" to verify.'), 'blue');

        // Test mode warning
        if (frm.doc.test_mode) {
            frm.dashboard.add_comment(__('Test Mode is enabled. No real payments will be processed.'), 'yellow', true);
        }
    },

    space_id: function(frm) {
        // When space_id changes, update the application user link
        update_application_user_link(frm);
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

function show_setup_wizard(frm, step) {
    let d;

    if (step === 'space_id') {
        d = new frappe.ui.Dialog({
            title: __('Wallee Setup - Step 1: Space ID'),
            size: 'large',
            static: true, // Cannot close by clicking outside
            fields: [
                {
                    fieldtype: 'HTML',
                    fieldname: 'intro_html',
                    options: `
                        <div class="wallee-setup-wizard">
                            <div class="alert alert-warning">
                                <strong>${__('Configuration Required')}</strong><br>
                                ${__('Wallee Integration needs to be configured before use.')}
                            </div>

                            <h4>${__('Step 1: Get your Space ID')}</h4>

                            <div class="step-instructions">
                                <p><strong>${__('Option A: Create a new account')}</strong></p>
                                <ol>
                                    <li>${__('Go to')} <a href="https://app-wallee.com/user/signup" target="_blank">https://app-wallee.com/user/signup</a></li>
                                    <li>${__('Create your account and follow the setup wizard')}</li>
                                </ol>

                                <p><strong>${__('Option B: Login to existing account')}</strong></p>
                                <ol>
                                    <li>${__('Go to')} <a href="https://app-wallee.com/user/login" target="_blank">https://app-wallee.com/user/login</a></li>
                                    <li>${__('Login with your credentials')}</li>
                                </ol>

                                <hr>

                                <p><strong>${__('Find your Space ID:')}</strong></p>
                                <p>${__('Your Space ID is the number shown next to your company name (see screenshot below)')}</p>

                                <div class="screenshot-container" style="text-align: center; margin: 20px 0; border: 1px solid #d1d8dd; padding: 10px; border-radius: 4px;">
                                    <img src="/assets/wallee_integration/images/wallee_space_id_guide.png"
                                         style="max-width: 100%; height: auto; border-radius: 4px;"
                                         alt="Wallee Space ID Location">
                                </div>

                                <p class="text-muted">${__('The Space ID is typically a 5-digit number like')} <code>#12345</code></p>
                            </div>
                        </div>
                    `
                },
                {
                    fieldtype: 'Section Break'
                },
                {
                    label: __('Enter your Space ID'),
                    fieldname: 'space_id',
                    fieldtype: 'Int',
                    reqd: 1,
                    description: __('Enter the number shown next to your company name in Wallee (e.g., 12345)')
                }
            ],
            primary_action_label: __('Next Step →'),
            primary_action: function(values) {
                if (!values.space_id || values.space_id <= 0) {
                    frappe.msgprint(__('Please enter a valid Space ID'));
                    return;
                }

                // Save the space_id
                frm.set_value('space_id', values.space_id);
                frm.save().then(() => {
                    d.hide();
                    // Show next step
                    show_setup_wizard(frm, 'credentials');
                });
            },
            secondary_action_label: __('I need help'),
            secondary_action: function() {
                window.open('https://app-wallee.com/en/doc/getting-started', '_blank');
            }
        });

        // Remove close button
        d.$wrapper.find('.btn-modal-close').hide();
        d.show();

    } else if (step === 'credentials') {
        const space_id = frm.doc.space_id;
        const app_user_url = `https://app-wallee.com/s/${space_id}/application-user/list`;

        d = new frappe.ui.Dialog({
            title: __('Wallee Setup - Step 2: API Credentials'),
            size: 'large',
            static: true,
            fields: [
                {
                    fieldtype: 'HTML',
                    fieldname: 'intro_html',
                    options: `
                        <div class="wallee-setup-wizard">
                            <div class="alert alert-info">
                                <strong>✓ ${__('Space ID configured:')} ${space_id}</strong>
                            </div>

                            <h4>${__('Step 2: Create an Application User')}</h4>

                            <div class="step-instructions">
                                <p>${__('You need to create an Application User to allow ERPNext to communicate with Wallee.')}</p>

                                <ol>
                                    <li>
                                        <strong>${__('Open Application Users page:')}</strong><br>
                                        <a href="${app_user_url}" target="_blank" class="btn btn-xs btn-primary" style="margin: 5px 0;">
                                            ${__('Open Application Users')} →
                                        </a>
                                    </li>
                                    <li>
                                        <strong>${__('Click "Create Application User"')}</strong><br>
                                        ${__('Give it a name like "ERPNext Integration"')}
                                    </li>
                                    <li>
                                        <strong>${__('Copy the credentials:')}</strong><br>
                                        <ul>
                                            <li><strong>User ID:</strong> ${__('The numeric ID shown after creation')}</li>
                                            <li><strong>Authentication Key:</strong> ${__('The long BASE64 key (shown only once!)')}</li>
                                        </ul>
                                    </li>
                                </ol>

                                <div class="alert alert-warning">
                                    <strong>⚠️ ${__('Important:')}</strong>
                                    ${__('The Authentication Key is only shown once when you create the Application User. Copy it immediately!')}
                                </div>
                            </div>
                        </div>
                    `
                },
                {
                    fieldtype: 'Section Break',
                    label: __('Enter your credentials')
                },
                {
                    label: __('User ID'),
                    fieldname: 'user_id',
                    fieldtype: 'Int',
                    reqd: 1,
                    description: __('The numeric Application User ID')
                },
                {
                    fieldtype: 'Column Break'
                },
                {
                    label: __('Authentication Key'),
                    fieldname: 'authentication_key',
                    fieldtype: 'Password',
                    reqd: 1,
                    description: __('The BASE64 authentication key')
                }
            ],
            primary_action_label: __('Save & Test Connection'),
            primary_action: function(values) {
                if (!values.user_id || values.user_id <= 0) {
                    frappe.msgprint(__('Please enter a valid User ID'));
                    return;
                }
                if (!values.authentication_key) {
                    frappe.msgprint(__('Please enter the Authentication Key'));
                    return;
                }

                // Save credentials
                frm.set_value('user_id', values.user_id);
                frm.set_value('authentication_key', values.authentication_key);
                frm.set_value('enabled', 1);

                frm.save().then(() => {
                    d.hide();
                    // Test connection
                    frappe.show_alert({
                        message: __('Credentials saved! Testing connection...'),
                        indicator: 'blue'
                    });

                    setTimeout(() => {
                        test_wallee_connection(frm);
                    }, 500);
                });
            },
            secondary_action_label: __('← Back'),
            secondary_action: function() {
                d.hide();
                show_setup_wizard(frm, 'space_id');
            }
        });

        // Remove close button
        d.$wrapper.find('.btn-modal-close').hide();
        d.show();
    }
}

function update_application_user_link(frm) {
    // Update description with direct link when space_id changes
    if (frm.doc.space_id && frm.doc.space_id > 0) {
        const url = `https://app-wallee.com/s/${frm.doc.space_id}/application-user/list`;
        frm.set_df_property('user_id', 'description',
            `${__('Your Application User ID.')} <a href="${url}" target="_blank">${__('Manage Application Users')}</a>`
        );
    }
}

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
                    message: __('Connection successful!'),
                    indicator: 'green'
                });

                // Show success dialog
                frappe.msgprint({
                    title: __('✓ Wallee Connection Verified'),
                    indicator: 'green',
                    message: `
                        <p><strong>${__('Space ID')}:</strong> ${frm.doc.space_id}</p>
                        <p><strong>${__('Status')}:</strong> ${__('Connected')}</p>
                        <hr>
                        <p>${__('You can now:')}</p>
                        <ul>
                            <li>${__('Enable Webshop payments')}</li>
                            <li>${__('Enable POS Terminal payments')}</li>
                            <li>${__('Sync terminals from Wallee')}</li>
                        </ul>
                    `
                });

                frm.reload_doc();
            } else {
                frappe.msgprint({
                    title: __('Connection Failed'),
                    indicator: 'red',
                    message: `
                        <p>${__('Unable to connect to Wallee API')}</p>
                        <p><strong>${__('Error')}:</strong> ${r.message ? r.message.error : __('Unknown error')}</p>
                        <hr>
                        <p>${__('Please verify:')}</p>
                        <ul>
                            <li>${__('Space ID is correct')}</li>
                            <li>${__('User ID is correct')}</li>
                            <li>${__('Authentication Key is correct and not expired')}</li>
                        </ul>
                    `
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
