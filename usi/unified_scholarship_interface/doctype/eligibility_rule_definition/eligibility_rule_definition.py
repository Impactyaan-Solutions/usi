# Copyright (c) 2025, Indusaction and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now


class EligibilityRuleDefinition(Document):
	def autoname(self):
		"""Generate name from rule_name - make it URL-friendly with unique identifier"""
		if not self.rule_name:
			frappe.throw("Rule Name is required")
		
		# Create a URL-friendly name from rule_name
		import re
		from frappe.utils import now_datetime
		import hashlib
		
		# Convert to lowercase, replace spaces/special chars with hyphens
		base_name = self.rule_name.lower()
		base_name = re.sub(r'[^a-z0-9]+', '-', base_name)
		base_name = base_name.strip('-')
		
		# Ensure base name is not empty
		if not base_name:
			base_name = "rule"
		
		# Generate a short unique identifier (6 characters) from timestamp + rule_name
		# This ensures uniqueness while keeping the name readable
		timestamp = now_datetime()
		unique_string = f"{base_name}-{timestamp.isoformat()}-{frappe.session.user}"
		unique_hash = hashlib.md5(unique_string.encode()).hexdigest()[:6]
		
		# Combine: base-name + short hash
		name = f"{base_name}-{unique_hash}"
		
		# Double-check uniqueness (extremely rare collision protection)
		counter = 1
		original_name = name
		while frappe.db.exists("Eligibility Rule Definition", name):
			# If collision, append counter
			name = f"{base_name}-{unique_hash}-{counter}"
			counter += 1
			# Safety limit - should never reach this
			if counter > 1000:
				# Fallback: use full timestamp
				name = f"{base_name}-{timestamp.strftime('%Y%m%d%H%M%S%f')}"
				break
		
		self.name = name
	
	@property
	def rule_code(self):
		"""Backward compatibility: return name (which is now based on rule_name)"""
		return self.name
	
	def before_insert(self):
		"""Set created_by and created_on, ensure autoname is called"""
		# Ensure autoname has been called (in case it wasn't called automatically)
		# Check if name exists and has the expected format (base-name-hash)
		if not self.name:
			# No name set, call autoname
			self.autoname()
		else:
			# Name exists, check if it has the hash format (ends with 6-char hex)
			# Format should be: base-name-XXXXXX where XXXXXX is 6 hex chars
			name_parts = self.name.split('-')
			if len(name_parts) < 2 or len(name_parts[-1]) != 6:
				# Doesn't match expected format, regenerate
				self.autoname()
			else:
				# Check if last part is hex (6 characters, all hex)
				last_part = name_parts[-1]
				if not all(c in '0123456789abcdef' for c in last_part):
					# Last part is not a hex hash, regenerate
					self.autoname()
		
		self.created_by = frappe.session.user
		self.created_on = now()
	
	def validate(self):
		"""Validate rule definition"""
		# Validate field_name format
		if self.rule_type != "Composite" and self.field_name:
			if "." not in self.field_name:
				frappe.throw("Field Name must be in format 'doctype.fieldname' (e.g., 'applicant.date_of_birth')")
		
		# Validate operator compatibility
		if self.operator in ["between"] and self.value_type == "Static Value":
			try:
				import json
				value = json.loads(self.value) if isinstance(self.value, str) else self.value
				if not isinstance(value, list) or len(value) != 2:
					frappe.throw("For 'between' operator, Value must be a JSON array with 2 elements: [min, max]")
			except:
				frappe.throw("For 'between' operator, Value must be a valid JSON array: [min, max]")
		
		# Validate value_expression if formula type
		if self.value_type == "Formula Expression" and self.value_expression:
			try:
				# Test compile the expression
				compile(self.value_expression, "<string>", "eval")
			except SyntaxError as e:
				frappe.throw(f"Invalid Python expression in Value Expression: {str(e)}")

