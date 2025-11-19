// Copyright (c) 2025, Indusaction and contributors
// For license information, please see license.txt

frappe.ui.form.on('Disbursement Batch', {
	refresh: function(frm) {
		if (frm.doc.status === 'Generated') {
			frm.add_custom_button(__('Send to Finance'), function() {
				frm.set_value('status', 'Sent to Finance');
				frm.save();
			});
		}
	}
});

