import frappe
from usi.utils.custom_response import custom_response
@frappe.whitelist(allow_guest=True)
def do():
    return custom_response(message="OK", data={}, status_code=200, error=False)