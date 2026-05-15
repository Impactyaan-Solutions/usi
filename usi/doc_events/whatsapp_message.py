import frappe
from usi.services.whatsapp_manager import WhatsAppManager
import traceback
def respond_to_whatsapp_message(doc, method):
    # only react to incoming messages
    try:
        phone = doc.get("from")
        message = doc.message
        if doc.type != "Incoming" or not message or not phone:
            return 

        frappe.enqueue(
            WhatsAppManager.respond_to_whatsapp_message, 
            phone=phone,
            message=message,
            timeout=120
        )
        return
    except Exception as e:
        frappe.log_error(
            title="Error in respond_to_whatsapp_message",
            message=traceback.format_exc()
        )
        return