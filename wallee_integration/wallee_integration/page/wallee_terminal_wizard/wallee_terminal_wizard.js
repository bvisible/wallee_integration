frappe.pages['wallee-terminal-wizard'].on_page_load = function(wrapper) {
	new WalleeTerminalWizard(wrapper);
};

// Helper function to show image in dialog with step info
function showHelpImageDialog(imgSrc, stepNumber, stepText) {
	const dialog = new frappe.ui.Dialog({
		title: __('Step {0}', [stepNumber]),
		size: 'large',
		fields: [
			{
				fieldtype: 'HTML',
				options: `
					<div class="help-dialog-content">
						<div class="help-dialog-text">
							<div class="help-dialog-step-badge">${stepNumber}</div>
							<p>${stepText}</p>
						</div>
						<div class="help-dialog-image">
							<img src="${imgSrc}" alt="Step ${stepNumber}">
						</div>
					</div>
					<style>
						.help-dialog-content {
							display: flex;
							flex-direction: column;
							gap: 20px;
						}
						.help-dialog-text {
							display: flex;
							align-items: center;
							gap: 15px;
							padding: 15px;
							background: var(--bg-light-gray);
							border-radius: 8px;
						}
						.help-dialog-step-badge {
							background: var(--primary);
							color: white;
							width: 32px;
							height: 32px;
							border-radius: 50%;
							display: flex;
							align-items: center;
							justify-content: center;
							font-weight: bold;
							flex-shrink: 0;
						}
						.help-dialog-text p {
							margin: 0;
							font-size: 16px;
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
					</style>
				`
			}
		]
	});
	dialog.show();
}

class WalleeTerminalWizard {
	constructor(wrapper) {
		this.wrapper = wrapper;
		this.page = frappe.ui.make_app_page({
			parent: wrapper,
			title: __('Terminal Registration Wizard'),
			single_column: true
		});

		this.currentStep = 1;
		this.totalSteps = 4;
		this.wizardData = {
			configuration: null,
			location: null,
			terminals: []
		};
		this.configurations = [];
		this.locations = [];
		this.createdTerminals = [];
		this.space_id = null;

		this.make();
		this.bind_events();
		this.load_settings().then(() => this.load_data());
	}

	make() {
		this.$content = $(this.wrapper).find('.layout-main-section');
		this.$content.html(this.get_html());
	}

