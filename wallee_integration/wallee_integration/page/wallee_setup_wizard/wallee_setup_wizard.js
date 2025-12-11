frappe.pages['wallee-setup-wizard'].on_page_load = function(wrapper) {
	new WalleeSetupWizard(wrapper);
};

class WalleeSetupWizard {
	constructor(wrapper) {
		this.wrapper = wrapper;
		this.page = frappe.ui.make_app_page({
			parent: wrapper,
			title: __('Wallee Setup Wizard'),
			single_column: true
		});

		this.currentStep = 1;
		this.totalSteps = 4;
		this.wizardData = {
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
							<div class="wallee-step-label">${__('Wallee Account')}</div>
						</div>
						<div class="wallee-progress-step" data-step="2">
							<div class="wallee-step-circle">2</div>
							<div class="wallee-step-label">${__('Application User')}</div>
						</div>
						<div class="wallee-progress-step" data-step="3">
							<div class="wallee-step-circle">3</div>
							<div class="wallee-step-label">${__('Space Selection')}</div>
						</div>
						<div class="wallee-progress-step" data-step="4">
							<div class="wallee-step-circle">4</div>
							<div class="wallee-step-label">${__('Test & Finish')}</div>
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
							<ol>
								<li>${__('Go to')} <a href="https://app-wallee.com" target="_blank">app-wallee.com</a> ${__('and log in to your account')}</li>
								<li>${__('Click on')} <strong>Account</strong> ${__('in the left sidebar')}</li>
								<li>${__('Look at the URL in your browser - it should look like:')} <code>https://app-wallee.com/a/<strong>84762</strong>/account/dashboard</code></li>
								<li>${__('The number after')} <code>/a/</code> ${__('is your')} <strong>${__('Account ID')}</strong></li>
							</ol>
						</div>

						<div class="wallee-screenshot">
							<img src="/assets/wallee_integration/images/wallee-account-url.png" alt="Wallee Account URL" onerror="this.parentElement.style.display='none'">
							<div class="wallee-screenshot-caption">${__('Example: Account ID is 84762 in the URL')}</div>
						</div>

						<div class="wallee-form-group">
							<label>${__('Account ID')} <span class="required">*</span></label>
							<input type="text" id="account_id" placeholder="84762" class="account-id-input">
							<div class="help-text">${__('This is used only for reference. The Space ID is required for API calls.')}</div>
						</div>
					</div>
				</div>

				<!-- Step 2: Application User -->
				<div class="wallee-step-content" data-step="2">
					<div class="wallee-card">
						<div class="wallee-card-header">
							<span class="icon">👤</span>
							<h3>${__('Create Application User')}</h3>
						</div>

						<div class="wallee-instructions">
							<h4>${__('Create an Application User for API Access')}</h4>
							<ol>
								<li>${__('In Wallee, go to')} <strong>Account → Users → Application Users</strong></li>
								<li>${__('Click')} <strong>${__('Create')}</strong> ${__('to add a new Application User')}</li>
								<li>${__('Give it a name like')} <code>ERPNext Integration</code></li>
								<li>${__('After creation, click on the user and go to')} <strong>${__('Authentication')}</strong></li>
								<li>${__('Click')} <strong>${__('Create')}</strong> ${__('to generate an Authentication Key')}</li>
								<li><strong>${__('Important:')}</strong> ${__('Copy the key immediately - it will only be shown once!')}</li>
							</ol>
						</div>

						<div class="wallee-instructions" style="background: var(--yellow-50); border-color: var(--yellow-300);">
							<h4 style="color: var(--yellow-700);">${__('Assign Required Permissions')}</h4>
							<ol>
								<li>${__('Still on the Application User page, find the')} <strong>${__('Roles')}</strong> ${__('section')}</li>
								<li>${__('Click')} <strong>${__('Manage')}</strong></li>
								<li>${__('Add the role')} <code>Account Admin (ID: 2)</code></li>
								<li>${__('This role allows creating transactions and managing terminals')}</li>
							</ol>
						</div>

						<div class="wallee-form-group">
							<label>${__('User ID')} <span class="required">*</span></label>
							<input type="text" id="user_id" placeholder="153739" class="user-id-input">
							<div class="help-text">${__('The ID of your Application User (shown in the user list)')}</div>
						</div>

						<div class="wallee-form-group">
							<label>${__('Authentication Key')} <span class="required">*</span></label>
							<input type="password" id="authentication_key" placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" class="auth-key-input">
							<div class="help-text">${__('The secret key generated in the Authentication section')}</div>
						</div>
					</div>
				</div>

				<!-- Step 3: Space Selection -->
				<div class="wallee-step-content" data-step="3">
					<div class="wallee-card">
						<div class="wallee-card-header">
							<span class="icon">🌐</span>
							<h3>${__('Select Your Space')}</h3>
						</div>

						<div class="wallee-instructions">
							<h4>${__('Find Your Space ID')}</h4>
							<ol>
								<li>${__('In Wallee, click on')} <strong>Space</strong> ${__('in the left sidebar')}</li>
								<li>${__('Select the Space you want to use for payments')}</li>
								<li>${__('Look at the URL - it should look like:')} <code>https://app-wallee.com/s/<strong>80320</strong>/space/current/view</code></li>
								<li>${__('The number after')} <code>/s/</code> ${__('is your')} <strong>${__('Space ID')}</strong></li>
							</ol>
						</div>

						<div class="wallee-instructions" style="background: var(--purple-50); border-color: var(--purple-300);">
							<h4 style="color: var(--purple-700);">${__('What is a Space?')}</h4>
							<p style="margin: 0; font-size: 13px; color: var(--text-color);">
								${__('A Space is like a separate environment within your Wallee account. Each Space has its own transactions, payment methods, and configurations. Typically you have one Space per business or per country.')}
							</p>
						</div>

						<div class="wallee-screenshot">
							<img src="/assets/wallee_integration/images/wallee-space-url.png" alt="Wallee Space URL" onerror="this.parentElement.style.display='none'">
							<div class="wallee-screenshot-caption">${__('Example: Space ID is 80320 in the URL')}</div>
						</div>

						<div class="wallee-form-group">
							<label>${__('Space ID')} <span class="required">*</span></label>
							<input type="text" id="space_id" placeholder="80320" class="space-id-input">
							<div class="help-text">${__('The ID of the Space where transactions will be processed')}</div>
						</div>
					</div>
				</div>

				<!-- Step 4: Test & Finish -->
				<div class="wallee-step-content" data-step="4">
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

	validate_step(step) {
		switch (step) {
			case 1:
				// Account ID is optional/informational
				return true;

			case 2:
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

			case 3:
				const spaceId = this.$content.find('#space_id').val().trim();
				if (!spaceId) {
					frappe.msgprint(__('Please enter the Space ID'));
					return false;
				}
				return true;

			case 4:
				return true;
		}
		return true;
	}

	collect_step_data(step) {
		switch (step) {
			case 2:
				this.wizardData.user_id = this.$content.find('#user_id').val().trim();
				const authKey = this.$content.find('#authentication_key').val().trim();
				if (authKey) {
					this.wizardData.authentication_key = authKey;
				}
				break;

			case 3:
				this.wizardData.space_id = this.$content.find('#space_id').val().trim();
				break;

			case 4:
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

			// Special handling for step 4
			if (this.currentStep === 4) {
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
					1. ${__('Go to Wallee → Account → Users → Application Users')}<br>
					2. ${__('Click on your user, then "Manage" in the Roles section')}<br>
					3. ${__('Add the role "Account Admin (ID: 2)"')}<br>
					4. ${__('Save and try again')}
				</p>
			`;
		} else if (data.error_type === 'space') {
			helpText = `
				<p style="margin-top: 12px; font-size: 12px;">
					<strong>${__('To fix this:')}</strong><br>
					${__('Verify the Space ID is correct. Go to Wallee → Space and check the URL for /s/{SPACE_ID}/')}
				</p>
			`;
		} else if (data.error_type === 'auth') {
			helpText = `
				<p style="margin-top: 12px; font-size: 12px;">
					<strong>${__('To fix this:')}</strong><br>
					${__('Check your User ID and Authentication Key. You may need to generate a new key.')}
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
		this.collect_step_data(4);

		const $btn = this.$content.find('#finish-btn');
		$btn.prop('disabled', true).text(__('Setting up...'));

		try {
			// Save final settings
			await this.save_credentials();

			// Setup webshop if enabled
			if (this.wizardData.enable_webshop) {
				const result = await frappe.call({
					method: 'wallee_integration.wallee_integration.page.wallee_setup_wizard.wallee_setup_wizard.setup_webshop',
					args: {
						currency: this.wizardData.currency,
						payment_account: this.wizardData.payment_account
					}
				});

				if (!result.message.success) {
					frappe.msgprint({
						title: __('Webshop Setup Warning'),
						message: result.message.error,
						indicator: 'orange'
					});
				}
			}

			// Success!
			frappe.msgprint({
				title: __('Setup Complete!'),
				message: __('Wallee integration has been configured successfully. You can now accept payments.'),
				indicator: 'green',
				primary_action: {
					label: __('Go to Wallee Settings'),
					action: () => {
						frappe.set_route('Form', 'Wallee Settings');
					}
				}
			});

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
