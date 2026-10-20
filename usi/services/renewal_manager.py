"""
Scholarship renewal wizard (deterministic, no AI).

Flow (flowchart V2):
  Consent -> Jan Aadhaar + previous application ID -> scheme confirm
  -> 3 document confirmations -> summary -> Submit | Edit Details -> new ID.

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

# ---------------------------------------------------------------------------
# Swap this when govt APIs are ready, e.g. STORE = ScholarshipPortalStore()
# Keep the same methods: validate_identity, fetch_linked_profile, submit_renewal
# ---------------------------------------------------------------------------
STORE = DummyRenewalStore()

# Wizard steps stored in Chat Session.renewal_payload
STEP_CONSENT = "CONSENT"
STEP_JAN_AADHAAR = "JAN_AADHAAR"
STEP_PREV_APP_ID = "PREV_APP_ID"
STEP_SCHEME = "SCHEME_CONFIRM"
STEP_DOC_MARKSHEET = "DOC_MARKSHEET"
STEP_DOC_FEE = "DOC_FEE"
STEP_DOC_INCOME = "DOC_INCOME"
STEP_SUMMARY = "SUMMARY"
STEP_DONE = "DONE"

# Button ids (website interactive_msg.id / WhatsApp button id)
BTN_CONSENT_YES = "RENEW_CONSENT_YES"
BTN_CONSENT_NO = "RENEW_CONSENT_NO"
BTN_SCHEME_YES = "RENEW_SCHEME_YES"
BTN_SCHEME_NO = "RENEW_SCHEME_NO"
BTN_DOC_OK = "RENEW_DOC_OK"
BTN_SUBMIT = "RENEW_SUBMIT"
BTN_EDIT = "RENEW_EDIT"

YES_WORDS = {"yes", "y", "haan", "han", "हाँ", "हां", "ok", "confirm"}
NO_WORDS = {"no", "n", "nahi", "नहीं", "नही", "cancel"}

SCHOLARSHIP_APP_ID_RE = re.compile(r"SCHOLARSHIP/\d{4}-\d{2}/\d+", re.IGNORECASE)
JAN_AADHAAR_RE = re.compile(r"\b\d{10,12}\b")


def _empty_payload() -> dict[str, Any]:
    return {
        "step": STEP_CONSENT,
        "consent": False,
        "janAadhaarId": None,
        "previousApplicationId": None,
        "applicantSnapshot": None,
        "documents": {
            "marksheet": None,
            "feeReceipt": None,
            "incomeCertificate": None,
        },
        "linkedProfile": None,
        "newApplicationId": None,
    }


class RenewalManager:
    @classmethod
    def clear_state(cls, chat_session: ChatSession) -> None:
        """Drop renewal wizard state. Call on scheme switch / welcome reset."""
        # last_classification_json is unused by the current STATUS/GENERAL
        # ChatManager. We reuse it as session storage so we do not need a
        # new DocType column. Live classification must not overwrite this
        # while intent == RENEW.
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
            step = payload.get("step") or STEP_CONSENT
            text = (message or "").strip()

            if step == STEP_CONSENT:
                result = cls._step_consent(payload, text)
            elif step == STEP_JAN_AADHAAR:
                result = cls._step_jan_aadhaar(payload, text)
            elif step == STEP_PREV_APP_ID:
                result = cls._step_prev_app_id(payload, text)
            elif step == STEP_SCHEME:
                result = cls._step_scheme(payload, text)
            elif step in (STEP_DOC_MARKSHEET, STEP_DOC_FEE, STEP_DOC_INCOME):
                result = cls._step_document(payload, text, step)
            elif step == STEP_SUMMARY:
                result = cls._step_summary(payload, text)
            elif step == STEP_DONE:
                result = cls._already_done(payload)
            else:
                payload["step"] = STEP_CONSENT
                result = cls._prompt_consent()

            # User backed out of renew — return to Scholarship intent picker.
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
            return cls._to_channel_result(
                result, chat_session.session_id, channel, mobile_no
            )
        except Exception:
            frappe.log_error(
                title="Error in RenewalManager.handle",
                message=traceback.format_exc(),
            )
            return Result.failure(
                message="Internal Server Error: scholarship renewal failed"
            )

    # ------------------------------------------------------------------
    # Steps
    # ------------------------------------------------------------------
    @classmethod
    def _step_consent(cls, payload: dict, text: str) -> Result:
        # First turn after tapping Renew: only show the prompt.
        if text.upper() == "RENEW" or not text:
            payload["step"] = STEP_CONSENT
            return cls._prompt_consent()

        if cls._is_yes(text) or text == BTN_CONSENT_YES:
            payload["consent"] = True
            payload["step"] = STEP_JAN_AADHAAR
            return cls._prompt_jan_aadhaar()

        if cls._is_no(text) or text == BTN_CONSENT_NO:
            return cls._exit_renew_result()

        return cls._prompt_consent()

    @classmethod
    def _step_jan_aadhaar(cls, payload: dict, text: str) -> Result:
        jan, app_id = cls._parse_identity(text)
        if jan and app_id:
            return cls._validate_and_show_scheme(payload, jan, app_id)
        if jan:
            payload["janAadhaarId"] = jan
            payload["step"] = STEP_PREV_APP_ID
            return cls._text(
                "धन्यवाद। अब पिछला आवेदन आईडी दर्ज करें।\n"
                "Please enter your previous application ID.\n"
                "उदाहरण / Example: SCHOLARSHIP/2025-26/9000001"
            )
        return cls._prompt_jan_aadhaar(invalid=bool(text))

    @classmethod
    def _step_prev_app_id(cls, payload: dict, text: str) -> Result:
        jan, app_id = cls._parse_identity(text)
        jan = jan or payload.get("janAadhaarId")
        if not jan:
            payload["step"] = STEP_JAN_AADHAAR
            return cls._prompt_jan_aadhaar()
        if not app_id:
            return cls._text(
                "आवेदन आईडी मान्य नहीं है। कृपया इस प्रारूप में दर्ज करें:\n"
                "Invalid application ID. Please use format:\n"
                "SCHOLARSHIP/2025-26/9000001"
            )
        return cls._validate_and_show_scheme(payload, jan, app_id)

    @classmethod
    def _validate_and_show_scheme(cls, payload: dict, jan: str, app_id: str) -> Result:
        # STORE.validate_identity is the portal API seam.
        applicant = STORE.validate_identity(jan, app_id)
        if not applicant:
            payload["janAadhaarId"] = None
            payload["previousApplicationId"] = None
            payload["step"] = STEP_JAN_AADHAAR
            return cls._text(
                "जन आधार / आवेदन आईडी सत्यापित नहीं हो सकी। कृपया दोबारा दर्ज करें।\n"
                "Jan Aadhaar or previous application ID could not be validated. Please re-enter.\n"
                "जन आधार आईडी दर्ज करें / Enter Jan Aadhaar ID:"
            )

        payload["janAadhaarId"] = jan
        payload["previousApplicationId"] = app_id
        payload["applicantSnapshot"] = applicant
        payload["step"] = STEP_SCHEME
        return cls._prompt_scheme(applicant)

    @classmethod
    def _step_scheme(cls, payload: dict, text: str) -> Result:
        if cls._is_no(text) or text == BTN_SCHEME_NO:
            return cls._exit_renew_result()
        if not (cls._is_yes(text) or text == BTN_SCHEME_YES):
            applicant = payload.get("applicantSnapshot") or {}
            return cls._prompt_scheme(applicant)

        payload["step"] = STEP_DOC_MARKSHEET
        return cls._prompt_document("marksheet")

    @classmethod
    def _step_document(cls, payload: dict, text: str, step: str) -> Result:
        # V1: no live file picker. User confirms each mandatory document.
        # Later: replace confirmation with uploaded file URL in payload["documents"].
        confirmed = text == BTN_DOC_OK or cls._is_yes(text)
        if not confirmed:
            kind = {
                STEP_DOC_MARKSHEET: "marksheet",
                STEP_DOC_FEE: "fee",
                STEP_DOC_INCOME: "income",
            }.get(step, "marksheet")
            return cls._prompt_document(kind)

        docs = payload.setdefault("documents", {})
        if step == STEP_DOC_MARKSHEET:
            docs["marksheet"] = "CONFIRMED"
            payload["step"] = STEP_DOC_FEE
            return cls._prompt_document("fee")
        if step == STEP_DOC_FEE:
            docs["feeReceipt"] = "CONFIRMED"
            payload["step"] = STEP_DOC_INCOME
            return cls._prompt_document("income")

        docs["incomeCertificate"] = "CONFIRMED"
        jan = payload.get("janAadhaarId")
        # STORE.fetch_linked_profile is the Jan Aadhaar DB seam.
        payload["linkedProfile"] = STORE.fetch_linked_profile(jan)
        payload["step"] = STEP_SUMMARY
        return cls._prompt_summary(payload)

    @classmethod
    def _step_summary(cls, payload: dict, text: str) -> Result:
        if text == BTN_EDIT:
            # Flowchart: Edit Details returns to identity collection.
            jan_consent = payload.get("consent")
            payload.clear()
            payload.update(_empty_payload())
            payload["consent"] = jan_consent
            payload["step"] = STEP_JAN_AADHAAR
            return cls._prompt_jan_aadhaar()

        if text != BTN_SUBMIT and not cls._is_yes(text):
            return cls._prompt_summary(payload)

        applicant = payload.get("applicantSnapshot") or {}
        documents = payload.get("documents") or {}
        # STORE.submit_renewal is the portal submit seam.
        new_id = STORE.submit_renewal(applicant, documents)
        payload["newApplicationId"] = new_id
        payload["step"] = STEP_DONE
        return cls._text(
            "नवीनीकरण आवेदन जमा हो गया है।\n"
            "Your scholarship renewal has been submitted.\n\n"
            f"नया आवेदन आईडी / New application ID:\n{new_id}"
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
                        {"id": BTN_CONSENT_NO, "title": "नहीं / No"},
                    ],
                }
            },
        )

    @staticmethod
    def _prompt_jan_aadhaar(invalid: bool = False) -> Result:
        prefix = (
            "जन आधार आईडी सही नहीं है। कृपया 10 अंकों की आईडी दर्ज करें।\n"
            "Invalid Jan Aadhaar. Please enter a 10-digit ID.\n\n"
            if invalid
            else ""
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
    def _prompt_scheme(applicant: dict) -> Result:
        title = (
            "पिछले वर्ष की योजना / Previous year scheme:\n\n"
            f"नाम / Name: {applicant.get('studentName') or '-'}\n"
            f"योजना / Scheme: {applicant.get('schemeName') or '-'}\n"
            f"संस्थान / Institute: {applicant.get('instituteName') or '-'}\n"
            f"कोर्स / Course: {applicant.get('courseName') or '-'}\n"
            f"वर्ष / Year of study: {applicant.get('renewalYearOfStudy') or '-'}\n"
            f"शैक्षणिक वर्ष / Academic year: {applicant.get('renewalAcademicYear') or '-'}\n\n"
            "क्या आप इसी योजना के लिए नवीनीकरण करना चाहते हैं?\n"
            "Do you confirm renewal for this scheme?"
        )
        return Result.success(
            message="renewal_prompt",
            data={
                "interactive_msg": {
                    "title": title,
                    "buttons": [
                        {"id": BTN_SCHEME_YES, "title": "पुष्टि / Confirm"},
                        {"id": BTN_SCHEME_NO, "title": "रद्द / Cancel"},
                    ],
                }
            },
        )

    @staticmethod
    def _prompt_document(kind: str) -> Result:
        labels = {
            "marksheet": (
                "1/3 — पिछले वर्ष की अंतिम अर्हता परीक्षा की मार्कशीट\n"
                "Previous year's last qualifying exam marksheet"
            ),
            "fee": (
                "2/3 — चालू शैक्षणिक वर्ष की फीस रसीद\n"
                "Current academic year's fee receipt"
            ),
            "income": (
                "3/3 — पारिवारिक आय प्रमाण पत्र\n"
                "Family income certificate"
            ),
        }
        return Result.success(
            message="renewal_prompt",
            data={
                "interactive_msg": {
                    "title": (
                        f"{labels.get(kind, kind)}\n\n"
                        "फ़ाइल अपलोड अभी उपलब्ध नहीं है। पुष्टि करें कि दस्तावेज़ तैयार है।\n"
                        "File upload is not enabled yet. Confirm that this document is ready."
                    ),
                    "buttons": [{"id": BTN_DOC_OK, "title": "Uploaded"}],
                }
            },
        )

    @staticmethod
    def _prompt_summary(payload: dict) -> Result:
        a = payload.get("applicantSnapshot") or {}
        d = payload.get("documents") or {}
        p = payload.get("linkedProfile") or {}
        title = (
            "सारांश / Summary — कृपया जाँचें\n\n"
            f"योजना / Scheme: {a.get('schemeName') or '-'}\n"
            f"मार्कशीट / Marksheet: {d.get('marksheet') or '-'}\n"
            f"फीस रसीद / Fee receipt: {d.get('feeReceipt') or '-'}\n"
            f"आय प्रमाण / Income certificate: {d.get('incomeCertificate') or '-'}\n"
            f"जाति प्रमाण पत्र / Caste certificate: {p.get('casteCertificateNo') or '-'}\n"
            f"आधार / Aadhaar: {p.get('aadhaarNumber') or '-'}\n"
            f"जन आधार / Jan Aadhaar: {payload.get('janAadhaarId') or '-'}\n"
            f"बैंक (आधार से लिंक) / Bank linked to Aadhaar: "
            f"{p.get('bankAccountLinkedToAadhaar') or '-'} {p.get('bankName') or ''}\n"
        )
        return Result.success(
            message="renewal_prompt",
            data={
                "interactive_msg": {
                    "title": title,
                    "buttons": [
                        {"id": BTN_SUBMIT, "title": "जमा / Submit"},
                        {"id": BTN_EDIT, "title": "संपादित / Edit"},
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
    def _parse_identity(text: str) -> tuple[Optional[str], Optional[str]]:
        app_match = SCHOLARSHIP_APP_ID_RE.search(text or "")
        jan_match = JAN_AADHAAR_RE.search(text or "")
        app_id = app_match.group(0).upper() if app_match else None
        jan = jan_match.group(0) if jan_match else None
        return jan, app_id

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
        data = result.data if isinstance(result.data, dict) else {}
        interactive = data.get("interactive_msg")
        reply = data.get("reply")

        if channel == "Website":
            payload = {"session_id": session_id}
            if interactive:
                payload["interactive_msg"] = interactive
            if reply:
                payload["reply"] = reply
            return Result.success(message="Response generated successfully", data=payload)

        # WhatsApp: same interactive / text pattern as message_helper.
        if interactive:
            msg = frappe.get_doc(
                {
                    "doctype": "WhatsApp Message",
                    "to": mobile_no,
                    "message": interactive.get("title") or "",
                    "type": "Outgoing",
                    "content_type": "interactive",
                    "buttons": json.dumps(interactive.get("buttons") or []),
                }
            )
            msg.insert(ignore_permissions=True)
            return Result.success(message="Response generated successfully", data={})

        if reply:
            msg = frappe.get_doc(
                {
                    "doctype": "WhatsApp Message",
                    "to": mobile_no,
                    "content_type": "text",
                    "message": reply,
                    "type": "Outgoing",
                }
            )
            msg.insert(ignore_permissions=True)
            return Result.success(message="Response generated successfully", data={})

        return Result.success(
            message="Response generated successfully",
            data={"session_id": session_id},
        )