	get_html() {
		return `
			<div class="terminal-wizard-container">
				<!-- Header -->
				<div class="terminal-wizard-header">
					<h1>${__('Terminal Registration')}</h1>
					<p>${__('Register payment terminals for your POS system')}</p>
				</div>

				<!-- Progress Bar -->
				<div class="terminal-progress-container">
					<div class="terminal-progress-bar">
						<div class="terminal-progress-step active" data-step="1">
							<div class="terminal-step-circle">1</div>
							<div class="terminal-step-label">${__('Configuration')}</div>
						</div>
						<div class="terminal-progress-step" data-step="2">
							<div class="terminal-step-circle">2</div>
							<div class="terminal-step-label">${__('Location')}</div>
						</div>
						<div class="terminal-progress-step" data-step="3">
							<div class="terminal-step-circle">3</div>
							<div class="terminal-step-label">${__('Terminals')}</div>
						</div>
						<div class="terminal-progress-step" data-step="4">
							<div class="terminal-step-circle">4</div>
							<div class="terminal-step-label">${__('Summary')}</div>
						</div>
					</div>
				</div>

				<!-- Step 1: Configuration -->
				<div class="terminal-step-content active" data-step="1">
					<div class="terminal-card">
						<div class="terminal-card-header">
							<h3>${__('Terminal Configuration')}</h3>
							<span class="icon">⚙️</span>
						</div>

						<div class="terminal-instructions">
							<p>${__('Select a Terminal Configuration from Wallee. If you don\'t have one yet, click the button below to create one.')}</p>
							<a href="#" class="btn btn-primary btn-sm btn-open-wallee-configs" target="_blank" style="margin-top: 10px;">
								<i class="fa fa-external-link"></i> ${__('Open Wallee Configurations')}
							</a>

							<div class="config-help-steps" style="margin-top: 20px;">
								<p><strong>${__('How to create a configuration:')}</strong></p>
								<div class="help-step" data-step="1" data-text="${__('Select "Physical terminal"')}">
									<span class="step-number">1</span>
									<span class="step-text">${__('Select "Physical terminal"')}</span>
									<img src="/assets/wallee_integration/images/wizard/step1_select_terminal_type.png" class="help-img">
								</div>
								<div class="help-step" data-step="2" data-text="${__('Enter a name for your configuration')}">
									<span class="step-number">2</span>
									<span class="step-text">${__('Enter a name for your configuration')}</span>
									<img src="/assets/wallee_integration/images/wizard/step2_name_configuration.png" class="help-img">
								</div>
								<div class="help-step" data-step="3" data-text="${__('Enable "API Terminal" in the settings')}">
									<span class="step-number">3</span>
									<span class="step-text">${__('Enable "API Terminal" in the settings')}</span>
									<img src="/assets/wallee_integration/images/wizard/step3_enable_api_access.png" class="help-img">
								</div>
								<div class="help-step" data-step="4" data-text="${__('In "Connectors", enable the payment methods you want')}">
									<span class="step-number">4</span>
									<span class="step-text">${__('In "Connectors", enable the payment methods you want')}</span>
									<img src="/assets/wallee_integration/images/wizard/step4_select_connectors.png" class="help-img">
								</div>
								<div class="help-step" data-step="5">
									<span class="step-number">5</span>
									<span class="step-text">${__('Select your configuration in the dropdown below and click "Sync from Wallee"')}</span>
								</div>
							</div>
						</div>

						<div class="terminal-form-section">
							<div class="terminal-form-row">
								<label>${__('Select Configuration')}</label>
								<div class="config-select-wrapper">
									<select id="config_select" class="form-control">
										<option value="">${__('-- Select Configuration --')}</option>
									</select>
									<button class="btn btn-default btn-sm btn-sync-configs">
										<i class="fa fa-refresh"></i> ${__('Sync from Wallee')}
									</button>
								</div>
							</div>
						</div>

						<div class="terminal-divider">
							<span>${__('OR')}</span>
						</div>

						<div class="terminal-import-shortcut">
							<button class="btn btn-default btn-jump-to-import">
								<i class="fa fa-download"></i> ${__('Import existing terminals from Wallee')}
							</button>
							<p class="text-muted">${__('Skip configuration if you already have terminals in Wallee')}</p>
						</div>
					</div>
				</div>

				<!-- Step 2: Location -->
				<div class="terminal-step-content" data-step="2">
					<div class="terminal-card">
						<div class="terminal-card-header">
							<h3>${__('Terminal Location')}</h3>
							<span class="icon">📍</span>
						</div>

						<div class="terminal-instructions">
							<p>${__('Select a Location (Site) from Wallee. If you don\'t have one yet, click the button below to create one.')}</p>
							<a href="#" class="btn btn-primary btn-sm btn-open-wallee-locations" target="_blank" style="margin-top: 10px;">
								<i class="fa fa-external-link"></i> ${__('Open Wallee Locations')}
							</a>

							<div class="config-help-steps" style="margin-top: 20px;">
								<p><strong>${__('How to create a location:')}</strong></p>
								<div class="help-step" data-step="1">
									<span class="step-number">1</span>
									<span class="step-text">${__('Click "Create" to add a new location')}</span>
								</div>
								<div class="help-step" data-step="2">
									<span class="step-number">2</span>
									<span class="step-text">${__('Enter a name for your location (e.g., "Main Store", "Branch Office")')}</span>
								</div>
								<div class="help-step" data-step="3">
									<span class="step-number">3</span>
									<span class="step-text">${__('Select your location in the dropdown below and click "Sync from Wallee"')}</span>
								</div>
							</div>
						</div>

						<div class="terminal-form-section">
							<div class="terminal-form-row">
								<label>${__('Select Location')}</label>
								<div class="location-select-wrapper">
									<select id="location_select" class="form-control">
										<option value="">${__('-- Select Location --')}</option>
									</select>
									<button class="btn btn-default btn-sm btn-sync-locations">
										<i class="fa fa-refresh"></i> ${__('Sync from Wallee')}
									</button>
								</div>
							</div>
						</div>
					</div>
				</div>

				<!-- Step 3: Terminal Creation/Import -->
				<div class="terminal-step-content" data-step="3">
					<div class="terminal-card">
						<div class="terminal-card-header">
							<h3>${__('Terminals')}</h3>
							<span class="icon">💳</span>
						</div>

						<!-- Mode Toggle -->
						<div class="terminal-mode-toggle">
							<button class="btn btn-mode active" data-mode="create">
								<i class="fa fa-plus-circle"></i> ${__('Create New')}
							</button>
							<button class="btn btn-mode" data-mode="import">
								<i class="fa fa-download"></i> ${__('Import Existing')}
							</button>
						</div>

						<!-- Create Mode -->
						<div class="terminal-mode-content active" data-mode="create">
							<div class="terminal-instructions">
								<p>${__('Add the terminals you want to create. You can create multiple terminals at once.')}</p>
								<p><strong>${__('Serial Number')}</strong>: ${__('Optional - Enter the device serial number to link the terminal to the physical device.')}</p>
							</div>

							<div class="terminal-form-section">
								<table class="terminal-table">
									<thead>
										<tr>
											<th>${__('Terminal Name')}</th>
											<th>${__('Serial Number')}</th>
											<th>${__('POS Profile')}</th>
											<th>${__('Warehouse')}</th>
											<th></th>
										</tr>
									</thead>
									<tbody id="terminals_table_body">
									</tbody>
								</table>
								<button class="btn btn-default btn-sm btn-add-terminal">
									<i class="fa fa-plus"></i> ${__('Add Terminal')}
								</button>
							</div>

							<div class="terminal-summary" style="margin-top: 20px;">
								<p><strong>${__('Configuration')}:</strong> <span id="selected_config">-</span></p>
								<p><strong>${__('Location')}:</strong> <span id="selected_location">-</span></p>
							</div>

							<div class="terminal-actions">
								<button class="btn btn-primary btn-lg btn-create-terminals" disabled>
									<i class="fa fa-check"></i> ${__('Create Terminals')}
								</button>
							</div>
						</div>

						<!-- Import Mode -->
						<div class="terminal-mode-content" data-mode="import">
							<div class="terminal-instructions">
								<p>${__('Import terminals that already exist in Wallee but are not yet in ERPNext.')}</p>
								<p>${__('Select the terminals you want to import and optionally assign them to a POS Profile and Warehouse.')}</p>
							</div>

							<div class="terminal-form-section">
								<button class="btn btn-default btn-sm btn-fetch-terminals">
									<i class="fa fa-refresh"></i> ${__('Fetch Terminals from Wallee')}
								</button>

								<div class="import-terminals-container" style="margin-top: 15px;">
									<div class="import-terminals-empty" style="display: none; padding: 20px; text-align: center; color: var(--text-muted);">
										<i class="fa fa-info-circle"></i> ${__('No terminals available for import. All terminals from Wallee are already imported.')}
									</div>
									<table class="terminal-table import-terminals-table" style="display: none;">
										<thead>
											<tr>
												<th style="width: 40px;"><input type="checkbox" id="select_all_terminals"></th>
												<th>${__('Terminal Name')}</th>
												<th>${__('Identifier')}</th>
												<th>${__('Status')}</th>
												<th>${__('POS Profile')}</th>
												<th>${__('Warehouse')}</th>
											</tr>
										</thead>
										<tbody id="import_terminals_table_body">
										</tbody>
									</table>
								</div>
							</div>

							<div class="terminal-actions" style="margin-top: 20px;">
								<button class="btn btn-primary btn-lg btn-import-terminals" disabled>
									<i class="fa fa-download"></i> ${__('Import Selected Terminals')}
								</button>
							</div>
						</div>
					</div>
				</div>

				<!-- Step 4: Summary -->
				<div class="terminal-step-content" data-step="4">
					<div class="terminal-card">
						<div class="terminal-card-header">
							<h3>${__('Registration Complete')}</h3>
							<span class="icon">✅</span>
						</div>

						<div class="terminal-results">
							<table class="terminal-results-table">
								<thead>
									<tr>
										<th>${__('Terminal Name')}</th>
										<th>${__('Terminal ID')}</th>
										<th>${__('Status')}</th>
										<th>${__('Details')}</th>
									</tr>
								</thead>
								<tbody id="results_table_body">
								</tbody>
							</table>
						</div>

						<div class="terminal-instructions" id="activation_instructions" style="display: none;">
							<h4>${__('Device Activation')}</h4>
							<p>${__('For terminals linked to a device, you may need to enter an activation code on the physical terminal.')}</p>
							<p>${__('Go to Wallee Portal → Terminal → Terminals to see the activation codes.')}</p>
						</div>

						<div class="terminal-actions">
							<button class="btn btn-default btn-create-more">
								<i class="fa fa-plus"></i> ${__('Create More Terminals')}
							</button>
							<button class="btn btn-primary btn-finish">
								${__('Finish')}
							</button>
						</div>
					</div>
				</div>

				<!-- Navigation Buttons -->
				<div class="terminal-wizard-nav">
					<button class="btn btn-default btn-prev" style="display: none;">
						<i class="fa fa-arrow-left"></i> ${__('Previous')}
					</button>
					<button class="btn btn-primary btn-next">
						${__('Next')} <i class="fa fa-arrow-right"></i>
					</button>
				</div>
			</div>
		`;
	}

