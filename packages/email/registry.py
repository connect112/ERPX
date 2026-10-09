"""
Every email ERPX sends, with its default wording.

The defaults live here in code; an organisation (or, for event emails, one hackathon) can override the
subject and body from the admin UI. Resetting an override brings the default back. Defaults are written in
the markup of `markup.py` and mirror what was sent before templates became editable.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Variable:
    name: str
    description: str
    sample: str


@dataclass(frozen=True)
class TemplateDef:
    key: str
    name: str
    category: str
    description: str
    when_sent: str
    subject: str
    body: str
    variables: tuple[Variable, ...]
    # Placeholders that must stay in the message (usually the link), or the email would be useless.
    required: tuple[str, ...] = ()
    button_color: str = "#2563eb"
    # Whether one hackathon can have its own wording of this email.
    event_scoped: bool = False
    has_attachment: bool = False
    extra: dict = field(default_factory=dict)


_NAME = Variable("full_name", "The person's full name", "Asha Rao")

TEMPLATES: tuple[TemplateDef, ...] = (
    TemplateDef(
        key="verification",
        name="Verify your email",
        category="Account",
        description="Asks a new user to confirm their email address.",
        when_sent="When someone registers (or asks for the verification email again).",
        subject="Verify your ERPX account",
        body=(
            "# Welcome to ERPX, {{full_name}}\n\n"
            "Please verify your email address to activate your account.\n\n"
            "[Verify Email]({{verification_url}})\n\n"
            "> This link expires in 24 hours. If you didn't create this account, you can ignore this email."
        ),
        variables=(_NAME, Variable("verification_url", "The link that confirms the address", "https://erp.example.com/verify?token=abc123")),
        required=("verification_url",),
    ),
    TemplateDef(
        key="password_reset",
        name="Reset password",
        category="Account",
        description="Lets someone choose a new password after they ask to reset it.",
        when_sent="When a user clicks 'Forgot password'.",
        subject="Reset your ERPX password",
        body=(
            "# Reset your password\n\n"
            "Hi {{full_name}}, click below to choose a new password.\n\n"
            "[Reset Password]({{reset_url}})\n\n"
            "> This link expires in 1 hour. If you didn't request this, you can ignore this email."
        ),
        variables=(_NAME, Variable("reset_url", "The link to choose a new password", "https://erp.example.com/reset-password?token=abc123")),
        required=("reset_url",),
    ),
    TemplateDef(
        key="account_invite",
        name="Account invite (set your password)",
        category="Account",
        description="Invites someone whose account an administrator created, so they can set a password.",
        when_sent="When an employee, student, organisation admin or provisioned account is created or its login email is re-sent.",
        subject="Reset your ERPX password",
        body=(
            "# Reset your password\n\n"
            "Hi {{full_name}}, click below to choose a new password.\n\n"
            "[Reset Password]({{set_password_url}})\n\n"
            "> This link expires in 1 hour. If you didn't request this, you can ignore this email."
        ),
        variables=(_NAME, Variable("set_password_url", "The link to set their password", "https://erp.example.com/reset-password?token=abc123")),
        required=("set_password_url",),
    ),
    TemplateDef(
        key="hackathon_participant_welcome",
        name="Hackathon participant welcome",
        category="Hackathons",
        description="Gives a hackathon participant their login and tells them what to do next.",
        when_sent="When participants are added to a hackathon (or sent a fresh login link).",
        subject="Your login for {{hackathon_title}}",
        body=(
            "# {{hackathon_title}}\n\n"
            "Hi {{full_name}}, you're registered and an ERPX account has been created for you.\n\n"
            "**1.** Choose your password (the link works for 3 days):\n\n"
            "[Set my password]({{set_password_url}})\n\n"
            "**2.** Then [sign in]({{login_url}}), open Hackathons, and create a team or join one.\n\n"
            "> If you weren't expecting this, you can ignore this email."
        ),
        variables=(
            _NAME,
            Variable("hackathon_title", "The hackathon's title", "DevSecStorm"),
            Variable("set_password_url", "The link to choose their password", "https://lms.example.com/reset-password?token=abc123"),
            Variable("login_url", "The sign-in page", "https://lms.example.com/login"),
        ),
        required=("set_password_url",),
        event_scoped=True,
    ),
    TemplateDef(
        key="hackathon_winner_certificate",
        name="Hackathon winner certificate",
        category="Hackathons",
        description="Delivers a winning team member's certificate (attached as a PDF).",
        when_sent="When the certificates for the 1st, 2nd and 3rd place teams are sent.",
        subject="Congratulations! Your certificate: {{place}} in {{hackathon_title}}",
        body=(
            "# Congratulations, {{full_name}}!\n\n"
            "Your team **{{team_name}}** secured **{{place}}** in **{{hackathon_title}}**. "
            "Your certificate is attached to this email as a PDF.\n\n"
            "> Well done, and thank you for taking part."
        ),
        variables=(
            _NAME,
            Variable("hackathon_title", "The hackathon's title", "DevSecStorm"),
            Variable("place", "The place the team won", "1st place"),
            Variable("team_name", "The person's team", "Team Alpha"),
        ),
        event_scoped=True,
        has_attachment=True,
    ),
    TemplateDef(
        key="hackathon_participation_certificate",
        name="Hackathon participation certificate",
        category="Hackathons",
        description="Delivers a participant's certificate of participation (attached as a PDF).",
        when_sent="When participation certificates are sent to a hackathon's other participants.",
        subject="Your participation certificate: {{hackathon_title}}",
        body=(
            "# Thank you for taking part\n\n"
            "Hi {{full_name}}, thank you for taking part in **{{hackathon_title}}**. "
            "Your certificate of participation is attached to this email as a PDF."
        ),
        variables=(
            _NAME,
            Variable("hackathon_title", "The hackathon's title", "DevSecStorm"),
            Variable("team_name", "The person's team", "Team Alpha"),
        ),
        event_scoped=True,
        has_attachment=True,
    ),
    TemplateDef(
        key="workshop_exam_invite",
        name="Exam invite",
        category="Workshops & exams",
        description="Sends an attendee their personal link to take a workshop exam.",
        when_sent="When an exam's invitations are sent.",
        subject="Your exam link: {{exam_title}}",
        body=(
            "# {{exam_title}}\n\n"
            "Hi {{full_name}}, here is your personal link for the MCQ exam ({{duration_minutes}} minutes once you start). "
            "No login is needed.\n\n"
            "[Start the exam]({{exam_url}})\n\n"
            "> The link is only for you -- please don't share it. Your certificate will be emailed to this address after the exam."
        ),
        variables=(
            _NAME,
            Variable("exam_title", "The exam's title", "DevSecOps Test 1"),
            Variable("exam_url", "The attendee's personal exam link", "https://erp.example.com/exam/abc123"),
            Variable("duration_minutes", "How long the exam lasts, in minutes", "30"),
        ),
        required=("exam_url",),
        button_color="#0f4c81",
    ),
    TemplateDef(
        key="social_publish_problem",
        name="Social media publishing problem",
        category="Social media",
        description="Tells the people who run the social media page that a post didn't go out as planned.",
        when_sent="When a scheduled post fails, is paused before publishing, or its outcome can't be confirmed.",
        subject="Social media: {{problem}} ({{post_title}})",
        body=(
            "# {{problem}}\n\n"
            "The post **{{post_title}}** needs your attention.\n\n"
            "> {{detail}}\n\n"
            "Open the Social Media page in ERPX and check the Queue tab: {{queue_url}}"
        ),
        variables=(
            Variable("problem", "What happened", "A post failed to publish"),
            Variable("post_title", "The post's working title", "What is a SIEM?"),
            Variable("detail", "What went wrong and what to do", "Instagram rejected the image."),
            Variable("queue_url", "A link to the queue", "https://erp.example.com/social-media?tab=queue"),
        ),
    ),
    TemplateDef(
        key="workshop_certificate",
        name="Exam certificate",
        category="Workshops & exams",
        description="Delivers an attendee's certificate (attached as a PDF).",
        when_sent="After an attendee finishes an exam.",
        subject="Your certificate: {{exam_title}}",
        body=(
            "# Your certificate\n\n"
            "Hi {{full_name}}, thank you for taking part in **{{exam_title}}**. "
            "Your certificate is attached to this email as a PDF."
        ),
        variables=(_NAME, Variable("exam_title", "The exam's title", "DevSecOps Test 1")),
        has_attachment=True,
    ),
    TemplateDef(
        key="announcement",
        name="Announcement",
        category="Announcements",
        description="Emails an announcement to the people it is addressed to.",
        when_sent="When an announcement is posted.",
        subject="[Announcement] {{title}}",
        body="# {{title}}\n\n> {{scope_label}}\n\n{{body}}",
        variables=(
            _NAME,
            Variable("title", "The announcement's title", "Holiday on Friday"),
            Variable("scope_label", "Who it is for", "All students"),
            Variable("body", "The announcement text", "The campus will be closed on Friday."),
        ),
        required=("body",),
    ),
    TemplateDef(
        key="payroll_draft_ready",
        name="Payroll draft ready",
        category="Payroll",
        description="Tells an administrator that a payroll draft is ready to review.",
        when_sent="When the monthly payroll draft is generated.",
        subject="Payroll draft for {{period_label}} is ready for review",
        body=(
            "# Payroll draft ready: {{period_label}}\n\n"
            "Hi {{full_name}}, the {{period_label}} payroll draft has been generated automatically and is ready for your review.\n\n"
            "[Review payroll run]({{review_url}})\n\n"
            "> Nothing has been finalized or paid yet — this is a draft awaiting your review."
        ),
        variables=(
            _NAME,
            Variable("period_label", "The payroll month", "October 2026"),
            Variable("review_url", "The link to the payroll run", "https://erp.example.com/payroll/runs/abc123"),
        ),
        required=("review_url",),
    ),
    TemplateDef(
        key="payslip_ready",
        name="Payslip",
        category="Payroll",
        description="Delivers an employee's payslip (attached as a PDF).",
        when_sent="When a payslip is issued.",
        subject="Your payslip for {{period_label}} is ready",
        body=(
            "# Your payslip for {{period_label}}\n\n"
            "Hi {{full_name}}, your payslip for {{period_label}} is attached to this email as a PDF.\n\n"
            "> This payslip is generated based on the attendance and salary structure on record as of the date of issue. "
            "Please report any discrepancy to HR within 7 working days."
        ),
        variables=(_NAME, Variable("period_label", "The payroll month", "October 2026")),
        has_attachment=True,
    ),
)

BY_KEY: dict[str, TemplateDef] = {t.key: t for t in TEMPLATES}


def get_def(key: str) -> TemplateDef | None:
    return BY_KEY.get(key)


def sample_values(definition: TemplateDef) -> dict[str, str]:
    return {v.name: v.sample for v in definition.variables}
