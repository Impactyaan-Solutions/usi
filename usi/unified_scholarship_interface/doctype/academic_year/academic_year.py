# Copyright (c) 2025, Indusaction and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class AcademicYear(Document):
	def validate(self):
		"""Validate academic year dates"""
		if self.start_date and self.end_date:
			if self.start_date >= self.end_date:
				frappe.throw("End Date must be after Start Date")
		
		# Check for overlapping academic years if active
		if self.is_active:
			overlapping = frappe.db.sql("""
				SELECT name, academic_year
				FROM `tabAcademic Year`
				WHERE name != %s
				AND is_active = 1
				AND (
					(start_date <= %s AND end_date >= %s)
					OR (start_date <= %s AND end_date >= %s)
					OR (start_date >= %s AND end_date <= %s)
				)
			""", (self.name, self.start_date, self.start_date, self.end_date, self.end_date, self.start_date, self.end_date))
			
			if overlapping:
				frappe.throw(f"Active Academic Year {overlapping[0][1]} already exists for this period")

