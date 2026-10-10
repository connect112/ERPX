"""
Starting content strategy, design rules and the honest capability matrix of the Social Media module.

Nothing here is a claim about the organisation's real results: the pillars, personas and voice are editable starting
points, the brand colours are placeholders until someone confirms them, and the capability matrix says what Meta's
documentation offers, what ERPX has implemented, and that none of it has been verified against a live account yet.
"""

DEFAULT_TIMEZONE = "Asia/Kolkata"

# Publishing policy: nothing newly generated is ever published without a recorded approval.
PUBLISH_MODES = ("manual", "scheduled")  # manual: an admin publishes each approved post; scheduled: at its set time

DEFAULT_BRAND = {
    "name": "Pentrix",
    "tagline": "Pentest Practice Dominate",
    "handle": "",
    "website": "",
    "voice": (
        "Clear, practical and credible. Teach one useful thing per post in plain language, the way a good trainer "
        "explains it to a keen beginner. Confident but never hype; no fear-mongering, no get-rich-quick or "
        "job-guarantee language."
    ),
    "colors": {
        # Placeholders: not confirmed brand colours. Replace with the approved palette.
        "background": "#F6F7F9",
        "ink": "#0F172A",
        "primary": "#1D4ED8",
        "accent": "#0EA5E9",
        "muted": "#475569",
    },
    "colors_confirmed": False,
    "fonts": {"heading": "Inter", "body": "Inter"},
    # The approved logo is uploaded with the artwork renderer. (The only logo in the ERPX repository is the
    # "GIR Technologies" one, so no Pentrix logo is assumed.)
    "logo_key": None,
}

DEFAULT_PILLARS = [
    {"key": "fundamentals", "label": "Cybersecurity fundamentals & awareness", "share": 12, "enabled": True,
     "description": "Core concepts, safe habits and common myths for beginners."},
    {"key": "soc", "label": "SOC, SIEM, threat hunting & incident response", "share": 12, "enabled": True,
     "description": "How a security operations centre works day to day."},
    {"key": "pentest", "label": "Ethical hacking & penetration testing", "share": 12, "enabled": True,
     "description": "Methodology, tools and legal, authorised practice."},
    {"key": "appsec", "label": "OWASP, web, API security & secure coding", "share": 12, "enabled": True,
     "description": "Common vulnerabilities and how developers prevent them."},
    {"key": "cloud_ai", "label": "Cloud security, DevSecOps & AI security", "share": 10, "enabled": True,
     "description": "Securing cloud workloads, pipelines and AI systems."},
    {"key": "intel_forensics", "label": "Threat intelligence, modelling & digital forensics", "share": 8, "enabled": True,
     "description": "Understanding adversaries and investigating incidents."},
    {"key": "labs", "label": "Tools, practical labs, CTFs & demos", "share": 10, "enabled": True,
     "description": "Hands-on walkthroughs, preferably from real lab screenshots."},
    {"key": "careers", "label": "Careers, interviews & learning roadmaps", "share": 8, "enabled": True,
     "description": "Honest guidance on roles, skills and how to prepare."},
    {"key": "news", "label": "Verified security news & disclosures", "share": 8, "enabled": True,
     "description": "Only sourced, verified items; always reviewed by a person before publishing."},
    {"key": "community", "label": "Workshops, hackathons & student projects", "share": 6, "enabled": True,
     "description": "Real events and genuine student work only."},
    {"key": "programs", "label": "Training programs & admissions", "share": 2, "enabled": True,
     "description": "Only where relevant, using verified course details."},
]

DEFAULT_PERSONAS = [
    {"key": "student", "label": "College student / fresher",
     "description": "Wants a first role in security and needs a clear learning path and hands-on practice."},
    {"key": "switcher", "label": "IT professional switching to security",
     "description": "Knows IT or development; wants practical security skills and credible next steps."},
    {"key": "practitioner", "label": "Early-career security practitioner",
     "description": "Works in or near security; wants deeper technical content and current developments."},
]

DEFAULT_PROHIBITED_CLAIMS = [
    "Guaranteed placement, salary or job outcomes",
    "Invented student achievements, testimonials, certifications or statistics",
    "Course fees, batch dates or schedules that are not confirmed in the course data",
    "Breaking-news or vulnerability claims without a verified source",
    "Guaranteed follower growth or going viral",
    "Instructions that help attack systems the reader does not own or have permission to test",
]

DEFAULT_OBJECTIVES = [
    "Educate a relevant audience about cybersecurity",
    "Build credibility through accurate, practical content",
    "Generate qualified enquiries for training programs (indirectly, never by pressure)",
]

# Read by the artwork renderer and the profile-grid check (a later phase). These are limits, not suggestions.
DEFAULT_DESIGN_RULES = {
    "max_headline_words": 8,
    "max_fonts": 2,
    "max_cover_text_chars": 90,
    "min_contrast_ratio": 4.5,
    "one_focal_point": True,
    "logo_exact_only": True,
    "forbidden_visuals": [
        "neon or glow effects",
        "3D effects and heavy gradients",
        "circuit-board or matrix patterns",
        "floating icons and decorative HUD elements",
        "hooded hackers and robotic heads",
        "fake terminal screenshots, illegible code or fabricated dashboards",
        "long explanations on a cover",
    ],
    "prefer": [
        "one clear idea and focal point per cover",
        "generous whitespace and readable type",
        "real lab screenshots and photographs where they exist",
        "consistent templates that still vary naturally across the grid",
    ],
}

