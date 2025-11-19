# Copyright (c) 2025, Indusaction and contributors
# For license information, please see license.txt

import frappe
import json
import re
from frappe.utils import getdate, date_diff, today, flt
from datetime import datetime
import logging
import os

# Configure logging to write to a file in Frappe's logs directory
def setup_logger():
	"""Setup logger for rules engine - called lazily to ensure Frappe is initialized"""
	logger = logging.getLogger("usi.rules_engine")
	
	# Only setup if not already configured
	if logger.handlers:
		return logger
		
	try:
		log_dir = frappe.get_site_path("logs")
		if not os.path.exists(log_dir):
			os.makedirs(log_dir)
		
		log_file = os.path.join(log_dir, "rules_engine.log")
		logger.setLevel(logging.INFO)
		
		handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
		handler.setLevel(logging.INFO)
		formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
		handler.setFormatter(formatter)
		logger.addHandler(handler)
		
		# Force flush after each log
		original_emit = handler.emit
		def emit_with_flush(record):
			original_emit(record)
			handler.stream.flush()
		handler.emit = emit_with_flush
	except Exception:
		# If Frappe not initialized or other error, use basic logging
		logging.basicConfig(level=logging.INFO)
	
	return logger

# Get logger instance (will be configured on first use)
logger = None

def get_logger():
	"""Get logger instance, setting it up if needed"""
	global logger
	if logger is None:
		logger = setup_logger()
	return logger

