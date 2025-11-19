# Copyright (c) 2025, Indusaction and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ScholarshipScheme(Document):
	def validate(self):
		"""Validate scheme data"""
		# Validate dates
		if self.start_date and self.end_date:
			if self.start_date >= self.end_date:
				frappe.throw("End Date must be after Start Date")
		
		# Calculate budget remaining
		if self.total_budget:
			self.budget_remaining = self.total_budget - (self.budget_utilized or 0)
	
	def on_update(self):
		"""Update budget calculations"""
		self.calculate_budget_utilization()
	
	def calculate_budget_utilization(self):
		"""Calculate utilized budget from approved applications"""
		# TODO: Calculate from Scholarship Application where status = 'Disbursed'
		# For now, keep it at 0
		utilized = frappe.db.sql("""
			SELECT SUM(sanctioned_amount)
			FROM `tabScholarship Application`
			WHERE scheme = %s
			AND application_status = 'Disbursed'
		""", self.name)
		
		self.budget_utilized = utilized[0][0] if utilized and utilized[0][0] else 0
		self.budget_remaining = self.total_budget - self.budget_utilized
		self.db_update()

