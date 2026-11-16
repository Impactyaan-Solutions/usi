"""
Scholarship renewal wizard (deterministic, no AI).

Flow:
  Consent
  -> Jan Aadhaar entry
  -> Family member selection
  -> OTP verification
  -> Personal / caste / income / bank details confirmation
  -> Previous application ID (last 6 digits)
  -> Marksheet upload confirmation
  -> Fee receipt upload confirmation
  -> Summary + biometric authentication message

Backend calls go through RenewalManager.STORE only, so swapping dummy JSON
for government APIs is a one-line change at STORE = ...
"""
from __future__ import annotations

import json
import re
import traceback
from typing import Any, Optional

import frappe
from usi.models.chat import ChatSession
from usi.models.result import Result
from usi.services.dummy_renewal_store import DummyRenewalStore

STORE = DummyRenewalStore()

# ---------------------------------------------------------------------------
# Wizard steps
# ---------------------------------------------------------------------------
STEP_CONSENT        = "CONSENT"
STEP_JAN_AADHAAR    = "JAN_AADHAAR"
STEP_FAMILY_SELECT  = "FAMILY_SELECT"
STEP_OTP            = "OTP"
STEP_DETAILS_CONFIRM = "DETAILS_CONFIRM"
STEP_PREV_APP_ID    = "PREV_APP_ID"
STEP_DOC_MARKSHEET  = "DOC_MARKSHEET"
STEP_DOC_FEE        = "DOC_FEE"
STEP_SUMMARY        = "SUMMARY"
STEP_DONE           = "DONE"

# ---------------------------------------------------------------------------
# Button IDs
# ---------------------------------------------------------------------------
BTN_CONSENT_YES  = "RENEW_CONSENT_YES"
BTN_CONSENT_NO   = "RENEW_CONSENT_NO"
BTN_DETAILS_OK   = "RENEW_DETAILS_OK"
BTN_DOC_OK       = "RENEW_DOC_OK"
BTN_SUBMIT       = "RENEW_SUBMIT"
BTN_EDIT         = "RENEW_EDIT"

YES_WORDS = {"yes", "y", "haan", "han", "हाँ", "हां", "ok", "confirm"}
NO_WORDS  = {"no", "n", "nahi", "नहीं", "नही", "cancel"}

JAN_AADHAAR_RE = re.compile(r"\b\d{10,12}\b")


def _empty_payload() -> dict[str, Any]:
    return {
        "step":                   STEP_CONSENT,
        "consent":                False,
        "janAadhaarId":           None,
        "selectedMemberId":       None,
        "selectedMemberName":     None,
        "otpVerified":            False,
        "personalDetails":        None,
        "previousApplicationId":  None,
        "applicantSnapshot":      None,
        "documents": {
            "marksheet":  None,
            "feeReceipt": None,
        },
        "linkedProfile":          None,
        "newApplicationId":       None,
    }


