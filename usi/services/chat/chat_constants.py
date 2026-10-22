ALLOWED_SCHEMES = {"Scholarship", "Pension", "Palanhaar"}
ALLOWED_CHANNELS = {"Website", "WhatsApp"}
ALLOWED_INTENTS = [
    {
        "title": "Status Enquiry",
        "id": "STATUS"
    },
    {
        "title": "General Query",
        "id": "GENERAL"
    }
]
# Scholarship-only. Kept out of ALLOWED_INTENTS so Pension/Palanhaar
# intent buttons stay Status + General.
SCHOLARSHIP_RENEW_INTENT = {
    "title": "Renew",
    "id": "RENEW",
}
# Available on the main menu for every scheme (and as a link after responses).
GRIEVANCE_INTENT = {
    "title": "Raise Grievance",
    "id": "GRIEVANCE",
}
SCHEME_KEYWORDS = {
        "Scholarship": [
            # English
            "scholarship",
            # Hindi
            "छात्रवृत्ति",
            "स्कॉलरशिप"
        ],
        "Pension": [
            # English
            "pension",
            # Hindi
            "पेंशन"
        ],
        "Palanhaar": [
            # English
            "palanhar",
            "palanhaar",
            # Hindi
            "पालनहार",
        ],
    }
BUTTONS = [
                {"id": "Scholarship", "title": "छात्रवृत्ति (Scholarship)"},
                {"id": "Pension", "title": "पेंशन (Pension)"},
                {"id": "Palanhaar", "title": "पालनहार (Palanhaar)"},
            ]
    