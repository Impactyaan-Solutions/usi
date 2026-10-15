import frappe
import json
import requests
import xml.etree.ElementTree as ET


@frappe.whitelist(allow_guest=True)
def get_application_status(application_id):
    url = "https://sjmsnew.rajasthan.gov.in/palanhaar/Tracking.asmx/APPLICATIONSTATUSChatBot"

    payload = {
        "APPLICATIONID": application_id
    }

    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }

    try:
        response = requests.post(
            url,
            data=payload,
            headers=headers,
            timeout=30
        )

        response.raise_for_status()

        root = ET.fromstring(response.content)

        json_string = root.text

        if not json_string:
            frappe.throw("Empty response from Palanhar API")

        return json.loads(json_string)

    except requests.exceptions.ConnectionError:
        frappe.throw(
            "Unable to connect to Palanhar API. "
            "Please check server internet/network connectivity."
        )

    except requests.exceptions.Timeout:
        frappe.throw("Palanhar API request timed out.")

    except ET.ParseError:
        frappe.throw("Invalid XML response received from Palanhar API.")

    except json.JSONDecodeError:
        frappe.throw("API response contains invalid JSON.")