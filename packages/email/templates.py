"""
Plain-text + HTML email templates.

Kept deliberately simple (string formatting, not a templating engine) at
this stage of the build. If/when the Marketing or Notifications modules
need richer templating (Jinja2, MJML, drag-and-drop editors), this module
becomes the single place that changes.
"""


def verification_email(full_name: str, verification_url: str) -> tuple[str, str, str]:
    subject = "Verify your ERPX account"
    text = (
        f"Hi {full_name},\n\n"
        f"Welcome to ERPX. Please verify your email address by visiting the "
        f"link below:\n\n{verification_url}\n\n"
        f"This link expires in 24 hours. If you didn't create this account, "
        f"you can safely ignore this email."
    )
    html = f"""
    <div style="font-family:sans-serif;max-width:480px;margin:0 auto">
      <h2>Welcome to ERPX, {full_name}</h2>
      <p>Please verify your email address to activate your account.</p>
      <p><a href="{verification_url}"
            style="background:#2563eb;color:#fff;padding:10px 20px;
                   border-radius:6px;text-decoration:none">Verify Email</a></p>
      <p style="color:#6b7280;font-size:13px">This link expires in 24 hours.
      If you didn't create this account, you can ignore this email.</p>
    </div>
    """
    return subject, text, html


def payroll_draft_ready_email(full_name: str, period_label: str, review_url: str) -> tuple[str, str, str]:
    subject = f"Payroll draft for {period_label} is ready for review"
    text = (
        f"Hi {full_name},\n\n"
        f"The {period_label} payroll draft has been generated automatically and is ready "
        f"for your review. Add any one-off amounts (e.g. reimbursements) and finalize it "
        f"here:\n\n{review_url}\n\n"
        f"Nothing has been finalized or paid yet — this is a draft awaiting your review."
    )
    html = f"""
    <div style="font-family:sans-serif;max-width:480px;margin:0 auto">
      <h2>Payroll draft ready: {period_label}</h2>
      <p>Hi {full_name}, the {period_label} payroll draft has been generated automatically
      and is ready for your review.</p>
      <p><a href="{review_url}"
            style="background:#2563eb;color:#fff;padding:10px 20px;
                   border-radius:6px;text-decoration:none">Review payroll run</a></p>
      <p style="color:#6b7280;font-size:13px">Nothing has been finalized or paid yet —
      this is a draft awaiting your review.</p>
    </div>
    """
    return subject, text, html


def password_reset_email(full_name: str, reset_url: str) -> tuple[str, str, str]:
    subject = "Reset your ERPX password"
    text = (
        f"Hi {full_name},\n\n"
        f"We received a request to reset your ERPX password. Visit the link "
        f"below to choose a new one:\n\n{reset_url}\n\n"
        f"This link expires in 1 hour. If you didn't request this, you can "
        f"safely ignore this email — your password will not be changed."
    )
    html = f"""
    <div style="font-family:sans-serif;max-width:480px;margin:0 auto">
      <h2>Reset your password</h2>
      <p>Hi {full_name}, click below to choose a new password.</p>
      <p><a href="{reset_url}"
            style="background:#2563eb;color:#fff;padding:10px 20px;
                   border-radius:6px;text-decoration:none">Reset Password</a></p>
      <p style="color:#6b7280;font-size:13px">This link expires in 1 hour.
      If you didn't request this, you can ignore this email.</p>
    </div>
    """
    return subject, text, html