	bind_events() {
		const me = this;

		// Navigation
		this.$content.on('click', '.btn-next', () => this.next_step());
		this.$content.on('click', '.btn-prev', () => this.prev_step());

		// Help step image click - open dialog only if there's an image
		this.$content.on('click', '.help-step', function() {
			const $step = $(this);
			const $img = $step.find('.help-img');
			if ($img.length && $img.attr('src')) {
				const stepNumber = $step.data('step');
				const stepText = $step.find('.step-text').text();
				const imgSrc = $img.attr('src');
				showHelpImageDialog(imgSrc, stepNumber, stepText);
			}
		});

		// Step 1: Configuration
		this.$content.on('click', '.btn-sync-configs', () => this.sync_configurations());
		this.$content.on('change', '#config_select', function() {
			me.wizardData.configuration = $(this).val();
		});

		// Jump to import
		this.$content.on('click', '.btn-jump-to-import', () => this.jump_to_import());

		// Step 2: Location
		this.$content.on('click', '.btn-sync-locations', () => this.sync_locations());
		this.$content.on('change', '#location_select', function() {
			me.wizardData.location = $(this).val();
		});

		// Step 3: Mode Toggle
		this.$content.on('click', '.btn-mode', function() {
			const mode = $(this).data('mode');
			me.switch_terminal_mode(mode);
		});

		// Step 3: Terminals (Create mode)
		this.$content.on('click', '.btn-add-terminal', () => this.add_terminal_row());
		this.$content.on('click', '.btn-remove-terminal', function() {
			$(this).closest('tr').remove();
			me.update_create_button_state();
		});
		this.$content.on('click', '.btn-create-terminals', () => this.create_terminals());
		this.$content.on('input', '#terminals_table_body input', () => this.update_create_button_state());

		// Step 3: Terminals (Import mode)
		this.$content.on('click', '.btn-fetch-terminals', () => this.fetch_existing_terminals());
		this.$content.on('click', '.btn-import-terminals', () => this.import_terminals());
		this.$content.on('change', '#select_all_terminals', function() {
			const checked = $(this).prop('checked');
			me.$content.find('.import-terminal-checkbox').prop('checked', checked);
			me.update_import_button_state();
		});
		this.$content.on('change', '.import-terminal-checkbox', () => this.update_import_button_state());

		// Step 4: Summary
		this.$content.on('click', '.btn-create-more', () => this.reset_wizard());
		this.$content.on('click', '.btn-finish', () => {
			frappe.set_route('List', 'Wallee Payment Terminal');
		});
	}

