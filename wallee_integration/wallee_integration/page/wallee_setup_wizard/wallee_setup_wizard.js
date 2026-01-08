frappe.pages['wallee-setup-wizard'].on_page_load = function(wrapper) {
	new WalleeSetupWizard(wrapper);
};

// Helper function to show image in dialog with step info
function showHelpImageDialog(imgSrc, stepNumber, stepText) {
	const title = stepNumber ? __('Step {0}', [stepNumber]) : (stepText || __('Help'));
	const dialog = new frappe.ui.Dialog({
		title: title,
		size: 'large',
		fields: [
			{
				fieldtype: 'HTML',
				options: `
					<div class="help-dialog-content">
						${stepNumber ? `
						<div class="help-dialog-text">
							<div class="help-dialog-step-badge">${stepNumber}</div>
							<p>${stepText || ''}</p>
						</div>
						` : (stepText ? `<div class="help-dialog-caption">${stepText}</div>` : '')}
						<div class="help-dialog-image">
							<img src="${imgSrc}" alt="Step ${stepNumber || ''}">
						</div>
					</div>
					<style>
						.help-dialog-content {
							display: flex;
							flex-direction: column;
							gap: 15px;
						}
						.help-dialog-text {
							display: flex;
							align-items: flex-start;
							gap: 12px;
							padding: 15px;
							background: var(--bg-light-gray);
							border-radius: 8px;
						}
						.help-dialog-step-badge {
							background: var(--primary);
							color: white;
							width: 28px;
							height: 28px;
							border-radius: 50%;
							display: flex;
							align-items: center;
							justify-content: center;
							font-weight: bold;
							flex-shrink: 0;
						}
						.help-dialog-text p {
							margin: 0;
							font-size: 14px;
							line-height: 1.5;
							padding-top: 3px;
						}
						.help-dialog-image {
							text-align: center;
						}
						.help-dialog-image img {
							max-width: 100%;
							max-height: 60vh;
							border: 1px solid var(--border-color);
							border-radius: 8px;
							box-shadow: 0 4px 12px rgba(0,0,0,0.1);
						}
						.help-dialog-caption {
							text-align: center;
							font-size: 14px;
							color: var(--text-muted);
							padding: 10px;
							background: var(--bg-light-gray);
							border-radius: 6px;
						}
					</style>
				`
			}
		]
	});
	dialog.show();
}

class WalleeSetupWizard {
	constructor(wrapper) {
		this.wrapper = wrapper;
		this.page = frappe.ui.make_app_page({
			parent: wrapper,
			title: __('Wallee Setup Wizard'),
			single_column: true
		});

		this.currentStep = 1;
		this.totalSteps = 5;
		this.wizardData = {
			account_id: '',
			user_id: '',
			authentication_key: '',
			space_id: '',
			enable_webshop: true,
			enable_pos_terminal: false,
			currency: 'CHF',
			payment_account: ''
		};

		this.make();
		this.bind_events();
		this.load_current_settings();
	}

	make() {
		this.$content = $(this.wrapper).find('.layout-main-section');
		this.$content.html(this.get_html());
	}

