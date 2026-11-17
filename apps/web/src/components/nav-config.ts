import type { LucideIcon } from "lucide-react";
import {
  Activity,
  PartyPopper as AlumniEventIcon,
  Award,
  BadgeCheck,
  Banknote,
  BarChart3,
  BookOpen,
  Boxes,
  Briefcase,
  Building2,
  Calendar,
  CalendarCheck,
  CalendarClock,
  CalendarDays,
  CalendarOff,
  CircleDollarSign,
  ClipboardCheck,
  ClipboardList,
  Contact,
  CreditCard,
  Crosshair,
  Database,
  FileText,
  Flag,
  Gift,
  Globe,
  GraduationCap,
  HandCoins,
  Handshake,
  HardDrive,
  History,
  IdCard,
  Images,
  Instagram,
  GraduationCap as InternGraduationCap,
  Landmark,
  Layers,
  LayoutDashboard,
  LayoutGrid,
  LineChart,
  ListChecks,
  Mail,
  Megaphone,
  MessageCircle,
  MessageSquare,
  Newspaper,
  NotebookPen,
  PartyPopper,
  Percent,
  Plug,
  Presentation,
  Radar,
  Receipt,
  ReceiptText,
  Rocket,
  School,
  Server,
  Share2,
  ShieldCheck,
  ShoppingCart,
  Ticket,
  TrendingDown,
  Trophy,
  Truck,
  University,
  UserCheck,
  UserCheck2,
  UserCircle,
  UserCog,
  Users,
  Video,
  Wallet,
  Warehouse,
  Workflow,
  Wrench,
} from "lucide-react";

/**
 * The admin navigation, and the single source of truth for who may open which page.
 *
 * Two jobs, one list: the sidebar, the mobile drawer and the search show the entries a user may open, and `router/route-guard.tsx` uses the
 * very same entries (flattened, including `hidden` ones) to refuse a page whose link would not be offered. Every route below a gated href
 * inherits its requirement; a new page therefore needs an entry here (visible, or `hidden: true` when it is reached from its parent page).
 * The server checks permissions again on every request.
 */
export interface NavItem {
  label: string;
  href: string;
  icon: LucideIcon;
  /** The permission code this page requires (its `.view` permission). Omitted for pages open to any signed-in user. */
  permission?: string;
  /** Platform operators only (`require_superuser()` server-side): no grantable permission code exists. */
  superuserOnly?: boolean;
  /** Shown to platform superusers as well as to holders of `permission` (a Super Admin holds no permission codes). */
  alsoSuperuser?: boolean;
  /** Gate on an ownership record instead of a permission: the page shows the caller's own data (their batches, their leave...). */
  ownership?: "trainer" | "employee" | "student";
  /** Extra words the search matches (for example "offer letters" finds Our Internships). */
  keywords?: string[];
  /** Routable and protected, and found by search, but not listed in the sidebar (it is reached from its parent page). */
  hidden?: boolean;
}

export interface NavGroup {
  id: string;
  title: string;
  icon: LucideIcon;
  items: NavItem[];
}

/** Pages with no entry of their own that still need the same protection as the section they belong to. */
export interface GuardOnly {
  href: string;
  permission: string;
}

export const topItems: NavItem[] = [
  { label: "Dashboard", href: "/", icon: LayoutDashboard, keywords: ["home", "overview"] },
  { label: "Calendar", href: "/events", icon: Calendar, keywords: ["holidays", "meetings", "events"] },
];

