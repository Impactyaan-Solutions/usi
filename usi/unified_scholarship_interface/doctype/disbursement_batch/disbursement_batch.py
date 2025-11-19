# Copyright (c) 2025, Indusaction and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now


class DisbursementBatch(Document):
	def before_insert(self):
		"""Set generated_by and generated_on"""
		self.generated_by = frappe.session.user
		self.generated_on = now()
	
	def validate(self):
		"""Calculate total applications and amount"""
		# TODO: Calculate from linked Disbursement Records
		pass