	jump_to_import() {
		// Go directly to step 3 in import mode
		this.importModeOnly = true;
		this.currentMode = 'import';
		this.go_to_step(3);
		this.switch_terminal_mode('import');
	}

	switch_terminal_mode(mode) {
		this.currentMode = mode;

		// Update button states
		this.$content.find('.btn-mode').removeClass('active');
		this.$content.find(`.btn-mode[data-mode="${mode}"]`).addClass('active');

		// Show/hide mode content
		this.$content.find('.terminal-mode-content').removeClass('active');
		this.$content.find(`.terminal-mode-content[data-mode="${mode}"]`).addClass('active');

		// If switching to import mode, auto-fetch terminals
		if (mode === 'import' && !this.existingTerminalsFetched) {
			this.fetch_existing_terminals();
		}
	}

	fetch_existing_terminals() {
		const me = this;
		frappe.show_alert({ message: __('Fetching terminals from Wallee...'), indicator: 'blue' });

		this.$content.find('.btn-fetch-terminals').prop('disabled', true).html('<i class="fa fa-spinner fa-spin"></i> ' + __('Fetching...'));

		frappe.call({
			method: 'wallee_integration.wallee_integration.page.wallee_terminal_wizard.wallee_terminal_wizard.get_existing_wallee_terminals',
			callback: (r) => {
				if (r.message && r.message.success) {
					me.existingTerminals = r.message.terminals || [];
					me.existingTerminalsFetched = true;
					me.populate_import_table();

					if (me.existingTerminals.length > 0) {
						frappe.show_alert({ message: __("{0} terminals available for import").replace("{0}", me.existingTerminals.length), indicator: 'green' });
					} else {
						frappe.show_alert({ message: __('No terminals available for import'), indicator: 'orange' });
					}
				} else {
					frappe.show_alert({ message: r.message?.error || __('Failed to fetch terminals'), indicator: 'red' });
				}
			},
			always: () => {
				me.$content.find('.btn-fetch-terminals').prop('disabled', false).html('<i class="fa fa-refresh"></i> ' + __('Fetch Terminals from Wallee'));
			}
		});
	}

