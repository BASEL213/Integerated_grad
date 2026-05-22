"""
safety.py — Input/output safety layer
Checks inputs before the model and redacts PII from outputs.
"""
import re
from fastapi import HTTPException

MAX_MESSAGE_LEN = 2000

_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"disregard\s+(your\s+)?system\s+prompt",
    r"you\s+are\s+now\s+",
    r"act\s+as\s+(a\s+)?(?!real estate)",
    r"jailbreak",
    r"dan\s+mode",
    r"pretend\s+(you\s+are|to\s+be)",
    r"forget\s+(everything|your\s+instructions)",
]

# Arabic mutation keywords — user-facing chat must never trigger writes
_MUTATION_PATTERNS_AR = [
    r"عدّل\s+(?:في|عدد|سعر|بيانات|معلومات|الوحدات|المشروع)",
    r"عدل\s+(?:في|عدد|سعر|بيانات|معلومات|الوحدات|المشروع)",
    r"حدّث\s+(?:بيانات|معلومات|عدد|سعر|الوحدات|المشروع)",
    r"حدث\s+(?:بيانات|معلومات|عدد|سعر|الوحدات|المشروع)",
    r"احذف\s+(?:مشروع|وحدة|بيانات|سجل)",
    r"امسح\s+(?:مشروع|وحدة|بيانات|سجل)",
    r"أضف\s+(?:مشروع|وحدة|سجل|بيانات)",
    r"اضف\s+(?:مشروع|وحدة|سجل|بيانات)",
    r"غيّر\s+(?:عدد|سعر|بيانات|معلومات|الوحدات)",
    r"غير\s+(?:عدد|سعر|بيانات|معلومات|الوحدات)",
    r"ارفع\s+(?:سعر|عدد|الأسعار)",
    r"خفّض\s+(?:سعر|عدد|الأسعار)",
    r"خفض\s+(?:سعر|عدد|الأسعار)",
    r"أنشئ\s+(?:مشروع|وحدة|سجل)",
    r"انشئ\s+(?:مشروع|وحدة|سجل)",
]

_EGYPTIAN_ID_RE = re.compile(r'\b[23]\d{13}\b')
_PHONE_RE       = re.compile(r'\b01[0125]\d{8}\b')
_EMAIL_RE       = re.compile(r'\b[\w.+-]+@[\w-]+\.\w+\b')


def check_input(message: str) -> str | None:
    """
    Returns a refusal string if the message should be blocked, None otherwise.
    Still raises HTTP 400 for length/injection — those are hard errors.
    """
    if len(message) > MAX_MESSAGE_LEN:
        raise HTTPException(
            400,
            f"الرسالة طويلة جداً — الحد الأقصى {MAX_MESSAGE_LEN} حرف"
        )
    lower = message.lower()
    for pattern in _INJECTION_PATTERNS:
        if re.search(pattern, lower):
            raise HTTPException(400, "محتوى غير مقبول في الرسالة")
    for pattern in _MUTATION_PATTERNS_AR:
        if re.search(pattern, message):
            return "عذراً، لا أملك صلاحية تعديل البيانات. هذه الصلاحية محجوزة للمسؤولين فقط عبر لوحة الإدارة.\nهل يمكنني مساعدتك في شيء آخر؟"
    return None


def redact_pii(text: str) -> str:
    """Remove PII (Egyptian ID, phone, email) from model output before sending to user."""
    text = _EGYPTIAN_ID_RE.sub("**[رقم قومي]**", text)
    text = _PHONE_RE.sub("**[رقم هاتف]**", text)
    text = _EMAIL_RE.sub("**[بريد إلكتروني]**", text)
    return text


def contains_pii(text: str) -> bool:
    return bool(
        _EGYPTIAN_ID_RE.search(text) or
        _PHONE_RE.search(text) or
        _EMAIL_RE.search(text)
    )
