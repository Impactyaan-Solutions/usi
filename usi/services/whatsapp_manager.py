import frappe
import traceback
from usi.services.chat_manager import ChatManager
import json
from usi.models.chat import ChatSession
from usi.models.result import Result
from frappe.utils import logger

logger.set_log_level("DEBUG")
logger = frappe.logger("api", allow_site=True, file_count=50)
class WhatsAppManager:
    @classmethod
    def respond_to_whatsapp_message(cls, phone: str, message: str):
        try:
            if phone == "918408880857":
                WhatsAppManager.get_answer(phone, message)
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
    def get_answer(phone: str, message: str):
        try:
            logger.info(f"Responding to WhatsApp message: {message}")



            # STEP 1 - check if session exists and needs to be extended or new needs to be created
            chat_session:ChatSession = ChatManager.get_or_create_chat_session_for_whatsapp(mobile_number=phone)
            if chat_session.is_new_session or ((chat_session.scheme=="Unknown" or chat_session.scheme==None or chat_session.scheme=="") and message not in ["Scholarship", "Pension"]):
                WhatsAppManager._initial_greeting(phone)
                return
            logger.info(f"intent is {chat_session.intent}")
            if message == "CHANGE_TO_PENSION":
                chat_session.scheme = "Pension"
                chat_session.intent = "UNKNOWN"
                chat_session.awaiting_clarification = "Yes"
                WhatsAppManager._pension_intent_selection(phone)
                return
            elif message == "CHANGE_TO_SCHOLARSHIP":
                chat_session.scheme = "Scholarship"
                chat_session.intent = "UNKNOWN"
                chat_session.awaiting_clarification = "Yes"
                WhatsAppManager._scholarship_intent_selection(phone)
                return
            
            if message in ["STATUS", "GENERAL"]:
                chat_session.intent = message
                chat_session.awaiting_clarification = "Yes"

            if chat_session.scheme=="Unknown" or chat_session.scheme==None or chat_session.scheme=="":
                chat_session.scheme = message

            if (chat_session.intent=='UNKNOWN' or chat_session.intent==None or chat_session.intent=="") and message not in ["STATUS", "GENERAL"]:
                if chat_session.scheme=='Pension':
                    WhatsAppManager._pension_intent_selection(phone)
                    return
                else:
                    WhatsAppManager._scholarship_intent_selection(phone)
                    return
        
            if chat_session.intent == 'STATUS':
                application_id = ChatManager.extract_application_id(message)
                if application_id:
                    chat_session.last_application_id = application_id
                    chat_session.awaiting_clarification = "No"

                if chat_session.awaiting_clarification == "Yes":
                    logger.info(f"application_id:{application_id}")
                    if chat_session.scheme == 'Pension':
                        WhatsAppManager._pension_status_nudge(phone)
                        return
                    elif chat_session.scheme == 'Scholarship':
                        WhatsAppManager._scholarship_status_nudge(phone)
                        return
            
            if chat_session.intent == 'GENERAL' and chat_session.awaiting_clarification == "Yes":
                chat_session.awaiting_clarification = "No"
                WhatsAppManager._general_nudge(phone)
                return
            
            result = ChatManager.get_response(chat_session, message)
            if result.is_success:
                answer = result.data.get("reply")
                if answer:
                    WhatsAppManager.send_whatsapp_message(phone, answer)
                    WhatsAppManager._post_response_menu(phone,chat_session.scheme)
            else:
                WhatsAppManager.send_whatsapp_message(phone, "Error occured")
        except Exception as e:
            frappe.log_error(
                title="Error in get_answer",
                message=traceback.format_exc()
            )
        finally:
            # Update the session always in finally so that irrespective of the code returns from any logical condition, chat session is updated only once
            ChatManager.update_session(chat_session)

    @staticmethod
    def _initial_greeting(phone: str):
        try:
            msg = frappe.get_doc({
                "doctype": "WhatsApp Message",
                "to": phone,
                "message": "नमस्कार! मैं आपका समाधान साथी हूँ।\n मैं पेंशन और छात्रवृत्ति से जुड़ी जानकारी में आपकी मदद के लिए यहाँ हूँ। \nकृपया नीचे दिए गए विकल्पों में से एक चुनें",
                "type": "Outgoing",
                "content_type": "interactive",
                "buttons":json.dumps([
                                        {"id": "Scholarship", "title": "छात्रवृत्ति (Scholarship)"},
                                        {"id": "Pension", "title": "पेंशन (Pension)"}
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
    
    @staticmethod
    def _pension_intent_selection(phone: str):
        try:
            msg = frappe.get_doc({
                "doctype": "WhatsApp Message",
                "to": phone,
                "message": "ठीक है 👍\n आप पेंशन के बारे में क्या जानना चाहते हैं?",
                "type": "Outgoing",
                "content_type": "interactive",
                "buttons":json.dumps([
                                        {"id": "STATUS", "title": "भुगतान की स्थिति"},
                                        {"id": "GENERAL", "title": "अन्य जानकारी"}
                                    ])
            })
            msg.insert(ignore_permissions=True)
            return
        except Exception as e:
            frappe.log_error(
                title="Error in _pension_intent_selection",
                message=traceback.format_exc()
            )
            return
    
    @staticmethod
    def _scholarship_intent_selection(phone: str):
        try:
            msg = frappe.get_doc({
                "doctype": "WhatsApp Message",
                "to": phone,
                "message": "ठीक है 👍\n आप छात्रवृत्ति के बारे में क्या जानना चाहते हैं?",
                "type": "Outgoing",
                "content_type": "interactive",
                "buttons":json.dumps([
                                        {"id": "STATUS", "title": "भुगतान की स्थिति"},
                                        {"id": "GENERAL", "title": "अन्य जानकारी"}
                                    ])
            })
            msg.insert(ignore_permissions=True)
            return
        except Exception as e:
            frappe.log_error(
                title="Error in _scholarship_intent_selection",
                message=traceback.format_exc()
            )
            return
    
    @staticmethod
    def _scholarship_status_nudge(phone: str):
        try:
            msg = frappe.get_doc({
                "doctype": "WhatsApp Message",
                "to": phone,
                "message": "कृपया अपनी आवेदन आईडी भेजें, ताकि मैं आपकी छात्रवृत्ति की स्थिति बता सकूँ।",
                "type": "Outgoing",
                "content_type": "text",
            })
            msg.insert(ignore_permissions=True)
            return
        except Exception as e:
            frappe.log_error(
                title="Error in _scholarship_status_nudge",
                message=traceback.format_exc()
            )
            return
    
    @staticmethod
    def _pension_status_nudge(phone: str):
        try:
            msg = frappe.get_doc({
                "doctype": "WhatsApp Message",
                "to": phone,
                "message": "कृपया अपनी पेंशन आईडी भेजें, ताकि मैं आपकी पेंशन भुगतान की स्थिति बता सकूँ।",
                "type": "Outgoing",
                "content_type": "text",
            })
            msg.insert(ignore_permissions=True)
            return
        except Exception as e:
            frappe.log_error(
                title="Error in _pension_status_nudge",
                message=traceback.format_exc()
            )
            return

    @staticmethod
    def _general_nudge(phone: str):
        try:
            msg = frappe.get_doc({
                "doctype": "WhatsApp Message",
                "to": phone,
                "message": "आप क्या जानना चाहते हैं, कृपया थोड़ा विस्तार से बताएं। \n (जैसे: पात्रता, आवेदन प्रक्रिया, जरूरी दस्तावेज आदि)",
                "type": "Outgoing",
                "content_type": "text",
            })
            msg.insert(ignore_permissions=True)
            return
        except Exception as e:
            frappe.log_error(
                title="Error in _general_nudge",
                message=traceback.format_exc()
            )
            return
    
    @staticmethod
    def _post_response_menu(phone: str, scheme: str = None):
        try:

            buttons = []

            # Same scheme actions
            if scheme == "Scholarship":
                buttons.append({
                    "id": "STATUS",
                    "title": "अन्य स्थिति देखें"
                })

                buttons.append({
                    "id": "GENERAL",
                    "title": "अन्य छात्रवृत्ति प्रश्न"
                })

                buttons.append({
                    "id": "CHANGE_TO_PENSION",
                    "title": "पेंशन पर बदलें"
                })

            elif scheme == "Pension":
                buttons.append({
                    "id": "STATUS",
                    "title": "अन्य स्थिति देखें"
                })

                buttons.append({
                    "id": "GENERAL",
                    "title": "अन्य पेंशन प्रश्न"
                })

                buttons.append({
                    "id": "CHANGE_TO_SCHOLARSHIP",
                    "title": "छात्रवृत्ति पर बदलें"
                })


            msg = frappe.get_doc({
                "doctype": "WhatsApp Message",
                "to": phone,
                "message": "अब आप आगे क्या करना चाहते हैं?",
                "type": "Outgoing",
                "content_type": "interactive",
                "buttons": json.dumps(buttons)
            })

            msg.insert(ignore_permissions=True)

        except Exception:
            frappe.log_error(
                title="Error in _post_response_menu",
                message=traceback.format_exc()
            )