	populate_import_table() {
		const $tbody = this.$content.find('#import_terminals_table_body');
		const $table = this.$content.find('.import-terminals-table');
		const $empty = this.$content.find('.import-terminals-empty');

		$tbody.empty();

		if (!this.existingTerminals || this.existingTerminals.length === 0) {
			$table.hide();
			$empty.show();
			return;
		}

		$table.show();
		$empty.hide();

		let pos_options = '<option value="">-</option>';
		(this.pos_profiles || []).forEach(p => {
			pos_options += `<option value="${p.name}">${p.name}</option>`;
		});

		let wh_options = '<option value="">-</option>';
		(this.warehouses || []).forEach(w => {
			wh_options += `<option value="${w.name}">${w.name}</option>`;
		});

		this.existingTerminals.forEach(terminal => {
			const statusClass = terminal.state === 'ACTIVE' ? 'text-success' : 'text-muted';
			const statusText = terminal.state === 'ACTIVE' ? __('Active') : __('Inactive');

			$tbody.append(`
				<tr data-terminal-id="${terminal.id}">
					<td><input type="checkbox" class="import-terminal-checkbox" data-id="${terminal.id}"></td>
					<td>
						<strong>${terminal.name || '-'}</strong>
						${terminal.configuration_name ? `<br><small class="text-muted">${terminal.configuration_name}</small>` : ''}
					</td>
					<td><code>${terminal.identifier || '-'}</code></td>
					<td class="${statusClass}">${statusText}</td>
					<td><select class="form-control import-pos-profile">${pos_options}</select></td>
					<td><select class="form-control import-warehouse">${wh_options}</select></td>
				</tr>
			`);
		});

		this.update_import_button_state();
	}

	update_import_button_state() {
		const selectedCount = this.$content.find('.import-terminal-checkbox:checked').length;
		this.$content.find('.btn-import-terminals').prop('disabled', selectedCount === 0);
	}

	import_terminals() {
		const me = this;
		const terminals = [];

		this.$content.find('.import-terminal-checkbox:checked').each(function() {
			const $row = $(this).closest('tr');
			const terminalId = $(this).data('id');
			const terminalData = me.existingTerminals.find(t => t.id == terminalId);

			if (terminalData) {
				terminals.push({
					id: terminalId,
					name: terminalData.name,
					pos_profile: $row.find('.import-pos-profile').val() || null,
					warehouse: $row.find('.import-warehouse').val() || null,
					terminal_type: terminalData.terminal_type,
					terminal_type_id: terminalData.terminal_type_id,
					configuration_version_id: terminalData.configuration_version_id,
					location_version_id: terminalData.location_version_id,
					device_serial_number: terminalData.device_serial_number
				});
			}
		});

		if (!terminals.length) {
			frappe.show_alert({ message: __('Please select at least one terminal'), indicator: 'red' });
			return;
		}

		frappe.show_alert({ message: __('Importing terminals...'), indicator: 'blue' });
		this.$content.find('.btn-import-terminals').prop('disabled', true).html('<i class="fa fa-spinner fa-spin"></i> ' + __('Importing...'));

		frappe.call({
			method: 'wallee_integration.wallee_integration.page.wallee_terminal_wizard.wallee_terminal_wizard.import_terminals',
			args: { terminals: terminals },
			callback: (r) => {
				if (r.message) {
					me.createdTerminals = r.message;
					me.isImportMode = true;
					me.show_results();
					me.go_to_step(4);
				}
			},
			always: () => {
				me.$content.find('.btn-import-terminals').prop('disabled', false).html('<i class="fa fa-download"></i> ' + __('Import Selected Terminals'));
			}
		});
	}

