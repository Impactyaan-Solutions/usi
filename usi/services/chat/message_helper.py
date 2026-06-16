from usi.models.result import Result
import frappe
import json
from usi.services.chat.chat_constants import (
    BUTTONS,
    ALLOWED_INTENTS
)
def send_welcome_message(session_id: str|None = None,channel:str = "Website",mobile_no:str|None = None) -> Result:
    
    if channel == "Website":
        return Result.success(message="Response generated successfully", data={
            "session_id": session_id,
            "interactive_msg":{
                "title": "नमस्कार! मैं आपका समाधान साथी हूँ।\n मैं पेंशन और छात्रवृत्ति से जुड़ी जानकारी में आपकी मदद के लिए यहाँ हूँ। \nकृपया नीचे दिए गए विकल्पों में से एक चुनें",
                "buttons":BUTTONS
            }
        })

    msg = frappe.get_doc({
            "doctype": "WhatsApp Message",
            "to": mobile_no,
            "message": "नमस्कार! मैं आपका समाधान साथी हूँ।\n मैं पेंशन और छात्रवृत्ति से जुड़ी जानकारी में आपकी मदद के लिए यहाँ हूँ। \nकृपया नीचे दिए गए विकल्पों में से एक चुनें",
            "type": "Outgoing",
            "content_type": "interactive",
            "buttons":json.dumps(BUTTONS)
        })
    msg.insert(ignore_permissions=True)
    


def send_intent_selection_message(session_id: str|None = None, channel:str = "Website",mobile_no:str|None = None)->Result:
    
    buttons = []
    for allowed_intent in ALLOWED_INTENTS:
        buttons.append({
            "title": allowed_intent["title"],
            "id": allowed_intent["id"]
        })
    
    if channel == "Website":
        return Result.success(message="Response generated successfully", data={
            "session_id": session_id,
            "interactive_msg":{
                "title": "ठीक है 👍\n आप क्या जानना चाहते हैं?",
                "buttons":buttons
            }
        })
    msg = frappe.get_doc({
            "doctype": "WhatsApp Message",
            "to": mobile_no,
            "message": "ठीक है 👍\n आप क्या जानना चाहते हैं?",
            "type": "Outgoing",
            "content_type": "interactive",
            "buttons":json.dumps(buttons)
        })
    msg.insert(ignore_permissions=True)


def send_intent_selection_message_on_scheme_change(session_id: str|None = None, scheme: str|None = None, channel="Website",mobile_no:str|None = None)->Result:
    
    buttons = []
    for allowed_intent in ALLOWED_INTENTS:
        buttons.append({
            "title": allowed_intent["title"],
            "id": allowed_intent["id"]
        })
    
    if channel == "Website":
        return Result.success(message="Response generated successfully", data={
            "session_id": session_id,
            "interactive_msg":{
                "title": "ऐसा लगता है कि आप " + scheme + " के बारे में जानना चाहते हैं। कृपया नीचे दिए गए विकल्पों में से एक चुनें:",
                "buttons":buttons
        }
    })

    msg = frappe.get_doc({
            "doctype": "WhatsApp Message",
            "to": mobile_no,
            "message": "ऐसा लगता है कि आप " + scheme + " के बारे में जानना चाहते हैं। कृपया नीचे दिए गए विकल्पों में से एक चुनें:",
            "type": "Outgoing",
            "content_type": "interactive",
            "buttons":json.dumps(buttons)
        })
    msg.insert(ignore_permissions=True)

def send_application_id_prompt(session_id: str|None = None):
    return Result.success(message="Response generated successfully", data={
        "session_id": session_id,
        "reply":"कृपया अपना एप्लिकेशन ID दर्ज करें"
    })

def send_general_query_prompt(session_id: str|None = None):
    return Result.success(message="Response generated successfully", data={
        "session_id": session_id,
        "reply":"कृपया अपना सामान्य प्रश्न दर्ज करें"
    })


def _application_not_found_response() -> str:

    return "इस आईडी/नंबर से संबंधित आवेदन नहीं मिला। कृपया अपना आवेदन नंबर दोबारा जांच लें। \n Application corresponding to this ID/number is not found. Please double check your application number."


def status_lookup_error_response(api_result: Result) -> str:
    if api_result.is_not_found:
        return _application_not_found_response()

    error_hint = str(api_result.error_data or api_result.message or "")
    if "whitelist" in error_hint.lower():
        reply = (
            "पेंशन स्थिति सेवा इस समय उपलब्ध नहीं है (सर्वर IP अनुमोदित नहीं है)। कृपया बाद में पुनः प्रयास करें या सहायता से संपर्क करें।\n"
            "Pension status service is temporarily unavailable (server not authorized). Please try again later or contact support."
        )
    else:
        reply = (
            "स्थिति जांच इस समय पूरी नहीं हो सकी। कृपया थोड़ी देर बाद फिर से प्रयास करें।\n"
            "Status lookup could not be completed right now. Please try again later."
        )
    return reply
