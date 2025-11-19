// Copyright (c) 2025, Indusaction and contributors
// For license information, please see license.txt

frappe.ui.form.on('Eligibility Rule Definition', {
	refresh: function(frm) {
		// Populate field_name dropdown with Applicant DocType fields
		if (frm.doc.rule_type && frm.doc.rule_type !== 'Composite') {
			frappe.model.with_doctype('Applicant', function() {
				let fields = frappe.meta.get_docfields('Applicant');
				let field_map = {}; // Map label to value
				let options = [];
				
				// Filter out system fields and add "applicant." prefix with labels
				fields.forEach(function(field) {
					// Skip system fields, section breaks, column breaks, etc.
					if (field.fieldtype && 
						!['Section Break', 'Column Break', 'Tab Break', 'HTML', 'Button'].includes(field.fieldtype) &&
						field.fieldname &&
						!field.fieldname.startsWith('_') &&
						field.fieldname !== 'name' &&
						field.fieldname !== 'owner' &&
						field.fieldname !== 'creation' &&
						field.fieldname !== 'modified' &&
						field.fieldname !== 'modified_by' &&
						field.fieldname !== 'docstatus') {
						// Get field label (use label if available, otherwise use fieldname formatted)
						let label = field.label || frappe.unscrub(field.fieldname);
						let value = `applicant.${field.fieldname}`;
						
						// Store mapping
						field_map[label] = value;
						options.push({
							value: value,
							label: label
						});
					}
				});
				
				// Sort by label
				options.sort(function(a, b) {
					return a.label.localeCompare(b.label);
				});
				
				// Store field map for later use
				frm.field_name_map = field_map;
				
				// Create options string with only labels (for display)
				let options_string = options.map(function(opt) {
					return opt.label;
				}).join('\n');
				
				// Update field options to show only labels
				frm.set_df_property('field_name', 'options', options_string);
				
				// If field already has a value, find and set the corresponding label for display
				if (frm.doc.field_name && frm.doc.field_name.startsWith('applicant.')) {
					let matching_option = options.find(function(opt) {
						return opt.value === frm.doc.field_name;
					});
					if (matching_option) {
						// Update the input to show label, but keep the value in doc
						// Use setTimeout to avoid triggering change detection
						setTimeout(function() {
							if (frm.fields_dict.field_name && frm.fields_dict.field_name.$input) {
								frm.fields_dict.field_name.$input.val(matching_option.label);
								// Don't mark as dirty
								frm.dirty = false;
							}
						}, 100);
					}
				}
			});
		}
		
		// Add custom buttons
		if (!frm.is_new()) {
			frm.add_custom_button(__('Test Rule'), function() {
				frappe.prompt([
					{
						fieldname: 'test_data',
						label: __('Test Data (JSON)'),
						fieldtype: 'Code',
						options: 'JSON',
						description: __('Enter JSON object with field values to test')
					}
				], function(data) {
					frappe.call({
						method: 'usi.api.eligibility.test_rule',
						args: {
							rule_name: frm.doc.name,
							test_data: JSON.parse(data.test_data)
						},
						callback: function(r) {
							if (r.message && r.message.passed) {
								frappe.show_alert({
									message: __('Rule passed!'),
									indicator: 'green'
								}, 5);
							} else {
								frappe.show_alert({
									message: __('Rule failed: ' + (r.message?.message || 'Unknown error')),
									indicator: 'red'
								}, 5);
							}
						}
					});
				}, __('Test Rule'), __('Test'));
			});
		}
	},
	
	rule_type: function(frm) {
		// Clear field-specific fields when rule type changes
		if (frm.doc.rule_type === 'Composite') {
			frm.set_value('field_name', '');
			frm.set_value('operator', '');
			frm.set_value('value', '');
		} else {
			// Reload field options when rule type changes to non-Composite
			frm.trigger('refresh');
		}
	},
	
	operator: function(frm) {
		// Show hint for 'between' operator
		if (frm.doc.operator === 'between') {
			frappe.show_alert({
				message: __('For "between" operator, use JSON array format: [min, max]'),
				indicator: 'blue'
			}, 3);
		}
	},
	
	field_name: function(frm) {
		// When field is selected, keep the label in the field
		// We'll convert it to value only in before_save
		// This prevents "Not Saved" from appearing unnecessarily
		// The field_name handler doesn't need to do anything here
		// since we're keeping the label as-is until save
	},
	
	onload: function(frm) {
		// On form load, if field_name exists, convert it to label for display
		if (frm.doc.field_name && frm.doc.field_name.startsWith('applicant.')) {
			frappe.model.with_doctype('Applicant', function() {
				let fields = frappe.meta.get_docfields('Applicant');
				let fieldname = frm.doc.field_name.replace('applicant.', '');
				let matching_field = fields.find(function(f) {
					return f.fieldname === fieldname;
				});
				if (matching_field) {
					let label = matching_field.label || frappe.unscrub(fieldname);
					// Store the mapping
					if (!frm.field_name_map) {
						frm.field_name_map = {};
					}
					frm.field_name_map[label] = frm.doc.field_name;
					// Update the field to show label (but keep value in doc)
					// We'll handle this in before_save
				}
			});
		}
	},
	
	before_save: function(frm) {
		// Before saving, convert label to field value if needed
		if (frm.doc.field_name && frm.field_name_map && !frm.doc.field_name.startsWith('applicant.')) {
			let field_value = frm.field_name_map[frm.doc.field_name];
			if (field_value) {
				// Convert label to value - this happens right before save
				frm.doc.field_name = field_value;
			}
		}
	},
	
	after_save: function(frm) {
		// After save, reload the field options and display label
		// This ensures the form shows the label but has the value stored
		if (frm.doc.field_name && frm.doc.field_name.startsWith('applicant.')) {
			// Trigger refresh to reload field options and display
			setTimeout(function() {
				frm.trigger('refresh');
			}, 200);
		}
	}
});

