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
from contextlib import contextmanager
from contextvars import ContextVar
from typing import NamedTuple

from flask import has_request_context, session

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
    # --- Pages, messages and stored codes added with the full Arabic translation ---
    # admin
    "Add Staff Account": "إضافة حساب موظف",
    "Add Maintenance Staff Account": "إضافة حساب فني صيانة",
    "Full name": "الاسم الكامل",
    "Create Staff Account": "إنشاء حساب موظف",
    "Cancel": "إلغاء",
    "A welcome email with a link to set a password will be sent to the new account.":
        "سيتم إرسال بريد ترحيبي إلى الحساب الجديد يتضمن رابطًا لتعيين كلمة المرور.",
    "Manage Users & Roles": "إدارة المستخدمين والأدوار",
    "+ Add Staff Account": "+ إضافة حساب موظف",
    "Role": "الدور",
    "Update": "تحديث",
    "Active": "نشط",
    "Inactive": "غير نشط",
    "Save": "حفظ",
    # rent
    "Record Rent Payment": "تسجيل دفعة إيجار",
    "Select a tenant…": "اختر مستأجرًا…",
    "balance {amount}": "الرصيد {amount}",
    "Current balance:": "الرصيد الحالي:",
    "Method": "طريقة الدفع",
    "Payment date": "تاريخ الدفع",
    "Notes / reference (optional)": "ملاحظات / مرجع (اختياري)",
    "Save Payment": "حفظ الدفعة",
    "Rent Statement": "كشف حساب الإيجار",
    "Download PDF": "تنزيل PDF",
    "Lease: {start} to {end}": "العقد: من {start} إلى {end}",
    "Pro rata: first month prorated to {amount} (full rate {full}).":
        "بالتناسب: احتُسب الشهر الأول بقيمة {amount} (القيمة الكاملة {full}).",
    "Current monthly rent: {current} (original {original}).": "الإيجار الشهري الحالي: {current} (الأصلي {original}).",
    "Statement Period Start": "بداية فترة الكشف",
    "Statement Period End": "نهاية فترة الكشف",
    "View Period": "عرض الفترة",
    "Clear": "مسح",
    "Receipt": "الإيصال",
    "No activity found for the selected period.": "لا توجد حركات في الفترة المحددة.",
    "Opening Balance": "الرصيد الافتتاحي",
    "Rent + Charges": "الإيجار + الرسوم",
    "Paid This Period": "المدفوع في هذه الفترة",
    "Closing Balance": "الرصيد الختامي",
    "Rent Due": "الإيجار المستحق",
    "Charges": "الرسوم",
    "Total Paid": "إجمالي المدفوع",
    "Operational & Sundry Charges": "الرسوم التشغيلية والمتفرقة",
    "Type": "النوع",
    "Description": "الوصف",
    "No operational or sundry charges have been added to this lease.":
        "لم تُضف أي رسوم تشغيلية أو متفرقة إلى هذا العقد.",
    "Charge Type": "نوع الرسوم",
    "Add Charge": "إضافة رسوم",
    "Electricity Meter": "عداد الكهرباء",
    "Rate: {rate} per unit of consumption.": "التعرفة: {rate} لكل وحدة استهلاك.",
    "Last reading: {value} on {date}.": "آخر قراءة: {value} بتاريخ {date}.",
    "No readings recorded yet.": "لم تُسجَّل أي قراءات بعد.",
    "Reading": "القراءة",
    "Consumption": "الاستهلاك",
    "Rate": "التعرفة",
    "No meter readings recorded for this unit.": "لم تُسجَّل أي قراءات عداد لهذه الوحدة.",
    "Reading Date": "تاريخ القراءة",
    "Meter Reading": "قراءة العداد",
    "Record Reading": "تسجيل القراءة",
    "Rent Revisions": "تعديلات الإيجار",
    "Base rent: {base}. Current rent: {current}.": "الإيجار الأساسي: {base}. الإيجار الحالي: {current}.",
    "Effective Date": "تاريخ السريان",
    "Reason": "السبب",
    "No rent revisions recorded for this lease.": "لم تُسجَّل أي تعديلات على الإيجار لهذا العقد.",
    "New Monthly Rent": "الإيجار الشهري الجديد",
    "Reason (optional)": "السبب (اختياري)",
    "Add Revision": "إضافة تعديل",
    "Rent Invoices": "فواتير الإيجار",
    "Automatically generated by the daily billing job as each period's due date arrives — one invoice per period, never duplicated.":
        "تُنشأ تلقائيًا بواسطة عملية الفوترة اليومية عند حلول موعد استحقاق كل فترة — فاتورة واحدة لكل فترة دون أي تكرار.",
    "Billing Period Due": "استحقاق فترة الفوترة",
    "Generated": "تاريخ الإنشاء",
    "No invoices generated yet for this lease.": "لم تُنشأ أي فواتير لهذا العقد بعد.",
    "Rent History": "سجل الإيجار",
    "Rent History — {name}": "سجل الإيجار — {name}",
    "Export CSV": "تصدير CSV",
    "No payment history available.": "لا يوجد سجل مدفوعات.",
    # auth
    "Forgot Password": "نسيت كلمة المرور",
    "Reset Password": "إعادة تعيين كلمة المرور",
    "Choose a new password": "اختر كلمة مرور جديدة",
    "New password": "كلمة المرور الجديدة",
    "Update password": "تحديث كلمة المرور",
    "Set Up Your Account": "إعداد حسابك",
    "Complete your tenant profile to finish setting up your account.": "أكمل ملفك كمستأجر لإنهاء إعداد حسابك.",
    "Phone number": "رقم الهاتف",
    "Emergency contact": "جهة الاتصال في حالات الطوارئ",
    "Choose a password": "اختر كلمة مرور",
    "Create my account": "إنشاء حسابي",
    # errors
    "Server Error": "خطأ في الخادم",
    "500 — Something went wrong": "500 — حدث خطأ ما",
    "Please try again, or contact support if the problem persists.":
        "يُرجى المحاولة مرة أخرى، أو التواصل مع الدعم إذا استمرت المشكلة.",
    "Go to login": "الذهاب إلى تسجيل الدخول",
    "Not Found": "غير موجود",
    "404 — Not Found": "404 — الصفحة غير موجودة",
    "The page you're looking for doesn't exist.": "الصفحة التي تبحث عنها غير موجودة.",
    "Forbidden": "غير مسموح",
    "403 — Forbidden": "403 — الوصول مرفوض",
    "You don't have permission to view this page.": "ليست لديك صلاحية لعرض هذه الصفحة.",
    # maintenance
    "Submit Maintenance Request": "تقديم طلب صيانة",
    "Category": "الفئة",
    "Photos (optional, up to 3, JPG/PNG, max 5 MB each)":
        "الصور (اختياري، حتى 3 صور، JPG/PNG، بحد أقصى 5 ميغابايت لكل صورة)",
    "Details": "التفاصيل",
    "Tenant:": "المستأجر:",
    "Category:": "الفئة:",
    "Description:": "الوصف:",
    "Assigned to:": "مُسنَد إلى:",
    "Target date:": "التاريخ المستهدف:",
    "Tenant rating:": "تقييم المستأجر:",
    "Assign to Staff": "تعيين إلى فني",
    "Staff member": "الفني",
    "Select…": "اختر…",
    "Target completion date": "تاريخ الإنجاز المستهدف",
    "Internal notes (optional)": "ملاحظات داخلية (اختياري)",
    "Confirm Assignment": "تأكيد التعيين",
    "Update Status": "تحديث الحالة",
    "Work notes": "ملاحظات العمل",
    "Mark In Progress": "تحديد كقيد التنفيذ",
    "Completion photos (optional, up to 3)": "صور إنجاز العمل (اختياري، حتى 3 صور)",
    "Mark Completed": "تحديد كمكتمل",
    "Submitted Photos": "الصور المرفقة",
    "Completion Photos": "صور إنجاز العمل",
    "Review Completed Work": "مراجعة العمل المنجز",
    "Satisfaction rating (1-5, optional)": "تقييم الرضا (1-5، اختياري)",
    "Confirm Resolution": "تأكيد الحل",
    "Reason for reopening": "سبب إعادة الفتح",
    "Reopen Request": "إعادة فتح الطلب",
    "Force-close this request?": "هل تريد إغلاق هذا الطلب إجباريًا؟",
    "Force Close": "إغلاق إجباري",
    "Work Notes": "ملاحظات العمل",
    "No notes yet.": "لا توجد ملاحظات بعد.",
    "Costs (total {amount})": "التكاليف (الإجمالي {amount})",
    "Costs": "التكاليف",
    "Labour": "العمالة",
    "Materials": "المواد",
    "Contractor": "مقاول",
    "Other": "أخرى",
    "Log Cost": "تسجيل التكلفة",
    # properties
    "Add Property": "إضافة عقار",
    "Add New Property": "إضافة عقار جديد",
    "Property name": "اسم العقار",
    "Address": "العنوان",
    "City": "المدينة",
    "Country": "الدولة",
    "Currency": "العملة",
    "Late fee": "غرامة التأخير",
    "Amount (fixed) or % (percentage)": "المبلغ (ثابت) أو % (نسبة مئوية)",
    "Map location (optional)": "الموقع على الخريطة (اختياري)",
    "Latitude": "خط العرض",
    "Longitude": "خط الطول",
    "Click the map to drop a pin, or type coordinates directly.":
        "انقر على الخريطة لوضع علامة، أو اكتب الإحداثيات مباشرة.",
    "Clear location": "مسح الموقع",
    "Property photos (up to 10, JPG/PNG, max 5 MB each)":
        "صور العقار (حتى 10 صور، JPG/PNG، بحد أقصى 5 ميغابايت لكل صورة)",
    "Save Property": "حفظ العقار",
    "Tenant History — {code}": "سجل المستأجرين — {code}",
    "Unit {number}": "الوحدة {number}",
    "Back to {name}": "العودة إلى {name}",
    "Every tenant who has occupied this unit": "جميع المستأجرين الذين شغلوا هذه الوحدة",
    "Lease Start": "بداية العقد",
    "Lease End": "نهاية العقد",
    "No tenant has occupied this unit yet.": "لم يشغل أي مستأجر هذه الوحدة بعد.",
    "Edit {name}": "تعديل {name}",
    "Electricity rate (per unit of consumption, 0 = not billed)": "تعرفة الكهرباء (لكل وحدة استهلاك، 0 = بدون فوترة)",
    "Click the map to move the pin, or type coordinates directly.":
        "انقر على الخريطة لنقل العلامة، أو اكتب الإحداثيات مباشرة.",
    "Current photos ({count}/10)": "الصور الحالية ({count}/10)",
    "Add more photos (JPG/PNG, max 5 MB each)": "إضافة صور أخرى (JPG/PNG، بحد أقصى 5 ميغابايت لكل صورة)",
    "Save Changes": "حفظ التغييرات",
    "Edit": "تعديل",
    "+ Add Unit": "+ إضافة وحدة",
    "Archive this property?": "هل تريد أرشفة هذا العقار؟",
    "Archive": "أرشفة",
    "Occupied": "مشغولة",
    "Vacant": "شاغرة",
    "Location": "الموقع",
    "Photos": "الصور",
    "Units": "الوحدات",
    "Rent": "الإيجار",
    "Invite Tenant": "دعوة مستأجر",
    "Create Tenant Profile": "إنشاء ملف مستأجر",
    "View Tenant": "عرض المستأجر",
    "No units yet.": "لا توجد وحدات بعد.",
    "Operating Expenses": "مصروفات التشغيل",
    "Costs the owner incurs against this property — taxes, insurance, management fees, utilities, and general upkeep — as distinct from charges billed to tenants.":
        "التكاليف التي يتحملها المالك على هذا العقار — الضرائب والتأمين ورسوم الإدارة والمرافق والصيانة العامة — وهي مختلفة عن الرسوم التي تُفوتر على المستأجرين.",
    "No expenses recorded for this property yet.": "لم تُسجَّل أي مصروفات لهذا العقار بعد.",
    "Add Expense": "إضافة مصروف",
    "Add Unit": "إضافة وحدة",
    "Add Unit to {property}": "إضافة وحدة إلى {property}",
    "Unit number": "رقم الوحدة",
    "Floor": "الطابق",
    "Size (sqm)": "المساحة (م²)",
    "Monthly rent": "الإيجار الشهري",
    "Security deposit": "مبلغ التأمين",
    "Unit photos (up to 5, JPG/PNG, max 5 MB each)": "صور الوحدة (حتى 5 صور، JPG/PNG، بحد أقصى 5 ميغابايت لكل صورة)",
    "Save Unit": "حفظ الوحدة",
    "Edit Unit {code}": "تعديل الوحدة {code}",
    "Under Maintenance": "تحت الصيانة",
    "Occupied (set automatically by an active lease)": "مشغولة (تُحدَّد تلقائيًا عند وجود عقد نشط)",
    "Status is locked to Occupied while a lease is active.": "الحالة مثبتة على «مشغولة» طالما يوجد عقد نشط.",
    "Current photos ({count}/5)": "الصور الحالية ({count}/5)",
    "Properties Map": "خريطة العقارات",
    "List View": "عرض القائمة",
    "1 of {total} properties has no map location set yet — add coordinates from the property's Edit page to show it here.":
        "عقار واحد من أصل {total} لم يُحدَّد موقعه على الخريطة بعد — أضف الإحداثيات من صفحة تعديل العقار لعرضه هنا.",
    "{count} of {total} properties have no map location set yet — add coordinates from the property's Edit page to show it here.":
        "{count} من أصل {total} عقارات لم يُحدَّد موقعها على الخريطة بعد — أضف الإحداثيات من صفحة تعديل العقار لعرضها هنا.",
    "No properties have a map location set yet.": "لم يُحدَّد موقع أي عقار على الخريطة بعد.",
    "Add coordinates from a property's Add or Edit page to see it here.":
        "أضف الإحداثيات من صفحة إضافة العقار أو تعديله لعرضه هنا.",
    # tenants
    "National ID number": "رقم الهوية الوطنية",
    "Email (optional)": "البريد الإلكتروني (اختياري)",
    "Phone": "الهاتف",
    "ID document (optional, PDF/JPG/PNG, max 10 MB)": "وثيقة الهوية (اختياري، PDF/JPG/PNG، بحد أقصى 10 ميغابايت)",
    "Save Profile": "حفظ الملف",
    "Invite Tenant to Unit {code}": "دعوة مستأجر إلى الوحدة {code}",
    "Sends a secure self-registration link, valid for 48 hours.": "يُرسل رابط تسجيل ذاتي آمن صالح لمدة 48 ساعة.",
    "Tenant name": "اسم المستأجر",
    "Email address": "عنوان البريد الإلكتروني",
    "Send Invitation": "إرسال الدعوة",
    "View ID Document": "عرض وثيقة الهوية",
    "Blacklisted: {reason}": "في القائمة السوداء: {reason}",
    "Remove Flag": "إزالة من القائمة السوداء",
    "Reason for blacklisting (required)": "سبب الإضافة إلى القائمة السوداء (مطلوب)",
    "Blacklist this tenant? They will be blocked from future leases.":
        "هل تريد إضافة هذا المستأجر إلى القائمة السوداء؟ لن يتمكن من إبرام عقود إيجار مستقبلًا.",
    "Blacklist Tenant": "إضافة إلى القائمة السوداء",
    "Active Lease": "العقد الحالي",
    "Term:": "المدة:",
    "{start} to {end}": "من {start} إلى {end}",
    "Monthly rent:": "الإيجار الشهري:",
    "(originally {amount})": "(كان في الأصل {amount})",
    "(first month prorated)": "(الشهر الأول محسوب بالتناسب)",
    "Balance:": "الرصيد:",
    "Generate Statement": "إنشاء كشف حساب",
    "Download Lease PDF": "تنزيل عقد الإيجار (PDF)",
    "No active lease.": "لا يوجد عقد نشط.",
    "Upload Lease Document": "رفع مستند عقد الإيجار",
    "Lease History": "سجل العقود",
    "Term": "المدة",
    "No lease history.": "لا يوجد سجل عقود.",
    "Upload Lease": "رفع عقد الإيجار",
    "Upload Lease for {name}": "رفع عقد إيجار لـ {name}",
    "Select a vacant unit…": "اختر وحدة شاغرة…",
    "{amount}/mo": "{amount} شهريًا",
    "Lease start date": "تاريخ بدء العقد",
    "Lease end date": "تاريخ انتهاء العقد",
    "Rent due day of month": "يوم استحقاق الإيجار من كل شهر",
    "Prorate the first month's rent based on the move-in date": "احتساب إيجار الشهر الأول بالتناسب حسب تاريخ الانتقال",
    "If the tenant moves in after the 1st, the first rent charge is reduced to a daily rate for the days actually occupied that month, instead of a full month.":
        "إذا انتقل المستأجر بعد اليوم الأول من الشهر، تُحتسب أول دفعة إيجار بمعدل يومي عن الأيام التي شغلها فعليًا في ذلك الشهر بدلًا من شهر كامل.",
    "Signed lease PDF (max 20 MB)": "عقد الإيجار الموقّع بصيغة PDF (بحد أقصى 20 ميغابايت)",
    "Save & Activate Lease": "حفظ وتفعيل العقد",
    # reports
    "Property Performance Report": "تقرير أداء العقارات",
    "Export Excel": "تصدير Excel",
    "Export PDF": "تصدير PDF",
    "Property": "العقار",
    "All Properties (Portfolio)": "جميع العقارات (المحفظة)",
    "Outstanding": "المتأخرات",
    "Total Expenses": "إجمالي المصروفات",
    "Maintenance cost:": "تكلفة الصيانة:",
    "General expenses:": "المصروفات العامة:",
    "Net income estimate:": "صافي الدخل التقديري:",
    "Open maintenance requests:": "طلبات الصيانة المفتوحة:",
    "By Property": "حسب العقار",
    "Collected": "المحصّل",
    "Expenses": "المصروفات",
    "Net Income": "صافي الدخل",
    "No data available for the selected period.": "لا توجد بيانات للفترة المحددة.",
    "Maintenance Summary": "ملخص الصيانة",
    "From": "من",
    "To": "إلى",
    "Apply": "تطبيق",
    "Requests raised between {start} and {end}, by their current stage. Open covers Submitted, Acknowledged and Assigned; Closed covers Completed and Closed.":
        "الطلبات المقدَّمة بين {start} و{end} حسب مرحلتها الحالية. تشمل «مفتوحة» الطلبات المقدَّمة والمستلَمة والمُسندة، وتشمل «مغلقة» الطلبات المكتملة والمغلقة.",
    "Open": "مفتوحة",
    "In Progress": "قيد التنفيذ",
    "Closed": "مغلق",
    "Total": "الإجمالي",
    "All properties": "جميع العقارات",
    "No properties to report on.": "لا توجد عقارات لإعداد تقرير عنها.",
    # portal
    "Full Account Statement": "كشف الحساب الكامل",
    "No payment history yet.": "لا يوجد سجل مدفوعات بعد.",
    # Messages
    "You may upload at most {count} photos at a time.": "يمكنك رفع {count} صور كحد أقصى في المرة الواحدة.",
    "Invalid email or password.": "البريد الإلكتروني أو كلمة المرور غير صحيحة.",
    "Account locked due to too many failed attempts. Try again in 15 minutes.":
        "تم قفل الحساب بسبب كثرة المحاولات الفاشلة. حاول مرة أخرى بعد 15 دقيقة.",
    "You have been logged out.": "تم تسجيل خروجك.",
    "If that email exists, a reset link has been sent.":
        "إذا كان هذا البريد الإلكتروني مسجّلًا، فقد تم إرسال رابط إعادة التعيين.",
    "This reset link is invalid or has expired.": "رابط إعادة التعيين غير صالح أو منتهي الصلاحية.",
    "Password must be at least 8 characters.": "يجب أن تتكون كلمة المرور من 8 أحرف على الأقل.",
    "Password updated. Please log in.": "تم تحديث كلمة المرور. يُرجى تسجيل الدخول.",
    "This invitation is invalid or has expired.": "هذه الدعوة غير صالحة أو منتهية الصلاحية.",
    "National ID is required.": "الرقم الوطني مطلوب.",
    "An account with this email already exists. Please log in instead.":
        "يوجد حساب بهذا البريد الإلكتروني بالفعل. يُرجى تسجيل الدخول بدلًا من ذلك.",
    "A tenant with this national ID already exists.": "يوجد مستأجر مسجّل بهذا الرقم الوطني بالفعل.",
    "Welcome to RentalPro! Your profile has been created.": "مرحبًا بك في RentalPro! تم إنشاء ملفك الشخصي.",
    "You do not have an active lease. Please contact your property manager.":
        "لا يوجد لديك عقد إيجار نشط. يُرجى التواصل مع مدير العقار.",
    "You already have {count} open requests. Please wait for one to be resolved.":
        "لديك بالفعل {count} طلبات مفتوحة. يُرجى الانتظار حتى يتم حل أحدها.",
    "Title is required.": "العنوان مطلوب.",
    "Description is required.": "الوصف مطلوب.",
    "Request submitted. Ticket number {ticket}.": "تم إرسال الطلب. رقم التذكرة {ticket}.",
    "Please choose a valid staff member.": "يُرجى اختيار فني صالح.",
    "Target date was invalid and was not saved.": "التاريخ المستهدف غير صالح ولم يتم حفظه.",
    "Request assigned.": "تم تعيين الطلب.",
    "Status updated.": "تم تحديث الحالة.",
    "Request closed. Thank you!": "تم إغلاق الطلب. شكرًا لك!",
    "Request reopened.": "تمت إعادة فتح الطلب.",
    "Cost amount must be a positive number.": "يجب أن تكون قيمة التكلفة رقمًا موجبًا.",
    "Cost logged.": "تم تسجيل التكلفة.",
    "Property name is required.": "اسم العقار مطلوب.",
    "Address is required.": "العنوان مطلوب.",
    "City is required.": "المدينة مطلوبة.",
    "Country is required.": "الدولة مطلوبة.",
    "You already have a property with this name.": "لديك عقار بهذا الاسم بالفعل.",
    "Late fee amount must be a positive number when a late fee type is selected.":
        "يجب أن تكون قيمة غرامة التأخير رقمًا موجبًا عند اختيار نوع الغرامة.",
    "Set both latitude and longitude, or leave the map location blank.":
        "حدِّد خط العرض وخط الطول معًا، أو اترك الموقع على الخريطة فارغًا.",
    "Map location is invalid — latitude must be -90 to 90 and longitude -180 to 180.":
        "الموقع على الخريطة غير صالح — يجب أن يكون خط العرض بين ‎-90 و90 وخط الطول بين ‎-180 و180.",
    "Property {code} created.": "تم إنشاء العقار {code}.",
    "A description is required for the expense.": "يجب إدخال وصف للمصروف.",
    "Expense amount must be a positive number.": "يجب أن يكون مبلغ المصروف رقمًا موجبًا.",
    "Expense date is invalid.": "تاريخ المصروف غير صالح.",
    "{category} expense of {amount} recorded.": "تم تسجيل مصروف {category} بقيمة {amount}.",
    "Electricity rate must be a non-negative number.": "يجب ألا تكون تعرفة الكهرباء رقمًا سالبًا.",
    "A property may have at most {count} photos in total.": "يمكن أن يحتوي العقار على {count} صور كحد أقصى.",
    "Property updated.": "تم تحديث العقار.",
    "Unit number is required.": "رقم الوحدة مطلوب.",
    "Unit number already in use in this property.": "رقم الوحدة مستخدم بالفعل في هذا العقار.",
    "Monthly rent must be a positive number.": "يجب أن يكون الإيجار الشهري رقمًا موجبًا.",
    "Unit {code} added.": "تمت إضافة الوحدة {code}.",
    "Occupancy status is set automatically when a lease is activated; it cannot be set to Occupied here.":
        "تُحدَّد حالة الإشغال تلقائيًا عند تفعيل العقد، ولا يمكن تعيينها كمشغولة من هنا.",
    "This unit has an active lease and cannot be manually set to Vacant.":
        "هذه الوحدة لديها عقد نشط ولا يمكن تعيينها يدويًا كشاغرة.",
    "A unit may have at most {count} photos in total.": "يمكن أن تحتوي الوحدة على {count} صور كحد أقصى.",
    "Unit updated.": "تم تحديث الوحدة.",
    "This property has active leases. Terminate them before archiving.":
        "يحتوي هذا العقار على عقود نشطة. يجب إنهاؤها قبل الأرشفة.",
    "Property archived.": "تمت أرشفة العقار.",
    "This unit has an active lease. Please terminate the lease before archiving.":
        "هذه الوحدة لديها عقد نشط. يُرجى إنهاء العقد قبل الأرشفة.",
    "Unit archived.": "تمت أرشفة الوحدة.",
    "You do not have an active lease.": "لا يوجد لديك عقد إيجار نشط.",
    "You have no outstanding balance.": "لا يوجد عليك رصيد مستحق.",
    "Nothing to confirm.": "لا يوجد ما يتطلب التأكيد.",
    "Payment successful. Thank you!": "تمت عملية الدفع بنجاح. شكرًا لك!",
    "Invalid role.": "الدور غير صالح.",
    "Every account must have at least one active Property Owner. This change was blocked.":
        "يجب أن يكون هناك مالك عقار نشط واحد على الأقل. تم منع هذا التغيير.",
    "Updated {name}.": "تم تحديث {name}.",
    "Full name is required.": "الاسم الكامل مطلوب.",
    "A valid email address is required.": "يجب إدخال بريد إلكتروني صالح.",
    "A user with this email already exists.": "يوجد مستخدم مسجّل بهذا البريد الإلكتروني بالفعل.",
    "Staff account created for {name}.": "تم إنشاء حساب موظف لـ {name}.",
    "Dates must be in YYYY-MM-DD format; showing the current month instead.":
        "يجب أن تكون التواريخ بصيغة YYYY-MM-DD؛ يُعرض الشهر الحالي بدلًا من ذلك.",
    "The start date must be on or before the end date; showing the current month instead.":
        "يجب أن يكون تاريخ البداية في تاريخ النهاية أو قبله؛ يُعرض الشهر الحالي بدلًا من ذلك.",
    "A tenant with this national ID may already exist. Please search before creating a new one.":
        "قد يكون هناك مستأجر مسجّل بهذا الرقم الوطني. يُرجى البحث قبل إنشاء ملف جديد.",
    "Email address is invalid.": "البريد الإلكتروني غير صالح.",
    "ID document must be a valid PDF, JPG, or PNG under 10 MB.":
        "يجب أن تكون وثيقة الهوية بصيغة PDF أو JPG أو PNG صالحة وبحجم أقل من 10 ميغابايت.",
    "Tenant profile created.": "تم إنشاء ملف المستأجر.",
    "Only vacant units can be invited to.": "لا يمكن إرسال دعوات إلا للوحدات الشاغرة.",
    "Tenant name is required.": "اسم المستأجر مطلوب.",
    "Invitation sent to {email} (valid 48 hours).": "تم إرسال الدعوة إلى {email} (صالحة لمدة 48 ساعة).",
    "This tenant is blacklisted ({reason}) and cannot be given a new lease.":
        "هذا المستأجر في القائمة السوداء ({reason}) ولا يمكن منحه عقدًا جديدًا.",
    "no reason on file": "لا يوجد سبب مسجّل",
    "Please select a unit.": "يُرجى اختيار وحدة.",
    "This unit already has a different active tenant.": "هذه الوحدة مؤجرة لمستأجر آخر حاليًا.",
    "A valid lease start date is required.": "يجب إدخال تاريخ بدء صالح للعقد.",
    "A valid lease end date is required.": "يجب إدخال تاريخ انتهاء صالح للعقد.",
    "Lease end date must be after the start date.": "يجب أن يكون تاريخ انتهاء العقد بعد تاريخ البدء.",
    "A signed lease PDF (max 20 MB) is required.": "يجب إرفاق عقد الإيجار الموقّع بصيغة PDF (بحد أقصى 20 ميغابايت).",
    "Lease activated and unit marked Occupied.": "تم تفعيل العقد وتحديد الوحدة كمشغولة.",
    "A reason is required to blacklist a tenant.": "يجب ذكر سبب لإضافة المستأجر إلى القائمة السوداء.",
    "Tenant flagged as blacklisted.": "تمت إضافة المستأجر إلى القائمة السوداء.",
    "Blacklist flag removed.": "تمت إزالة المستأجر من القائمة السوداء.",
    "Please select a tenant/lease.": "يُرجى اختيار مستأجر / عقد.",
    "Amount must be a positive number.": "يجب أن يكون المبلغ رقمًا موجبًا.",
    "Payment date is invalid.": "تاريخ الدفع غير صالح.",
    "Payment date is in the future — please confirm this is correct.":
        "تاريخ الدفع في المستقبل — يُرجى التأكد من صحته.",
    "Payment recorded. Receipt {receipt}.": "تم تسجيل الدفعة. رقم الإيصال {receipt}.",
    "Statement period dates are invalid.": "تواريخ فترة الكشف غير صالحة.",
    "Statement end date must be on or after the start date.": "يجب أن يكون تاريخ نهاية الكشف في تاريخ البداية أو بعده.",
    "A description is required for the charge.": "يجب إدخال وصف للرسوم.",
    "Charge amount must be a positive number.": "يجب أن يكون مبلغ الرسوم رقمًا موجبًا.",
    "{type} charge of {amount} added.": "تمت إضافة رسوم {type} بقيمة {amount}.",
    "Reading date is invalid.": "تاريخ القراءة غير صالح.",
    "Meter reading must be a non-negative number.": "يجب ألا تكون قراءة العداد رقمًا سالبًا.",
    "Reading ({value}) is lower than the last recorded reading ({previous}).":
        "القراءة ({value}) أقل من آخر قراءة مسجّلة ({previous}).",
    "Reading recorded. Electricity charge of {amount} added.": "تم تسجيل القراءة وإضافة رسوم كهرباء بقيمة {amount}.",
    "Reading recorded. This unit has no active lease, so no charge was billed.":
        "تم تسجيل القراءة. لا يوجد عقد نشط لهذه الوحدة، لذا لم تُحتسب أي رسوم.",
    "Reading recorded as the baseline for this unit.": "تم تسجيل القراءة كقراءة أساسية لهذه الوحدة.",
    "A valid effective date is required.": "يجب إدخال تاريخ سريان صالح.",
    "Effective date cannot be before the lease start date.": "لا يمكن أن يسبق تاريخ السريان تاريخ بدء العقد.",
    "Revised monthly rent must be a positive number.": "يجب أن يكون الإيجار الشهري المعدّل رقمًا موجبًا.",
    "Rent revision recorded: {amount} effective {date}.": "تم تسجيل تعديل الإيجار: {amount} اعتبارًا من {date}.",
    "\"{filename}\" is not a valid JPG/PNG under 5 MB and was not attached.":
        "الملف \"{filename}\" ليس صورة JPG/PNG صالحة بحجم أقل من 5 ميغابايت، ولم يتم إرفاقه.",
    "\"{filename}\" is not a valid JPG/PNG under 5 MB and was not uploaded.":
        "الملف \"{filename}\" ليس صورة JPG/PNG صالحة بحجم أقل من 5 ميغابايت، ولم يتم رفعه.",
    # Stored codes (label filter) and status badges
    "Admin": "المسؤول",
    "Property Owner": "مالك العقار",
    "Property Manager": "مدير العقار",
    "Maintenance Staff": "فني صيانة",
    "Residential": "سكني",
    "Commercial": "تجاري",
    "Mixed": "مختلط",
    "None": "بدون",
    "Fixed": "ثابت",
    "Percentage": "نسبة مئوية",
    "Studio": "استوديو",
    "1 Bedroom": "غرفة نوم واحدة",
    "2 Bedrooms": "غرفتا نوم",
    "3 Bedrooms": "ثلاث غرف نوم",
    "Shop": "محل تجاري",
    "Office": "مكتب",
    "Cash": "نقدًا",
    "Bank Transfer": "تحويل بنكي",
    "Online": "إلكترونيًا",
    "Cheque": "شيك",
    "Operational": "تشغيلية",
    "Sundry": "متفرقة",
    "Electricity": "كهرباء",
    "Tax": "الضرائب",
    "Insurance": "التأمين",
    "Utilities": "المرافق",
    "Management Fee": "رسوم الإدارة",
    "Plumbing": "السباكة",
    "Electrical": "كهرباء",
    "Structural": "إنشائي",
    "HVAC": "التكييف والتهوية",
    "Pest Control": "مكافحة الحشرات",
    "Low": "منخفض",
    "Medium": "متوسط",
    "High": "مرتفع",
    "Emergency": "طارئ",
    "UNDER MAINTENANCE": "تحت الصيانة",
    "ARCHIVED": "مؤرشف",
    "TERMINATED": "منتهٍ بالإلغاء",
    "EXPIRED": "منتهي المدة",
    "ACKNOWLEDGED": "مُستلَم",
    # --- Emails, SMS, PDFs and spreadsheets ---
    "Rent of {amount} for unit {unit} is due on {date}.": "يستحق إيجار بقيمة {amount} للوحدة {unit} في {date}.",
    "[{tier}] Rent of {amount} is {days} day(s) overdue.":
        "[{tier}] الإيجار البالغ {amount} متأخر منذ {days} يوم/أيام.",
    "Lease for unit {unit} at {property} expires on {date} ({days} days remaining).":
        "ينتهي عقد إيجار الوحدة {unit} في {property} بتاريخ {date} (متبقٍّ {days} يومًا).",
    "Rent due soon": "موعد استحقاق الإيجار قريب",
    "Overdue rent notice": "إشعار بتأخر الإيجار",
    "Daily overdue rent summary": "الملخص اليومي للإيجارات المتأخرة",
    "{count} tenant(s) overdue, totalling {amount} outstanding.":
        "{count} مستأجر/مستأجرين متأخرون، بإجمالي مستحقات {amount}.",
    "Ticket {ticket} is {days} day(s) past its target completion date.":
        "التذكرة {ticket} متأخرة {days} يوم/أيام عن تاريخ الإنجاز المستهدف.",
    "EMERGENCY ticket {ticket} has not been acknowledged in over 2 hours.":
        "لم يتم استلام التذكرة الطارئة {ticket} منذ أكثر من ساعتين.",
    "Your lease is expiring soon": "عقد إيجارك على وشك الانتهاء",
    "Tenant lease expiring in {days} days": "عقد إيجار مستأجر ينتهي خلال {days} يومًا",
    "{name}: Lease for unit {unit} at {property} expires on {date} ({days} days remaining).":
        "{name}: ينتهي عقد إيجار الوحدة {unit} في {property} بتاريخ {date} (متبقٍّ {days} يومًا).",
    "New rent invoice generated": "تم إصدار فاتورة إيجار جديدة",
    "A rent invoice of {amount} for unit {unit} has been generated for the billing period due {date}. Current balance: {balance}.":
        "تم إصدار فاتورة إيجار بقيمة {amount} للوحدة {unit} عن فترة الفوترة المستحقة في {date}. الرصيد الحالي: {balance}.",
    "Gentle reminder": "تذكير ودّي",
    "Overdue maintenance escalation": "تصعيد صيانة متأخرة",
    "Emergency maintenance not acknowledged": "لم يتم استلام طلب صيانة طارئ",
    "Firm notice — late fee may apply": "إشعار حازم — قد تُطبَّق غرامة تأخير",
    "Final notice — escalation warning": "إشعار نهائي — تحذير بالتصعيد",
    "Portfolio Summary": "ملخص المحفظة",
    "Metric": "المؤشر",
    "Value": "القيمة",
    "Occupancy %": "نسبة الإشغال %",
    "Maintenance Cost": "تكلفة الصيانة",
    "General Expenses": "المصروفات العامة",
    "Open Requests": "الطلبات المفتوحة",
    "Property: {name}": "العقار: {name}",
    "RentalPro — Rent Statement": "RentalPro — كشف حساب الإيجار",
    "Tenant: {name}": "المستأجر: {name}",
    "Unit: {unit}": "الوحدة: {unit}",
    "Lease term: {start} to {end}": "مدة العقد: من {start} إلى {end}",
    "Generated by {name}": "أعدّه {name}",
    "RentalPro — Payment Receipt": "RentalPro — إيصال دفع",
    "Receipt #: {receipt}": "رقم الإيصال: {receipt}",
    "Date Paid": "تاريخ الدفع",
    "Amount Paid": "المبلغ المدفوع",
    "Notes": "ملاحظات",
    "Balance after this payment: {amount}": "الرصيد بعد هذه الدفعة: {amount}",
    "RentalPro — Property Performance Report": "RentalPro — تقرير أداء العقارات",
    "Statement period: {start} to {end}": "فترة الكشف: من {start} إلى {end}",
    "Opening balance: {amount}": "الرصيد الافتتاحي: {amount}",
    "Payment": "دفعة",
    "Rent charged this period: {amount}": "الإيجار المستحق في هذه الفترة: {amount}",
    "Paid this period: {amount}": "المدفوع في هذه الفترة: {amount}",
    "Closing balance: {amount}": "الرصيد الختامي: {amount}",
    "Rent charged to date: {amount}": "الإيجار المستحق حتى تاريخه: {amount}",
    "Total paid: {amount}": "إجمالي المدفوع: {amount}",
    "Outstanding balance: {amount}": "الرصيد المستحق: {amount}",
    "Recorded by {name}": "سجّلها {name}",
    "Rent payment": "دفعة إيجار",
    "Operational/sundry charges this period: {amount}": "الرسوم التشغيلية والمتفرقة في هذه الفترة: {amount}",
    "Operational/sundry charges: {amount}": "الرسوم التشغيلية والمتفرقة: {amount}",
    "Reset your RentalPro password": "إعادة تعيين كلمة مرور RentalPro",
    "Reset your password (valid 1 hour): {link}": "أعد تعيين كلمة المرور (الرابط صالح لمدة ساعة): {link}",
    "Maintenance request received": "تم استلام طلب الصيانة",
    "Ticket {ticket} has been received.": "تم استلام التذكرة {ticket}.",
    "New maintenance request": "طلب صيانة جديد",
    "{ticket}: {title} ({severity})": "{ticket}: {title} ({severity})",
    "Maintenance request assigned to you": "تم إسناد طلب صيانة إليك",
    "Ticket {ticket}: {title}": "التذكرة {ticket}: {title}",
    "Your request has been assigned": "تم إسناد طلبك",
    "Ticket {ticket} has been assigned to our team.": "تم إسناد التذكرة {ticket} إلى فريقنا.",
    "EMERGENCY maintenance request {ticket}: {title}": "طلب صيانة طارئ {ticket}: {title}",
    "Maintenance request updated": "تم تحديث طلب الصيانة",
    "Ticket {ticket} is now {status}.": "حالة التذكرة {ticket} الآن: {status}.",
    "Maintenance request reopened": "تمت إعادة فتح طلب الصيانة",
    "Ticket {ticket} was reopened by the tenant.": "أعاد المستأجر فتح التذكرة {ticket}.",
    "Payment received": "تم استلام الدفعة",
    "We received your online payment of {amount} ({receipt}).": "استلمنا دفعتك الإلكترونية بقيمة {amount} ({receipt}).",
    "Tenant payment received": "تم استلام دفعة من مستأجر",
    "{name} paid {amount} online.": "دفع {name} مبلغ {amount} إلكترونيًا.",
    "Your RentalPro account was updated": "تم تحديث حسابك في RentalPro",
    "Your account role is now {role}.": "دور حسابك الآن: {role}.",
    "Welcome to RentalPro": "مرحبًا بك في RentalPro",
    "A Maintenance Staff account has been created for you. Set your password: {link}":
        "تم إنشاء حساب موظف صيانة لك. عيّن كلمة المرور: {link}",
    "You're invited to RentalPro": "أنت مدعو إلى RentalPro",
    "You've been invited to set up your tenant account: {link}": "تمت دعوتك لإعداد حسابك كمستأجر: {link}",
    "Your lease has been activated": "تم تفعيل عقد إيجارك",
    "Your lease for unit {unit} from {start} to {end} is now active.":
        "عقد إيجارك للوحدة {unit} من {start} إلى {end} أصبح ساريًا الآن.",
    "An account has been created for you. Set your password: {link}": "تم إنشاء حساب لك. عيّن كلمة المرور: {link}",
    "A new charge was added to your account": "تمت إضافة رسوم جديدة إلى حسابك",
    "A {type} charge of {amount} ({description}) was added to your unit {unit}. Updated balance: {balance}.":
        "تمت إضافة رسوم {type} بقيمة {amount} ({description}) إلى وحدتك {unit}. الرصيد المحدَّث: {balance}.",
    "Your rent is changing": "إيجارك سيتغير",
    "Your monthly rent for unit {unit} will change to {amount}, effective {date}.":
        "سيتغير إيجارك الشهري للوحدة {unit} إلى {amount} اعتبارًا من {date}.",
    "Rent payment received": "تم استلام دفعة الإيجار",
    "We received your payment of {amount} ({receipt}). Remaining balance: {balance}.":
        "استلمنا دفعتك بقيمة {amount} ({receipt}). الرصيد المتبقي: {balance}.",
    "A new electricity charge was added to your account": "تمت إضافة رسوم كهرباء جديدة إلى حسابك",
    "An electricity charge of {amount} ({consumption} units) was added to your unit {unit}. Updated balance: {balance}.":
        "تمت إضافة رسوم كهرباء بقيمة {amount} ({consumption} وحدة استهلاك) إلى وحدتك {unit}. الرصيد المحدَّث: {balance}.",
    "Receipt Number": "رقم الإيصال",
    "Occupied Units": "الوحدات المشغولة",
    "Submitted": "مُقدَّم",
    "Acknowledged": "تم الاستلام",
    "Completed": "مكتمل",
    # Rate limit page
    "Too many attempts": "محاولات كثيرة جدًا",
    "429 — Too many attempts": "429 — محاولات كثيرة جدًا",
    "You have tried this too many times in a short time. Please wait a minute, then try again.":
        "لقد حاولت عدة مرات في وقت قصير. يُرجى الانتظار دقيقة ثم المحاولة مرة أخرى.",
}

