import frappe
import json
from typing import Dict
from usi.models.result import Result
from frappe import _
from usi.utils.custom_response import custom_response

logger = frappe.logger("api", allow_site=True, file_count=50)
class BaseSchemeManager:

    DOCTYPE = None

    def __init__(self, scheme_config=None, user=None):
        self.scheme_config = scheme_config or {}
        self.user = user or frappe.session.user
    
    def run_eligibility_check(self, applicant_data: dict) -> Result:
        pass
    
    def get_scheme_meta(self) -> Result:
        meta = frappe.get_meta(self.DOCTYPE)
        all_fields = [
            {
                "fieldname": df.fieldname,
                "label": self._get_multilingual(df.label),
                "fieldtype": df.fieldtype,
                "required": df.reqd,
                "hidden": df.hidden,
                "options": self._get_field_options(df)
            }
            for df in meta.fields
            if df.fieldname and df.fieldtype not in ( "Column Break")
        ] 
        return Result.success(message="Scheme meta fetched successfully", data={"fields": all_fields})
    
    def create_application(self, data):
        self._validate_create(data)
        data = self._transform_create(data)

        doc = self._insert_doc(data)
        self._post_create(doc)

        return doc

    def get_application(self, name):
        return self._get_doc(name)

    def list_applications(self, filters=None):
        return frappe.get_list(self.DOCTYPE, filters=filters or {}, fields=["*"])

    def _validate_create(self, data):
        parsed_data = self._parse_payload(data)
        if not parsed_data:
            frappe.throw("applicant_data must be a non-empty JSON object")

        meta = frappe.get_meta(self.DOCTYPE)
        required_fields = [
            df
            for df in meta.fields
            if df.reqd and df.fieldname and df.fieldtype not in ("Section Break", "Column Break")
        ]

        missing_fields = []
        for df in required_fields:
            value = parsed_data.get(df.fieldname)
            if value in (None, "", "null", "undefined"):
                missing_fields.append(df.label or df.fieldname)

        if missing_fields:
            frappe.throw("Missing required fields: " + ", ".join(missing_fields))

    def _get_multilingual(self, label):
        translations = {}

        original_lang = getattr(frappe.local, "lang", "en")

        try:
            for lang in ["en", "hi"]:
                frappe.local.lang = lang
                translations[lang] = _(label)
        finally:
            frappe.local.lang = original_lang

        return translations

    def _transform_create(self, data):
        parsed_data = self._parse_payload(data)
        meta = frappe.get_meta(self.DOCTYPE)
        allowed_fieldnames = {
            df.fieldname
            for df in meta.fields
            if df.fieldname and df.fieldtype not in ("Section Break", "Column Break")
        }

        transformed = {}
        for key, value in parsed_data.items():
            if key not in allowed_fieldnames:
                continue
            if value in ("", "null", "undefined"):
                transformed[key] = None
            else:
                transformed[key] = value
        return transformed

    def _post_create(self, doc):
        pass
        
    def _insert_doc(self, data):
        logger.info(f"Inserting document: {data}")
        doc = frappe.get_doc({
            "doctype": self.DOCTYPE,
            **data
        })
        doc.insert()
        return doc

    def _get_doc(self, name):
        return frappe.get_doc(self.DOCTYPE, name)
    
    def _parse_payload(self, data) -> Dict:
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError as exc:
                frappe.throw(f"Invalid JSON in applicant_data: {exc}")

        if not isinstance(data, dict):
            frappe.throw("applicant_data must be a JSON object")

        return data

    def _get_field_options(self, df):
        if df.fieldtype != "Select" or not df.options:
            return None

        # options are newline separated
        raw_options = df.options.split("\n")

        return [
            {
                "value": opt.strip(),
                "label": self._get_multilingual(opt.strip())
            }
            for opt in raw_options
            if opt.strip()
        ]