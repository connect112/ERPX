"""
Triage of incoming comments and messages: a category, a priority, and whether a person must handle it with care.

This is deliberately plain keyword rules, not an AI: it is free, instant, predictable and keeps the text inside the server. It
only ever *labels* things so the inbox can be filtered. It never replies, hides or deletes anything, and the labels are
suggestions a person can see are labels. Wording is matched in English plus a few common Hinglish phrases.

Sensitive items (complaints, refunds, legal threats, security incidents, personal contact details) are flagged `needs_care`:
the reply screen then tells the person to handle it personally and asks them to confirm before sending.
"""

import re
from dataclasses import dataclass

CATEGORIES = ("enquiry", "complaint", "question", "thanks", "spam", "other")

_URL = re.compile(r"(https?://|www\.|\b[a-z0-9-]+\.(com|in|co|io|xyz|ru|top|click|link)\b)", re.IGNORECASE)
_PHONE = re.compile(r"(?<!\d)(\+?\d[\d\s().-]{8,}\d)(?!\d)")
_EMAIL = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+")

_SPAM = re.compile(
    r"\b(dm\s+me\s+for|earn\s+\$|make\s+money|crypto|bitcoin|forex|investment\s+plan|follow\s*(me|back|for\s*follow)|f4f|"
    r"check\s+(my|out\s+my)\s+(profile|page)|promote\s+your|boost\s+your|buy\s+followers|click\s+(the\s+)?link|free\s+gift|giveaway\s+winner|telegram|"
    r"whatsapp\s+me|sugar\s+(daddy|mommy))\b",
    re.IGNORECASE,
)
_REFUND = re.compile(r"\b(refund|money\s*back|chargeback|return\s+my\s+money|paise\s+wapas|refund\s+chahiye)\b", re.IGNORECASE)
_COMPLAINT = re.compile(
    r"\b(complain(t)?|scam|fraud|cheat(ed|ing)?|fake|worst|waste\s+of|not\s+happy|disappointed|misleading|false\s+promise|rip[\s-]?off|"
    r"pathetic|useless|no\s+response|nobody\s+(replies|responds)|harass(ed|ment)?)\b",
    re.IGNORECASE,
)
_LEGAL = re.compile(r"\b(legal\s+(action|notice)|lawyer|advocate|consumer\s+(court|forum)|police|cyber\s*crime|fir\b|sue\b|defam(ation|e))\b", re.IGNORECASE)
_SECURITY_INCIDENT = re.compile(
    r"\b(my\s+(account|data|password|phone|laptop)\s+(was|got|has\s+been)?\s*(hacked|compromised|leaked|stolen)|data\s+(breach|leak)|ransomware|"
    r"i\s+(was|got)\s+hacked|someone\s+hacked|hacked\s+my|account\s+takeover)\b",
    re.IGNORECASE,
)
_ENQUIRY = re.compile(
    r"\b(fee(s)?|price|pricing|cost|how\s+much|batch(es)?|course(s)?|enrol(l|ment)?|admission(s)?|apply|join(ing)?|syllabus|curriculum|duration|"
    r"demo(\s+class)?|certificat(e|ion)|placement(s)?|intern(ship)?|brochure|weekend|weekday|online\s+or\s+offline|timings?|schedule|"
    r"details|contact(\s+number)?|call\s+me|how\s+to\s+(join|apply|register)|register|seats?|eligib(le|ility)|"
    r"fees?\s+kitn(a|i)|kab\s+start|batch\s+kab|details\s+do)\b",
    re.IGNORECASE,
)
_THANKS = re.compile(r"\b(thank(s| you)?|thanx|awesome|great\s+(post|content|work|explanation)|love\s+(this|it)|helpful|well\s+explained|nice\s+(post|one|work)|amazing|superb|shukriya|dhanyavad)\b", re.IGNORECASE)


@dataclass(frozen=True)
class Triage:
    category: str
    priority: str  # high | medium | low
    needs_care: bool
    care_reason: str | None


def classify(text: str | None) -> Triage:
    """Label one piece of incoming text. Never raises: anything odd is simply "other"."""
    body = (text or "").strip()
    if not body:
        return Triage("other", "low", False, None)

    reasons: list[str] = []
    if _LEGAL.search(body):
        reasons.append("mentions legal action or the police")
    if _SECURITY_INCIDENT.search(body):
        reasons.append("reports a security incident")
    if _REFUND.search(body):
        reasons.append("asks for a refund")
    complaint = bool(_COMPLAINT.search(body))
    if complaint and not reasons:
        reasons.append("is a complaint")
    if _PHONE.search(body) or _EMAIL.search(body):
        reasons.append("contains personal contact details (answer privately, don't repeat them in public)")
    sensitive = [r for r in reasons if not r.startswith("contains personal")]

    spam_signals = len(_URL.findall(body)) >= 2 or bool(_SPAM.search(body))
    if spam_signals and not sensitive:
        return Triage("spam", "low", False, None)

    if sensitive:
        return Triage("complaint", "high", True, "This " + "; ".join(reasons[:2]) + ". Handle it personally.")
    if _ENQUIRY.search(body):
        care = next((r for r in reasons if r.startswith("contains personal")), None)
        return Triage("enquiry", "medium", care is not None, ("This " + care + ".") if care else None)
    care = next((r for r in reasons if r.startswith("contains personal")), None)
    if "?" in body:
        return Triage("question", "low", care is not None, ("This " + care + ".") if care else None)
    if _THANKS.search(body):
        return Triage("thanks", "low", care is not None, ("This " + care + ".") if care else None)
    return Triage("other", "low", care is not None, ("This " + care + ".") if care else None)
