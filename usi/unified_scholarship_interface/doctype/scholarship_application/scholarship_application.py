# Copyright (c) 2025, Indusaction and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now


class ScholarshipApplication(Document):
	def validate(self):
		"""Validate application data"""
		# Set submitted_on when status changes to Submitted
		if self.application_status == "Submitted" and not self.submitted_on:
			self.submitted_on = now()
		
		# Validate scheme is published
		if self.scheme:
			scheme = frappe.get_doc("Scholarship Scheme", self.scheme)
			if scheme.status != "Published":
				frappe.throw(f"Scheme {scheme.scheme_name} is not published. Cannot submit application.")
	
	def before_save(self):
		"""Auto-generate application number if not set"""
		if not self.application_number:
			# Will be set by naming series
			pass
	
	def on_submit(self):
		"""Handle application submission"""
		if self.application_status != "Submitted":
			frappe.throw("Application status must be 'Submitted' to submit the document")
		
		self.submitted_on = now()
		# Trigger eligibility check
		self.check_eligibility()
		# TODO: Send notifications
	
	def check_eligibility(self):
		"""Check eligibility using rules engine"""
		try:
			from usi.api.eligibility import evaluate_eligibility
			
			result = evaluate_eligibility(application_name=self.name)
			
			# Update eligibility fields
			self.eligibility_status = "Eligible" if result.get("eligible", False) else "Ineligible"
			self.eligibility_score = result.get("proximity_score", 0)
			
			# Store remarks
			if result.get("critical_failed"):
				failed_rules = [r.get("rule_name", "") for r in result.get("critical_failed", [])]
				self.eligibility_remarks = f"Failed critical rules: {', '.join(failed_rules)}"
			elif result.get("eligible"):
				self.eligibility_remarks = "All eligibility criteria met"
			else:
				self.eligibility_remarks = "Eligibility check completed"
			
			# Get rule version
			criteria = frappe.db.get_value(
				"Scheme Eligibility Criteria",
				{"scheme": self.scheme, "is_active": 1},
				"rule_version"
			)
			self.eligibility_version = criteria or "1.0"
			
		except Exception as e:
			frappe.log_error(frappe.get_traceback(), "Eligibility Check Error")
			self.eligibility_status = "Pending Clarification"
			self.eligibility_remarks = f"Error checking eligibility: {str(e)}"
	
	def on_update_after_submit(self):
		"""Handle status changes after submission"""
		# Track status changes for audit
		pass