	async load_settings() {
		const r = await frappe.call({
			method: 'frappe.client.get_value',
			args: {
				doctype: 'Wallee Settings',
				fieldname: 'space_id'
			}
		});
		if (r.message) {
			this.space_id = r.message.space_id;
			this.update_wallee_links();
		}
	}

	update_wallee_links() {
		if (this.space_id) {
			this.$content.find('.btn-open-wallee-configs').attr('href',
				`https://app-wallee.com/s/${this.space_id}/payment/terminal/configuration/list`);
			this.$content.find('.btn-open-wallee-locations').attr('href',
				`https://app-wallee.com/s/${this.space_id}/payment/terminal/location/list`);
		}
	}

	load_data() {
		this.load_configurations();
		this.load_locations();
		this.load_pos_profiles();
		this.load_warehouses();
	}

	load_configurations() {
		frappe.call({
			method: 'wallee_integration.wallee_integration.page.wallee_terminal_wizard.wallee_terminal_wizard.get_configurations',
			callback: (r) => {
				if (r.message) {
					this.configurations = r.message;
					this.populate_config_select();
				}
			}
		});
	}

	populate_config_select() {
		const $select = this.$content.find('#config_select');
		$select.find('option:not(:first)').remove();
		this.configurations.forEach(config => {
			$select.append(`<option value="${config.name}">${config.configuration_name} (${config.wallee_configuration_version_id})</option>`);
		});
	}

	load_locations() {
		frappe.call({
			method: 'wallee_integration.wallee_integration.page.wallee_terminal_wizard.wallee_terminal_wizard.get_locations',
			callback: (r) => {
				if (r.message) {
					this.locations = r.message;
					this.populate_location_select();
				}
			}
		});
	}

	populate_location_select() {
		const $select = this.$content.find('#location_select');
		$select.find('option:not(:first)').remove();
		this.locations.forEach(loc => {
			const versionInfo = loc.wallee_location_version_id ? ` (${loc.wallee_location_version_id})` : '';
			$select.append(`<option value="${loc.name}">${loc.location_name}${versionInfo}</option>`);
		});
	}

	load_pos_profiles() {
		frappe.call({
			method: 'frappe.client.get_list',
			args: {
				doctype: 'POS Profile',
				filters: { disabled: 0 },
				fields: ['name']
			},
			callback: (r) => {
				this.pos_profiles = r.message || [];
			}
		});
	}

	load_warehouses() {
		frappe.call({
			method: 'frappe.client.get_list',
			args: {
				doctype: 'Warehouse',
				filters: { is_group: 0 },
				fields: ['name']
			},
			callback: (r) => {
				this.warehouses = r.message || [];
			}
		});
	}

	sync_configurations() {
		frappe.show_alert({ message: __('Syncing configurations from Wallee...'), indicator: 'blue' });
		frappe.call({
			method: 'wallee_integration.wallee_integration.page.wallee_terminal_wizard.wallee_terminal_wizard.sync_configurations_from_wallee',
			callback: (r) => {
				if (r.message && r.message.success) {
					frappe.show_alert({ message: __('Configurations synced successfully'), indicator: 'green' });
					this.load_configurations();
				} else {
					frappe.show_alert({ message: r.message?.error || __('Failed to sync'), indicator: 'red' });
				}
			}
		});
	}

	sync_locations() {
		frappe.show_alert({ message: __('Syncing locations from Wallee...'), indicator: 'blue' });
		frappe.call({
			method: 'wallee_integration.wallee_integration.page.wallee_terminal_wizard.wallee_terminal_wizard.sync_locations_from_wallee',
			callback: (r) => {
				if (r.message && r.message.success) {
					frappe.show_alert({ message: __('Locations synced successfully'), indicator: 'green' });
					this.load_locations();
				} else {
					frappe.show_alert({ message: r.message?.error || __('Failed to sync'), indicator: 'red' });
				}
			}
		});
	}

