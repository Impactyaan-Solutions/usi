# Copyright (c) 2025, Indusaction and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class SchemeRuleItem(Document):
	def validate(self):
		"""Validate rule item"""
		# Validate effective dates
		if self.effective_from and self.effective_to:
			if self.effective_from > self.effective_to:
				frappe.throw("Effective To date must be after Effective From date")
		
		# Validate value for 'between' operator
		if self.operator == "between":
			if not self.value_from or not self.value_to:
				frappe.throw("For 'between' operator, both Value From and Value To are required")
			if self.value_from >= self.value_to:
				frappe.throw("Value To must be greater than Value From")
		
		# Validate value for 'in' and 'not_in' operators
		if self.operator in ["in", "not_in"]:
			if not self.value or not str(self.value).strip():
				frappe.throw("For 'in' or 'not_in' operator, at least one value must be specified in the Value field (comma-separated)")

