# Copyright (c) 2025, Indusaction and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class DisbursementRecord(Document):
	def validate(self):
		"""Auto-fill applicant and scheme from application"""
		if self.application and not self.applicant:
			app = frappe.get_doc("Scholarship Application", self.application)
			self.applicant = app.applicant
			self.scheme = app.scheme
		
		# Auto-generate sanction order number if not set
		if not self.sanction_order_number and self.application:
			self.sanction_order_number = f"SO-{self.application}-{frappe.utils.nowdate().replace('-', '')}"

