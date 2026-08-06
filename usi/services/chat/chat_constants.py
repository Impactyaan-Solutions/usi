ALLOWED_SCHEMES = {"Scholarship", "Pension", "Palanhaar","Anuprati"}
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
         "Anuprati": [
                # English
                "Anuprati",
                # Hindi
                "अनुप्रति"
            ]
    }
BUTTONS = [
                {"id": "Scholarship", "title": "छात्रवृत्ति (Scholarship)"},
                {"id": "Pension", "title": "पेंशन (Pension)"},
                {"id": "Palanhaar", "title": "पालनहार (Palanhaar)"},
                {"id": "Anuprati", "title":"अनुप्रति (Anuprati)"}
            ]
    