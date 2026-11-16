"""
Dummy Scholarship Renewal store.

This class is the ONLY place that should talk to renewal "backends".
Today it reads usi/data/scholarship_renewal_dummy.json.

When government APIs are available, add a live client with the same method
signatures and change RenewalManager.STORE to that client.
Do not change the chat wizard.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Optional
import json

import frappe

DUMMY_OTP = "123456"


class DummyRenewalStore:
    """Stand-in for Scholarship Portal + Jan Aadhaar DB."""

    @staticmethod
    @lru_cache(maxsize=1)
    def _load() -> dict[str, Any]:
        path = Path(frappe.get_app_path("usi")) / "data" / "scholarship_renewal_dummy.json"
        return json.loads(path.read_text(encoding="utf-8"))

    # ------------------------------------------------------------------
    # NEW: family members linked to a Jan Aadhaar
    # ------------------------------------------------------------------
    def get_family_members(self, jan_aadhaar_id: str) -> list[dict[str, Any]]:
        """
        Returns list of family members for the given Jan Aadhaar.
        Each item: {"id": str, "name": str, "relation": str}
        Live API later: GET Jan Aadhaar family members.
        """
        jan_aadhaar_id = (jan_aadhaar_id or "").strip()
        return self._load().get("familyMembers", {}).get(jan_aadhaar_id) or []

    # ------------------------------------------------------------------
    # NEW: personal details for a selected family member
    # ------------------------------------------------------------------
    def get_personal_details(self, member_id: str) -> dict[str, Any]:
        """
        Returns personal details for a family member.
        Live API later: GET Jan Aadhaar personal/caste/income details.
        """
        member_id = (member_id or "").strip()
        return self._load().get("personalDetails", {}).get(member_id) or {}

    # ------------------------------------------------------------------
    # NEW: dummy OTP validation — any 6-digit number accepted in live,
    # but dummy only accepts DUMMY_OTP = "123456"
    # ------------------------------------------------------------------
    def validate_otp(self, otp: str) -> bool:
        """
        Validate OTP. Dummy: accepts only '123456'.
        Live API later: POST OTP verify endpoint.
        """
        return (otp or "").strip() == DUMMY_OTP

    # ------------------------------------------------------------------
    # Existing: validate Jan Aadhaar + last 6 digits of application ID
    # ------------------------------------------------------------------
    def validate_identity(
        self, jan_aadhaar_id: str, previous_application_id: str
    ) -> Optional[dict[str, Any]]:
        """
        Scholarship portal identity check.
        previous_application_id is now accepted as last 6 digits OR full ID.
        Live API later: POST portal validate(janAadhaarId, previousApplicationId).
        """
        jan_aadhaar_id = (jan_aadhaar_id or "").strip()
        previous_application_id = (previous_application_id or "").strip().upper()
        if not jan_aadhaar_id or not previous_application_id:
            return None

        applicants = self._load().get("applicants") or {}
        applicant = applicants.get(jan_aadhaar_id)
        if not applicant:
            return None

        stored_id = str(applicant.get("previousApplicationId") or "").strip().upper()

        # Accept last 6 digits OR full application ID
        if (
            stored_id != previous_application_id
            and not stored_id.endswith(previous_application_id)
        ):
            return None

        return {"janAadhaarId": jan_aadhaar_id, **applicant}

    # ------------------------------------------------------------------
    # Existing: Jan Aadhaar linked documents (caste, domicile)
    # ------------------------------------------------------------------
    def fetch_linked_profile(self, jan_aadhaar_id: str) -> dict[str, Any]:
        """
        Jan Aadhaar DB fetch (caste, domicile, aadhaar, bank).
        Live API later: GET Jan Aadhaar linked documents/profile.
        """
        jan_aadhaar_id = (jan_aadhaar_id or "").strip()
        data = self._load()
        docs = (data.get("janAadhaarDocuments") or {}).get(jan_aadhaar_id) or []
        applicant = (data.get("applicants") or {}).get(jan_aadhaar_id) or {}

        caste = next((d for d in docs if d.get("type") == "CASTE_CERTIFICATE"), None)
        domicile = next((d for d in docs if d.get("type") == "DOMICILE_CERTIFICATE"), None)

        return {
            "casteCertificateNo": (caste or {}).get("certificateNo"),
            "casteAvailable": bool((caste or {}).get("available")),
            "domicileCertificateNo": (domicile or {}).get("certificateNo"),
            "aadhaarNumber": applicant.get("aadhaarNumber") or "Not available (dummy)",
            "bankAccountLinkedToAadhaar": applicant.get("bankAccountLinkedToAadhaar")
            or "Not available (dummy)",
            "bankName": applicant.get("bankName") or "",
        }

    # ------------------------------------------------------------------
    # Existing: submit renewal
    # ------------------------------------------------------------------
    def submit_renewal(self, applicant: dict[str, Any], documents: dict[str, Any]) -> str:
        """
        Submit renewal to Scholarship portal and return the new application ID.
        Live API later: POST portal submit(applicant, documents) -> newApplicationId.
        """
        previous_id = str(applicant.get("previousApplicationId") or "")
        running = previous_id.rsplit("/", 1)[-1] if "/" in previous_id else "9000000"
        year = applicant.get("renewalAcademicYear") or "2026-27"
        _ = documents
        return f"SCHOLARSHIP/{year}/{running}"