TRANSLATIONS = {"sn": SHONA, "ar": ARABIC}


def ltr(value) -> str:
    """Keep a left-to-right value (a date, code or email) in order inside other text.

    On an Arabic page a date such as 2026-03-13 inside a sentence is otherwise
    reordered by the browser to read 13-03-2026. The Unicode isolate
    characters (U+2066 ... U+2069) are only added on right-to-left pages.
    """
    return f"\u2066{value}\u2069" if text_direction() == "rtl" else str(value)


# Set by use_language() to render text for someone other than the current
# visitor, e.g. an email to a tenant sent by a nightly job.
_language_override: ContextVar[str | None] = ContextVar("language_override", default=None)


def money(value, currency=None) -> str:
    """An amount the same way on every screen: "USD 1,250.00", or "1,250.00"
    when there is no single currency (e.g. a portfolio mixing currencies).
    Kept in left-to-right order on Arabic pages."""
    if value is None:
        return ""
    text = f"{value:,.2f}"
    return ltr(f"{currency} {text}" if currency else text)


def current_language() -> str:
    lang = _language_override.get()
    if lang is None:
        lang = session.get("lang", DEFAULT_LANGUAGE) if has_request_context() else DEFAULT_LANGUAGE
    return lang if lang in LANGUAGES else DEFAULT_LANGUAGE


