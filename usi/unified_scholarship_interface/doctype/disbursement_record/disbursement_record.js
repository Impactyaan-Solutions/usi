// Copyright (c) 2025, Indusaction and contributors
// For license information, please see license.txt

frappe.ui.form.on('Disbursement Record', {
	application: function(frm) {
		// Auto-fill applicant and scheme from application
		if (frm.doc.application) {
			frappe.db.get_doc('Scholarship Application', frm.doc.application)
				.then(doc => {
					frm.set_value('applicant', doc.applicant);
					frm.set_value('scheme', doc.scheme);
					frm.set_value('disbursement_amount', doc.sanctioned_amount || doc.applied_amount);
				});
		}
	}
});