	get_html() {
		return `
			<div class="wallee-wizard-container">
				<!-- Header -->
				<div class="wallee-wizard-header">
					<h1>${__('Wallee Payment Integration')}</h1>
					<p>${__('Configure your Wallee account to accept payments in your webshop and POS')}</p>
				</div>

				<!-- Progress Bar -->
				<div class="wallee-progress-container">
					<div class="wallee-progress-bar">
						<div class="wallee-progress-step active" data-step="1">
							<div class="wallee-step-circle">1</div>
							<div class="wallee-step-label">${__('Account')}</div>
						</div>
						<div class="wallee-progress-step" data-step="2">
							<div class="wallee-step-circle">2</div>
							<div class="wallee-step-label">${__('Space')}</div>
						</div>
						<div class="wallee-progress-step" data-step="3">
							<div class="wallee-step-circle">3</div>
							<div class="wallee-step-label">${__('App User')}</div>
						</div>
						<div class="wallee-progress-step" data-step="4">
							<div class="wallee-step-circle">4</div>
							<div class="wallee-step-label">${__('Roles')}</div>
						</div>
						<div class="wallee-progress-step" data-step="5">
							<div class="wallee-step-circle">5</div>
							<div class="wallee-step-label">${__('Test')}</div>
						</div>
					</div>
				</div>

				<!-- Step 1: Wallee Account -->
				<div class="wallee-step-content active" data-step="1">
					<div class="wallee-card">
						<div class="wallee-card-header">
							<span class="icon">🏦</span>
							<h3>${__('Connect to Wallee')}</h3>
						</div>

						<div class="wallee-instructions">
							<h4>${__('Getting Started')}</h4>
							<p style="margin: 0; font-size: 13px;">${__('Find your Wallee Account ID:')}</p>
						</div>

						<div class="config-help-steps">
							<div class="help-step" data-step="1">
								<span class="step-number">1</span>
								<span class="step-text">${__('Go to app-wallee.com and log in to your account')}</span>
								<a href="https://app-wallee.com" target="_blank" class="help-btn">${__('Open Wallee')}</a>
							</div>
							<div class="help-step" data-step="2">
								<span class="step-number">2</span>
								<span class="step-text">${__('Go to Account Selection to see your Account ID next to each account name')}</span>
								<a href="https://app-wallee.com/account/select" target="_blank" class="help-btn">${__('Open')}</a>
							</div>
							<div class="help-step" data-step="3">
								<span class="step-number">3</span>
								<span class="step-text">${__('Or look at the URL when viewing an account: https://app-wallee.com/a/12345/...')}</span>
								<img class="help-img" src="/assets/wallee_integration/images/wallee_account_id_guide.png" alt="Account ID">
							</div>
						</div>

						<div class="wallee-form-group" style="margin-top: 20px;">
							<label>${__('Account ID')} <span class="required">*</span></label>
							<input type="text" id="account_id" placeholder="12345" class="account-id-input" autocomplete="off">
							<div class="help-text">${__('This is used to create Application Users. The Space ID is required for API calls.')}</div>
						</div>
					</div>
				</div>

				<!-- Step 2: Space Selection -->
				<div class="wallee-step-content" data-step="2">
					<div class="wallee-card">
						<div class="wallee-card-header">
							<span class="icon">🌐</span>
							<h3>${__('Select Your Space')}</h3>
						</div>

						<div class="wallee-instructions">
							<h4>${__('Find Your Space ID')}</h4>
							<p style="margin: 0; font-size: 13px;">${__('The Space ID is shown in your Account Dashboard:')}</p>
						</div>

						<div class="config-help-steps">
							<div class="help-step" data-step="1">
								<span class="step-number">1</span>
								<span class="step-text">${__('Open your Account Dashboard')}</span>
								<a href="https://app-wallee.com" target="_blank" class="help-btn" id="open-wallee-spaces-link">${__('Open')}</a>
							</div>
							<div class="help-step" data-step="2">
								<span class="step-number">2</span>
								<span class="step-text">${__('Copy the Space ID shown next to your Space name (e.g. #89359)')}</span>
								<img class="help-img" src="/assets/wallee_integration/images/wallee_space_id_guide.png" alt="Space ID">
							</div>
						</div>

						<div class="wallee-instructions" style="background: var(--blue-50, #eff6ff); border-color: var(--blue-300, #93c5fd); margin-top: 15px;">
							<h4 style="color: var(--blue-700, #1d4ed8);">${__('What is a Space?')}</h4>
							<p style="margin: 0; font-size: 13px; color: var(--text-color);">
								${__('A Space is like a separate environment within your Wallee account. Each Space has its own transactions, payment methods, and configurations. Typically you have one Space per business or per country.')}
							</p>
						</div>

						<div class="wallee-form-group" style="margin-top: 20px;">
							<label>${__('Space ID')} <span class="required">*</span></label>
							<input type="text" id="space_id" placeholder="98765" class="space-id-input" autocomplete="off">
							<div class="help-text">${__('The ID of the Space where transactions will be processed')}</div>
						</div>
					</div>
				</div>

				<!-- Step 3: Application User -->
				<div class="wallee-step-content" data-step="3">
					<div class="wallee-card">
						<div class="wallee-card-header">
							<span class="icon">👤</span>
							<h3>${__('Create Application User')}</h3>
						</div>

						<div class="wallee-instructions">
							<h4>${__('Create an Application User for API Access')}</h4>
							<p style="margin: 0; font-size: 13px;">${__('Follow these steps in Wallee to create an Application User:')}</p>
						</div>

						<div class="config-help-steps">
							<div class="help-step" data-step="1">
								<span class="step-number">1</span>
								<span class="step-text">${__('In Wallee, go to Account → Users → Application Users')}</span>
								<a href="https://app-wallee.com" target="_blank" class="help-btn" id="open-app-users-link">${__('Open')}</a>
							</div>
							<div class="help-step" data-step="2">
								<span class="step-number">2</span>
								<span class="step-text">${__('Click "Create" to add a new Application User')}</span>
							</div>
							<div class="help-step" data-step="3">
								<span class="step-number">3</span>
								<span class="step-text">${__('Give it a name like "Neoffice" and save')}</span>
							</div>
							<div class="help-step" data-step="4">
								<span class="step-number">4</span>
								<span class="step-text">${__('Click on the user to view its details and note the User ID (e.g. #67890)')}</span>
								<img class="help-img" src="/assets/wallee_integration/images/wallee_page_user_app.png" alt="User ID">
							</div>
							<div class="help-step" data-step="5">
								<span class="step-number">5</span>
								<span class="step-text">${__('Click "Generate a new key" and copy it immediately - it will only be shown once!')}</span>
							</div>
						</div>

						<div class="wallee-form-group" style="margin-top: 20px;">
							<label>${__('User ID')} <span class="required">*</span></label>
							<input type="text" id="user_id" placeholder="67890" class="user-id-input" autocomplete="off">
							<div class="help-text">${__('The ID of your Application User (shown next to the name)')}</div>
						</div>

						<div class="wallee-form-group">
							<label>${__('Authentication Key')} <span class="required">*</span></label>
							<input type="password" id="authentication_key" placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" class="auth-key-input" autocomplete="new-password">
							<div class="help-text">${__('The secret key generated - copy it before closing the dialog!')}</div>
						</div>
					</div>
				</div>

				<!-- Step 4: Assign Roles -->
				<div class="wallee-step-content" data-step="4">
					<div class="wallee-card">
						<div class="wallee-card-header">
							<span class="icon">🔐</span>
							<h3>${__('Assign Permissions')}</h3>
						</div>

						<div class="wallee-instructions">
							<h4>${__('Assign the Account Admin Role')}</h4>
							<p style="margin: 0; font-size: 13px;">${__('Give your Application User the necessary permissions to create transactions:')}</p>
						</div>

						<div class="config-help-steps">
							<div class="help-step" data-step="1">
								<span class="step-number">1</span>
								<span class="step-text">${__('On the Application User page, find the "Roles" section on the right and click "Manage"')}</span>
								<img class="help-img" src="/assets/wallee_integration/images/wallee_page_user_app.png" alt="Roles section">
							</div>
							<div class="help-step" data-step="2">
								<span class="step-number">2</span>
								<span class="step-text">${__('Click the "+" button next to "Rôles de l\'Account" to add a role')}</span>
								<img class="help-img" src="/assets/wallee_integration/images/wallee_add_role.png" alt="Add role">
							</div>
							<div class="help-step" data-step="3">
								<span class="step-number">3</span>
								<span class="step-text">${__('Select your account in "Contexte", then select "Account Admin (ID: 2)" in "Rôles"')}</span>
								<img class="help-img" src="/assets/wallee_integration/images/wallee_dialog_add_role.png" alt="Select role">
							</div>
							<div class="help-step" data-step="4">
								<span class="step-number">4</span>
								<span class="step-text">${__('Click "Assign roles", then click "Save roles" (blue button at the top). You will need to re-enter your password to confirm.')}</span>
							</div>
						</div>

						<div class="wallee-instructions" style="background: var(--blue-50, #eff6ff); border-color: var(--blue-300, #93c5fd); margin-top: 15px;">
							<h4 style="color: var(--blue-700, #1d4ed8);">${__('Note')}</h4>
							<p style="margin: 0; font-size: 13px; color: var(--text-color);">
								${__('You only need to add the role at the Account level. This automatically grants permissions to all Spaces and Subaccounts.')}
							</p>
						</div>
					</div>
				</div>

				<!-- Step 5: Test & Finish -->
				<div class="wallee-step-content" data-step="5">
					<div class="wallee-card">
						<div class="wallee-card-header">
							<span class="icon">✅</span>
							<h3>${__('Test Connection & Configure')}</h3>
						</div>

						<div class="wallee-summary">
							<div class="wallee-summary-row">
								<span class="label">${__('User ID')}</span>
								<span class="value" id="summary-user-id">-</span>
							</div>
							<div class="wallee-summary-row">
								<span class="label">${__('Space ID')}</span>
								<span class="value" id="summary-space-id">-</span>
							</div>
							<div class="wallee-summary-row">
								<span class="label">${__('Authentication Key')}</span>
								<span class="value" id="summary-auth-key">-</span>
							</div>
							<div class="wallee-summary-row">
								<span class="label">${__('Connection Status')}</span>
								<span class="value pending" id="summary-status">${__('Not tested')}</span>
							</div>
						</div>

						<div style="margin-top: 20px; text-align: center;">
							<button class="wallee-test-btn" id="test-connection-btn">
								<span class="icon">🔌</span>
								<span class="spinner">⏳</span>
								<span class="text">${__('Test Connection')}</span>
							</button>
						</div>

						<div id="connection-status"></div>

						<div id="features-section" style="display: none; margin-top: 30px;">
							<h4 style="margin-bottom: 16px;">${__('Enable Features')}</h4>

							<div class="wallee-feature-list">
								<div class="wallee-feature-item selected" data-feature="webshop">
									<input type="checkbox" id="enable_webshop" checked>
									<div class="feature-info">
										<h4>${__('Webshop Payments')}</h4>
										<p>${__('Accept online payments in your webshop with credit cards')}</p>
									</div>
								</div>
								<div class="wallee-feature-item" data-feature="pos">
									<input type="checkbox" id="enable_pos_terminal">
									<div class="feature-info">
										<h4>${__('POS Terminal')}</h4>
										<p>${__('Use physical payment terminals at point of sale')}</p>
									</div>
								</div>
							</div>

							<div id="webshop-config" style="margin-top: 20px;">
								<div class="wallee-form-group">
									<label>${__('Currency')}</label>
									<select id="currency" class="currency-select">
										<option value="CHF">CHF - Swiss Franc</option>
										<option value="EUR">EUR - Euro</option>
										<option value="USD">USD - US Dollar</option>
									</select>
								</div>
								<div class="wallee-form-group">
									<label>${__('Payment Account')}</label>
									<select id="payment_account" class="payment-account-select">
										<option value="">${__('Select an account...')}</option>
									</select>
									<div class="help-text">${__('Bank or cash account where payments will be recorded')}</div>
								</div>

								<div class="wallee-form-group" id="payment-methods-group" style="display: none;">
									<label>${__('Payment Methods')}</label>
									<div class="help-text" style="margin-bottom: 10px;">${__('Select which payment methods to enable. Each will appear as a separate option at checkout.')}</div>
									<div id="payment-methods-list" class="payment-methods-list">
										<div class="loading-methods">${__('Loading available methods...')}</div>
									</div>
								</div>
							</div>
						</div>
					</div>
				</div>

				<!-- Navigation Buttons -->
				<div class="wallee-wizard-actions">
					<button class="btn btn-secondary" id="prev-btn" style="display: none;">
						← ${__('Previous')}
					</button>
					<div></div>
					<button class="btn btn-primary" id="next-btn">
						${__('Next')} →
					</button>
					<button class="btn btn-primary" id="finish-btn" style="display: none;">
						${__('Finish Setup')} ✓
					</button>
				</div>
			</div>
		`;
	}

