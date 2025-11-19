// Copyright (c) 2025, Indusaction and contributors
// For license information, please see license.txt

frappe.ui.form.on('Scheme Rule Configuration', {
	refresh: function(frm) {
		// Add button to auto-sort rules by order
		if (frm.doc.rules && frm.doc.rules.length > 0) {
			frm.add_custom_button(__('Sort Rules by Order'), function() {
				let rules = frm.doc.rules || [];
				rules.sort((a, b) => (a.rule_order || 0) - (b.rule_order || 0));
				frm.clear_table('rules');
				rules.forEach((rule, idx) => {
					let row = frm.add_child('rules');
					Object.assign(row, rule);
				});
				frm.refresh_field('rules');
			});
		}
	}
});

// Child table for rules
frappe.ui.form.on('Scheme Rule Item', {
	rule: function(frm, cdt, cdn) {
		// Always load default values from rule definition when rule is selected
		// User can modify these values if needed for this specific scheme
		let row = locals[cdt][cdn];
		if (row.rule) {
			frappe.db.get_doc('Eligibility Rule Definition', row.rule)
				.then(doc => {
					if (doc.rule_type !== 'Composite') {
						// Always populate operator from rule definition (user can override)
						if (doc.operator) {
							frappe.model.set_value(cdt, cdn, 'operator', doc.operator);
						}
						
						// Populate value based on operator type
						if (doc.operator === 'between') {
							// For "between" operator, parse value field (format: [min, max] or "min,max")
							if (doc.value) {
								try {
									// Try parsing as JSON array first
									let parsed = JSON.parse(doc.value);
									if (Array.isArray(parsed) && parsed.length === 2) {
										frappe.model.set_value(cdt, cdn, 'value_from', parseFloat(parsed[0]));
										frappe.model.set_value(cdt, cdn, 'value_to', parseFloat(parsed[1]));
									}
								} catch (e) {
									// Try comma-separated values
									let parts = doc.value.split(',');
									if (parts.length === 2) {
										frappe.model.set_value(cdt, cdn, 'value_from', parseFloat(parts[0].trim()));
										frappe.model.set_value(cdt, cdn, 'value_to', parseFloat(parts[1].trim()));
									}
								}
							}
							// Clear value field for between operator
							frappe.model.set_value(cdt, cdn, 'value', '');
						} else if (doc.operator === 'in' || doc.operator === 'not_in') {
							// For "in" and "not_in" operators, copy value as-is (comma-separated values)
							if (doc.value) {
								frappe.model.set_value(cdt, cdn, 'value', doc.value);
							}
							// Clear value_from and value_to
							frappe.model.set_value(cdt, cdn, 'value_from', '');
							frappe.model.set_value(cdt, cdn, 'value_to', '');
						} else {
							// For other operators, copy value as-is
							if (doc.value) {
								frappe.model.set_value(cdt, cdn, 'value', doc.value);
							}
							// Clear value_from and value_to for other operators
							frappe.model.set_value(cdt, cdn, 'value_from', '');
							frappe.model.set_value(cdt, cdn, 'value_to', '');
						}
						
						// Always populate error message from rule definition (user can override)
						if (doc.error_message_template) {
							frappe.model.set_value(cdt, cdn, 'error_message', doc.error_message_template);
						}
						
						// Set default priority if not set
						if (!row.rule_priority) {
							frappe.model.set_value(cdt, cdn, 'rule_priority', 'Critical');
						}
						
						// Set default is_active if not set
						if (row.is_active === undefined || row.is_active === null) {
							frappe.model.set_value(cdt, cdn, 'is_active', 1);
						}
					}
					frm.refresh_field('rules');
				})
				.catch(err => {
					console.error('Error loading rule definition:', err);
				});
		}
	},
	
	operator: function(frm, cdt, cdn) {
		// Clear value fields when operator changes
		let row = locals[cdt][cdn];
		if (row.operator === 'between') {
			frappe.model.set_value(cdt, cdn, 'value', '');
		} else if (row.operator === 'in' || row.operator === 'not_in') {
			frappe.model.set_value(cdt, cdn, 'value', '');
			frappe.model.set_value(cdt, cdn, 'value_from', '');
			frappe.model.set_value(cdt, cdn, 'value_to', '');
		} else {
			frappe.model.set_value(cdt, cdn, 'value_from', '');
			frappe.model.set_value(cdt, cdn, 'value_to', '');
		}
		frm.refresh_field('rules');
	},
	
	rule_order: function(frm, cdt, cdn) {
		// Auto-increment if not set
		let row = locals[cdt][cdn];
		if (!row.rule_order && frm.doc.rules) {
			let max_order = Math.max(...frm.doc.rules.map(r => r.rule_order || 0), 0);
			frappe.model.set_value(cdt, cdn, 'rule_order', max_order + 1);
		}
	}
});

// Child table for value list
frappe.ui.form.on('Rule Value List Item', {
	value_item: function(frm, cdt, cdn) {
		// Auto-save when value is entered
	}
});

