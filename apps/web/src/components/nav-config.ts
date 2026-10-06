import {
  Award,
  Banknote,
  BarChart3,
  BookOpen,
  Boxes,
  Briefcase,
  Building2,
  CalendarCheck,
  CalendarClock,
  CalendarDays,
  CalendarOff,
  CircleDollarSign,
  ClipboardList,
  CreditCard,
  Crosshair,
  FileText,
  Flag,
  Gift,
  Globe,
  GraduationCap,
  History,
  HandCoins,
  IdCard,
  Landmark,
  Layers,
  LayoutDashboard,
  LineChart,
  Megaphone,
  MessageCircle,
  NotebookPen,
  Percent,
  Presentation,
  Receipt,
  ReceiptText,
  School,
  Share2,
  ShieldCheck,
  ShoppingCart,
  Ticket,
  TrendingDown,
  Trophy,
  Truck,
  UserCheck,
  UserCircle,
  UserCog,
  Users,
  Wallet,
  Warehouse,
  Wrench,
  PartyPopper,
  ClipboardCheck,
  Rocket,
  Handshake,
  GraduationCap as InternGraduationCap,
  Contact,
  PartyPopper as AlumniEventIcon,
  Newspaper,
  Images,
  Workflow,
  ListChecks,
  Video,
  UserCheck2,
  MessageSquare,
  Calendar,
  Database,
  Plug,
  Activity,
} from "lucide-react";

export interface NavItem {
  label: string;
  href: string;
  icon: typeof LayoutDashboard;
  enabled: boolean;
  /**
   * The permission code this item's underlying page actually requires
   * (its `.view` permission, matching modules/authorization/service.py's
   * DEFAULT_PERMISSIONS) — omitted for the handful of items open to any
   * authenticated user (Dashboard, Calendar). Filtered in app-sidebar.tsx
   * against the caller's real effective_permissions, the same pattern
   * apps/student-portal's own sidebar already uses.
   */
  permission?: string;
  /**
   * True only for the 3 items whose backend route is require_superuser()
   * -gated (modules/organizations, modules/backups, modules/monitoring —
   * see _PLATFORM_ONLY_PERMISSIONS) rather than permission-gated: no
   * grantable permission code exists for these at all, even
   * Administrator doesn't have one, so they're filtered on the
   * is_superuser flag instead.
   */
  superuserOnly?: boolean;
  /**
   * Gates this item on an ownership record instead of a permission code
   * — "trainer" means "only if this account has a Trainer record"
   * (GET /trainers/me succeeds), checked in app-sidebar.tsx via
   * useIsTrainer(). These are self-service pages scoped to the caller's
   * own data (their own batches, their own live classes), so no
   * permission code applies the way it does for the admin CRUD items
   * below — a narrow custom role and the Administrator role should both
   * see these if the account is actually a trainer/employee, regardless
   * of what permissions that role happens to hold. Every trainer is also
   * an employee (Trainer is layered on Employee), so an account can see
   * both sets of "My X" items at once.
   */
  ownership?: "trainer" | "employee" | "student";
}

export interface NavSection {
  title: string;
  items: NavItem[];
}

