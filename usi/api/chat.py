from __future__ import annotations
from usi.services.chat_manager import ChatManager
import frappe	

logger = frappe.logger("api", allow_site=True, file_count=50)


@frappe.whitelist(allow_guest=True)
def initate_chat(message: str, session_id: str|None = None):
	return ChatManager.chat(message=message, session_id=session_id).to_custom_response()
	