	bind_events() {
		const self = this;

		// Navigation buttons
		this.$content.find('#next-btn').on('click', () => this.next_step());
		this.$content.find('#prev-btn').on('click', () => this.prev_step());
		this.$content.find('#finish-btn').on('click', () => this.finish_setup());

		// Test connection
		this.$content.find('#test-connection-btn').on('click', () => this.test_connection());

		// Screenshot click - open dialog with enlarged image
		this.$content.on('click', '.wallee-screenshot', function() {
			const $screenshot = $(this);
			const imgSrc = $screenshot.find('img').attr('src');
			const caption = $screenshot.find('.wallee-screenshot-caption').text();
			if (imgSrc) {
				showHelpImageDialog(imgSrc, null, caption);
			}
		});

		// Help step click - open dialog with step info and image (only if has image)
		this.$content.on('click', '.help-step', function(e) {
			// Don't open dialog if clicking on a button or link
			if ($(e.target).hasClass('help-btn') || $(e.target).closest('.help-btn').length) {
				return;
			}
			const $step = $(this);
			const imgSrc = $step.find('.help-img').attr('src');
			// Only open dialog if there's an image
			if (imgSrc) {
				const stepNumber = $step.data('step');
				const stepText = $step.find('.step-text').text();
				showHelpImageDialog(imgSrc, stepNumber, stepText);
			}
		});

		// Feature checkboxes
		this.$content.find('.wallee-feature-item').on('click', function(e) {
			if (e.target.tagName !== 'INPUT') {
				const checkbox = $(this).find('input[type="checkbox"]');
				checkbox.prop('checked', !checkbox.prop('checked'));
			}
			$(this).toggleClass('selected', $(this).find('input').prop('checked'));

			// Show/hide webshop config
			if ($(this).data('feature') === 'webshop') {
				self.$content.find('#webshop-config').toggle($(this).find('input').prop('checked'));
			}
		});

		// Input change handlers
		this.$content.find('input, select').on('change', function() {
			const field = $(this).attr('id');
			if (field && self.wizardData.hasOwnProperty(field)) {
				self.wizardData[field] = $(this).val();
			}
		});

		// Update Application User link when account_id changes
		this.$content.find('#account_id').on('input', function() {
			self.update_app_user_link();
		});
	}