export const navSections: NavSection[] = [
  {
    title: "Overview",
    items: [
      { label: "Dashboard", href: "/", icon: LayoutDashboard, enabled: true },
      { label: "Calendar", href: "/events", icon: Calendar, enabled: true },
    ],
  },
  {
    title: "My Work",
    items: [
      { label: "My Batches", href: "/my/batches", icon: Presentation, enabled: true, ownership: "trainer" },
      { label: "My Live Classes", href: "/my/live-classes", icon: Video, enabled: true, ownership: "trainer" },
      { label: "My Announcements", href: "/my/announcements", icon: Megaphone, enabled: true, ownership: "trainer" },
      { label: "My Messages", href: "/my/messages", icon: MessageCircle, enabled: true, ownership: "trainer" },
      { label: "My Attendance", href: "/my/attendance", icon: CalendarCheck, enabled: true, ownership: "employee" },
      { label: "My Leave", href: "/my/leave", icon: CalendarOff, enabled: true, ownership: "employee" },
      { label: "My Payslips", href: "/my/payslips", icon: Wallet, enabled: true, ownership: "employee" },
      { label: "My Expenses", href: "/my/expenses", icon: ReceiptText, enabled: true, ownership: "employee" },
      { label: "My Schedule", href: "/my/schedule", icon: CalendarDays, enabled: true, ownership: "student" },
    ],
  },
  {
    title: "Administration",
    items: [
      { label: "Organizations", href: "/organizations", icon: Building2, enabled: true, superuserOnly: true },
      { label: "Users", href: "/administration/users", icon: IdCard, enabled: true, permission: "users.view" },
      { label: "Roles", href: "/administration/roles", icon: ShieldCheck, enabled: true, permission: "authorization.roles.view" },
      { label: "Audit Logs", href: "/administration/audit-logs", icon: History, enabled: true, permission: "audit.view" },
      { label: "Broadcast Notification", href: "/administration/broadcast", icon: Megaphone, enabled: true, permission: "notifications.manage" },
      { label: "Database Backups", href: "/administration/backups", icon: Database, enabled: true, superuserOnly: true },
      { label: "Integrations", href: "/administration/integrations", icon: Plug, enabled: true, permission: "integrations.view" },
      { label: "System Health", href: "/administration/monitoring", icon: Activity, enabled: true, superuserOnly: true },
    ],
  },
  {
    title: "Business Modules",
    items: [
      { label: "Leads", href: "/crm/leads", icon: Users, enabled: true, permission: "crm.leads.view" },
      { label: "Admissions", href: "/crm/admissions", icon: UserCheck, enabled: true, permission: "crm.admissions.view" },
      { label: "Students", href: "/students", icon: GraduationCap, enabled: true, permission: "students.view" },
      { label: "Courses", href: "/courses", icon: BookOpen, enabled: true, permission: "courses.view" },
      { label: "Batches", href: "/batches", icon: CalendarClock, enabled: true, permission: "batches.view" },
      { label: "Trainers", href: "/trainers", icon: Presentation, enabled: true, permission: "trainers.view" },
      { label: "Classrooms", href: "/classrooms", icon: School, enabled: true, permission: "classrooms.view" },
      { label: "Announcements", href: "/lms/announcements", icon: Megaphone, enabled: true, permission: "lms.announcements.view" },
      { label: "Badges", href: "/lms/badges", icon: Award, enabled: true, permission: "lms.badges.view" },
      { label: "Student-Trainer Messages", href: "/messaging", icon: MessageCircle, enabled: true, permission: "messaging.view_all" },
      { label: "Question Bank", href: "/examinations/question-bank", icon: ClipboardList, enabled: true, permission: "examinations.question_bank.view" },
      { label: "Pentrix Labs", href: "/pentrix/labs", icon: Crosshair, enabled: true, permission: "pentrix.labs.view" },
      { label: "Pentrix Challenges", href: "/pentrix/challenges", icon: Flag, enabled: true, permission: "pentrix.challenges.view" },
      { label: "Pentrix Leaderboard", href: "/pentrix/leaderboard", icon: Trophy, enabled: true, permission: "pentrix.leaderboard.view" },
      { label: "Pentrix Achievements", href: "/pentrix/achievements", icon: Award, enabled: true, permission: "pentrix.achievements.view" },
      { label: "Chart of Accounts", href: "/accounting/ledger", icon: Landmark, enabled: true, permission: "accounting.ledger.view" },
      { label: "Journals", href: "/accounting/journals", icon: NotebookPen, enabled: true, permission: "accounting.journals.view" },
      { label: "Customers", href: "/accounting/customers", icon: UserCircle, enabled: true, permission: "accounting.customers.view" },
      { label: "Vendors", href: "/accounting/vendors", icon: Truck, enabled: true, permission: "accounting.vendors.view" },
      { label: "Invoices", href: "/accounting/invoices", icon: FileText, enabled: true, permission: "accounting.invoices.view" },
      { label: "Receipts", href: "/accounting/receipts", icon: Receipt, enabled: true, permission: "accounting.receipts.view" },
      { label: "Expenses", href: "/accounting/expenses", icon: CreditCard, enabled: true, permission: "accounting.expenses.view" },
      { label: "Payments", href: "/accounting/payments", icon: HandCoins, enabled: true, permission: "accounting.payments.view" },
      { label: "Bank Accounts", href: "/accounting/bank", icon: Banknote, enabled: true, permission: "accounting.bank.view" },
      { label: "GST", href: "/accounting/gst", icon: Percent, enabled: true, permission: "accounting.gst.view" },
      { label: "TDS", href: "/accounting/tds", icon: ReceiptText, enabled: true, permission: "accounting.tds.view" },
      { label: "Financial Reports", href: "/accounting/reports", icon: BarChart3, enabled: true, permission: "accounting.reports.view" },
      { label: "Employees", href: "/employees", icon: UserCog, enabled: true, permission: "employees.view" },
      { label: "Departments & Designations", href: "/hr/departments-designations", icon: Building2, enabled: true, permission: "hr.departments.view" },
      { label: "Attendance", href: "/attendance", icon: CalendarCheck, enabled: true, permission: "attendance.view" },
      { label: "Leave Types", href: "/leave/types", icon: CalendarOff, enabled: true, permission: "leave.types.view" },
      { label: "Leave Applications", href: "/leave/applications", icon: CalendarDays, enabled: true, permission: "leave.applications.view" },
      { label: "Expense Claims", href: "/expense-claims", icon: HandCoins, enabled: true, permission: "expense_claims.view" },
      { label: "Salary Components", href: "/payroll/components", icon: Wallet, enabled: true, permission: "payroll.components.view" },
      { label: "Payroll Runs", href: "/payroll/runs", icon: CircleDollarSign, enabled: true, permission: "payroll.runs.view" },
      { label: "Item Categories & Warehouses", href: "/inventory/settings", icon: Warehouse, enabled: true, permission: "inventory.items.view" },
      { label: "Inventory Items", href: "/inventory/items", icon: Boxes, enabled: true, permission: "inventory.items.view" },
      { label: "Asset Categories", href: "/assets/categories", icon: Layers, enabled: true, permission: "assets.view" },
      { label: "Fixed Assets", href: "/assets", icon: Wrench, enabled: true, permission: "assets.view" },
      { label: "Depreciation Runs", href: "/assets/depreciation-runs", icon: TrendingDown, enabled: true, permission: "assets.depreciation.view" },
      { label: "Purchase Orders", href: "/procurement/purchase-orders", icon: ShoppingCart, enabled: true, permission: "procurement.purchase_orders.view" },
      { label: "Clients", href: "/corporate/clients", icon: Briefcase, enabled: true, permission: "corporate.clients.view" },
      { label: "Corporate Reports", href: "/corporate/reports", icon: BarChart3, enabled: true, permission: "corporate.reports.view" },
      { label: "Campaigns", href: "/marketing/campaigns", icon: Megaphone, enabled: true, permission: "marketing.campaigns.view" },
      { label: "Coupons", href: "/marketing/coupons", icon: Ticket, enabled: true, permission: "marketing.coupons.view" },
      { label: "Landing Pages", href: "/marketing/landing-pages", icon: Globe, enabled: true, permission: "marketing.landing_pages.view" },
      { label: "Referral Programs", href: "/marketing/referrals/programs", icon: Gift, enabled: true, permission: "marketing.referrals.view" },
      { label: "Referrals", href: "/marketing/referrals", icon: Share2, enabled: true, permission: "marketing.referrals.view" },
      { label: "Marketing Overview", href: "/marketing/analytics", icon: LineChart, enabled: true, permission: "marketing.analytics.view" },
      { label: "Workshops", href: "/workshops", icon: PartyPopper, enabled: true, permission: "workshops.view" },
      { label: "Workshop Exams", href: "/workshop-exams", icon: ClipboardCheck, enabled: true, permission: "workshops.view" },
      { label: "Hackathons", href: "/hackathons", icon: Rocket, enabled: true, permission: "hackathons.view" },
      { label: "Placement Companies", href: "/placements/companies", icon: Building2, enabled: true, permission: "placements.view" },
      { label: "Job Postings", href: "/placements/postings", icon: Handshake, enabled: true, permission: "placements.view" },
      { label: "Internship Postings", href: "/internships/postings", icon: InternGraduationCap, enabled: true, permission: "internships.view" },
      { label: "Active Internships", href: "/internships", icon: ClipboardList, enabled: true, permission: "internships.view" },
      { label: "Alumni Profiles", href: "/alumni/profiles", icon: Contact, enabled: true, permission: "alumni.view" },
      { label: "Alumni Events", href: "/alumni/events", icon: AlumniEventIcon, enabled: true, permission: "alumni.view" },
      { label: "Job Referrals", href: "/alumni/referrals", icon: Newspaper, enabled: true, permission: "alumni.view" },
      { label: "Media Gallery", href: "/media/albums", icon: Images, enabled: true, permission: "media.view" },
      { label: "Communication Log", href: "/communication/logs", icon: MessageSquare, enabled: true, permission: "communication.view" },
      { label: "Approval Workflows", href: "/workflow/workflows", icon: Workflow, enabled: true, permission: "workflow.view" },
      { label: "Approval Requests", href: "/workflow/requests", icon: ListChecks, enabled: true, permission: "workflow.view" },
      { label: "My Approvals", href: "/workflow/my-approvals", icon: UserCheck2, enabled: true, permission: "workflow.view" },
    ],
  },
];
