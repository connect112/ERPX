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
        "muted": "#64748B",
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
    {"key": "connect", "label": "Connect the Instagram account", "api": "supported", "implemented": "phase 4",
     "note": "Needs a Meta app and an Instagram professional (Business or Creator) account."},
    {"key": "publish_image", "label": "Publish single-image posts", "api": "supported", "implemented": "phase 3",
     "note": "Needs the content-publish permission; subject to a daily publishing quota."},
    {"key": "publish_carousel", "label": "Publish carousels", "api": "supported", "implemented": "phase 3",
     "note": "2 to 10 images; each is created as a container before the post."},
    {"key": "publish_reel", "label": "Publish Reels", "api": "supported", "implemented": "phase 3",
     "note": "Needs a finished video file; scripts and storyboards are not Reels."},
    {"key": "publish_story", "label": "Publish Stories", "api": "supported", "implemented": "phase 3",
     "note": "Availability depends on the account type and permissions."},
    {"key": "comments_read", "label": "Read comments on your own posts", "api": "needs_app_review", "implemented": "phase 4",
     "note": "Needs the manage-comments permission; live access for accounts beyond your own testers needs app review."},
    {"key": "comments_reply", "label": "Reply to comments (manual only)", "api": "needs_app_review", "implemented": "phase 4",
     "note": "Every reply is typed and sent by a person. Nothing is ever sent automatically."},
    {"key": "dm_read", "label": "Read direct messages", "api": "needs_app_review", "implemented": "phase 4",
     "note": "Needs the messaging permission; only conversations the API exposes, within its history limits."},
    {"key": "dm_reply", "label": "Reply to direct messages (manual only)", "api": "needs_app_review", "implemented": "phase 4",
     "note": "Replies are limited to the messaging window Meta allows. Always sent by a person."},
    {"key": "insights", "label": "Account and post insights", "api": "supported", "implemented": "phase 5",
     "note": "Only metrics the API returns for this account; missing values are shown as unavailable, never zero."},
    {"key": "webhooks", "label": "Webhooks for new comments and messages", "api": "supported", "implemented": "phase 4",
     "note": "Needs a public HTTPS callback and signature verification."},
    {"key": "hashtag_trends", "label": "Measured hashtag popularity", "api": "restricted", "implemented": "phase 5",
     "note": "Meta's hashtag search is limited and does not return popularity counts; suggestions are labelled as AI-generated."},
    {"key": "save_share_identities", "label": "Who saved or shared a post", "api": "unavailable", "implemented": "never",
     "note": "Not provided by the API. Counts may be available; identities are not."},
    {"key": "profile_grid", "label": "Full live profile grid preview", "api": "supported", "implemented": "phase 2",
     "note": "Built from the media the API returns plus planned posts; anything missing is shown as missing."},
]

ROADMAP = [
    {"phase": 1, "title": "Data model, strategy and settings, draft and approval workflow, ERP lead link", "status": "done"},
    {"phase": 2, "title": "Research, AI studio and fact checks are built (2a). Artwork rendering and the 9-post grid preview are next (2b)", "status": "next"},
    {"phase": 3, "title": "Content calendar, durable scheduling and reliable publishing", "status": "planned"},
    {"phase": 4, "title": "Instagram connection, comments and DMs with manual-only replies", "status": "planned"},
    {"phase": 5, "title": "Analytics, trend intelligence, growth reports and lead attribution", "status": "planned"},
    {"phase": 6, "title": "Security hardening, recovery, cost controls, accessibility and full regression tests", "status": "planned"},
]