	add_terminal_row() {
		const $tbody = this.$content.find('#terminals_table_body');
		const row_id = Date.now();

		let pos_options = '<option value="">-</option>';
		(this.pos_profiles || []).forEach(p => {
			pos_options += `<option value="${p.name}">${p.name}</option>`;
		});

		let wh_options = '<option value="">-</option>';
		(this.warehouses || []).forEach(w => {
			wh_options += `<option value="${w.name}">${w.name}</option>`;
		});

		$tbody.append(`
			<tr data-row-id="${row_id}">
				<td><input type="text" class="form-control terminal-name" placeholder="${__('Terminal Name')}" required></td>
				<td><input type="text" class="form-control serial-number" placeholder="${__('Optional')}"></td>
				<td><select class="form-control pos-profile">${pos_options}</select></td>
				<td><select class="form-control warehouse">${wh_options}</select></td>
				<td><button class="btn btn-danger btn-xs btn-remove-terminal"><i class="fa fa-trash"></i></button></td>
			</tr>
		`);

		this.update_create_button_state();
	}

	update_create_button_state() {
		const $rows = this.$content.find('#terminals_table_body tr');
		let hasValidTerminal = false;

		$rows.each(function() {
			const name = $(this).find('.terminal-name').val();
			if (name && name.trim()) {
				hasValidTerminal = true;
			}
		});

		this.$content.find('.btn-create-terminals').prop('disabled', !hasValidTerminal);
	}

	create_terminals() {
		const me = this;
		const terminals = [];

		this.$content.find('#terminals_table_body tr').each(function() {
			const name = $(this).find('.terminal-name').val();
			if (name && name.trim()) {
				terminals.push({
					name: name.trim(),
					serial_number: $(this).find('.serial-number').val() || null,
					pos_profile: $(this).find('.pos-profile').val() || null,
					warehouse: $(this).find('.warehouse').val() || null
				});
			}
		});

		if (!terminals.length) {
			frappe.show_alert({ message: __('Please add at least one terminal'), indicator: 'red' });
			return;
		}

		frappe.show_alert({ message: __('Creating terminals...'), indicator: 'blue' });
		this.$content.find('.btn-create-terminals').prop('disabled', true).html('<i class="fa fa-spinner fa-spin"></i> ' + __('Creating...'));

		frappe.call({
			method: 'wallee_integration.wallee_integration.page.wallee_terminal_wizard.wallee_terminal_wizard.create_terminals',
			args: {
				terminals: terminals,
				configuration: this.wizardData.configuration,
				location: this.wizardData.location
			},
			callback: (r) => {
				if (r.message) {
					me.createdTerminals = r.message;
					me.show_results();
					me.go_to_step(4);
				}
			},
			always: () => {
				this.$content.find('.btn-create-terminals').prop('disabled', false).html('<i class="fa fa-check"></i> ' + __('Create Terminals'));
			}
		});
	}

	show_results() {
		const $tbody = this.$content.find('#results_table_body');
		$tbody.empty();

		let hasLinkedDevices = false;
		const isImport = this.isImportMode;

		// Update header text based on mode
		const $header = this.$content.find('.terminal-step-content[data-step="4"] .terminal-card-header h3');
		if (isImport) {
			$header.text(__('Import Complete'));
		} else {
			$header.text(__('Registration Complete'));
		}

		this.createdTerminals.forEach(terminal => {
			const statusClass = terminal.success ? 'text-success' : 'text-danger';
			const statusIcon = terminal.success ? '✓' : '✗';

			let details;
			if (terminal.success) {
				if (isImport) {
					details = __('Imported successfully');
				} else {
					details = terminal.serial_number ? __('Device linked') : __('Ready to link device');
				}
			} else {
				details = terminal.error;
			}

			if (terminal.serial_number && terminal.success && !isImport) {
				hasLinkedDevices = true;
			}

			const actionText = terminal.success
				? (isImport ? __('Imported') : __('Created'))
				: __('Failed');

			$tbody.append(`
				<tr>
					<td>${terminal.name}</td>
					<td>${terminal.terminal_id || '-'}</td>
					<td class="${statusClass}">${statusIcon} ${actionText}</td>
					<td>${details}</td>
				</tr>
			`);
		});

		if (hasLinkedDevices) {
			this.$content.find('#activation_instructions').show();
		} else {
			this.$content.find('#activation_instructions').hide();
		}
	}