class RenewalManager:

    @classmethod
    def clear_state(cls, chat_session: ChatSession) -> None:
        """Drop renewal wizard state. Call on scheme switch / welcome reset."""
        chat_session.last_classification_json = None

    @classmethod
    def handle(
        cls,
        chat_session: ChatSession,
        message: str,
        channel: str = "Website",
        mobile_no: str | None = None,
    ) -> Result:
        try:
            payload = cls._load_payload(chat_session)
            step    = payload.get("step") or STEP_CONSENT
            text    = (message or "").strip()

            if step == STEP_CONSENT:
                result = cls._step_consent(payload, text)
            elif step == STEP_JAN_AADHAAR:
                result = cls._step_jan_aadhaar(payload, text)
            elif step == STEP_FAMILY_SELECT:
                result = cls._step_family_select(payload, text)
            elif step == STEP_OTP:
                result = cls._step_otp(payload, text)
            elif step == STEP_DETAILS_CONFIRM:
                result = cls._step_details_confirm(payload, text)
            elif step == STEP_PREV_APP_ID:
                result = cls._step_prev_app_id(payload, text)
            elif step == STEP_DOC_MARKSHEET:
                result = cls._step_document(payload, text, step)
            elif step == STEP_DOC_FEE:
                result = cls._step_document(payload, text, step)
            elif step == STEP_SUMMARY:
                result = cls._step_summary(payload, text)
            elif step == STEP_DONE:
                result = cls._already_done(payload)
            else:
                payload["step"] = STEP_CONSENT
                result = cls._prompt_consent()

            # User backed out — return to intent picker
            if result.data and result.data.get("_exit_renew"):
                chat_session.intent = "UNKNOWN"
                cls.clear_state(chat_session)
                from usi.services.chat.message_helper import send_intent_selection_message
                return send_intent_selection_message(
                    chat_session.session_id,
                    channel=channel,
                    mobile_no=mobile_no,
                    scheme=chat_session.scheme,
                )

            chat_session.last_classification_json = json.dumps(payload, ensure_ascii=False)
            return cls._to_channel_result(result, chat_session.session_id, channel, mobile_no)

        except Exception:
            frappe.log_error(
                title="Error in RenewalManager.handle",
                message=traceback.format_exc(),
            )
            return Result.failure(message="Internal Server Error: scholarship renewal failed")

    # ------------------------------------------------------------------
    # Step handlers
    # ------------------------------------------------------------------

    @classmethod
    def _step_consent(cls, payload: dict, text: str) -> Result:
        if text.upper() == "RENEW" or not text:
            payload["step"] = STEP_CONSENT
            return cls._prompt_consent()

        if cls._is_yes(text) or text == BTN_CONSENT_YES:
            payload["consent"] = True
            payload["step"]    = STEP_JAN_AADHAAR
            return cls._prompt_jan_aadhaar()

        if cls._is_no(text) or text == BTN_CONSENT_NO:
            return cls._exit_renew_result()

        return cls._prompt_consent()

    @classmethod
    def _step_jan_aadhaar(cls, payload: dict, text: str) -> Result:
        jan = cls._parse_jan_aadhaar(text)
        if not jan:
            return cls._prompt_jan_aadhaar(invalid=bool(text))

        members = STORE.get_family_members(jan)
        if not members:
            return cls._text(
                "इस जन आधार आईडी से कोई परिवार सदस्य नहीं मिला। कृपया दोबारा दर्ज करें।\n"
                "No family members found for this Jan Aadhaar ID. Please try again."
            )

        payload["janAadhaarId"]  = jan
        payload["familyMembers"] = members
        payload["step"]          = STEP_FAMILY_SELECT
        return cls._prompt_family_select(members)

    @classmethod
    def _step_family_select(cls, payload: dict, text: str) -> Result:
        members = payload.get("familyMembers") or []
        member  = next((m for m in members if m["id"] == text), None)
        if not member:
            return cls._prompt_family_select(members)

        payload["selectedMemberId"]   = member["id"]
        payload["selectedMemberName"] = member["name"]
        payload["step"]               = STEP_OTP
        return cls._prompt_otp(member["name"])

    @classmethod
    def _step_otp(cls, payload: dict, text: str) -> Result:
        if not re.fullmatch(r"\d{6}", text):
            return cls._text(
                "कृपया 6 अंकों का OTP दर्ज करें।\n"
                "Please enter the 6-digit OTP sent to your registered mobile."
            )

        if not STORE.validate_otp(text):
            return cls._text(
                "OTP गलत है। कृपया दोबारा दर्ज करें।\n"
                "Incorrect OTP. Please try again."
            )

        payload["otpVerified"] = True
        member_id = payload.get("selectedMemberId")
        details   = STORE.get_personal_details(member_id)
        payload["personalDetails"] = details
        payload["step"]            = STEP_DETAILS_CONFIRM
        return cls._prompt_details_confirm(payload)

    @classmethod
    def _step_details_confirm(cls, payload: dict, text: str) -> Result:
        if cls._is_no(text):
            return cls._exit_renew_result()

        if cls._is_yes(text) or text == BTN_DETAILS_OK:
            payload["step"] = STEP_PREV_APP_ID
            return cls._prompt_prev_app_id()

        return cls._prompt_details_confirm(payload)

    @classmethod
    def _step_prev_app_id(cls, payload: dict, text: str) -> Result:
        # Accept last 6 digits only e.g. "900001"
        app_id_suffix = cls._parse_app_id_suffix(text)
        if not app_id_suffix:
            return cls._text(
                "आवेदन संख्या सही नहीं है। कृपया अपनी पिछली आवेदन संख्या के अंतिम अंक दर्ज करें।\n"
                "Invalid application number. Please enter the last digits of your previous application number.\n"
                "उदाहरण / Example: 9000001"
            )

        jan = payload.get("janAadhaarId")
        applicant = STORE.validate_identity(jan, app_id_suffix)
        if not applicant:
            return cls._text(
                "जन आधार और आवेदन संख्या का मिलान नहीं हुआ। कृपया दोबारा दर्ज करें।\n"
                "Jan Aadhaar and application number do not match. Please try again."
            )

        payload["previousApplicationId"] = applicant.get("previousApplicationId")
        payload["applicantSnapshot"]      = applicant
        payload["step"]                   = STEP_DOC_MARKSHEET
        return cls._prompt_document("marksheet")

    @classmethod
    def _step_document(cls, payload: dict, text: str, step: str) -> Result:
        confirmed = text == BTN_DOC_OK or cls._is_yes(text)
        if not confirmed:
            kind = STEP_DOC_MARKSHEET if step == STEP_DOC_MARKSHEET else "fee"
            return cls._prompt_document(kind)

        docs = payload.setdefault("documents", {})
        if step == STEP_DOC_MARKSHEET:
            docs["marksheet"] = "CONFIRMED"
            payload["step"]   = STEP_DOC_FEE
            return cls._prompt_document("fee")

        # STEP_DOC_FEE — income certificate comes from Jan Aadhaar, no upload needed
        docs["feeReceipt"] = "CONFIRMED"
        jan = payload.get("janAadhaarId")
        payload["linkedProfile"] = STORE.fetch_linked_profile(jan)
        payload["step"]          = STEP_SUMMARY
        return cls._prompt_summary(payload)

    @classmethod
    def _step_summary(cls, payload: dict, text: str) -> Result:
        if text == BTN_EDIT:
            payload.clear()
            payload.update(_empty_payload())
            payload["step"] = STEP_JAN_AADHAAR
            return cls._prompt_jan_aadhaar()

        if text != BTN_SUBMIT and not cls._is_yes(text):
            return cls._prompt_summary(payload)

        applicant = payload.get("applicantSnapshot") or {}
        documents = payload.get("documents") or {}
        new_id    = STORE.submit_renewal(applicant, documents)
        payload["newApplicationId"] = new_id
        payload["step"]             = STEP_DONE
        return cls._text(
            f"आवेदन सारांश / Application Summary\n\n"
            f"नाम / Name           : {applicant.get('studentName') or '-'}\n"
            f"योजना / Scheme       : {applicant.get('schemeName') or '-'}\n"
            f"नया आवेदन / New ID   : {new_id}\n\n"
            "Your Application is saved and ready to be submitted. "
            "The last step is Biometric Authentication.\n\n"
            "Kindly download the *SJED APPLICATIONS* mobile app on your phone "
            "OR visit nearest e-mitra kiosk to complete your biometric "
            "authentication and submit the application."
        )

    @classmethod
    def _already_done(cls, payload: dict) -> Result:
        new_id = payload.get("newApplicationId") or "-"
        return cls._text(
            f"यह नवीनीकरण पहले जमा हो चुका है।\n"
            f"This renewal is already submitted.\n"
            f"आवेदन आईडी / Application ID: {new_id}"
        )

    # ------------------------------------------------------------------
    # Prompts
    # ------------------------------------------------------------------

    @staticmethod
    def _prompt_consent() -> Result:
        return Result.success(
            message="renewal_prompt",
            data={
                "interactive_msg": {
                    "title": (
                        "छात्रवृत्ति नवीनीकरण के लिए व्यक्तिगत जानकारी (जन आधार, आवेदन आईडी) "
                        "एकत्र की जाएगी। क्या आप सहमति देते हैं?\n"
                        "We will collect personal information (Jan Aadhaar, application ID) "
                        "for scholarship renewal. Do you consent?"
                    ),
                    "buttons": [
                        {"id": BTN_CONSENT_YES, "title": "हाँ / Yes"},
                        {"id": BTN_CONSENT_NO,  "title": "नहीं / No"},
                    ],
                }
            },
        )

    @staticmethod
    def _prompt_jan_aadhaar(invalid: bool = False) -> Result:
        prefix = (
            "जन आधार आईडी सही नहीं है। कृपया 10–12 अंकों की आईडी दर्ज करें।\n"
            "Invalid Jan Aadhaar. Please enter a 10–12 digit ID.\n\n"
            if invalid else ""
        )
        return Result.success(
            message="renewal_prompt",
            data={
                "reply": (
                    prefix
                    + "कृपया जन आधार आईडी दर्ज करें।\n"
                    + "Please enter your Jan Aadhaar ID."
                )
            },
        )

    @staticmethod
    def _prompt_family_select(members: list) -> Result:
        buttons = [{"id": m["id"], "title": f"{m['name']} ({m['relation']})"} for m in members]
        return Result.success(
            message="renewal_prompt",
            data={
                "interactive_msg": {
                    "title": (
                        "कृपया अपना नाम चुनें।\n"
                        "Please select your name from the family members below."
                    ),
                    "buttons": buttons,
                }
            },
        )

    @staticmethod
    def _prompt_otp(member_name: str) -> Result:
        return Result.success(
            message="renewal_prompt",
            data={
                "reply": (
                    f"नमस्ते {member_name}!\n"
                    f"Hello {member_name}!\n\n"
                    "आपके पंजीकृत मोबाइल नंबर पर OTP भेजा गया है।\n"
                    "An OTP has been sent to your registered mobile number.\n\n"
                    "कृपया 6 अंकों का OTP दर्ज करें।\n"
                    "Please enter the 6-digit OTP."
                )
            },
        )

    @staticmethod
    def _prompt_details_confirm(payload: dict) -> Result:
        d    = payload.get("personalDetails") or {}
        name = payload.get("selectedMemberName") or "-"
        title = (
            "आपकी जानकारी / Your Details\n\n"
            f"नाम / Name          : {name}\n"
            f"श्रेणी / Category   : {d.get('category') or '-'}\n"
            f"जाति / Caste        : {d.get('caste') or '-'}\n"
            f"पारिवारिक आय / Family Income : ₹{d.get('familyIncome') or '-'}\n"
            f"बैंक खाता / Bank Account     : {d.get('bankAccount') or '-'}\n"
            f"बैंक / Bank                  : {d.get('bankName') or '-'}\n\n"
            "क्या यह जानकारी सही है? / Is this information correct?"
        )
        return Result.success(
            message="renewal_prompt",
            data={
                "interactive_msg": {
                    "title": title,
                    "buttons": [
                        {"id": BTN_DETAILS_OK, "title": "हाँ, सही है / Yes, Confirm"},
                        {"id": "no",           "title": "नहीं / No"},
                    ],
                }
            },
        )

    @staticmethod
    def _prompt_prev_app_id() -> Result:
        return Result.success(
            message="renewal_prompt",
            data={
                "reply": (
                    "कृपया अपनी पिछली आवेदन संख्या के अंतिम अंक दर्ज करें।\n"
                    "Please enter the last digits of your previous application number.\n\n"
                    "उदाहरण / Example: 9000001"
                )
            },
        )

    @staticmethod
    def _prompt_document(kind: str) -> Result:
        labels = {
            "marksheet": (
                "1/2 — पिछले वर्ष की अंतिम अर्हता परीक्षा की मार्कशीट\n"
                "Previous year's last qualifying exam marksheet"
            ),
            "fee": (
                "2/2 — चालू शैक्षणिक वर्ष की फीस रसीद\n"
                "Current academic year's fee receipt"
            ),
        }
        return Result.success(
            message="renewal_prompt",
            data={
                "interactive_msg": {
                    "title": (
                        f"{labels.get(kind, kind)}\n\n"
                        "फ़ाइल अपलोड करें और पुष्टि करें।\n"
                        "Upload the document and confirm."
                    ),
                    "buttons": [{"id": BTN_DOC_OK, "title": "Uploaded ✓"}],
                }
            },
        )

    @staticmethod
    def _prompt_summary(payload: dict) -> Result:
        a  = payload.get("applicantSnapshot") or {}
        d  = payload.get("documents") or {}
        p  = payload.get("linkedProfile") or {}
        pd = payload.get("personalDetails") or {}
        title = (
            "सारांश / Summary — कृपया जाँचें\n\n"
            f"नाम / Name              : {payload.get('selectedMemberName') or a.get('studentName') or '-'}\n"
            f"योजना / Scheme          : {a.get('schemeName') or '-'}\n"
            f"श्रेणी / Category       : {pd.get('category') or '-'}\n"
            f"जाति / Caste            : {pd.get('caste') or '-'}\n"
            f"पारिवारिक आय / Income   : ₹{pd.get('familyIncome') or '-'}\n"
            f"मार्कशीट / Marksheet    : {d.get('marksheet') or '-'}\n"
            f"फीस रसीद / Fee receipt  : {d.get('feeReceipt') or '-'}\n"
            f"जाति प्रमाण / Caste Cert: {p.get('casteCertificateNo') or '-'}\n"
            f"आधार / Aadhaar          : {p.get('aadhaarNumber') or '-'}\n"
            f"बैंक / Bank             : {pd.get('bankAccount') or '-'} {pd.get('bankName') or ''}\n"
        )
        return Result.success(
            message="renewal_prompt",
            data={
                "interactive_msg": {
                    "title": title,
                    "buttons": [
                        {"id": BTN_SUBMIT, "title": "जमा / Submit"},
                        {"id": BTN_EDIT,   "title": "संपादित / Edit"},
                    ],
                }
            },
        )

    @staticmethod
    def _text(reply: str) -> Result:
        return Result.success(message="renewal_prompt", data={"reply": reply})

    @staticmethod
    def _exit_renew_result() -> Result:
        return Result.success(message="renewal_exit", data={"_exit_renew": True})

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load_payload(chat_session: ChatSession) -> dict[str, Any]:
        raw = chat_session.last_classification_json
        if raw:
            try:
                data = json.loads(raw)
                if isinstance(data, dict) and data.get("step"):
                    return data
            except (TypeError, json.JSONDecodeError):
                pass
        return _empty_payload()

    @staticmethod
    def _parse_jan_aadhaar(text: str) -> Optional[str]:
        m = JAN_AADHAAR_RE.search(text or "")
        return m.group(0) if m else None

    @staticmethod
    def _parse_app_id_suffix(text: str) -> Optional[str]:
        """Accept 4–10 digit application ID suffix."""
        text = (text or "").strip()
        m = re.fullmatch(r"\d{4,10}", text)
        return text if m else None

    @staticmethod
    def _is_yes(text: str) -> bool:
        return (text or "").strip().lower() in YES_WORDS

    @staticmethod
    def _is_no(text: str) -> bool:
        return (text or "").strip().lower() in NO_WORDS

    @staticmethod
    def _to_channel_result(
        result: Result,
        session_id: str | None,
        channel: str,
        mobile_no: str | None,
    ) -> Result:
        data        = result.data if isinstance(result.data, dict) else {}
        interactive = data.get("interactive_msg")
        reply       = data.get("reply")

        if channel == "Website":
            payload = {"session_id": session_id}
            if interactive:
                payload["interactive_msg"] = interactive
            if reply:
                payload["reply"] = reply
            return Result.success(message="Response generated successfully", data=payload)

        if interactive:
            msg = frappe.get_doc({
                "doctype": "WhatsApp Message",
                "to": mobile_no,
                "message": interactive.get("title") or "",
                "type": "Outgoing",
                "content_type": "interactive",
                "buttons": json.dumps(interactive.get("buttons") or []),
            })
            msg.insert(ignore_permissions=True)
            return Result.success(message="Response generated successfully", data={})

        if reply:
            msg = frappe.get_doc({
                "doctype": "WhatsApp Message",
                "to": mobile_no,
                "content_type": "text",
                "message": reply,
                "type": "Outgoing",
            })
            msg.insert(ignore_permissions=True)
            return Result.success(message="Response generated successfully", data={})

        return Result.success(
            message="Response generated successfully",
            data={"session_id": session_id},
        )
