"""
Plain-text + HTML email templates (the built-in defaults).

The wording lives in `registry.py` and can be edited per organisation from the admin UI; these functions
render the *default* wording and are kept for callers (and tests) that want it without a database.
Senders use `modules.email_templates.render`, which applies an organisation's edits when there are any.
"""

from modules.email_templates.render import render_default


def verification_email(full_name: str, verification_url: str) -> tuple[str, str, str]:
    return render_default("verification", {"full_name": full_name, "verification_url": verification_url})


def password_reset_email(full_name: str, reset_url: str) -> tuple[str, str, str]:
    return render_default("password_reset", {"full_name": full_name, "reset_url": reset_url})


def account_invite_email(full_name: str, set_password_url: str) -> tuple[str, str, str]:
    return render_default("account_invite", {"full_name": full_name, "set_password_url": set_password_url})


def payroll_draft_ready_email(full_name: str, period_label: str, review_url: str) -> tuple[str, str, str]:
    return render_default(
        "payroll_draft_ready", {"full_name": full_name, "period_label": period_label, "review_url": review_url}
    )


def payslip_ready_email(full_name: str, period_label: str) -> tuple[str, str, str]:
    return render_default("payslip_ready", {"full_name": full_name, "period_label": period_label})


def announcement_email(full_name: str, title: str, body: str, scope_label: str) -> tuple[str, str, str]:
    return render_default(
        "announcement", {"full_name": full_name, "title": title, "body": body, "scope_label": scope_label}
    )


def workshop_exam_invite_email(
    full_name: str, exam_title: str, exam_url: str, duration_minutes: int
) -> tuple[str, str, str]:
    return render_default(
        "workshop_exam_invite",
        {"full_name": full_name, "exam_title": exam_title, "exam_url": exam_url, "duration_minutes": duration_minutes},
    )


def workshop_certificate_email(full_name: str, exam_title: str) -> tuple[str, str, str]:
    return render_default("workshop_certificate", {"full_name": full_name, "exam_title": exam_title})


def hackathon_participant_welcome_email(
    full_name: str, hackathon_title: str, set_password_url: str, login_url: str
) -> tuple[str, str, str]:
    return render_default(
        "hackathon_participant_welcome",
        {
            "full_name": full_name,
            "hackathon_title": hackathon_title,
            "set_password_url": set_password_url,
            "login_url": login_url,
        },
    )