	next_step() {
		if (this.validate_step(this.currentStep)) {
			if (this.currentStep < this.totalSteps) {
				this.go_to_step(this.currentStep + 1);
			}
		}
	}

	prev_step() {
		if (this.currentStep > 1) {
			// If in import-only mode and on step 3, go back to step 1
			if (this.importModeOnly && this.currentStep === 3) {
				this.importModeOnly = false;
				this.go_to_step(1);
			} else {
				this.go_to_step(this.currentStep - 1);
			}
		}
	}

	validate_step(step) {
		switch (step) {
			case 1:
				// Also check select value directly as fallback
				const configVal = this.$content.find('#config_select').val();
				if (configVal) {
					this.wizardData.configuration = configVal;
				}
				if (!this.wizardData.configuration) {
					frappe.show_alert({ message: __('Please select a configuration'), indicator: 'red' });
					return false;
				}
				return true;
			case 2:
				// Also check select value directly as fallback
				const locationVal = this.$content.find('#location_select').val();
				if (locationVal) {
					this.wizardData.location = locationVal;
				}
				if (!this.wizardData.location) {
					frappe.show_alert({ message: __('Please select a location'), indicator: 'red' });
					return false;
				}
				return true;
			case 3:
				// Validation happens on create
				return true;
			default:
				return true;
		}
	}

	go_to_step(step) {
		this.currentStep = step;

		// Update progress bar
		this.$content.find('.terminal-progress-step').each(function() {
			const stepNum = parseInt($(this).data('step'));
			$(this).toggleClass('active', stepNum <= step);
			$(this).toggleClass('completed', stepNum < step);
		});

		// Show/hide step content
		this.$content.find('.terminal-step-content').each(function() {
			$(this).toggleClass('active', parseInt($(this).data('step')) === step);
		});

		// Update navigation
		const showPrev = step > 1 && step < 4;
		const showNext = step < 3 && !this.importModeOnly;
		this.$content.find('.btn-prev').toggle(showPrev);
		this.$content.find('.btn-next').toggle(showNext);

		// Handle step 3 specific logic
		if (step === 3) {
			// If import mode only, hide mode toggle and show only import
			if (this.importModeOnly) {
				this.$content.find('.terminal-mode-toggle').hide();
				this.$content.find('.terminal-mode-content').removeClass('active');
				this.$content.find('.terminal-mode-content[data-mode="import"]').addClass('active');
			} else {
				this.$content.find('.terminal-mode-toggle').show();
				this.update_step3_summary();
				if (this.$content.find('#terminals_table_body tr').length === 0) {
					this.add_terminal_row();
				}
			}
		}
	}

	update_step3_summary() {
		const config = this.configurations.find(c => c.name === this.wizardData.configuration);
		const location = this.locations.find(l => l.name === this.wizardData.location);

		this.$content.find('#selected_config').text(config ? config.configuration_name : '-');
		this.$content.find('#selected_location').text(location ? location.location_name : '-');
	}

	reset_wizard() {
		this.wizardData = {
			configuration: null,
			location: null,
			terminals: []
		};
		this.createdTerminals = [];
		this.existingTerminals = [];
		this.existingTerminalsFetched = false;
		this.isImportMode = false;
		this.importModeOnly = false;
		this.currentMode = 'create';

		this.$content.find('#config_select').val('');
		this.$content.find('#location_select').val('');
		this.$content.find('#terminals_table_body').empty();
		this.$content.find('#import_terminals_table_body').empty();
		this.$content.find('#select_all_terminals').prop('checked', false);

		// Reset mode toggle
		this.$content.find('.terminal-mode-toggle').show();
		this.$content.find('.btn-mode').removeClass('active');
		this.$content.find('.btn-mode[data-mode="create"]').addClass('active');
		this.$content.find('.terminal-mode-content').removeClass('active');
		this.$content.find('.terminal-mode-content[data-mode="create"]').addClass('active');

		this.go_to_step(1);
	}
}
