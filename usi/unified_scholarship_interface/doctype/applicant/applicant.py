# Copyright (c) 2025, Indusaction and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class Applicant(Document):
	def validate(self):
		"""Validate applicant data"""
		# Validate Aadhaar number format
		if self.aadhaar_number and len(self.aadhaar_number) != 12:
			frappe.throw("Aadhaar Number must be 12 digits")
		
		# Validate mobile number
		if self.mobile_number and len(self.mobile_number) != 10:
			frappe.throw("Mobile Number must be 10 digits")
		
		# Validate email format
		if self.email and "@" not in self.email:
			frappe.throw("Please enter a valid email address")
	
	def on_update(self):
		"""Update last sync date if synced from external source"""
		if self.data_synced_from and self.data_synced_from != "Manual":
			self.last_sync_date = frappe.utils.now()
