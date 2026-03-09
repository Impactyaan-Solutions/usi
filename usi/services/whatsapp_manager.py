import frappe
import traceback
from usi.services.chat_manager import ChatManager

class WhatsAppManager:
    @classmethod
    def respond_to_whatsapp_message(cls, phone: str, message: str):
        try:
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