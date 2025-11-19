# Copyright (c) 2025, Indusaction and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now, add_days


class GrievanceTicket(Document):
	def before_insert(self):
		"""Set created_by, created_on, and SLA deadline"""
		self.created_by = frappe.session.user
		self.created_on = now()
		
		# Set SLA deadline based on level and priority
		# Level 1: 5 days, Level 2: 10 days, Level 3: 15 days
		sla_days = 5
		if "Level 2" in (self.current_level or ""):
			sla_days = 10
		elif "Level 3" in (self.current_level or ""):
			sla_days = 15
		
		# Adjust for priority
		if self.priority == "Urgent":
			sla_days = int(sla_days * 0.7)  # 30% reduction
		elif self.priority == "High":
			sla_days = int(sla_days * 0.85)  # 15% reduction
		
		self.sla_deadline = add_days(now(), sla_days)
	
	def validate(self):
		"""Check SLA breach"""
		if self.sla_deadline and now() > self.sla_deadline:
			if self.ticket_status not in ["Resolved", "Closed"]:
				self.sla_breached = 1
			else:
				self.sla_breached = 0