	update_app_user_link() {
		const accountId = this.$content.find('#account_id').val().trim();
		const link = this.$content.find('#open-app-users-link');

		if (accountId && link.length) {
			const url = `https://app-wallee.com/a/${accountId}/user/application/list`;
			link.attr('href', url);
		}
	}

	update_spaces_link() {
		const accountId = this.$content.find('#account_id').val().trim();
		const link = this.$content.find('#open-wallee-spaces-link');

		if (accountId && link.length) {
			const url = `https://app-wallee.com/a/${accountId}/account/dashboard`;
			link.attr('href', url);
		}
	}

	async load_current_settings() {
		try {
			const settings = await frappe.call({
				method: 'wallee_integration.wallee_integration.page.wallee_setup_wizard.wallee_setup_wizard.get_current_settings'
			});

			if (settings.message) {
				const data = settings.message;
				if (data.user_id) {
					this.wizardData.user_id = data.user_id;
					this.$content.find('#user_id').val(data.user_id);
				}
				if (data.space_id) {
					this.wizardData.space_id = data.space_id;
					this.$content.find('#space_id').val(data.space_id);
				}
				if (data.has_auth_key) {
					this.$content.find('#authentication_key').attr('placeholder', '••••••••••••••••');
					this.wizardData.has_auth_key = true;
				}
			}

			// Load payment accounts
			this.load_payment_accounts();
		} catch (e) {
			console.error('Error loading settings:', e);
		}
	}

