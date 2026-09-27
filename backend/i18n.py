"""Lightweight English/Shona/Arabic interface translation.

Templates wrap user-facing text in ``_("...")``. English is the source
language; for Shona or Arabic the phrase is looked up in that language's
table (SHONA, ARABIC) and falls back to the English text if it has not been
translated yet. Arabic is written right to left, so base.html sets dir="rtl"
for it (see RTL_LANGUAGES).

Only the app's own interface text is translated. Data is never passed
through ``_()``: property names, street addresses, suburbs, cities and
countries (e.g. "Avondale Heights", "Samora Machel Avenue", "Harare") read
the same in every language. tests/test_i18n.py checks this.
"""
from flask import session

LANGUAGES = {"en": "English", "sn": "ChiShona", "ar": "العربية"}
RTL_LANGUAGES = {"ar"}
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


ARABIC = {
    # Navigation and layout
    "Dashboard": "لوحة التحكم",
    "Properties": "العقارات",
    "Map": "الخريطة",
    "Tenants": "المستأجرون",
    "Rent Tracker": "متابعة الإيجار",
    "Maintenance": "الصيانة",
    "Reports": "التقارير",
    "+ Add Staff": "+ موظف",
    "Manage Users": "المستخدمون",
    "My Work Queue": "قائمة أعمالي",
    "My Dashboard": "لوحتي",
    "Pay Rent": "دفع الإيجار",
    "Payment History": "سجل المدفوعات",
    "Submit Request": "تقديم طلب",
    "Log out": "خروج",
    "Language": "اللغة",
    "Digital Rental Management System": "نظام رقمي لإدارة الإيجارات",
    # Login and password reset
    "Log in": "تسجيل الدخول",
    "Email": "البريد الإلكتروني",
    "Password": "كلمة المرور",
    "Forgot your password?": "هل نسيت كلمة المرور؟",
    "Reset your password": "إعادة تعيين كلمة المرور",
    "Enter your email and we'll send you a reset link.": "أدخل بريدك الإلكتروني وسنرسل إليك رابطًا لإعادة التعيين.",
    "Send reset link": "إرسال الرابط",
    "Back to login": "العودة إلى تسجيل الدخول",
    # Portfolio dashboard
    "Portfolio Dashboard": "لوحة المحفظة العقارية",
    "Total Units": "إجمالي الوحدات",
    "Occupancy Rate": "نسبة الإشغال",
    "Rent Collected": "الإيجار المحصّل",
    "Outstanding Balance": "الرصيد المستحق",
    "Leases Expiring Within 30 Days": "عقود تنتهي خلال 30 يومًا",
    "No leases expiring soon.": "لا توجد عقود تنتهي قريبًا.",
    "Open Maintenance Requests": "طلبات الصيانة المفتوحة",
    "No open maintenance requests.": "لا توجد طلبات صيانة مفتوحة.",
    "Your Properties": "عقاراتك",
    "View all": "عرض الكل",
    "End Date": "تاريخ الانتهاء",
    # Table headings and common labels
    "Name": "الاسم",
    "Code": "الرمز",
    "Occupancy": "الإشغال",
    "Ticket": "رقم الطلب",
    "Title": "العنوان",
    "Status": "الحالة",
    "Tenant": "المستأجر",
    "Unit": "الوحدة",
    "Balance": "الرصيد",
    "National ID": "رقم الهوية",
    "Monthly Rent": "الإيجار الشهري",
    "Severity": "الأولوية",
    "Assigned": "المسؤول",
    "Date": "التاريخ",
    "Amount": "المبلغ",
    "Receipt #": "رقم الإيصال",
    # Properties
    "View on Map": "عرض على الخريطة",
    "+ Add New Property": "+ إضافة عقار",
    "Occupancy: {rate}%": "الإشغال: {rate}%",
    "No properties yet.": "لا توجد عقارات بعد.",
    "Add your first property": "أضف عقارك الأول",
    # Tenants
    "+ Create Tenant Profile": "+ تسجيل مستأجر",
    "Blacklisted": "محظور",
    "No Lease": "لا يوجد عقد",
    "No tenants yet.": "لا يوجد مستأجرون بعد.",
    # Rent tracker
    "Paid up": "مسدَّد",
    "Record Payment": "تسجيل دفعة",
    "History": "السجل",
    "No active leases.": "لا توجد عقود سارية.",
    # Maintenance
    "Maintenance Requests": "طلبات الصيانة",
    "Overdue": "متأخر",
    "No maintenance requests.": "لا توجد طلبات صيانة.",
    # Tenant portal
    "Welcome, {name}": "مرحبًا، {name}",
    "{property} · Unit {unit}": "{property} · الوحدة {unit}",
    "Balance Due": "المبلغ المستحق",
    "Pay Rent Now": "ادفع الإيجار الآن",
    "View Full Account Statement": "عرض كشف الحساب الكامل",
    "Download My Lease PDF": "تنزيل عقد الإيجار (PDF)",
    "You do not have an active lease on file. Please contact your property manager.":
        "لا يوجد لديك عقد إيجار ساري. يُرجى التواصل مع مدير العقار.",
    "Recent Payments": "أحدث المدفوعات",
    "No payments yet.": "لا توجد مدفوعات بعد.",
    "My Maintenance Requests": "طلبات الصيانة الخاصة بي",
    "+ New Request": "+ طلب جديد",
    "No maintenance requests yet.": "لا توجد طلبات صيانة بعد.",
    "Amount due:": "المبلغ المستحق:",
    "Unit:": "الوحدة:",
    "Pay Now": "ادفع الآن",
    "You have no outstanding balance. Thank you!": "لا يوجد عليك رصيد مستحق. شكرًا لك!",
    # Status badges
    "ACTIVE": "نشط",
    "OCCUPIED": "مشغولة",
    "VACANT": "شاغرة",
    "ASSIGNED": "مُسنَد",
    "SUBMITTED": "مُقدَّم",
    "IN PROGRESS": "قيد التنفيذ",
    "COMPLETED": "مكتمل",
    "CLOSED": "مغلق",
    "PENDING": "قيد الانتظار",
    "LOW": "منخفضة",
    "MEDIUM": "متوسطة",
    "HIGH": "عالية",
    "EMERGENCY": "طارئة",
}

TRANSLATIONS = {"sn": SHONA, "ar": ARABIC}


def current_language() -> str:
    lang = session.get("lang", DEFAULT_LANGUAGE)
    return lang if lang in LANGUAGES else DEFAULT_LANGUAGE


def text_direction() -> str:
    return "rtl" if current_language() in RTL_LANGUAGES else "ltr"


def translate(text: str, **values) -> str:
    text = TRANSLATIONS.get(current_language(), {}).get(text, text)
    return text.format(**values) if values else text
