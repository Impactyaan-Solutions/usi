// Copyright (c) 2025, Indusaction and contributors
// For license information, please see license.txt

frappe.ui.form.on('Composite Rule', {
	refresh: function(frm) {
		// Add helper to preview rule logic
		if (!frm.is_new() && frm.doc.child_rules && frm.doc.child_rules.length > 0) {
			frm.add_custom_button(__('Preview Logic'), function() {
				let logic = frm.doc.child_rules.map((r, idx) => {
					let prefix = r.negate ? 'NOT ' : '';
					return prefix + r.rule;
				}).join(` ${frm.doc.logic_operator} `);
				
				frappe.msgprint({
					title: __('Rule Logic'),
					message: logic
				});
			});
		}
	}
});

