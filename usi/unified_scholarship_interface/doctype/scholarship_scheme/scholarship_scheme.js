// Copyright (c) 2025, Indusaction and contributors
// For license information, please see license.txt

frappe.ui.form.on('Scholarship Scheme', {
	refresh: function(frm) {
		// Add custom buttons
		if (frm.doc.status === 'Published') {
			frm.add_custom_button(__('View Applications'), function() {
				frappe.set_route('List', 'Scholarship Application', {
					scheme: frm.doc.name
				});
			});
		}
		
		// Add button to view Scheme Rule Configuration
		if (!frm.is_new()) {
			frm.add_custom_button(__('View Rule Configuration'), function() {
				// Check if there are any rule configurations for this scheme
				frappe.call({
					method: 'frappe.client.get_list',
					args: {
						doctype: 'Scheme Rule Configuration',
						filters: {
							scheme: frm.doc.name
						},
						fields: ['name', 'is_active'],
						limit_page_length: 10
					},
					callback: function(r) {
						if (r.message && r.message.length > 0) {
							// If only one configuration, open it directly
							if (r.message.length === 1) {
								frappe.set_route('Form', 'Scheme Rule Configuration', r.message[0].name);
							} else {
								// If multiple, show list filtered by scheme
								frappe.set_route('List', 'Scheme Rule Configuration', {
									scheme: frm.doc.name
								});
							}
						} else {
							frappe.msgprint({
								title: __('No Rule Configuration Found'),
								message: __('No Scheme Rule Configuration found for this scheme. Would you like to create one?'),
								indicator: 'orange',
								primary_action: {
									label: __('Create Rule Configuration'),
									action: function() {
										frappe.new_doc('Scheme Rule Configuration', {
											scheme: frm.doc.name
										});
									}
								}
							});
						}
					}
				});
			}, __('Rules'));
		}
	},
	
	start_date: function(frm) {
		if (frm.doc.start_date && frm.doc.end_date) {
			if (frm.doc.start_date >= frm.doc.end_date) {
				frappe.msgprint(__('End Date must be after Start Date'));
				frm.set_value('end_date', '');
			}
		}
	},
	
	end_date: function(frm) {
		if (frm.doc.start_date && frm.doc.end_date) {
			if (frm.doc.start_date >= frm.doc.end_date) {
				frappe.msgprint(__('End Date must be after Start Date'));
				frm.set_value('end_date', '');
			}
		}
	},
	
	total_budget: function(frm) {
		if (frm.doc.total_budget) {
			frm.set_value('budget_remaining', frm.doc.total_budget - (frm.doc.budget_utilized || 0));
		}
	}
});