class RulesEngine:
	"""Rules Engine for evaluating eligibility criteria"""
	
	def __init__(self, scheme_name):
		self.scheme = scheme_name
		self.rules = self.load_rules()
	
	def load_rules(self):
		"""Load active rules for the scheme"""
		rules = {
			"critical": [],
			"optional": [],
			"composite": []
		}
		
		# Load scheme rule configurations
		rule_configs = frappe.get_all(
			"Scheme Rule Configuration",
			filters={
				"scheme": self.scheme,
				"is_active": 1
			},
			fields=["name", "is_active", "effective_from", "effective_to"]
		)
		
		# Check effective dates and load rule items
		today_date = today()
		for config_doc in rule_configs:
			config = frappe.get_doc("Scheme Rule Configuration", config_doc.name)
			
			# Check effective dates at config level
			if config.effective_from and getdate(config.effective_from) > getdate(today_date):
				continue
			if config.effective_to and getdate(config.effective_to) < getdate(today_date):
				continue
			
			# Process each rule item in the configuration (sorted by order)
			sorted_rules = sorted(config.rules, key=lambda x: x.rule_order or 0)
			for rule_item in sorted_rules:
				# Check effective dates at rule item level
				if rule_item.effective_from and getdate(rule_item.effective_from) > getdate(today_date):
					continue
				if rule_item.effective_to and getdate(rule_item.effective_to) < getdate(today_date):
					continue
				
				if not rule_item.is_active:
					continue
				
				# Get rule definition
				rule_def = frappe.get_doc("Eligibility Rule Definition", rule_item.rule)
				if not rule_def.is_active:
					continue
				
				# Build rule object
				rule_obj = {
					"rule_id": f"{config.name}-{rule_item.idx}",
					"rule_name": rule_def.rule_name,
					"rule_type": rule_def.rule_type,
					"field_name": rule_def.field_name,
				"operator": rule_item.operator or rule_def.operator,
				"value": self._get_rule_value(rule_item, rule_def),
				"error_message": rule_item.error_message or rule_def.error_message_template or f"Rule {rule_def.rule_name} failed",
				"priority": rule_item.rule_priority,
				"score_weight": rule_item.score_weight or 0,
				"rule_order": rule_item.rule_order or 0
			}
				
				if rule_item.rule_priority == "Critical":
					rules["critical"].append(rule_obj)
				else:
					rules["optional"].append(rule_obj)
		
		# Load composite rules
		composite_rules = frappe.get_all(
			"Composite Rule",
			filters={
				"scheme": self.scheme,
				"is_active": 1
			},
			fields=["*"]
		)
		
		for comp_rule in composite_rules:
			comp_doc = frappe.get_doc("Composite Rule", comp_rule.name)
			rules["composite"].append({
				"rule_id": comp_doc.name,
				"rule_name": comp_doc.composite_rule_name,
				"logic_operator": comp_doc.logic_operator,
				"is_critical": comp_doc.is_critical,
				"child_rules": [cr.rule for cr in comp_doc.child_rules],
				"negate_flags": {cr.rule: cr.negate for cr in comp_doc.child_rules},
				"error_message": comp_doc.error_message or f"Composite rule {comp_doc.composite_rule_name} failed"
			})
		
		return rules
	
	def _get_rule_value(self, rule_item, rule_def):
		"""Get the value to use for rule evaluation"""
		# Use override value if provided
		operator = rule_item.operator or rule_def.operator
		
		if operator == "between":
			if rule_item.value_from and rule_item.value_to:
				return [flt(rule_item.value_from), flt(rule_item.value_to)]
		elif operator in ["in", "not_in"]:
			# For "in" and "not_in" operators, parse value field (comma-separated or JSON array)
			# Try rule_item.value first
			if rule_item.value:
				val_str = str(rule_item.value).strip()
				if val_str:
					try:
						# Try JSON first
						parsed = json.loads(val_str)
						if isinstance(parsed, list):
							get_logger().info(f"_get_rule_value: Parsed value from JSON: {parsed}")
							return parsed
					except:
						# Try comma-separated
						parsed = [v.strip() for v in val_str.split(",") if v.strip()]
						if parsed:
							get_logger().info(f"_get_rule_value: Parsed value from comma-separated: {parsed}")
							return parsed
			# Fall back to rule_def.value
			if rule_def.value:
				val_str = str(rule_def.value).strip()
				if val_str:
					try:
						# Try JSON first
						parsed = json.loads(val_str)
						if isinstance(parsed, list):
							get_logger().info(f"_get_rule_value: Parsed value from rule_def JSON: {parsed}")
							return parsed
					except:
						# Try comma-separated
						parsed = [v.strip() for v in val_str.split(",") if v.strip()]
						if parsed:
							get_logger().info(f"_get_rule_value: Parsed value from rule_def comma-separated: {parsed}")
							return parsed
			# Return empty list if no value found (will cause rule to fail, which is correct)
			get_logger().info(f"_get_rule_value: No value found for 'in'/'not_in' operator in rule {rule_item.rule}")
			return []
		
		# For age operators, ensure value is numeric
		if operator in ["age_greater_than", "age_less_than", "age_between"]:
			# Try rule_item.value first
			if rule_item.value:
				val = str(rule_item.value).strip()
				if val:
					try:
						return flt(val)
					except:
						frappe.log_error(f"_get_rule_value: Could not convert rule_item.value '{val}' to float for operator {operator}", "Rules Engine")
			# Fall back to rule_def.value
			if rule_def.value:
				val = str(rule_def.value).strip()
				if val:
					try:
						return flt(val)
					except:
						frappe.log_error(f"_get_rule_value: Could not convert rule_def.value '{val}' to float for operator {operator}", "Rules Engine")
			frappe.log_error(f"_get_rule_value: No value found for age operator {operator} in rule_item or rule_def", "Rules Engine")
			return None
		
		if rule_item.value:
			return rule_item.value
		
		# Use rule definition value
		if rule_def.value_type == "Formula Expression" and rule_def.value_expression:
			# This would need to be evaluated in context - for now, return as-is
			return rule_def.value_expression
		
		return rule_def.value
	
	def evaluate(self, applicant_data, application_data=None):
		"""Evaluate applicant against all rules"""
		get_logger().info(f"=== Starting evaluation for scheme: {self.scheme} ===")
		get_logger().info(f"Applicant data keys: {list(applicant_data.keys()) if applicant_data else 'None'}")
		
		result = {
			"eligible": True,
			"critical_passed": 0,
			"critical_failed": [],
			"optional_passed": [],
			"optional_failed": [],
			"optional_score": 0,
			"max_optional_score": 0,
			"details": [],
			"proximity_score": 0.0
		}
		
		# Get list of available fields from applicant_data
		available_fields = set(applicant_data.keys()) if applicant_data else set()
		get_logger().info(f"Available fields in applicant_data: {available_fields}")
		
		# Filter rules to only evaluate those for which we have data
		def should_evaluate_rule(rule):
			field_path = rule.get("field_name", "")
			if not field_path:
				return False
			# Parse field path (e.g., "applicant.gender" -> "gender")
			parts = field_path.split(".")
			if len(parts) != 2:
				return False
			doctype, fieldname = parts
			# Only evaluate if field is in applicant_data (for applicant fields)
			if doctype == "applicant":
				return fieldname in available_fields
			# For application fields, check if application_data exists
			elif doctype == "application":
				return application_data is not None and fieldname in (application_data.keys() if application_data else [])
			return False
		
		# Filter critical rules to only those we can evaluate
		evaluable_critical_rules = [r for r in self.rules["critical"] if should_evaluate_rule(r)]
		unevaluable_critical_rules = [r for r in self.rules["critical"] if not should_evaluate_rule(r)]
		
		get_logger().info(f"Total critical rules: {len(self.rules['critical'])}, Evaluable: {len(evaluable_critical_rules)}, Unevaluable: {len(unevaluable_critical_rules)}")
		
		# If there are unevaluable critical rules (rules for fields not provided), mark as ineligible
		# But still evaluate what we can to show partial match
		if unevaluable_critical_rules:
			unevaluable_fields = [r.get("field_name", "") for r in unevaluable_critical_rules]
			get_logger().info(f"Scheme has critical rules for fields not provided: {unevaluable_fields}")
			result["eligible"] = False
			# Extract field names from field paths (e.g., "applicant.gender" -> "gender")
			field_names = []
			for field_path in unevaluable_fields:
				parts = field_path.split(".")
				if len(parts) == 2:
					field_names.append(parts[1])
			result["critical_failed"].append({
				"rule_id": "missing_fields",
				"rule_name": "Missing Required Fields",
				"passed": False,
				"message": f"Additional information required: {', '.join(field_names) if field_names else ', '.join(unevaluable_fields)}"
			})
			# Continue evaluation to show partial match
		
		# Evaluate critical rules (only if all are evaluable)
		for rule in evaluable_critical_rules:
			get_logger().info(f"Evaluating rule: {rule.get('rule_name')}, operator: {rule.get('operator')}")
			rule_result = self.evaluate_rule(rule, applicant_data, application_data)
			result["details"].append(rule_result)
			
			get_logger().info(f"Rule result: {rule.get('rule_name')} - Passed: {rule_result['passed']}")
			
			if not rule_result["passed"]:
				result["eligible"] = False
				result["critical_failed"].append(rule_result)
				get_logger().info(f"Rule FAILED: {rule.get('rule_name')} - {rule_result.get('message', 'No message')}")
			else:
				result["critical_passed"] += 1
				get_logger().info(f"Rule PASSED: {rule.get('rule_name')}")
		
		# Evaluate composite critical rules
		for comp_rule in self.rules["composite"]:
			if comp_rule["is_critical"]:
				comp_result = self.evaluate_composite_rule(comp_rule, applicant_data, application_data)
				result["details"].append(comp_result)
				
				if not comp_result["passed"]:
					result["eligible"] = False
					result["critical_failed"].append(comp_result)
				else:
					result["critical_passed"] += 1
		
		# Evaluate optional rules (evaluate even if critical failed to show partial match)
		# Filter optional rules to only those we can evaluate
		evaluable_optional_rules = [r for r in self.rules["optional"] if should_evaluate_rule(r)]
		for rule in evaluable_optional_rules:
			rule_result = self.evaluate_rule(rule, applicant_data, application_data)
			result["details"].append(rule_result)
			
			if rule_result["passed"]:
				result["optional_passed"].append(rule_result)
				result["optional_score"] += rule.get("score_weight", 0)
			else:
				result["optional_failed"].append(rule_result)
			
			result["max_optional_score"] += rule.get("score_weight", 0)
		
		# Evaluate composite optional rules
		for comp_rule in self.rules["composite"]:
			if not comp_rule["is_critical"]:
				comp_result = self.evaluate_composite_rule(comp_rule, applicant_data, application_data)
				result["details"].append(comp_result)
				
				if comp_result["passed"]:
					result["optional_passed"].append(comp_result)
				else:
					result["optional_failed"].append(comp_result)
		
		# Set totals before calculating proximity
		result["critical_rules_total"] = len(self.rules["critical"]) + len([r for r in self.rules["composite"] if r["is_critical"]])
		
		# Calculate proximity score
		result["proximity_score"] = self.calculate_proximity(result)
		
		return result
	
	def evaluate_rule(self, rule, applicant_data, application_data=None):
		"""Evaluate a single rule"""
		field_value = self.get_field_value(rule["field_name"], applicant_data, application_data)
		operator = rule["operator"]
		expected_value = rule["value"]
		
		get_logger().info(f"evaluate_rule: {rule.get('rule_name')}, field={rule.get('field_name')}, operator={operator}, field_value={field_value}, expected_value={expected_value}, expected_value_type={type(expected_value)}")
		
		# Log rule evaluation details (shortened to avoid truncation)
		if operator in ["age_greater_than", "age_less_than", "age_between"]:
			get_logger().info(f"AGE RULE: {rule.get('rule_name')}, DOB={field_value}, operator={operator}, expected={expected_value}")
			frappe.log_error(
				f"eval: {rule.get('rule_name')[:20]}, op={operator}, val={field_value}, exp={expected_value}",
				"Rules Engine"
			)
		
		# Handle formula expressions
		if isinstance(expected_value, str) and "doc." in expected_value:
			# This is a formula - would need proper evaluation context
			# For now, skip formula evaluation
			expected_value = rule.get("value", "")
		
		passed = self.apply_operator(field_value, operator, expected_value)
		
		# Format error message
		error_message = rule.get("error_message", "")
		if "{field_value}" in error_message:
			error_message = error_message.replace("{field_value}", str(field_value))
		if "{expected_value}" in error_message:
			error_message = error_message.replace("{expected_value}", str(expected_value))
		
		return {
			"rule_id": rule["rule_id"],
			"rule_name": rule["rule_name"],
			"passed": passed,
			"field_value": field_value,
			"expected_value": expected_value,
			"operator": operator,
			"message": error_message if not passed else ""
		}
	
	def evaluate_composite_rule(self, comp_rule, applicant_data, application_data=None):
		"""Evaluate a composite rule"""
		child_results = []
		
		for child_rule_id in comp_rule["child_rules"]:
			# Get the rule configuration
			rule_config = frappe.get_doc("Scheme Rule Configuration", child_rule_id)
			
			# Get the first active rule from the configuration's rules table
			# Note: Composite rules should ideally reference Eligibility Rule Definition directly
			# For now, we'll use the first active rule item
			rule_item = None
			if rule_config.rules and len(rule_config.rules) > 0:
				# Get first active rule item, or first rule if none active
				active_rules = [r for r in rule_config.rules if r.is_active]
				rule_item = active_rules[0] if active_rules else rule_config.rules[0]
			
			if not rule_item or not rule_item.rule:
				# Fallback: if no rule items, skip this child rule
				child_results.append({
					"rule_id": child_rule_id,
					"rule_name": "Unknown Rule",
					"passed": False,
					"message": "Rule configuration has no active rules"
				})
				continue
			
			rule_def = frappe.get_doc("Eligibility Rule Definition", rule_item.rule)
			
			rule_obj = {
				"rule_id": f"{rule_config.name}-{rule_item.idx}",
				"rule_name": rule_def.rule_name,
				"field_name": rule_def.field_name,
				"operator": rule_item.operator or rule_def.operator,
				"value": self._get_rule_value(rule_item, rule_def),
				"error_message": rule_item.error_message or rule_def.error_message_template
			}
			
			child_result = self.evaluate_rule(rule_obj, applicant_data, application_data)
			
			# Apply negation if needed
			if comp_rule["negate_flags"].get(child_rule_id, False):
				child_result["passed"] = not child_result["passed"]
			
			child_results.append(child_result)
		
		# Apply logic operator
		if comp_rule["logic_operator"] == "AND":
			passed = all(r["passed"] for r in child_results)
		else:  # OR
			passed = any(r["passed"] for r in child_results)
		
		return {
			"rule_id": comp_rule["rule_id"],
			"rule_name": comp_rule["rule_name"],
			"passed": passed,
			"child_results": child_results,
			"message": comp_rule["error_message"] if not passed else ""
		}
	
	def get_field_value(self, field_path, applicant_data, application_data=None):
		"""Get field value from applicant or application data"""
		# Parse field path (e.g., "applicant.date_of_birth" or "application.academic_year")
		parts = field_path.split(".")
		if len(parts) != 2:
			return None
		
		doctype, fieldname = parts
		
		if doctype == "applicant":
			return applicant_data.get(fieldname)
		elif doctype == "application" and application_data:
			return application_data.get(fieldname)
		
		return None
	
	def apply_operator(self, field_value, operator, expected_value):
		"""Apply operator to compare values - similar to Frappe's depends_on eval logic"""
		if field_value is None:
			frappe.log_error(f"apply_operator: field_value is None for operator '{operator}'", "Rules Engine")
			return False
		
		operators = {
			"equals": lambda a, b: a == b,
			"not_equals": lambda a, b: a != b,
			"greater_than": lambda a, b: flt(a) > flt(b),
			"less_than": lambda a, b: flt(a) < flt(b),
			"between": lambda a, b: flt(b[0]) <= flt(a) <= flt(b[1]) if isinstance(b, list) and len(b) == 2 else False,
			"in": lambda a, b: a in (b if isinstance(b, list) else [b]),
			"not_in": lambda a, b: a not in (b if isinstance(b, list) else [b]),
			"contains": lambda a, b: str(b) in str(a),
			"age_between": lambda a, b: self.age_between(a, b),
			"age_greater_than": lambda a, b: self._age_greater_than(a, b),
			"age_less_than": lambda a, b: self._age_less_than(a, b),
			"regex": lambda a, b: bool(re.match(b, str(a))) if b else False
		}
		
		if operator in operators:
			try:
				# Handle list values for 'in' and 'not_in'
				if operator in ["in", "not_in"]:
					# Ensure expected_value is a list
					if not isinstance(expected_value, list):
						if isinstance(expected_value, str):
							# Try to parse as JSON array or comma-separated
							try:
								expected_value = json.loads(expected_value)
							except:
								expected_value = [v.strip() for v in expected_value.split(",") if v.strip()]
						else:
							# Convert single value to list
							expected_value = [expected_value] if expected_value is not None else []
					
					# Ensure field_value is a string for comparison
					if field_value is not None:
						field_value = str(field_value).strip()
					
					# Log for debugging
					get_logger().info(f"apply_operator 'in': field_value='{field_value}', expected_value={expected_value}, result={field_value in expected_value}")
				
				result = operators[operator](field_value, expected_value)
				if operator in ["age_greater_than", "age_less_than"]:
					frappe.log_error(f"apply_operator: operator={operator}, field_value={field_value}, expected_value={expected_value}, result={result}", "Rules Engine")
				return result
			except Exception as e:
				frappe.log_error(f"Rule evaluation error for operator '{operator}': {str(e)}\nfield_value={field_value}, expected_value={expected_value}", "Rules Engine")
				return False
		return False
	
	def _age_greater_than(self, date_of_birth, expected_age):
		"""Helper for age_greater_than with logging"""
		age = self.calculate_age(date_of_birth)
		get_logger().info(f"age_greater_than: DOB={date_of_birth}, age={age}, exp={expected_age}")
		expected = flt(expected_age)
		result = age > expected
		# Use shorter log message to avoid truncation
		get_logger().info(f"age_gt: DOB={date_of_birth}, age={age}, exp={expected}, result={result}")
		return result
	
	def _age_less_than(self, date_of_birth, expected_age):
		"""Helper for age_less_than with logging"""
		age = self.calculate_age(date_of_birth)
		get_logger().info(f"age_less_than: DOB={date_of_birth}, age={age}, exp={expected_age}")
		expected = flt(expected_age)
		result = age < expected
		# Use shorter log message to avoid truncation
		get_logger().info(f"age_lt: DOB={date_of_birth}, age={age}, exp={expected}, result={result}")
		return result
	
	def calculate_age(self, date_of_birth):
		"""Calculate age from date of birth - uses Frappe utils"""
		if not date_of_birth:
			return 0
		
		try:
			# Handle different date formats
			# If it's already a date object, use it directly
			from datetime import date
			if isinstance(date_of_birth, date):
				dob = date_of_birth
			else:
				# Convert string to date - handle DD-MM-YYYY format
				date_str = str(date_of_birth).strip()
				
				# Try parsing DD-MM-YYYY format first (common in Indian context)
				if '-' in date_str and len(date_str.split('-')) == 3:
					parts = date_str.split('-')
					if len(parts[0]) == 2 and len(parts[2]) == 4:
						# Likely DD-MM-YYYY format
						try:
							day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
							from datetime import date
							dob = date(year, month, day)
						except (ValueError, IndexError):
							# Fall back to getdate which handles YYYY-MM-DD
							dob = getdate(date_of_birth)
					else:
						# Try getdate which handles YYYY-MM-DD
						dob = getdate(date_of_birth)
				else:
					# Use Frappe's getdate for standard formats
					dob = getdate(date_of_birth)
			
			today_date = getdate(today())
			days = date_diff(today_date, dob)
			
			if days < 0:
				# Future date - invalid DOB
				return 0
			
			age = days / 365.25
			age_int = int(age)
			return age_int
			
		except Exception as e:
			frappe.log_error(f"calculate_age error for DOB '{date_of_birth}': {str(e)}", "Rules Engine Age Calculation")
			return 0
	
	def age_between(self, date_of_birth, age_range):
		"""Check if age is between min and max"""
		if not date_of_birth or not age_range:
			return False
		
		if isinstance(age_range, str):
			try:
				age_range = json.loads(age_range)
			except:
				return False
		
		if not isinstance(age_range, list) or len(age_range) != 2:
			return False
		
		age = self.calculate_age(date_of_birth)
		return flt(age_range[0]) <= age <= flt(age_range[1])
	
	def calculate_proximity(self, result):
		"""Calculate proximity score (0-1) - how close applicant is to eligibility"""
		if result["eligible"]:
			return 1.0
		
		# Ensure critical_rules_total exists and is valid
		critical_rules_total = result.get("critical_rules_total", 0)
		if critical_rules_total == 0:
			return 0.0
		
		# Calculate based on critical rules passed
		critical_passed = result.get("critical_passed", 0)
		critical_ratio = critical_passed / critical_rules_total
		
		# Add optional score if available
		optional_ratio = 0
		max_optional_score = result.get("max_optional_score", 0)
		if max_optional_score > 0:
			optional_score = result.get("optional_score", 0)
			optional_ratio = optional_score / max_optional_score
		
		# Weighted average (critical is more important)
		return (critical_ratio * 0.8) + (optional_ratio * 0.2)


