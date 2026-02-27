import frappe
from typing import Any
from usi.models.result import Result
from usi.utils import utils
from pathlib import Path
from functools import lru_cache
SJMS_STATUS_API_URL = "https://ssp.rajasthan.gov.in/SSPService/SSPPensionerServiceForChatBot.svc/PensionStatus"
import json
import logging
from urllib.parse import urlencode
logger = logging.getLogger(__name__)
import requests
class PensionManager:
    
    @classmethod
    def get_pension_faq(cls) -> str:
        return cls._read_text_file("pensions/FAQ.txt")

    @staticmethod
    @lru_cache(maxsize=64)
    def _read_text_file(filename: str) -> str:
        # Robust path resolution (never relative to /usi/api)
        app_root = Path(frappe.get_app_path("usi"))
        path = app_root / "prompt" / filename
        return path.read_text(encoding="utf-8")
    
    @classmethod
    def get_pension_status_from_file(cls, application_id: str) -> Result:
        try:
            pension_candidates = cls._read_text_file("pensions/pension_candidates.json")
            pension_candidates = json.loads(pension_candidates)
            pension_candidate = pension_candidates.get(application_id)
            if not pension_candidate:
                return Result.not_found(message="Pension candidate not found", data="Pension candidate not found")
            return Result.success(message="Pension status fetched successfully", data=pension_candidate)
        except Exception:
            error_data = frappe.get_traceback()
            frappe.log_error(frappe.get_traceback(), "Pension Assistant: status lookup failed")
            return Result.failure(message="Failed to fetch pension status", error_data=error_data) 


    @classmethod
    def fetch_pension_status(cls, application_id: str) -> Result:
        """
        Fetch live application status from your backend.

        Uses SSP Pension API:
        POST https://ssp.rajasthan.gov.in/SSPService/SSPPensionerServiceForChatBot.svc/PensionStatus
        Query params:
          - Key
          - Mode
          - AppMob
        """
        if not application_id:
            return Result.failure(message="Application ID is required and cannot be empty")
        result_data: Any = None
        error_data: Any = None
        try:

            query_string = urlencode({
                "Key": "sSp@InchaTBOt0226",
                "Mode": 1,
                "AppMob": application_id,
            })

            full_url = f"{SJMS_STATUS_API_URL}?{query_string}"

            headers = {
                "Content-Type": "application/json",
                "User-Agent": "curl/7.79.1",   # 👈 important
                "Accept": "*/*",
                "Connection": "close",
            }

            res = requests.post(
                full_url,
                data="",  # explicitly empty body
                headers=headers,
                timeout=12,
            )
            
            try:
                payload: Any = res.json()
     
            except Exception:
                error_data = f"Non-JSON response from pension status service: {res.text}"
                return Result.failure(message="Failed to fetch application status", error_data=error_data)

            status = str(payload.get("Status") or "").strip()
            message_text = str(payload.get("Message") or "").strip()
            # Some backend failures return a .NET null-reference message; treat it as "not found/invalid id"
            if status != "0":
                return Result.not_found(
                    message="Application not found",
                    data=message_text,
                )

            # Contract observed:
            # - "0" => success (payload contains PensionerStatusPara)
            # - "3" => application not found
            # - other / empty => failure
            if status == "3":
                error_data = "Application not found"
                return Result.not_found(message="Application not found", data=error_data)
            if status != "0":
                error_data = message_text or "Unknown error"
                return Result.failure(message="Failed to fetch application status", error_data=error_data)

            result_data = payload.get("PensionerStatusPara")[0]
            result_data["pensionNumber"] = application_id
          
            if not result_data:
                return Result.not_found(
                    message="Application not found",
                    data="PensionerStatusPara missing/empty for successful response",
                )

            return Result.success(message="Application status fetched successfully", data=result_data)
        except Exception:
            error_data = frappe.get_traceback()
            frappe.log_error(frappe.get_traceback(), "Pension Assistant: status lookup failed")
            return Result.failure(message="Failed to fetch application status", error_data=error_data) 
        finally:
            utils.log_integration_request(
                request_data={"application_id": application_id},
                response_data=result_data,
                service_name='Fetch Pension Application Status',
                request_description='Fetch application status for application ID: {application_id}',
                error_data=error_data,
                reference_doctype=None,
                reference_docname=None,
                error_title='Fetch Pension Application Status Error',
            )