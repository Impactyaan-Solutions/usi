# Copyright (c) 2025, Indusaction and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now


class SchemeRuleConfiguration(Document):
	def before_insert(self):
		"""Set created_by, created_on, and rule_version"""
		self.created_by = frappe.session.user
		self.created_on = now()
		self.set_rule_version()
	
	def validate(self):
		"""Validate rule configuration"""
		# Validate effective dates
		if self.effective_from and self.effective_to:
			if self.effective_from > self.effective_to:
				frappe.throw("Effective To date must be after Effective From date")
		
		# Validate rules table
		if not self.rules or len(self.rules) == 0:
			frappe.throw("At least one rule must be added")
		
		# Validate each rule item
		rule_orders = []
		for rule_item in self.rules:
			if not rule_item.rule:
				frappe.throw("All rules must have a Rule selected")
			
			# Check for duplicate rule orders
			if rule_item.rule_order in rule_orders:
				frappe.throw(f"Duplicate rule order {rule_item.rule_order}. Each rule must have a unique order.")
			rule_orders.append(rule_item.rule_order)
	
	def on_update(self):
		"""Update rule version and compile rules to JSON"""
		self.set_rule_version()
		# Auto-compile rules to Scheme Eligibility Criteria
		self.compile_to_scheme_eligibility()
	
	def set_rule_version(self):
		"""Set rule version from rule definitions"""
		if self.rules:
			# Get the latest modified date from all rules
			latest_version = None
			for rule_item in self.rules:
				if rule_item.rule:
					rule_doc = frappe.get_doc("Eligibility Rule Definition", rule_item.rule)
					rule_version = str(rule_doc.modified or rule_doc.created)
					if not latest_version or rule_version > latest_version:
						latest_version = rule_version
			self.rule_version = latest_version or "1.0"
	
	def compile_to_scheme_eligibility(self):
		"""Auto-compile rules to Scheme Eligibility Criteria JSON"""
		if not self.scheme:
			return
		
		try:
			# Get or create Scheme Eligibility Criteria
			criteria_name = frappe.db.get_value(
				"Scheme Eligibility Criteria",
				{"scheme": self.scheme},
				"name"
			)
			
			if not criteria_name:
				# Create new
				criteria_doc = frappe.get_doc({
					"doctype": "Scheme Eligibility Criteria",
					"scheme": self.scheme,
					"is_active": 1
				})
				criteria_doc.insert()
				criteria_name = criteria_doc.name
			
			# Compile all active rules for this scheme
			from usi.engine.rules_engine import compile_scheme_rules
			compile_scheme_rules(self.scheme)
			
		except Exception as e:
			frappe.log_error(f"Error compiling rules: {str(e)}", "Rule Compilation")
			# Don't throw error, just log it

