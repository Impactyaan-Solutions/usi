// Copyright (c) 2025, Indusaction and contributors
// For license information, please see license.txt

frappe.ui.form.on('Eligibility Evaluation Result', {
	refresh: function(frm) {
		// Add button to re-evaluate
		if (frm.doc.application) {
			frm.add_custom_button(__('Re-evaluate'), function() {
				frappe.call({
					method: 'usi.api.eligibility.evaluate_eligibility',
					args: {
						application_name: frm.doc.application
					},
					callback: function(r) {
						if (r.message) {
							frappe.show_alert({
								message: __('Re-evaluation completed'),
								indicator: 'green'
							}, 3);
							frm.reload_doc();
						}
					}
				});
			});
		}
		
		// Format JSON fields for better display
		if (frm.doc.evaluation_details) {
			frm.set_df_property('evaluation_details', 'options', 'JSON');
		}
	}
});

