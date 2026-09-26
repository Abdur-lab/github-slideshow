"""Lightweight English/Shona interface translation.

Templates wrap user-facing text in ``_("...")``. English is the source
language; when the session language is Shona the phrase is looked up in
SHONA and falls back to the English text if it has not been translated yet.
"""
from flask import session

LANGUAGES = {"en": "English", "sn": "ChiShona"}
DEFAULT_LANGUAGE = "en"

SHONA = {
    # Navigation and layout
    "Dashboard": "Dhashibhodhi",
    "Properties": "Zvivakwa",
    "Map": "Mepu",
    "Tenants": "Varoji",
    "Rent Tracker": "Kutevera Rendi",
    "Maintenance": "Kugadzirisa",
    "Reports": "Mishumo",
    "+ Add Staff": "+ Mushandi",
    "Manage Users": "Vashandisi",
    "My Work Queue": "Basa Rangu",
    "My Dashboard": "Dhashibhodhi Yangu",
    "Pay Rent": "Bhadhara Rendi",
    "Payment History": "Nhoroondo Yemibhadharo",
    "Submit Request": "Tumira Chikumbiro",
    "Log out": "Buda",
    "Language": "Mutauro",
    "Digital Rental Management System": "Sisitimu Yedhijitari Yekutarisira Rendi",
    # Login and password reset
    "Log in": "Pinda",
    "Email": "Email",
    "Password": "Pasiwedhi",
    "Forgot your password?": "Wakanganwa pasiwedhi yako?",
    "Reset your password": "Chinja pasiwedhi yako",
    "Enter your email and we'll send you a reset link.": "Isa email yako tigokutumira link yekuchinja pasiwedhi.",
    "Send reset link": "Tumira link",
    "Back to login": "Dzokera kunopinda",
    # Portfolio dashboard
    "Portfolio Dashboard": "Dhashibhodhi yeZvivakwa",
    "Total Units": "Mayuniti Ose",
    "Occupancy Rate": "Chiyero Chekugarwa",
    "Rent Collected": "Rendi Yaunganidzwa",
    "Outstanding Balance": "Chikwereti Chasara",
    "Leases Expiring Within 30 Days": "Zvibvumirano Zvinopera Mukati Memazuva 30",
    "No leases expiring soon.": "Hapana zvibvumirano zviri kupera munguva pfupi.",
    "Open Maintenance Requests": "Zvikumbiro Zvekugadzirisa Zvakavhurika",
    "No open maintenance requests.": "Hapana zvikumbiro zvekugadzirisa zvakavhurika.",
    "Your Properties": "Zvivakwa Zvako",
    "View all": "Ona zvose",
    "End Date": "Zuva Rekupera",
    # Table headings and common labels
    "Name": "Zita",
    "Code": "Kodhi",
    "Occupancy": "Kugarwa",
    "Ticket": "Tiketi",
    "Title": "Musoro",
    "Status": "Mamiriro",
    "Tenant": "Muroji",
    "Unit": "Yuniti",
    "Balance": "Chikwereti",
    "National ID": "Chitupa",
    "Monthly Rent": "Rendi Yemwedzi",
    "Severity": "Kukomba",
    "Assigned": "Akapiwa",
    "Date": "Zuva",
    "Amount": "Mari",
    "Receipt #": "Risiti #",
    # Properties
    "View on Map": "Ona paMepu",
    "+ Add New Property": "+ Wedzera Chivakwa",
    "Occupancy: {rate}%": "Kugarwa: {rate}%",
    "No properties yet.": "Hapana zvivakwa parizvino.",
    "Add your first property": "Wedzera chivakwa chako chekutanga",
    # Tenants
    "+ Create Tenant Profile": "+ Nyoresa Muroji",
    "Blacklisted": "Akarambidzwa",
    "No Lease": "Hapana Chibvumirano",
    "No tenants yet.": "Hapana varoji parizvino.",
    # Rent tracker
    "Paid up": "Zvakabhadharwa",
    "Record Payment": "Nyora Mubhadharo",
    "History": "Nhoroondo",
    "No active leases.": "Hapana zvibvumirano zviripo.",
    # Maintenance
    "Maintenance Requests": "Zvikumbiro Zvekugadzirisa",
    "Overdue": "Yapfuura nguva",
    "No maintenance requests.": "Hapana zvikumbiro zvekugadzirisa.",
    # Tenant portal
    "Welcome, {name}": "Mauya, {name}",
    "{property} · Unit {unit}": "{property} · Yuniti {unit}",
    "Balance Due": "Chikwereti",
    "Pay Rent Now": "Bhadhara Rendi Iye Zvino",
    "View Full Account Statement": "Ona Chitatimendi Chose",
    "Download My Lease PDF": "Dhawunirodha Chibvumirano Changu (PDF)",
    "You do not have an active lease on file. Please contact your property manager.":
        "Hauna chibvumirano chiri kushanda. Ndapota taura nemaneja wechivakwa chako.",
    "Recent Payments": "Mibhadharo Yichangobva Kuitwa",
    "No payments yet.": "Hapana mibhadharo parizvino.",
    "My Maintenance Requests": "Zvikumbiro Zvangu Zvekugadzirisa",
    "+ New Request": "+ Chikumbiro Chitsva",
    "No maintenance requests yet.": "Hapana zvikumbiro zvekugadzirisa parizvino.",
    "Amount due:": "Mari inofanira kubhadharwa:",
    "Unit:": "Yuniti:",
    "Pay Now": "Bhadhara Iye Zvino",
    "You have no outstanding balance. Thank you!": "Hauna chikwereti. Maita basa!",
    # Status badges
    "ACTIVE": "INOSHANDA",
    "OCCUPIED": "INOGARWA",
    "VACANT": "HAINA MUNHU",
    "ASSIGNED": "YAPIWA",
    "SUBMITTED": "YATUMIRWA",
    "IN PROGRESS": "IRI KUGADZIRWA",
    "COMPLETED": "YAPEDZWA",
    "CLOSED": "YAVHARWA",
    "PENDING": "YAKAMIRIRA",
    "LOW": "ZVISHOMA",
    "MEDIUM": "ZVEPAKATI",
    "HIGH": "ZVAKANYANYA",
    "EMERGENCY": "CHIMBICHIMBI",
}


def current_language() -> str:
    lang = session.get("lang", DEFAULT_LANGUAGE)
    return lang if lang in LANGUAGES else DEFAULT_LANGUAGE


def translate(text: str, **values) -> str:
    if current_language() == "sn":
        text = SHONA.get(text, text)
    return text.format(**values) if values else text
