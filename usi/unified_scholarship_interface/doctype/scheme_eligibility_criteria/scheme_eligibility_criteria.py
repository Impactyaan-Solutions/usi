# Copyright (c) 2025, Indusaction and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now


class SchemeEligibilityCriteria(Document):
	def before_insert(self):
		"""Set created_by and created_on"""
		self.created_by = frappe.session.user
		self.created_on = now()
	
	def validate(self):
		"""Validate eligibility rules JSON"""
		if self.eligibility_rule_json:
			try:
				import json
				if isinstance(self.eligibility_rule_json, str):
					json.loads(self.eligibility_rule_json)
			except:
				frappe.throw("Invalid JSON format in Eligibility Rule JSON")

