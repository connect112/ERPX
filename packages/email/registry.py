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
        key="internship_completion_certificate",
        name="Internship completion certificate",
        category="Internships",
        description="Delivers a student's certificate of completion (attached as a PDF).",
        when_sent="When the completion certificates of an internship are sent.",
        subject="Your internship completion certificate: {{internship_title}}",
        body=(
            "# Congratulations, {{full_name}}!\n\n"
            "You have completed **{{internship_title}}**. "
            "Your certificate of completion is attached to this email as a PDF.\n\n"
            "> Well done, and thank you for all your work."
        ),
        variables=(
            _NAME,
            Variable("internship_title", "The internship's title", "Pentrix Cyber Internship"),
            Variable("certificate_type", "completion or participation", "completion"),
        ),
        has_attachment=True,
    ),
    TemplateDef(
        key="internship_participation_certificate",
        name="Internship participation certificate",
        category="Internships",
        description="Delivers a student's certificate of participation (attached as a PDF).",
        when_sent="When the participation certificates of an internship are sent.",
        subject="Your internship participation certificate: {{internship_title}}",
        body=(
            "# Thank you for taking part\n\n"
            "Hi {{full_name}}, thank you for taking part in **{{internship_title}}**. "
            "Your certificate of participation is attached to this email as a PDF."
        ),
        variables=(
            _NAME,
            Variable("internship_title", "The internship's title", "Pentrix Cyber Internship"),
            Variable("certificate_type", "completion or participation", "completion"),
        ),
        has_attachment=True,
    ),
    TemplateDef(
        key="internship_offer_letter",
        name="Internship offer letter",
        category="Internships",
        description="Congratulates a selected student and carries their offer letter (attached as a PDF).",
        when_sent="When an administrator releases an approved offer letter.",
        subject="Your internship offer letter - {{company_name}}",
        body=(
            "# Congratulations, {{student_name}}!\n\n"
            "We are pleased to offer you the position of {{internship_position}} on {{internship_name}} at {{company_name}}.\n\n"
            "Your offer letter (reference {{reference}}) is attached to this email. Please read it carefully, sign it, and send it back "
            "with the documents it lists. Reply to this email if you have any questions.\n\n"
            "> We look forward to working with you."
        ),
        variables=(
            Variable("full_name", "The student's name (same as student_name)", "Asha Rao"),
            Variable("student_name", "The student's full name", "Asha Rao"),
            Variable("student_email", "The student's email address", "asha@example.com"),
            Variable("registration_id", "The student's registration or roll number", "APL-1002"),
            Variable("institution_name", "The student's institution", "Apollo University"),
            Variable("institution_location", "Where the institution is", "Tirupati"),
            Variable("internship_name", "The internship programme", "Pentrix Cyber Internship"),
            Variable("internship_position", "The position offered", "Intern"),
            Variable("internship_duration", "How long it runs", "3 months"),
            Variable("internship_start_date", "The start date", "13-03-2026"),
            Variable("internship_end_date", "The end date", "12-06-2026"),
            Variable("program_type", "Paid or unpaid internship", "Unpaid Internship"),
            Variable("company_name", "The company's name", "GIR Technologies"),
            Variable("authorized_signatory", "The authorised signatory", "Atluri Srujan"),
            Variable("authorized_designation", "Their designation", "CEO"),
            Variable("reference", "The offer letter's reference number", "OFR-2026-AB12-001"),
            Variable("letter_date", "The date on the letter", "28 October 2026"),
            Variable("onboarding_link", "The student's personal onboarding link (empty when onboarding is manual)", "https://erp.example.com/internship-onboarding#t=..."),
            Variable("onboarding_deadline", "When onboarding closes for this student", "15 Nov 2026, 11:59 PM IST"),
            Variable("onboarding_start_date", "When onboarding opens", "1 Nov 2026"),
            Variable("internship_fee", "The internship fee", "INR 5,000.00"),
            Variable("late_fee", "The late fee, if one applies", "INR 500.00"),
            Variable("total_payable", "What the student pays in total", "INR 5,900.00"),
            Variable("application_reference", "The student's application reference", "ERPX-INT-2026-000001"),
        ),
        has_attachment=True,
    ),
    TemplateDef(
        key="internship_onboarding_invitation",
        name="Internship onboarding invitation",
        category="Internships",
        description="Sends a selected student their personal onboarding link (information, documents, acceptance, payment).",
        when_sent="When an administrator sends or resends the onboarding invitation. Each sending replaces the previous link.",
        subject="Complete your internship onboarding - {{internship_name}}",
        body=(
            "# Welcome aboard, {{student_name}}\n\n"
            "Please complete your onboarding for {{internship_name}} before {{onboarding_deadline}}. "
            "Your application reference is {{application_reference}}.\n\n"
            "[Start onboarding]({{onboarding_link}})\n\n"
            "> This link is personal. Do not forward it. Use the newest email if you receive more than one."
        ),
        variables=(
            _NAME,
            Variable("student_name", "The student's full name", "Asha Rao"),
            Variable("internship_name", "The internship programme", "Pentrix Cyber Internship"),
            Variable("onboarding_link", "The student's personal onboarding link (empty when onboarding is manual)", "https://erp.example.com/internship-onboarding#t=..."),
            Variable("onboarding_deadline", "When onboarding closes for this student", "15 Nov 2026, 11:59 PM IST"),
            Variable("onboarding_start_date", "When onboarding opens", "1 Nov 2026"),
            Variable("internship_fee", "The internship fee", "INR 5,000.00"),
            Variable("late_fee", "The late fee, if one applies", "INR 500.00"),
            Variable("total_payable", "What the student pays in total", "INR 5,900.00"),
            Variable("application_reference", "The student's application reference", "ERPX-INT-2026-000001"),
        ),
        required=("onboarding_link",),
    ),
    TemplateDef(
        key="internship_welcome",
        name="Internship welcome (LMS access)",
        category="Internships",
        description="Tells a student who already has an ERPX account that their internship access is ready.",
        when_sent="When LMS access is granted for an internship and the student already has an account.",
        subject="Your Pentrix LMS access is ready",
        body=(
            "# Welcome, {{full_name}}\n\n"
            "Your access to the Pentrix LMS is ready. You are now enrolled in {{course_title}}.\n\n"
            "[Sign in]({{login_url}})\n\n"
            "> Sign in with your existing account."
        ),
        variables=(
            _NAME,
            Variable("internship_title", "The internship's title", "Pentrix Cyber Internship"),
            Variable("course_title", "The course they are enrolled in", "Cyber Security Fundamentals"),
            Variable("login_url", "The sign-in page", "https://lms.example.com/login"),
        ),
        required=("login_url",),
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
        key="social_account_problem",
        name="Instagram connection problem",
        category="Social media",
        description="Tells the people who run the social media page that the Instagram connection needs attention.",
        when_sent="When the Instagram access token is about to expire, can't be refreshed, or has been revoked.",
        subject="Social media: {{problem}} ({{account_name}})",
        body=(
            "# {{problem}}\n\n"
            "The Instagram connection for **{{account_name}}** needs your attention.\n\n"
            "> {{detail}}\n\n"
            "Open Social Media > Settings in ERPX: {{settings_url}}"
        ),
        variables=(
            Variable("problem", "What happened", "The Instagram connection needs attention"),
            Variable("account_name", "The Instagram account", "@pentrix"),
            Variable("detail", "What went wrong and what to do", "The access token could not be refreshed."),
            Variable("settings_url", "A link to the settings page", "https://erp.example.com/social-media?tab=settings"),
        ),
    ),
    TemplateDef(
        key="social_job_problem",
        name="Social media job problem",
        category="Social media",
        description="Tells the people who run the social media page that a scheduled background job failed or has stopped running.",
        when_sent="When a background job (publishing, reading comments, insights, reports) has failed or hasn't run when it should. At most once a day per job.",
        subject="Social media: {{job}} needs attention",
        body=(
            "# {{job}} needs attention\n\n"
            "A background job behind the social media page {{state}}.\n\n"
            "> {{detail}}\n\n"
            "Open Social Media > Overview in ERPX: {{overview_url}}"
        ),
        variables=(
            Variable("job", "Which job", "Publishing scheduled posts"),
            Variable("state", "What is wrong", "has failed"),
            Variable("detail", "What was recorded", "It last finished 10 Oct 08:00 UTC and should run every 1 minute(s)."),
            Variable("overview_url", "A link to the overview", "https://erp.example.com/social-media"),
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

def _booking_reminders() -> tuple[TemplateDef, ...]:
    """The reminder emails for a Pentrix appointment: three moments, each worded for the candidate and for the team member."""
    shared = (
        Variable("full_name", "The recipient's name", "Asha Rao"),
        Variable("candidate_name", "The candidate the appointment is with", "Meera Iyer"),
        Variable("booking_date", "The date of the appointment", "Friday, 30 October 2026"),
        Variable("booking_time", "The start time", "6:00 PM"),
        Variable("timezone", "The time zone the time is in", "IST (India Standard Time)"),
        Variable("duration_minutes", "How long it lasts", "60"),
        Variable("representative", "The team member it is with", "Priya Nair"),
        Variable("booking_reference", "The booking reference", "BK-7F3KQ2"),
        Variable("meeting_url", "The meeting link, or the page with the details when there is no link yet", "https://meet.example.com/pentrix-bk-7f3kq2"),
        Variable("meeting_label", "What the link is called", "Join the meeting"),
    )
    details = "**{{booking_date}}** at **{{booking_time}}** ({{timezone}}) · {{duration_minutes}} minutes · Booking {{booking_reference}}"
    moments = (
        ("30m", "30 minutes", "starts in 30 minutes", "Your appointment starts in 30 minutes"),
        ("5m", "5 minutes", "starts in 5 minutes", "Your appointment starts in 5 minutes"),
        ("now", "now", "is starting now", "Your appointment is starting now"),
    )
    out: list[TemplateDef] = []
    for kind, label, phrase, subject in moments:
        out.append(
            TemplateDef(
                key=f"pentrix_booking_reminder_{kind}_candidate",
                name=f"Pentrix booking reminder, {label} (candidate)",
                category="Pentrix",
                description=f"Reminds the candidate that their Pentrix appointment {phrase}.",
                when_sent=f"Automatically {'at the start time' if kind == 'now' else label + ' before the appointment'}, to the candidate.",
                subject=f"{subject}: {{{{booking_time}}}} {{{{timezone}}}}",
                body=(
                    f"# Your appointment {phrase}\n\n"
                    f"Hi {{{{full_name}}}}, your appointment with {{{{representative}}}} {phrase}.\n\n"
                    f"{details}\n\n"
                    "[{{meeting_label}}]({{meeting_url}})\n\n"
                    "> Need to change it? Open your Pentrix portal."
                ),
                variables=shared,
                required=("meeting_url",),
            )
        )
        out.append(
            TemplateDef(
                key=f"pentrix_booking_reminder_{kind}_staff",
                name=f"Pentrix booking reminder, {label} (team member)",
                category="Pentrix",
                description=f"Reminds the assigned team member that their Pentrix appointment {phrase}.",
                when_sent=f"Automatically {'at the start time' if kind == 'now' else label + ' before the appointment'}, to the assigned team member.",
                subject=f"{subject}: {{{{candidate_name}}}}, {{{{booking_time}}}} {{{{timezone}}}}",
                body=(
                    f"# Appointment {phrase}\n\n"
                    f"Hi {{{{full_name}}}}, your appointment with **{{{{candidate_name}}}}** {phrase}.\n\n"
                    f"{details}\n\n"
                    "[{{meeting_label}}]({{meeting_url}})"
                ),
                variables=shared,
                required=("meeting_url",),
            )
        )
    return tuple(out)


def _marketing() -> tuple[TemplateDef, ...]:
    """The placeholders available to a Pentrix marketing email. Which wording is sent is decided per campaign (any published Email Studio
    template made available for it), so this is the list of values, not one fixed email."""
    return (
        TemplateDef(
            key="pentrix_marketing",
            name="Pentrix marketing email",
            category="Pentrix",
            description="An update or offer sent to Pentrix candidates who agreed to receive them.",
            when_sent="When an administrator confirms a send from Pentrix > Registrations.",
            subject="News from Pentrix",
            body=(
                "# Hello {{first_name}}\n\n"
                "Here is the latest from Pentrix.\n\n"
                "[Open your Pentrix portal]({{portal_url}})\n\n"
                "> You are receiving this because you chose to hear from Pentrix. [Unsubscribe]({{unsubscribe_url}})"
            ),
            variables=(
                Variable("full_name", "The candidate's full name", "Asha Rao"),
                Variable("first_name", "The candidate's first name", "Asha"),
                Variable("email", "The candidate's email address", "asha@example.com"),
                Variable("campaign_name", "The name of the campaign", "November intake"),
                Variable("assessment_status", "Where they are with the assessment (Not started, In progress or Completed)", "Completed"),
                Variable("qualification_status", "Qualified, Not qualified, or No result yet", "Qualified"),
                Variable("portal_url", "The address of their Pentrix portal", "https://pentrix.in/portal"),
                Variable("unsubscribe_url", "The link that stops these emails", "https://erp.example.com/pentrix-unsubscribe?token=sample"),
            ),
            required=("unsubscribe_url",),
        ),
    )


TEMPLATES = TEMPLATES + _booking_reminders() + _marketing()

BY_KEY: dict[str, TemplateDef] = {t.key: t for t in TEMPLATES}


def get_def(key: str) -> TemplateDef | None:
    return BY_KEY.get(key)


def sample_values(definition: TemplateDef) -> dict[str, str]:
    return {v.name: v.sample for v in definition.variables}