@contextmanager
def use_language(code):
    """Translate in the given language (e.g. a recipient's saved preference) for the block."""
    token = _language_override.set(code if code in LANGUAGES else DEFAULT_LANGUAGE)
    try:
        yield
    finally:
        _language_override.reset(token)


class Code(str):
    """A stored code (IN_PROGRESS, BANK_TRANSFER) passed as a message value; it is
    shown through label() in the language the message is translated into."""


class Phrase(str):
    """An English phrase passed as a message value; it is translated along with the message."""


class Money(NamedTuple):
    """An amount passed as a message value; formatted by money() in the message's language."""

    amount: float
    currency: str | None = None


def render_message(text: str, **values) -> str:
    """Translate a message whose values may include Code and Phrase items."""
    values = {
        key: (
            label(value) if isinstance(value, Code)
            else translate(value) if isinstance(value, Phrase)
            else money(*value) if isinstance(value, Money)
            else value
        )
        for key, value in values.items()
    }
    return translate(text, **values)


def text_direction() -> str:
    return "rtl" if current_language() in RTL_LANGUAGES else "ltr"


def translate(text: str, **values) -> str:
    text = TRANSLATIONS.get(current_language(), {}).get(text, text)
    return text.format(**values) if values else text


# Stored codes whose English wording is not just the code in title case.
LABEL_ENGLISH = {"1BR": "1 Bedroom", "2BR": "2 Bedrooms", "3BR": "3 Bedrooms", "HVAC": "HVAC"}


def label(value) -> str:
    """Show a stored code (BANK_TRANSFER, MANAGEMENT_FEE, 2BR) as words in the current language."""
    if value is None:
        return ""
    return translate(LABEL_ENGLISH.get(value, str(value).replace("_", " ").title()))
