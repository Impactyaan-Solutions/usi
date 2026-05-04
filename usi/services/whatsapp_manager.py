import frappe
import traceback
from usi.services.chat_manager import ChatManager
import json
class WhatsAppManager:
    @classmethod
    def respond_to_whatsapp_message(cls, phone: str, message: str):
        try:
            if phone == "918408880857":
                WhatsAppManager._initial_greeting()
                return
            result = ChatManager.chat(message=message, mobile_number=phone, channel="WhatsApp")
            if not result.is_success:
                return
            answer = result.data.get("reply")
            if not answer:
                return
            cls.send_whatsapp_message(phone, answer)
        except Exception as e:
            frappe.log_error(
                title="Error in respond_to_whatsapp_message",
                message=traceback.format_exc()
            )
            return

    @classmethod
    def send_whatsapp_message(cls, phone: str, message: str):
        try:
            msg = frappe.get_doc({
                "doctype": "WhatsApp Message",
                "to": phone,
                "content_type": "text",
                "message": message,
                "type": "Outgoing",
            })
            msg.insert(ignore_permissions=True)
            return
        except Exception as e:
            frappe.log_error(
                title="Error in send_whatsapp_message",
                message=traceback.format_exc()
            )
            return
    
    @staticmethod
    def _initial_greeting():
        try:
            msg = frappe.get_doc({
                "doctype": "WhatsApp Message",
                "to": "8408880857",
                "message": "नमस्कार! मैं आपका समाधान साथी हूँ 😊 कृपया एक विकल्प चुनें:\n Hi! I’m your Samadhaan Saathi 😊 Please select one option:",
                "type": "Outgoing",
                "content_type": "interactive",
                "buttons":json.dumps([
                                        {"id": "scholarship", "title": "छात्रवृत्ति (Scholarship)"},
                                        {"id": "pension", "title": "पेंशन (Pension)"}
                                    ])
            })
            msg.insert(ignore_permissions=True)
            return
        except Exception as e:
            frappe.log_error(
                title="Error in _initial_greeting",
                message=traceback.format_exc()
            )
            return