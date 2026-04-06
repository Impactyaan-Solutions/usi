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
from datetime import datetime, timedelta
import calendar
import re
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
            # Normalize field name for downstream consumers
            if "YearlyVerificationStatus" in result_data and "VerificationValidUpto" not in result_data:
                verification_valid_upto = result_data.get("YearlyVerificationStatus").strip()
                if "(" in verification_valid_upto:
                    verification_valid_upto = verification_valid_upto.split("(")[0].strip()
                    result_data["VerificationValidUpto"] = verification_valid_upto
                    result_data["VerificationStatus"] = PensionManager.get_verification_status(verification_valid_upto)
                else:
                    result_data["VerificationValidUpto"] = verification_valid_upto
                result_data["VerificationValidUpto"] = result_data.get("YearlyVerificationStatus")
                del result_data["YearlyVerificationStatus"]


            if "LastPaymentDate" in result_data:
                last_payment_date = result_data["LastPaymentDate"].strip()
                if "," in result_data["LastPaymentDate"]:
                    last_payment_date = result_data["LastPaymentDate"].split(",")[1].strip()
                    if "Paid Upto" in last_payment_date:
                        last_payment_date = last_payment_date.split("Paid Upto")[1].strip()
                        result_data["PAYMENT_STATUS"] = PensionManager.get_payment_status(last_payment_date)
                    else:
                        result_data["PAYMENT_STATUS"]=PensionManager.get_payment_status(last_payment_date)
                else:
                    result_data["PAYMENT_STATUS"] = PensionManager.get_payment_status(last_payment_date)
                result_data["LastPaymentDate"] = last_payment_date
                
            
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
    @staticmethod
    def get_payment_status(last_payment_date: str) -> str:
        last_payment_date_dt = PensionManager._convert_date_to_datetime(last_payment_date)
        if last_payment_date_dt is None:
            return "UNKNOWN"
        # Get last day of that month
        last_day = calendar.monthrange(last_payment_date_dt.year, last_payment_date_dt.month)[1]
        final_dt = last_payment_date_dt.replace(day=last_day)
        today = datetime.now().date()
        if final_dt.date() + timedelta(days=60) < today:
            return "DELAYED"
        else:
            return "REGULAR"
    
    @staticmethod
    def _convert_date_to_datetime(date_str: str) -> datetime:
        try:
            dt = datetime.strptime(date_str, "%B %Y")
            return dt
        except ValueError:
            try:
                    match = re.search(r"\d{2}/\d{2}/\d{4}", date_str)
                    if match:
                        date_str = match.group()
                    elif not re.fullmatch(r"\d{2}/\d{2}/\d{4}", date_str):
                        return None  # clearly invalid format

                    dt = datetime.strptime(date_str, "%d/%m/%Y")
                    return dt.replace(day=1)
            except ValueError:
                return None

    @staticmethod
    def get_verification_status(verification_valid_upto: str) -> str:
        today = datetime.now().date()
        verification_valid_upto_dt = PensionManager._convert_date_to_datetime(verification_valid_upto)
        if verification_valid_upto_dt is None: 
            return "UNKNOWN"
        if verification_valid_upto_dt.date() < today:
            return "EXPIRED"
        elif verification_valid_upto_dt.date() <= today + timedelta(days=45):
            return "ABOUT TO EXPIRE"
        else:
            return "VALID"