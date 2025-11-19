// Copyright (c) 2025, Indusaction and contributors
// For license information, please see license.txt

frappe.ui.form.on('Grievance Ticket', {
	refresh: function(frm) {
		// Add action buttons based on status
		if (frm.doc.ticket_status === 'Open' || frm.doc.ticket_status === 'In Progress') {
			frm.add_custom_button(__('Resolve'), function() {
				frappe.prompt({
					fieldname: 'resolution_remarks',
					label: __('Resolution Remarks'),
					fieldtype: 'Text',
					reqd: 1
				}, function(values) {
					frm.set_value('resolution_remarks', values.resolution_remarks);
					frm.set_value('ticket_status', 'Resolved');
					frm.set_value('resolved_on', frappe.datetime.now_datetime());
					frm.save();
				});
			}, __('Actions'));
		}
	}
});

