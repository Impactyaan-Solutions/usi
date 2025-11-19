// Copyright (c) 2025, Indusaction and contributors
// For license information, please see license.txt

frappe.ui.form.on('Applicant', {
	refresh: function(frm) {
		// Add custom buttons
		frm.add_custom_button(__('View Applications'), function() {
			frappe.set_route('List', 'Scholarship Application', {
				applicant: frm.doc.name
			});
		});
	},
	
	disability_status: function(frm) {
		// Clear disability fields if status is No
		if (frm.doc.disability_status === 'No') {
			frm.set_value('disability_type', '');
			frm.set_value('disability_percentage', 0);
		}
	}
});