def compile_scheme_rules(scheme_name):
	"""Compile all rules for a scheme to JSON format (for performance)"""
	try:
		engine = RulesEngine(scheme_name)
		
		# Build compiled rules structure
		compiled = {
			"version": datetime.now().isoformat(),
			"critical_rules": [],
			"optional_rules": [],
			"composite_rules": []
		}
		
		# Sort rules by priority and order
		critical_sorted = sorted(engine.rules["critical"], key=lambda x: x.get("rule_order", 0))
		optional_sorted = sorted(engine.rules["optional"], key=lambda x: x.get("rule_order", 0))
		
		# Compile critical rules
		for rule in critical_sorted:
			compiled["critical_rules"].append({
				"rule_id": rule["rule_id"],
				"rule_name": rule["rule_name"],
				"field_name": rule["field_name"],
				"operator": rule["operator"],
				"value": rule["value"],
				"error_message": rule["error_message"]
			})
		
		# Compile optional rules
		for rule in optional_sorted:
			compiled["optional_rules"].append({
				"rule_id": rule["rule_id"],
				"rule_name": rule["rule_name"],
				"field_name": rule["field_name"],
				"operator": rule["operator"],
				"value": rule["value"],
				"error_message": rule["error_message"],
				"score_weight": rule["score_weight"]
			})
		
		# Compile composite rules
		for comp_rule in engine.rules["composite"]:
			compiled["composite_rules"].append({
				"rule_id": comp_rule["rule_id"],
				"rule_name": comp_rule["rule_name"],
				"logic_operator": comp_rule["logic_operator"],
				"is_critical": comp_rule["is_critical"],
				"child_rules": comp_rule["child_rules"],
				"error_message": comp_rule["error_message"]
			})
		
		# Update Scheme Eligibility Criteria
		criteria_name = frappe.db.get_value(
			"Scheme Eligibility Criteria",
			{"scheme": scheme_name},
			"name"
		)
		
		if criteria_name:
			criteria_doc = frappe.get_doc("Scheme Eligibility Criteria", criteria_name)
			criteria_doc.eligibility_rule_json = json.dumps(compiled, indent=2)
			criteria_doc.save(ignore_permissions=True)
		
		return compiled
	except Exception as e:
		frappe.log_error(f"Error compiling rules: {str(e)}", "Rule Compilation")
		return None