export const navGroups: NavGroup[] = [
  {
    id: "workspace",
    title: "Workspace",
    icon: LayoutGrid,
    items: [
      { label: "Batches", href: "/my/batches", icon: Presentation, ownership: "trainer", keywords: ["my batches", "trainer"] },
      { label: "Live Classes", href: "/my/live-classes", icon: Video, ownership: "trainer", keywords: ["my live classes", "video", "meeting"] },
      { label: "Announcements", href: "/my/announcements", icon: Megaphone, ownership: "trainer", keywords: ["my announcements"] },
      { label: "Messages", href: "/my/messages", icon: MessageCircle, ownership: "trainer", keywords: ["my messages", "doubts", "chat"] },
      { label: "Attendance", href: "/my/attendance", icon: CalendarCheck, ownership: "employee", keywords: ["my attendance", "check in"] },
      { label: "Leave", href: "/my/leave", icon: CalendarOff, ownership: "employee", keywords: ["my leave", "time off"] },
      { label: "Payslips", href: "/my/payslips", icon: Wallet, ownership: "employee", keywords: ["my payslips", "salary slip"] },
      { label: "Expenses", href: "/my/expenses", icon: ReceiptText, ownership: "employee", keywords: ["my expenses", "reimbursement", "claim"] },
      { label: "Schedule", href: "/my/schedule", icon: CalendarDays, ownership: "student", keywords: ["my schedule", "timetable"] },
      { label: "Approvals", href: "/workflow/my-approvals", icon: UserCheck2, permission: "workflow.view", keywords: ["my approvals", "pending approval"] },
      { label: "Assigned Bookings", href: "/pentrix-ops/my-bookings", icon: UserCheck, permission: "pentrix_ops.bookings.assigned", keywords: ["my assigned bookings", "pentrix"] },
    ],
  },
  {
    id: "internships",
    title: "Internships",
    icon: BadgeCheck,
    items: [
      { label: "Our Internships", href: "/our-internships", icon: BadgeCheck, permission: "our_internships.view", keywords: ["offer letters", "onboarding", "selected students", "internship exams", "certificates", "instructors", "lms course"] },
      { label: "Internship Postings", href: "/internships/postings", icon: InternGraduationCap, permission: "internships.view", keywords: ["openings", "apply"] },
      { label: "Active Internships", href: "/internships", icon: ClipboardList, permission: "internships.view", keywords: ["applications"] },
    ],
  },
  {
    id: "students-learning",
    title: "Students & Learning",
    icon: GraduationCap,
    items: [
      { label: "Admissions", href: "/crm/admissions", icon: UserCheck, permission: "crm.admissions.view", keywords: ["admission", "enrolment"] },
      { label: "Students", href: "/students", icon: GraduationCap, permission: "students.view", keywords: ["learners", "profiles", "enrollment"] },
      { label: "Courses", href: "/courses", icon: BookOpen, permission: "courses.view", keywords: ["lms", "learning paths", "categories", "chapters", "lessons", "internship course"] },
      { label: "Batches", href: "/batches", icon: CalendarClock, permission: "batches.view", keywords: ["cohorts", "timetable"] },
      { label: "Classrooms", href: "/classrooms", icon: School, permission: "classrooms.view", keywords: ["rooms", "virtual"] },
      { label: "Question Bank", href: "/examinations/question-bank", icon: ClipboardList, permission: "examinations.question_bank.view", keywords: ["exams", "questions", "mcq"] },
      { label: "Badges", href: "/lms/badges", icon: Award, permission: "lms.badges.view", keywords: ["achievements", "awards"] },
    ],
  },
  {
    id: "events",
    title: "Events & Institutions",
    icon: University,
    items: [
      { label: "Institutions", href: "/institutions", icon: University, permission: "institutions.view", keywords: ["colleges", "mou", "faculty"] },
      { label: "Workshops", href: "/workshops", icon: PartyPopper, permission: "workshops.view", keywords: ["training events"] },
      { label: "Workshop Exams", href: "/workshop-exams", icon: ClipboardCheck, permission: "workshops.view", keywords: ["certificates", "mcq"] },
      { label: "Hackathons", href: "/hackathons", icon: Rocket, permission: "hackathons.view", keywords: ["competition", "teams", "prizes"] },
    ],
  },
  {
    id: "pentrix",
    title: "Pentrix",
    icon: Crosshair,
    items: [
      { label: "Overview", href: "/pentrix-ops/overview", icon: LayoutDashboard, permission: "pentrix_ops.overview.view", keywords: ["pentrix dashboard"] },
      { label: "Registrations", href: "/pentrix-ops/registrations", icon: Contact, permission: "pentrix_ops.registrations.view", keywords: ["candidates"] },
      { label: "Assessments", href: "/pentrix-ops/assessments", icon: ClipboardCheck, permission: "pentrix_ops.assessments.view", keywords: ["scores", "qualified"] },
      { label: "Bookings", href: "/pentrix-ops/bookings", icon: CalendarClock, permission: "pentrix_ops.bookings.view", keywords: ["appointments"] },
      { label: "Payments", href: "/pentrix-ops/payments", icon: CreditCard, permission: "pentrix_ops.payments.view", keywords: ["pentrix payments", "daily summary", "invoices"] },
      { label: "Daily Payment Summary", href: "/pentrix-ops/payments/daily", icon: BarChart3, permission: "pentrix_ops.payments.view", keywords: ["pentrix payments", "export"], hidden: true },
      { label: "Booking Settings", href: "/pentrix-ops/availability", icon: CalendarDays, permission: "pentrix_ops.bookings.view", keywords: ["availability", "slots"], hidden: true },
      { label: "Marketing", href: "/pentrix-ops/marketing", icon: Megaphone, permission: "pentrix_ops.marketing.view", keywords: ["pentrix marketing", "offers", "emails"] },
      { label: "Labs", href: "/pentrix/labs", icon: Crosshair, permission: "pentrix.labs.view", keywords: ["cyber range", "lab"] },
      { label: "Challenges", href: "/pentrix/challenges", icon: Flag, permission: "pentrix.challenges.view", keywords: ["ctf", "flags"] },
      { label: "Leaderboard", href: "/pentrix/leaderboard", icon: Trophy, permission: "pentrix.leaderboard.view", keywords: ["ranking"] },
      { label: "Achievements", href: "/pentrix/achievements", icon: Award, permission: "pentrix.achievements.view", keywords: ["badges"] },
    ],
  },
  {
    id: "marketing-sales",
    title: "Marketing & Sales",
    icon: Megaphone,
    items: [
      { label: "Leads", href: "/crm/leads", icon: Users, permission: "crm.leads.view", keywords: ["crm", "pipeline", "enquiries"] },
      { label: "Campaigns", href: "/marketing/campaigns", icon: Megaphone, permission: "marketing.campaigns.view", keywords: ["email campaign"] },
      { label: "Landing Pages", href: "/marketing/landing-pages", icon: Globe, permission: "marketing.landing_pages.view", keywords: ["website"] },
      { label: "Coupons", href: "/marketing/coupons", icon: Ticket, permission: "marketing.coupons.view", keywords: ["discount", "promo code"] },
      { label: "Referrals", href: "/marketing/referrals", icon: Share2, permission: "marketing.referrals.view", keywords: ["referral"] },
      { label: "Referral Programs", href: "/marketing/referrals/programs", icon: Gift, permission: "marketing.referrals.view", keywords: ["referral rewards"] },
      { label: "Marketing Overview", href: "/marketing/analytics", icon: LineChart, permission: "marketing.analytics.view", keywords: ["analytics"] },
      { label: "Social Media", href: "/social-media", icon: Instagram, permission: "social_media.view", keywords: ["instagram", "posts"] },
      { label: "Media Gallery", href: "/media/albums", icon: Images, permission: "media.view", keywords: ["photos", "albums"] },
    ],
  },
  {
    id: "careers",
    title: "Careers & Alumni",
    icon: Handshake,
    items: [
      { label: "Placement Companies", href: "/placements/companies", icon: Building2, permission: "placements.view", keywords: ["recruiters", "employers"] },
      { label: "Job Postings", href: "/placements/postings", icon: Handshake, permission: "placements.view", keywords: ["jobs", "openings"] },
      { label: "Job Feed", href: "/placements/job-feed", icon: Radar, permission: "placements.view", keywords: ["external jobs"] },
      { label: "Alumni Profiles", href: "/alumni/profiles", icon: Contact, permission: "alumni.view", keywords: ["graduates"] },
      { label: "Alumni Events", href: "/alumni/events", icon: AlumniEventIcon, permission: "alumni.view", keywords: ["reunion"] },
      { label: "Job Referrals", href: "/alumni/referrals", icon: Newspaper, permission: "alumni.view", keywords: ["alumni referral"] },
    ],
  },
  {
    id: "communications",
    title: "Communications",
    icon: Mail,
    items: [
      { label: "Announcements", href: "/lms/announcements", icon: Megaphone, permission: "lms.announcements.view", keywords: ["course announcements", "organization announcements"] },
      { label: "Student-Trainer Messages", href: "/messaging", icon: MessageCircle, permission: "messaging.view_all", keywords: ["doubts", "conversations"] },
      { label: "Broadcast Notifications", href: "/administration/broadcast", icon: Megaphone, permission: "notifications.manage", keywords: ["notification", "bell"] },
      { label: "Email Studio", href: "/administration/email-templates", icon: Mail, permission: "email_templates.view", keywords: ["email templates", "email history", "brands", "signatures"] },
      { label: "Manual Communications", href: "/communication/logs", icon: MessageSquare, permission: "communication.view", keywords: ["sms", "whatsapp", "send message", "message log"] },
    ],
  },
  {
    id: "people-hr",
    title: "People & HR",
    icon: UserCog,
    items: [
      { label: "Employees", href: "/employees", icon: UserCog, permission: "employees.view", keywords: ["staff"] },
      { label: "Trainers", href: "/trainers", icon: Presentation, permission: "trainers.view", keywords: ["instructors", "teachers"] },
      { label: "Departments & Designations", href: "/hr/departments-designations", icon: Building2, permission: "hr.departments.view", keywords: ["branches", "org structure"] },
      { label: "Attendance", href: "/attendance", icon: CalendarCheck, permission: "attendance.view", keywords: ["employee attendance"] },
      { label: "Leave Types", href: "/leave/types", icon: CalendarOff, permission: "leave.types.view", keywords: ["policy"] },
      { label: "Leave Applications", href: "/leave/applications", icon: CalendarDays, permission: "leave.applications.view", keywords: ["time off requests"] },
      { label: "Expense Claims", href: "/expense-claims", icon: HandCoins, permission: "expense_claims.view", keywords: ["reimbursements"] },
      { label: "Salary Components", href: "/payroll/components", icon: Wallet, permission: "payroll.components.view", keywords: ["allowances", "deductions"] },
      { label: "Payroll Runs", href: "/payroll/runs", icon: CircleDollarSign, permission: "payroll.runs.view", keywords: ["salary", "payslips"] },
    ],
  },
  {
    id: "finance",
    title: "Finance",
    icon: Landmark,
    items: [
      { label: "Invoices", href: "/accounting/invoices", icon: FileText, permission: "accounting.invoices.view", keywords: ["billing", "sales invoice"] },
      { label: "Customer Receipts", href: "/accounting/receipts", icon: Receipt, permission: "accounting.receipts.view", keywords: ["payments received"] },
      { label: "Expenses", href: "/accounting/expenses", icon: CreditCard, permission: "accounting.expenses.view", keywords: ["bills", "vendor bills"] },
      { label: "Vendor Payments", href: "/accounting/payments", icon: HandCoins, permission: "accounting.payments.view", keywords: ["pay vendors"] },
      { label: "Customers", href: "/accounting/customers", icon: UserCircle, permission: "accounting.customers.view", keywords: ["clients", "receivables"] },
      { label: "Vendors", href: "/accounting/vendors", icon: Truck, permission: "accounting.vendors.view", keywords: ["suppliers", "payables"] },
      { label: "Bank Accounts", href: "/accounting/bank", icon: Banknote, permission: "accounting.bank.view", keywords: ["reconciliation"] },
      { label: "Journals", href: "/accounting/journals", icon: NotebookPen, permission: "accounting.journals.view", keywords: ["journal entries", "ledger"] },
      { label: "Chart of Accounts", href: "/accounting/ledger", icon: Landmark, permission: "accounting.ledger.view", keywords: ["ledger", "accounts"] },
      { label: "GST", href: "/accounting/gst", icon: Percent, permission: "accounting.gst.view", keywords: ["tax"] },
      { label: "TDS", href: "/accounting/tds", icon: ReceiptText, permission: "accounting.tds.view", keywords: ["tax deducted"] },
      { label: "Financial Reports", href: "/accounting/reports", icon: BarChart3, permission: "accounting.reports.view", keywords: ["trial balance", "profit and loss", "balance sheet"] },
    ],
  },
  {
    id: "operations",
    title: "Operations & Assets",
    icon: Boxes,
    items: [
      { label: "Purchase Orders", href: "/procurement/purchase-orders", icon: ShoppingCart, permission: "procurement.purchase_orders.view", keywords: ["procurement", "po"] },
      { label: "Inventory Items", href: "/inventory/items", icon: Boxes, permission: "inventory.items.view", keywords: ["stock"] },
      { label: "Item Categories & Warehouses", href: "/inventory/settings", icon: Warehouse, permission: "inventory.items.view", keywords: ["inventory settings"] },
      { label: "Fixed Assets", href: "/assets", icon: Wrench, permission: "assets.view", keywords: ["equipment"] },
      { label: "Asset Categories", href: "/assets/categories", icon: Layers, permission: "assets.view" },
      { label: "Depreciation Runs", href: "/assets/depreciation-runs", icon: TrendingDown, permission: "assets.depreciation.view" },
    ],
  },
  {
    id: "corporate",
    title: "Corporate",
    icon: Briefcase,
    items: [
      { label: "Clients", href: "/corporate/clients", icon: Briefcase, permission: "corporate.clients.view", keywords: ["projects", "tickets", "contracts", "vapt"] },
      { label: "Corporate Reports", href: "/corporate/reports", icon: BarChart3, permission: "corporate.reports.view", keywords: ["sla", "portfolio"] },
    ],
  },
  {
    id: "administration",
    title: "Administration",
    icon: ShieldCheck,
    items: [
      { label: "Users", href: "/administration/users", icon: IdCard, permission: "users.view", keywords: ["accounts", "logins"] },
      { label: "Roles", href: "/administration/roles", icon: ShieldCheck, permission: "authorization.roles.view", keywords: ["permissions", "access"] },
      { label: "Audit Logs", href: "/administration/audit-logs", icon: History, permission: "audit.view", keywords: ["history", "activity"] },
      { label: "Approval Requests", href: "/workflow/requests", icon: ListChecks, permission: "workflow.view", keywords: ["approvals"] },
      { label: "Approval Workflows", href: "/workflow/workflows", icon: Workflow, permission: "workflow.view", keywords: ["approval rules"] },
      { label: "Integrations", href: "/administration/integrations", icon: Plug, permission: "integrations.view", keywords: ["cashfree", "payment gateway", "connectors"] },
    ],
  },
  {
    id: "platform",
    title: "Platform",
    icon: Server,
    items: [
      { label: "Organizations", href: "/organizations", icon: Building2, superuserOnly: true, keywords: ["tenants"] },
      { label: "Storage Manager", href: "/administration/storage", icon: HardDrive, permission: "storage.view", alsoSuperuser: true, keywords: ["files", "disk"] },
      { label: "Database Backups", href: "/administration/backups", icon: Database, superuserOnly: true, keywords: ["restore"] },
      { label: "System Health", href: "/administration/monitoring", icon: Activity, superuserOnly: true, keywords: ["status", "monitoring"] },
    ],
  },
];

export const guardOnly: GuardOnly[] = [
  // /corporate/projects/:projectId is reached from a client's page and had no entry, so it was never guarded in the UI.
  { href: "/corporate/projects", permission: "corporate.projects.view" },
];

/** Every entry, visible or hidden, in menu order. */
export const allNavItems: NavItem[] = [...topItems, ...navGroups.flatMap((g) => g.items)];
