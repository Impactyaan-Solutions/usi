// Copyright (c) 2025, Indusaction and contributors
// For license information, please see license.txt

frappe.ui.form.on('Scholarship Application', {
	refresh: function(frm) {
		// Add Re-evaluate Eligibility button (available for all statuses if applicant and scheme are set)
		if (frm.doc.applicant && frm.doc.scheme && !frm.is_new()) {
			frm.add_custom_button(__('Re-evaluate Eligibility'), function() {
				frappe.call({
					method: 'usi.api.eligibility.evaluate_eligibility',
					args: {
						application_name: frm.doc.name
					},
					freeze: true,
					freeze_message: __('Re-evaluating eligibility...'),
					callback: function(r) {
						if (r.message) {
							let result = r.message;
							let message = __('Eligibility Re-evaluation Results:\n\n');
							message += __('Status: ') + (result.eligible ? __('Eligible') : __('Ineligible')) + '\n';
							message += __('Proximity Score: ') + (result.proximity_score * 100).toFixed(1) + '%\n';
							message += __('Critical Rules Passed: ') + result.critical_passed + '/' + result.critical_rules_total + '\n';
							
							if (result.critical_failed && result.critical_failed.length > 0) {
								message += '\n' + __('Failed Rules:') + '\n';
								result.critical_failed.forEach(function(rule) {
									message += '- ' + rule.rule_name + ': ' + (rule.message || '') + '\n';
								});
							}
							
							frappe.msgprint({
								title: __('Eligibility Re-evaluation'),
								message: message,
								indicator: result.eligible ? 'green' : 'orange'
							});
							
							// Reload form to show updated eligibility fields
							frm.reload_doc();
						}
					},
					error: function(r) {
						frappe.msgprint({
							title: __('Error'),
							message: __('Error re-evaluating eligibility: ') + (r.message || 'Unknown error'),
							indicator: 'red'
						});
					}
				});
			}, __('Actions'));
		}
		
		// Add custom buttons based on status
		if (frm.doc.application_status === 'Draft') {
			frm.add_custom_button(__('Check Eligibility'), function() {
				if (!frm.doc.applicant || !frm.doc.scheme) {
					frappe.msgprint(__('Please select Applicant and Scheme first'));
					return;
				}
				
				frappe.call({
					method: 'usi.api.eligibility.evaluate_eligibility',
					args: {
						application_name: frm.doc.name
					},
					callback: function(r) {
						if (r.message) {
							let result = r.message;
							let message = __('Eligibility Check Results:\n\n');
							message += __('Status: ') + (result.eligible ? __('Eligible') : __('Ineligible')) + '\n';
							message += __('Proximity Score: ') + (result.proximity_score * 100).toFixed(1) + '%\n';
							message += __('Critical Rules Passed: ') + result.critical_passed + '/' + result.critical_rules_total + '\n';
							
							if (result.critical_failed && result.critical_failed.length > 0) {
								message += '\n' + __('Failed Rules:') + '\n';
								result.critical_failed.forEach(function(rule) {
									message += '- ' + rule.rule_name + ': ' + (rule.message || '') + '\n';
								});
							}
							
							frappe.msgprint({
								title: __('Eligibility Check'),
								message: message,
								indicator: result.eligible ? 'green' : 'orange'
							});
							
							// Reload form to show updated eligibility fields
							frm.reload_doc();
						}
					}
				});
			}, __('Actions'));
			
			frm.add_custom_button(__('Submit Application'), function() {
				frappe.confirm(
					__('Are you sure you want to submit this application?'),
					function() {
						frm.set_value('application_status', 'Submitted');
						frm.save();
					}
				);
			});
		}
		
		if (frm.doc.application_status === 'Under Verification') {
			frm.add_custom_button(__('Approve'), function() {
				frm.set_value('application_status', 'Approved');
				frm.save();
			}, __('Actions'));
			
			frm.add_custom_button(__('Reject'), function() {
				frappe.prompt({
					fieldname: 'rejection_reason',
					label: __('Rejection Reason'),
					fieldtype: 'Text',
					reqd: 1
				}, function(values) {
					frm.set_value('rejection_reason', values.rejection_reason);
					frm.set_value('application_status', 'Rejected');
					frm.save();
				});
			}, __('Actions'));
		}
		
		// Show eligibility status indicator
		if (frm.doc.eligibility_status) {
			let indicator = 'gray';
			if (frm.doc.eligibility_status === 'Eligible') {
				indicator = 'green';
			} else if (frm.doc.eligibility_status === 'Ineligible') {
				indicator = 'red';
			} else if (frm.doc.eligibility_status === 'Pending Clarification') {
				indicator = 'orange';
			}
			
			frm.dashboard.add_indicator(__('Eligibility: ') + frm.doc.eligibility_status, indicator);
		}
	},
	
	applicant: function(frm) {
		// Auto-fill some fields from applicant
		if (frm.doc.applicant) {
			frappe.db.get_doc('Applicant', frm.doc.applicant)
				.then(doc => {
					// Can auto-fill institution if applicant has current institution
				});
		}
	},
	
	scheme: function(frm) {
		// Load scheme details
		if (frm.doc.scheme) {
			frappe.db.get_doc('Scholarship Scheme', frm.doc.scheme)
				.then(doc => {
					// Can set default applied_amount from scheme
				});
		}
	}
});