DEFAULT_BUDGETS = {"monthly_budget_inr": 0, "alert_at_percent": 80}

DEFAULT_NOTIFICATIONS = {"emails": [], "notify_on_failure": True, "notify_on_token_expiry": True}

# What each capability needs. `api` is what Meta's Instagram platform documents for a Business/Creator account (to
# be confirmed when the account is connected); `implemented` is ERPX's own status. `verified_live` is always False
# until the behaviour has been exercised against a real account.
CAPABILITIES = [
    {"key": "connect", "label": "Connect the Instagram account", "api": "supported", "implemented": "yes",
     "note": "Built (Instagram login, one-use link, encrypted token, automatic renewal). Needs a Meta app and a Professional (Business or Creator) account."},
    {"key": "publish_image", "label": "Publish single-image posts", "api": "supported", "implemented": "yes",
     "note": "Built, with scheduling, retries and recovery. Needs a connected account and the content-publish permission; Instagram applies a daily limit. Not yet tried on a live account."},
    {"key": "publish_carousel", "label": "Publish carousels", "api": "supported", "implemented": "yes",
     "note": "Built: 2 to 10 pictures, each created as a container, then one post. Not yet tried on a live account."},
    {"key": "publish_reel", "label": "Publish Reels", "api": "supported", "implemented": "later",
     "note": "Needs a finished video file, which can't be made here yet. Only a script and a cover exist, so Reels can't be published."},
    {"key": "publish_story", "label": "Publish Stories", "api": "supported", "implemented": "yes",
     "note": "Built (a picture, no caption). Availability depends on the account type and permissions. Not yet tried on a live account."},
    {"key": "comments_read", "label": "Read comments on your own posts", "api": "needs_app_review", "implemented": "yes",
     "note": "Built: the latest posts' comments are read (not every old one), labelled by simple keyword rules and shown with the post. Needs the manage-comments permission; live access for accounts beyond your own testers needs app review."},
    {"key": "comments_reply", "label": "Reply to comments (manual only)", "api": "needs_app_review", "implemented": "yes",
     "note": "Built. Every reply is written or confirmed and sent by a person, once, with a record of who sent what. Nothing is ever sent automatically."},
    {"key": "dm_read", "label": "Read direct messages", "api": "needs_app_review", "implemented": "yes",
     "note": "Built. Needs the messaging permission. Only the 20 most recent messages of each conversation can be read, requests older than 30 days are not returned, and Instagram doesn't say which messages you have read."},
    {"key": "dm_reply", "label": "Reply to direct messages (manual only)", "api": "needs_app_review", "implemented": "yes",
     "note": "Built. Only within 24 hours of the person's last message, and never to start a conversation. Always sent by a person."},
    {"key": "insights", "label": "Account and post insights", "api": "supported", "implemented": "yes",
     "note": "Built: profile counts, daily account figures and each recent post's figures, with source, period and sync time. Needs the insights permission. Only metrics the API returns for this account; missing values are shown as unavailable, never zero. Instagram says figures can lag by up to 48 hours, and follower history only exists from the day ERPX started reading."},
    {"key": "webhooks", "label": "Webhooks for new comments and messages", "api": "supported", "implemented": "yes",
     "note": "Built: the callback checks Meta's signature, ignores retries and records ids only; a notification only triggers reading the new comment or message from the API. Needs a public HTTPS address and the app set to Live."},
    {"key": "hashtag_trends", "label": "Measured hashtag popularity", "api": "restricted", "implemented": "never",
     "note": "Not available: Meta's hashtag search is restricted and returns no popularity counts, and ERPX does not scrape. Instead the Analytics tab shows how the profile's own posts did with each hashtag (measured, with sample sizes) and the Studio's AI hashtags are labelled as suggestions, not measurements."},
    {"key": "save_share_identities", "label": "Who saved or shared a post", "api": "unavailable", "implemented": "never",
     "note": "Not provided by the API. Counts may be available; identities are not."},
    {"key": "profile_grid", "label": "Nine-post profile grid preview", "api": "supported", "implemented": "yes",
     "note": "Built from the designed posts known to ERPX. Posts already on your live profile are added once the account is connected (phase 4); until then they are shown as missing."},
]

ROADMAP = [
    {"phase": 1, "title": "Data model, strategy and settings, draft and approval workflow, ERP lead link", "status": "done"},
    {"phase": 2, "title": "AI research and content studio, source verification, artwork rendering, 9-post grid preview", "status": "done"},
    {"phase": 3, "title": "Content calendar, durable scheduling and reliable publishing", "status": "done"},
    {"phase": 4, "title": "Instagram connection, comments and DMs with manual-only replies", "status": "done"},
    {"phase": 5, "title": "Analytics, growth reports, tracked links and lead attribution", "status": "done"},
    {"phase": 6, "title": "Security hardening, recovery, cost controls, accessibility and full regression tests", "status": "done"},
]