	async load_payment_accounts() {
		try {
			const result = await frappe.call({
				method: 'wallee_integration.wallee_integration.page.wallee_setup_wizard.wallee_setup_wizard.get_payment_accounts'
			});

			if (result.message) {
				const $select = this.$content.find('#payment_account');
				result.message.forEach(acc => {
					$select.append(`<option value="${acc.name}">${acc.account_name} (${acc.company})</option>`);
				});
			}
		} catch (e) {
			console.error('Error loading accounts:', e);
		}
	}

	async load_payment_methods() {
		const $group = this.$content.find('#payment-methods-group');
		const $list = this.$content.find('#payment-methods-list');

		try {
			const result = await frappe.call({
				method: 'wallee_integration.wallee_integration.page.wallee_setup_wizard.wallee_setup_wizard.get_wallee_payment_methods'
			});

			if (result.message && result.message.success && result.message.methods.length > 0) {
				this.availablePaymentMethods = result.message.methods;

				let html = '';
				result.message.methods.forEach((method, index) => {
					const isChecked = index === 0 ? 'checked' : ''; // First method checked by default
					html += `
						<div class="payment-method-item ${isChecked ? 'selected' : ''}" data-method-id="${method.id}">
							<input type="checkbox" id="pm_${method.id}" value="${method.id}" ${isChecked}>
							<label for="pm_${method.id}">
								<strong>${method.title}</strong>
								<span class="method-id">ID: ${method.id}</span>
							</label>
						</div>
					`;
				});

				$list.html(html);
				$group.show();

				// Bind click events
				$list.find('.payment-method-item').on('click', function(e) {
					if (e.target.tagName !== 'INPUT') {
						const checkbox = $(this).find('input[type="checkbox"]');
						checkbox.prop('checked', !checkbox.prop('checked'));
					}
					$(this).toggleClass('selected', $(this).find('input').prop('checked'));
				});
			} else {
				// No methods available or error
				$list.html(`<div class="no-methods">${__('No payment methods configured in Wallee. A generic payment gateway will be created.')}</div>`);
				$group.show();
			}
		} catch (e) {
			console.error('Error loading payment methods:', e);
			$list.html(`<div class="error-methods">${__('Could not load payment methods.')}</div>`);
		}
	}

