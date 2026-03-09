import frappe
from usi.models.result import Result
from frappe.utils import now_datetime, add_to_date
from usi.services.whatsapp_manager import WhatsAppManager
import traceback
def check_feedback_timer() -> None:
    two_minutes_ago = add_to_date(now_datetime(), minutes=-3)

    sessions = frappe.get_all(
        "Chat Session",
        filters={
            "last_user_message_at": ("<=", two_minutes_ago),
            "feedback_message_sent": "No"
        },
        fields=["name", "mobile_no"]
    )

    for s in sessions:
        # send whatsapp feedback
        send_feedback_message(s.mobile_no)

        # mark feedback sent
        frappe.db.set_value(
            "Chat Session",
            s.name,
            "feedback_message_sent",
            "Yes"
        )


def send_feedback_message(mobile_no: str) -> None   :
    try:
        WhatsAppManager.send_whatsapp_message(mobile_no, "Please share your feedback on how we can improve our service.")
    except Exception as e:
        frappe.log_error(
            title="Error in send_feedback_message",
            message=traceback.format_exc()
        )
        return