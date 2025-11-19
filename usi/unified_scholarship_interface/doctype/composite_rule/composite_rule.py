# Copyright (c) 2025, Indusaction and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class CompositeRule(Document):
	def validate(self):
		"""Validate composite rule"""
		# Must have at least one child rule
		if not self.child_rules or len(self.child_rules) == 0:
			frappe.throw("At least one child rule is required")
		
		# Validate child rules exist and are active
		for child in self.child_rules:
			if not child.rule:
				frappe.throw("All child rules must have a rule specified")
			
			# Check if rule configuration exists and is active
			rule_config = frappe.get_doc("Scheme Rule Configuration", child.rule)
			if not rule_config.is_active:
				frappe.throw(f"Child rule configuration {child.rule} is not active")
			
			# Check if rule configuration has at least one active rule item
			active_rules = [r for r in rule_config.rules if r.is_active]
			if not active_rules:
				frappe.throw(f"Child rule configuration {child.rule} has no active rules")
	
	def on_update(self):
		"""Compile to Scheme Eligibility Criteria"""
		if self.scheme:
			from usi.engine.rules_engine import compile_scheme_rules
			compile_scheme_rules(self.scheme)