	getSelectedPaymentMethods() {
		const selected = [];
		this.$content.find('#payment-methods-list input:checked').each((i, el) => {
			const methodId = $(el).val();
			const method = this.availablePaymentMethods?.find(m => m.id == methodId);
			if (method) {
				selected.push(method);
			}
		});
		return selected;
	}

	validate_step(step) {
		switch (step) {
			case 1:
				// Account ID is optional but helpful
				return true;

			case 2:
				const spaceId = this.$content.find('#space_id').val().trim();
				if (!spaceId) {
					frappe.msgprint(__('Please enter the Space ID'));
					return false;
				}
				return true;

			case 3:
				const userId = this.$content.find('#user_id').val().trim();
				const authKey = this.$content.find('#authentication_key').val().trim();

				if (!userId) {
					frappe.msgprint(__('Please enter the User ID'));
					return false;
				}
				if (!authKey && !this.wizardData.has_auth_key) {
					frappe.msgprint(__('Please enter the Authentication Key'));
					return false;
				}
				return true;

			case 4:
				// Role assignment step - just informational
				return true;

			case 5:
				return true;
		}
		return true;
	}

	collect_step_data(step) {
		switch (step) {
			case 1:
				this.wizardData.account_id = this.$content.find('#account_id').val().trim();
				break;

			case 2:
				this.wizardData.space_id = this.$content.find('#space_id').val().trim();
				break;

			case 3:
				this.wizardData.user_id = this.$content.find('#user_id').val().trim();
				const authKey = this.$content.find('#authentication_key').val().trim();
				if (authKey) {
					this.wizardData.authentication_key = authKey;
				}
				break;

			case 4:
				// Role step - no data to collect
				break;

			case 5:
				this.wizardData.enable_webshop = this.$content.find('#enable_webshop').prop('checked');
				this.wizardData.enable_pos_terminal = this.$content.find('#enable_pos_terminal').prop('checked');
				this.wizardData.currency = this.$content.find('#currency').val();
				this.wizardData.payment_account = this.$content.find('#payment_account').val();
				break;
		}
	}

	next_step() {
		if (!this.validate_step(this.currentStep)) {
			return;
		}

		this.collect_step_data(this.currentStep);

		if (this.currentStep < this.totalSteps) {
			this.currentStep++;
			this.show_step(this.currentStep);

			// When entering step 2, update the Wallee Spaces link with account ID
			if (this.currentStep === 2) {
				this.update_spaces_link();
			}

			// When entering step 3, update the Application User link
			if (this.currentStep === 3) {
				this.update_app_user_link();
			}

			// Special handling for step 5
			if (this.currentStep === 5) {
				this.update_summary();
				this.save_credentials();
			}
		}
	}

	prev_step() {
		if (this.currentStep > 1) {
			this.currentStep--;
			this.show_step(this.currentStep);
		}
	}

	show_step(step) {
		// Update progress bar
		this.$content.find('.wallee-progress-step').each(function() {
			const stepNum = $(this).data('step');
			$(this).removeClass('active completed');
			if (stepNum < step) {
				$(this).addClass('completed');
			} else if (stepNum === step) {
				$(this).addClass('active');
			}
		});

		// Show/hide step content
		this.$content.find('.wallee-step-content').removeClass('active');
		this.$content.find(`.wallee-step-content[data-step="${step}"]`).addClass('active');

		// Update buttons
		this.$content.find('#prev-btn').toggle(step > 1);
		this.$content.find('#next-btn').toggle(step < this.totalSteps);
		this.$content.find('#finish-btn').toggle(step === this.totalSteps);
	}

	update_summary() {
		this.$content.find('#summary-user-id').text(this.wizardData.user_id || '-');
		this.$content.find('#summary-space-id').text(this.wizardData.space_id || '-');
		this.$content.find('#summary-auth-key').text(
			this.wizardData.authentication_key ? '••••••••' + this.wizardData.authentication_key.slice(-4) : __('(using saved key)')
		);
	}

	async save_credentials() {
		try {
			await frappe.call({
				method: 'wallee_integration.wallee_integration.page.wallee_setup_wizard.wallee_setup_wizard.save_credentials',
				args: {
					user_id: this.wizardData.user_id,
					authentication_key: this.wizardData.authentication_key || '',
					space_id: this.wizardData.space_id
				}
			});
		} catch (e) {
			console.error('Error saving credentials:', e);
		}
	}

	async test_connection() {
		const $btn = this.$content.find('#test-connection-btn');
		const $status = this.$content.find('#connection-status');

		$btn.addClass('loading').prop('disabled', true);
		$status.html('');

		try {
			// First test read connection
			const readResult = await frappe.call({
				method: 'wallee_integration.wallee_integration.page.wallee_setup_wizard.wallee_setup_wizard.test_connection'
			});

			if (!readResult.message.success) {
				this.show_connection_error(readResult.message);
				$btn.removeClass('loading').prop('disabled', false);
				return;
			}

			// Then test write (transaction creation)
			const writeResult = await frappe.call({
				method: 'wallee_integration.wallee_integration.page.wallee_setup_wizard.wallee_setup_wizard.test_transaction_creation'
			});

			if (!writeResult.message.success) {
				this.show_connection_error(writeResult.message, true);
				$btn.removeClass('loading').prop('disabled', false);
				return;
			}

			// Success!
			this.show_connection_success(writeResult.message);
			this.$content.find('#features-section').show();
			this.$content.find('#summary-status')
				.removeClass('pending')
				.addClass('success')
				.text(__('Connected'));

			// Load available payment methods
			this.load_payment_methods();

		} catch (e) {
			$status.html(`
				<div class="wallee-status error">
					<span class="status-icon">❌</span>
					<div class="status-content">
						<h4>${__('Connection Failed')}</h4>
						<p>${e.message || __('An unexpected error occurred')}</p>
					</div>
				</div>
			`);
		}

		$btn.removeClass('loading').prop('disabled', false);
	}

	show_connection_success(data) {
		const $status = this.$content.find('#connection-status');
		$status.html(`
			<div class="wallee-status success">
				<span class="status-icon">✅</span>
				<div class="status-content">
					<h4>${__('Connection Successful!')}</h4>
					<p>${__('Successfully connected to Wallee Space')} #${this.wizardData.space_id}</p>
					<p style="font-size: 12px; margin-top: 8px;">
						${__('Test transaction created:')} #${data.transaction_id}
					</p>
				</div>
			</div>
		`);
	}

	show_connection_error(data, isWriteError = false) {
		const $status = this.$content.find('#connection-status');

		let helpText = '';
		if (data.error_type === 'permission') {
			helpText = `
				<p style="margin-top: 12px; font-size: 12px;">
					<strong>${__('To fix this:')}</strong><br>
					${__('Go back to Step 4 and make sure you assigned the "Account Admin (ID: 2)" role and saved it with your password.')}
				</p>
			`;
		} else if (data.error_type === 'space') {
			helpText = `
				<p style="margin-top: 12px; font-size: 12px;">
					<strong>${__('To fix this:')}</strong><br>
					${__('Go back to Step 2 and verify the Space ID is correct.')}
				</p>
			`;
		} else if (data.error_type === 'auth') {
			helpText = `
				<p style="margin-top: 12px; font-size: 12px;">
					<strong>${__('To fix this:')}</strong><br>
					${__('Go back to Step 3 and check your User ID and Authentication Key.')}
				</p>
			`;
		}

		$status.html(`
			<div class="wallee-status error">
				<span class="status-icon">❌</span>
				<div class="status-content">
					<h4>${isWriteError ? __('Write Permission Error') : __('Connection Failed')}</h4>
					<p>${data.error}</p>
					${helpText}
				</div>
			</div>
		`);

		this.$content.find('#summary-status')
			.removeClass('pending success')
			.addClass('error')
			.text(__('Failed'));
	}

	async finish_setup() {
		this.collect_step_data(5);

		const $btn = this.$content.find('#finish-btn');
		$btn.prop('disabled', true).text(__('Setting up...'));

		try {
			// Save final settings (admin credentials)
			await this.save_credentials();

			// Save feature flags
			await frappe.call({
				method: 'wallee_integration.wallee_integration.page.wallee_setup_wizard.wallee_setup_wizard.save_features',
				args: {
					enable_webshop: this.wizardData.enable_webshop,
					enable_pos_terminal: this.wizardData.enable_pos_terminal
				}
			});

			// Create dedicated Application Users for Webshop/POS (with restricted roles)
			let usersCreated = { webshop: null, pos: null };
			if (this.wizardData.enable_webshop || this.wizardData.enable_pos_terminal) {
				$btn.text(__('Creating dedicated users...'));

				const userResult = await frappe.call({
					method: 'wallee_integration.wallee_integration.page.wallee_setup_wizard.wallee_setup_wizard.create_dedicated_users',
					args: {
						enable_webshop: this.wizardData.enable_webshop,
						enable_pos_terminal: this.wizardData.enable_pos_terminal
					}
				});

				if (userResult.message) {
					usersCreated = userResult.message;

					if (!userResult.message.success) {
						frappe.msgprint({
							title: __('User Creation Warning'),
							message: userResult.message.error || __('Could not create dedicated users. The admin user will be used instead.'),
							indicator: 'orange'
						});
					}
				}
			}

			// Setup webshop Payment Gateway if enabled
			if (this.wizardData.enable_webshop) {
				$btn.text(__('Configuring webshop...'));

				// Get selected payment methods
				const selectedMethods = this.getSelectedPaymentMethods();

				const result = await frappe.call({
					method: 'wallee_integration.wallee_integration.page.wallee_setup_wizard.wallee_setup_wizard.setup_webshop',
					args: {
						currency: this.wizardData.currency,
						payment_account: this.wizardData.payment_account,
						payment_methods: JSON.stringify(selectedMethods)
					}
				});

				if (!result.message.success) {
					frappe.msgprint({
						title: __('Webshop Setup Warning'),
						message: result.message.error,
						indicator: 'orange'
					});
				} else if (result.message.accounts && result.message.accounts.length > 0) {
					// Store created accounts for success message
					usersCreated.payment_accounts = result.message.accounts;
				}
			}

			// Build success message with details
			let successDetails = __('Wallee integration has been configured successfully.');

			if (usersCreated.webshop && usersCreated.webshop.status === 'created') {
				successDetails += '<br><br><b>' + __('Webshop User') + ':</b> ' + usersCreated.webshop.name + ' (ID: ' + usersCreated.webshop.user_id + ')';
			}
			if (usersCreated.pos && usersCreated.pos.status === 'created') {
				successDetails += '<br><b>' + __('POS User') + ':</b> ' + usersCreated.pos.name + ' (ID: ' + usersCreated.pos.user_id + ')';
			}

			if (usersCreated.payment_accounts && usersCreated.payment_accounts.length > 0) {
				successDetails += '<br><br><b>' + __('Payment Methods Created') + ':</b>';
				usersCreated.payment_accounts.forEach(acc => {
					successDetails += '<br>• ' + acc.method_title + ' (' + acc.name + ')';
				});
			}

			successDetails += '<br><br>' + __('You can now accept payments.');

			// Build custom dialog with multiple actions
			const dialog = new frappe.ui.Dialog({
				title: __('Setup Complete!'),
				indicator: 'green',
				fields: [
					{
						fieldtype: 'HTML',
						options: `<div style="margin-bottom: 15px;">${successDetails}</div>`
					}
				]
			});

			// Primary action based on POS Terminal setting
			if (this.wizardData.enable_pos_terminal) {
				dialog.set_primary_action(__('Configure Terminals'), () => {
					window.open(frappe.urllib.get_full_url('/app/wallee-terminal-wizard'), '_blank');
				});

				dialog.set_secondary_action_label(__('Wallee Settings'));
				dialog.$wrapper.find('.btn-modal-secondary').on('click', () => {
					window.open(frappe.urllib.get_full_url('/app/Form/Wallee%20Settings'), '_blank');
				});
			} else {
				dialog.set_primary_action(__('Go to Wallee Settings'), () => {
					window.open(frappe.urllib.get_full_url('/app/Form/Wallee%20Settings'), '_blank');
				});
			}

			// Add "Restart Wizard" button in the footer
			dialog.$wrapper.find('.modal-footer').append(`
				<button class="btn btn-default btn-restart-wizard" style="margin-left: 10px;">
					${__('Restart Wizard')}
				</button>
			`);

			dialog.$wrapper.find('.btn-restart-wizard').on('click', () => {
				dialog.hide();
				window.location.reload();
			});

			dialog.show();

		} catch (e) {
			frappe.msgprint({
				title: __('Setup Error'),
				message: e.message || __('An error occurred during setup'),
				indicator: 'red'
			});
		}

		$btn.prop('disabled', false).text(__('Finish Setup') + ' ✓');
	}
}
