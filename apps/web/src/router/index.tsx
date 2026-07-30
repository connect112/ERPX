import { lazy } from "react";
import { createBrowserRouter } from "react-router-dom";

const AccountSettingsPage = lazy(() => import("@/features/auth/pages/account-settings-page").then((m) => ({ default: m.AccountSettingsPage })));
import { ForgotPasswordPage } from "@/features/auth/pages/forgot-password-page";
import { LoginPage } from "@/features/auth/pages/login-page";
import { RegisterPage } from "@/features/auth/pages/register-page";
import { ResetPasswordPage } from "@/features/auth/pages/reset-password-page";
import { VerifyEmailPage } from "@/features/auth/pages/verify-email-page";
const AccountDetailPage = lazy(() => import("@/features/accounting/ledger/pages/account-detail-page").then((m) => ({ default: m.AccountDetailPage })));
const AccountsListPage = lazy(() => import("@/features/accounting/ledger/pages/accounts-list-page").then((m) => ({ default: m.AccountsListPage })));
const BankAccountDetailPage = lazy(() => import("@/features/accounting/bank/pages/bank-account-detail-page").then((m) => ({ default: m.BankAccountDetailPage })));
const BankAccountsListPage = lazy(() => import("@/features/accounting/bank/pages/bank-accounts-list-page").then((m) => ({ default: m.BankAccountsListPage })));
const CustomersListPage = lazy(() => import("@/features/accounting/customers/pages/customers-list-page").then((m) => ({ default: m.CustomersListPage })));
const ExpenseDetailPage = lazy(() => import("@/features/accounting/expenses/pages/expense-detail-page").then((m) => ({ default: m.ExpenseDetailPage })));
const ExpensesListPage = lazy(() => import("@/features/accounting/expenses/pages/expenses-list-page").then((m) => ({ default: m.ExpensesListPage })));
const GSTPage = lazy(() => import("@/features/accounting/gst/pages/gst-page").then((m) => ({ default: m.GSTPage })));
const InvoiceCreatePage = lazy(() => import("@/features/accounting/invoices/pages/invoice-create-page").then((m) => ({ default: m.InvoiceCreatePage })));
const InvoiceDetailPage = lazy(() => import("@/features/accounting/invoices/pages/invoice-detail-page").then((m) => ({ default: m.InvoiceDetailPage })));
const InvoicesListPage = lazy(() => import("@/features/accounting/invoices/pages/invoices-list-page").then((m) => ({ default: m.InvoicesListPage })));
const JournalDetailPage = lazy(() => import("@/features/accounting/journals/pages/journal-detail-page").then((m) => ({ default: m.JournalDetailPage })));
const JournalsListPage = lazy(() => import("@/features/accounting/journals/pages/journals-list-page").then((m) => ({ default: m.JournalsListPage })));
const PaymentsListPage = lazy(() => import("@/features/accounting/payments/pages/payments-list-page").then((m) => ({ default: m.PaymentsListPage })));
const ReceiptsListPage = lazy(() => import("@/features/accounting/receipts/pages/receipts-list-page").then((m) => ({ default: m.ReceiptsListPage })));
const ReportsPage = lazy(() => import("@/features/accounting/reports/pages/reports-page").then((m) => ({ default: m.ReportsPage })));
const TDSPage = lazy(() => import("@/features/accounting/tds/pages/tds-page").then((m) => ({ default: m.TDSPage })));
const VendorDetailPage = lazy(() => import("@/features/accounting/vendors/pages/vendor-detail-page").then((m) => ({ default: m.VendorDetailPage })));
const VendorsListPage = lazy(() => import("@/features/accounting/vendors/pages/vendors-list-page").then((m) => ({ default: m.VendorsListPage })));
const AdmissionsListPage = lazy(() => import("@/features/crm/admissions/pages/admissions-list-page").then((m) => ({ default: m.AdmissionsListPage })));
const LeadDetailPage = lazy(() => import("@/features/crm/leads/pages/lead-detail-page").then((m) => ({ default: m.LeadDetailPage })));
const LeadsListPage = lazy(() => import("@/features/crm/leads/pages/leads-list-page").then((m) => ({ default: m.LeadsListPage })));
const CategoriesListPage = lazy(() => import("@/features/courses/categories/pages/categories-list-page").then((m) => ({ default: m.CategoriesListPage })));
const CourseDetailPage = lazy(() => import("@/features/courses/pages/course-detail-page").then((m) => ({ default: m.CourseDetailPage })));
const CoursesListPage = lazy(() => import("@/features/courses/pages/courses-list-page").then((m) => ({ default: m.CoursesListPage })));
const LearningPathDetailPage = lazy(() => import("@/features/courses/learning-paths/pages/learning-path-detail-page").then((m) => ({ default: m.LearningPathDetailPage })));
const LearningPathsListPage = lazy(() => import("@/features/courses/learning-paths/pages/learning-paths-list-page").then((m) => ({ default: m.LearningPathsListPage })));
const DashboardPage = lazy(() => import("@/features/dashboard/pages/dashboard-page").then((m) => ({ default: m.DashboardPage })));
const QuestionBankPage = lazy(() => import("@/features/examinations/question-bank/pages/question-bank-page").then((m) => ({ default: m.QuestionBankPage })));
const AnnouncementsListPage = lazy(() => import("@/features/lms/announcements/pages/announcements-list-page").then((m) => ({ default: m.AnnouncementsListPage })));
const BadgesListPage = lazy(() => import("@/features/lms/badges/pages/badges-list-page").then((m) => ({ default: m.BadgesListPage })));
import { CertificateVerifyPage } from "@/features/lms/certificates/pages/certificate-verify-page";
const AchievementsListPage = lazy(() => import("@/features/pentrix/achievements/pages/achievements-list-page").then((m) => ({ default: m.AchievementsListPage })));
import { CertificationVerifyPage } from "@/features/pentrix/certifications/pages/certification-verify-page";
const ChallengeDetailPage = lazy(() => import("@/features/pentrix/challenges/pages/challenge-detail-page").then((m) => ({ default: m.ChallengeDetailPage })));
const ChallengesListPage = lazy(() => import("@/features/pentrix/challenges/pages/challenges-list-page").then((m) => ({ default: m.ChallengesListPage })));
const LabDetailPage = lazy(() => import("@/features/pentrix/labs/pages/lab-detail-page").then((m) => ({ default: m.LabDetailPage })));
const LabsListPage = lazy(() => import("@/features/pentrix/labs/pages/labs-list-page").then((m) => ({ default: m.LabsListPage })));
const LeaderboardPage = lazy(() => import("@/features/pentrix/leaderboard/pages/leaderboard-page").then((m) => ({ default: m.LeaderboardPage })));
const StudentDetailPage = lazy(() => import("@/features/students/pages/student-detail-page").then((m) => ({ default: m.StudentDetailPage })));
const StudentsListPage = lazy(() => import("@/features/students/pages/students-list-page").then((m) => ({ default: m.StudentsListPage })));
const EmployeeDetailPage = lazy(() => import("@/features/employees/pages/employee-detail-page").then((m) => ({ default: m.EmployeeDetailPage })));
const EmployeesListPage = lazy(() => import("@/features/employees/pages/employees-list-page").then((m) => ({ default: m.EmployeesListPage })));
const HRSettingsPage = lazy(() => import("@/features/hr/pages/hr-settings-page").then((m) => ({ default: m.HRSettingsPage })));
const AttendancePage = lazy(() => import("@/features/attendance/pages/attendance-page").then((m) => ({ default: m.AttendancePage })));
const LeaveApplicationsPage = lazy(() => import("@/features/leave/pages/leave-applications-page").then((m) => ({ default: m.LeaveApplicationsPage })));
const LeaveTypesPage = lazy(() => import("@/features/leave/pages/leave-types-page").then((m) => ({ default: m.LeaveTypesPage })));
const PayrollRunDetailPage = lazy(() => import("@/features/payroll/pages/payroll-run-detail-page").then((m) => ({ default: m.PayrollRunDetailPage })));
const PayrollRunsPage = lazy(() => import("@/features/payroll/pages/payroll-runs-page").then((m) => ({ default: m.PayrollRunsPage })));
const SalaryComponentsPage = lazy(() => import("@/features/payroll/pages/salary-components-page").then((m) => ({ default: m.SalaryComponentsPage })));
const InventorySettingsPage = lazy(() => import("@/features/inventory/categories/pages/inventory-settings-page").then((m) => ({ default: m.InventorySettingsPage })));
const ItemDetailPage = lazy(() => import("@/features/inventory/items/pages/item-detail-page").then((m) => ({ default: m.ItemDetailPage })));
const ItemsListPage = lazy(() => import("@/features/inventory/items/pages/items-list-page").then((m) => ({ default: m.ItemsListPage })));
const AssetCategoriesPage = lazy(() => import("@/features/assets/categories/pages/asset-categories-page").then((m) => ({ default: m.AssetCategoriesPage })));
const AssetDetailPage = lazy(() => import("@/features/assets/assets/pages/asset-detail-page").then((m) => ({ default: m.AssetDetailPage })));
const AssetsListPage = lazy(() => import("@/features/assets/assets/pages/assets-list-page").then((m) => ({ default: m.AssetsListPage })));
const DepreciationRunDetailPage = lazy(() => import("@/features/assets/depreciation/pages/depreciation-run-detail-page").then((m) => ({ default: m.DepreciationRunDetailPage })));
const DepreciationRunsPage = lazy(() => import("@/features/assets/depreciation/pages/depreciation-runs-page").then((m) => ({ default: m.DepreciationRunsPage })));
const PurchaseOrderCreatePage = lazy(() => import("@/features/procurement/purchase-orders/pages/purchase-order-create-page").then((m) => ({ default: m.PurchaseOrderCreatePage })));
const PurchaseOrderDetailPage = lazy(() => import("@/features/procurement/purchase-orders/pages/purchase-order-detail-page").then((m) => ({ default: m.PurchaseOrderDetailPage })));
const PurchaseOrdersListPage = lazy(() => import("@/features/procurement/purchase-orders/pages/purchase-orders-list-page").then((m) => ({ default: m.PurchaseOrdersListPage })));
const ClientDetailPage = lazy(() => import("@/features/corporate/clients/pages/client-detail-page").then((m) => ({ default: m.ClientDetailPage })));
const ClientsListPage = lazy(() => import("@/features/corporate/clients/pages/clients-list-page").then((m) => ({ default: m.ClientsListPage })));
const ProjectDetailPage = lazy(() => import("@/features/corporate/projects/pages/project-detail-page").then((m) => ({ default: m.ProjectDetailPage })));
const CorporateReportsPage = lazy(() => import("@/features/corporate/reports/pages/corporate-reports-page").then((m) => ({ default: m.CorporateReportsPage })));
const CampaignDetailPage = lazy(() => import("@/features/marketing/campaigns/pages/campaign-detail-page").then((m) => ({ default: m.CampaignDetailPage })));
const CampaignsListPage = lazy(() => import("@/features/marketing/campaigns/pages/campaigns-list-page").then((m) => ({ default: m.CampaignsListPage })));
const CouponDetailPage = lazy(() => import("@/features/marketing/coupons/pages/coupon-detail-page").then((m) => ({ default: m.CouponDetailPage })));
const CouponsListPage = lazy(() => import("@/features/marketing/coupons/pages/coupons-list-page").then((m) => ({ default: m.CouponsListPage })));
const LandingPageDetailPage = lazy(() => import("@/features/marketing/landing-pages/pages/landing-page-detail-page").then((m) => ({ default: m.LandingPageDetailPage })));
const LandingPagesListPage = lazy(() => import("@/features/marketing/landing-pages/pages/landing-pages-list-page").then((m) => ({ default: m.LandingPagesListPage })));
const ReferralProgramsPage = lazy(() => import("@/features/marketing/referrals/pages/referral-programs-page").then((m) => ({ default: m.ReferralProgramsPage })));
const ReferralsListPage = lazy(() => import("@/features/marketing/referrals/pages/referrals-list-page").then((m) => ({ default: m.ReferralsListPage })));
const MarketingOverviewPage = lazy(() => import("@/features/marketing/analytics/pages/marketing-overview-page").then((m) => ({ default: m.MarketingOverviewPage })));
const WorkshopDetailPage = lazy(() => import("@/features/workshops/pages/workshop-detail-page").then((m) => ({ default: m.WorkshopDetailPage })));
const WorkshopsListPage = lazy(() => import("@/features/workshops/pages/workshops-list-page").then((m) => ({ default: m.WorkshopsListPage })));
const HackathonDetailPage = lazy(() => import("@/features/hackathons/pages/hackathon-detail-page").then((m) => ({ default: m.HackathonDetailPage })));
const HackathonsListPage = lazy(() => import("@/features/hackathons/pages/hackathons-list-page").then((m) => ({ default: m.HackathonsListPage })));
const CompaniesListPage = lazy(() => import("@/features/placements/pages/companies-list-page").then((m) => ({ default: m.CompaniesListPage })));
const PostingDetailPage = lazy(() => import("@/features/placements/pages/posting-detail-page").then((m) => ({ default: m.PostingDetailPage })));
const PostingsListPage = lazy(() => import("@/features/placements/pages/postings-list-page").then((m) => ({ default: m.PostingsListPage })));
const InternshipsListPage = lazy(() => import("@/features/internships/pages/internships-list-page").then((m) => ({ default: m.InternshipsListPage })));
const InternshipPostingDetailPage = lazy(() => import("@/features/internships/pages/posting-detail-page").then((m) => ({ default: m.PostingDetailPage })));
const InternshipPostingsListPage = lazy(() => import("@/features/internships/pages/postings-list-page").then((m) => ({ default: m.PostingsListPage })));
const AlumniProfilesListPage = lazy(() => import("@/features/alumni/pages/profiles-list-page").then((m) => ({ default: m.ProfilesListPage })));
const AlumniEventsListPage = lazy(() => import("@/features/alumni/pages/events-list-page").then((m) => ({ default: m.EventsListPage })));
const AlumniEventDetailPage = lazy(() => import("@/features/alumni/pages/event-detail-page").then((m) => ({ default: m.EventDetailPage })));
const AlumniReferralsListPage = lazy(() => import("@/features/alumni/pages/referrals-list-page").then((m) => ({ default: m.ReferralsListPage })));
const MediaAlbumsListPage = lazy(() => import("@/features/media/pages/albums-list-page").then((m) => ({ default: m.AlbumsListPage })));
const MediaAlbumDetailPage = lazy(() => import("@/features/media/pages/album-detail-page").then((m) => ({ default: m.AlbumDetailPage })));
const WorkflowsListPage = lazy(() => import("@/features/workflow/pages/workflows-list-page").then((m) => ({ default: m.WorkflowsListPage })));
const WorkflowDetailPage = lazy(() => import("@/features/workflow/pages/workflow-detail-page").then((m) => ({ default: m.WorkflowDetailPage })));
const RequestsListPage = lazy(() => import("@/features/workflow/pages/requests-list-page").then((m) => ({ default: m.RequestsListPage })));
const MyApprovalsPage = lazy(() => import("@/features/workflow/pages/my-approvals-page").then((m) => ({ default: m.MyApprovalsPage })));
const BroadcastPage = lazy(() => import("@/features/notifications/pages/broadcast-page").then((m) => ({ default: m.BroadcastPage })));
const CommunicationLogPage = lazy(() => import("@/features/communication/pages/communication-log-page").then((m) => ({ default: m.CommunicationLogPage })));
const EventsListPage = lazy(() => import("@/features/events/pages/events-list-page").then((m) => ({ default: m.EventsListPage })));
const BackupsPage = lazy(() => import("@/features/backups/pages/backups-page").then((m) => ({ default: m.BackupsPage })));
const IntegrationsPage = lazy(() => import("@/features/integrations/pages/integrations-page").then((m) => ({ default: m.IntegrationsPage })));
const MonitoringPage = lazy(() => import("@/features/monitoring/pages/monitoring-page").then((m) => ({ default: m.MonitoringPage })));
const OrganizationDetailPage = lazy(() => import("@/features/organizations/pages/organization-detail-page").then((m) => ({ default: m.OrganizationDetailPage })));
const OrganizationsListPage = lazy(() => import("@/features/organizations/pages/organizations-list-page").then((m) => ({ default: m.OrganizationsListPage })));
const UserDetailPage = lazy(() => import("@/features/users/pages/user-detail-page").then((m) => ({ default: m.UserDetailPage })));
const UsersListPage = lazy(() => import("@/features/users/pages/users-list-page").then((m) => ({ default: m.UsersListPage })));
const RoleDetailPage = lazy(() => import("@/features/authorization/pages/role-detail-page").then((m) => ({ default: m.RoleDetailPage })));
const RolesListPage = lazy(() => import("@/features/authorization/pages/roles-list-page").then((m) => ({ default: m.RolesListPage })));
const AuditLogListPage = lazy(() => import("@/features/audit/pages/audit-log-list-page").then((m) => ({ default: m.AuditLogListPage })));
const BatchDetailPage = lazy(() => import("@/features/batches/pages/batch-detail-page").then((m) => ({ default: m.BatchDetailPage })));
const BatchesListPage = lazy(() => import("@/features/batches/pages/batches-list-page").then((m) => ({ default: m.BatchesListPage })));
const ClassroomsListPage = lazy(() => import("@/features/classrooms/pages/classrooms-list-page").then((m) => ({ default: m.ClassroomsListPage })));
const TrainersListPage = lazy(() => import("@/features/trainers/pages/trainers-list-page").then((m) => ({ default: m.TrainersListPage })));
import { AppLayout } from "@/layouts/app-layout";
import { ProtectedRoute } from "@/router/protected-route";

/**
 * Root router. Each business module adds a child route under the
 * `AppLayout` element as it's built, e.g.:
 *
 *   { path: "crm/leads", element: <LeadsPage /> }
 */
export const router = createBrowserRouter([
  {
    path: "/",
    element: (
      <ProtectedRoute>
        <AppLayout />
      </ProtectedRoute>
    ),
    children: [
      { index: true, element: <DashboardPage /> },
      { path: "account-settings", element: <AccountSettingsPage /> },
      { path: "crm/leads", element: <LeadsListPage /> },
      { path: "crm/leads/:leadId", element: <LeadDetailPage /> },
      { path: "crm/admissions", element: <AdmissionsListPage /> },
      { path: "students", element: <StudentsListPage /> },
      { path: "students/:studentId", element: <StudentDetailPage /> },
      { path: "courses", element: <CoursesListPage /> },
      { path: "courses/categories", element: <CategoriesListPage /> },
      { path: "courses/learning-paths", element: <LearningPathsListPage /> },
      { path: "courses/learning-paths/:pathId", element: <LearningPathDetailPage /> },
      { path: "courses/:courseId", element: <CourseDetailPage /> },
      { path: "batches", element: <BatchesListPage /> },
      { path: "batches/:batchId", element: <BatchDetailPage /> },
      { path: "trainers", element: <TrainersListPage /> },
      { path: "classrooms", element: <ClassroomsListPage /> },
      { path: "lms/announcements", element: <AnnouncementsListPage /> },
      { path: "lms/badges", element: <BadgesListPage /> },
      { path: "examinations/question-bank", element: <QuestionBankPage /> },
      { path: "pentrix/labs", element: <LabsListPage /> },
      { path: "pentrix/labs/:labId", element: <LabDetailPage /> },
      { path: "pentrix/challenges", element: <ChallengesListPage /> },
      { path: "pentrix/challenges/:challengeId", element: <ChallengeDetailPage /> },
      { path: "pentrix/leaderboard", element: <LeaderboardPage /> },
      { path: "pentrix/achievements", element: <AchievementsListPage /> },
      { path: "accounting/ledger", element: <AccountsListPage /> },
      { path: "accounting/ledger/:accountId", element: <AccountDetailPage /> },
      { path: "accounting/journals", element: <JournalsListPage /> },
      { path: "accounting/journals/:entryId", element: <JournalDetailPage /> },
      { path: "accounting/customers", element: <CustomersListPage /> },
      { path: "accounting/vendors", element: <VendorsListPage /> },
      { path: "accounting/vendors/:vendorId", element: <VendorDetailPage /> },
      { path: "accounting/gst", element: <GSTPage /> },
      { path: "accounting/tds", element: <TDSPage /> },
      { path: "accounting/bank", element: <BankAccountsListPage /> },
      { path: "accounting/bank/:bankAccountId", element: <BankAccountDetailPage /> },
      { path: "accounting/invoices", element: <InvoicesListPage /> },
      { path: "accounting/invoices/new", element: <InvoiceCreatePage /> },
      { path: "accounting/invoices/:invoiceId", element: <InvoiceDetailPage /> },
      { path: "accounting/receipts", element: <ReceiptsListPage /> },
      { path: "accounting/expenses", element: <ExpensesListPage /> },
      { path: "accounting/expenses/:expenseId", element: <ExpenseDetailPage /> },
      { path: "accounting/payments", element: <PaymentsListPage /> },
      { path: "accounting/reports", element: <ReportsPage /> },
      { path: "employees", element: <EmployeesListPage /> },
      { path: "employees/:employeeId", element: <EmployeeDetailPage /> },
      { path: "hr/departments-designations", element: <HRSettingsPage /> },
      { path: "attendance", element: <AttendancePage /> },
      { path: "leave/types", element: <LeaveTypesPage /> },
      { path: "leave/applications", element: <LeaveApplicationsPage /> },
      { path: "payroll/components", element: <SalaryComponentsPage /> },
      { path: "payroll/runs", element: <PayrollRunsPage /> },
      { path: "payroll/runs/:runId", element: <PayrollRunDetailPage /> },
      { path: "inventory/settings", element: <InventorySettingsPage /> },
      { path: "inventory/items", element: <ItemsListPage /> },
      { path: "inventory/items/:itemId", element: <ItemDetailPage /> },
      { path: "assets/categories", element: <AssetCategoriesPage /> },
      { path: "assets", element: <AssetsListPage /> },
      { path: "assets/depreciation-runs", element: <DepreciationRunsPage /> },
      { path: "assets/depreciation-runs/:runId", element: <DepreciationRunDetailPage /> },
      { path: "assets/:assetId", element: <AssetDetailPage /> },
      { path: "procurement/purchase-orders", element: <PurchaseOrdersListPage /> },
      { path: "procurement/purchase-orders/new", element: <PurchaseOrderCreatePage /> },
      { path: "procurement/purchase-orders/:poId", element: <PurchaseOrderDetailPage /> },
      { path: "corporate/clients", element: <ClientsListPage /> },
      { path: "corporate/clients/:clientId", element: <ClientDetailPage /> },
      { path: "corporate/projects/:projectId", element: <ProjectDetailPage /> },
      { path: "corporate/reports", element: <CorporateReportsPage /> },
      { path: "marketing/campaigns", element: <CampaignsListPage /> },
      { path: "marketing/campaigns/:campaignId", element: <CampaignDetailPage /> },
      { path: "marketing/coupons", element: <CouponsListPage /> },
      { path: "marketing/coupons/:couponId", element: <CouponDetailPage /> },
      { path: "marketing/landing-pages", element: <LandingPagesListPage /> },
      { path: "marketing/landing-pages/:pageId", element: <LandingPageDetailPage /> },
      { path: "marketing/referrals/programs", element: <ReferralProgramsPage /> },
      { path: "marketing/referrals", element: <ReferralsListPage /> },
      { path: "marketing/analytics", element: <MarketingOverviewPage /> },
      { path: "workshops", element: <WorkshopsListPage /> },
      { path: "workshops/:workshopId", element: <WorkshopDetailPage /> },
      { path: "hackathons", element: <HackathonsListPage /> },
      { path: "hackathons/:hackathonId", element: <HackathonDetailPage /> },
      { path: "placements/companies", element: <CompaniesListPage /> },
      { path: "placements/postings", element: <PostingsListPage /> },
      { path: "placements/postings/:postingId", element: <PostingDetailPage /> },
      { path: "internships/postings", element: <InternshipPostingsListPage /> },
      { path: "internships/postings/:postingId", element: <InternshipPostingDetailPage /> },
      { path: "internships", element: <InternshipsListPage /> },
      { path: "alumni/profiles", element: <AlumniProfilesListPage /> },
      { path: "alumni/events", element: <AlumniEventsListPage /> },
      { path: "alumni/events/:eventId", element: <AlumniEventDetailPage /> },
      { path: "alumni/referrals", element: <AlumniReferralsListPage /> },
      { path: "media/albums", element: <MediaAlbumsListPage /> },
      { path: "media/albums/:albumId", element: <MediaAlbumDetailPage /> },
      { path: "workflow/workflows", element: <WorkflowsListPage /> },
      { path: "workflow/workflows/:workflowId", element: <WorkflowDetailPage /> },
      { path: "workflow/requests", element: <RequestsListPage /> },
      { path: "workflow/my-approvals", element: <MyApprovalsPage /> },
      { path: "organizations", element: <OrganizationsListPage /> },
      { path: "organizations/:orgId", element: <OrganizationDetailPage /> },
      { path: "administration/users", element: <UsersListPage /> },
      { path: "administration/users/:userId", element: <UserDetailPage /> },
      { path: "administration/roles", element: <RolesListPage /> },
      { path: "administration/roles/:roleId", element: <RoleDetailPage /> },
      { path: "administration/audit-logs", element: <AuditLogListPage /> },
      { path: "administration/broadcast", element: <BroadcastPage /> },
      { path: "administration/backups", element: <BackupsPage /> },
      { path: "administration/integrations", element: <IntegrationsPage /> },
      { path: "administration/monitoring", element: <MonitoringPage /> },
      { path: "communication/logs", element: <CommunicationLogPage /> },
      { path: "events", element: <EventsListPage /> },
    ],
  },
  { path: "/login", element: <LoginPage /> },
  { path: "/register", element: <RegisterPage /> },
  { path: "/verify-email", element: <VerifyEmailPage /> },
  { path: "/forgot-password", element: <ForgotPasswordPage /> },
  { path: "/reset-password", element: <ResetPasswordPage /> },
  { path: "/certificates/verify", element: <CertificateVerifyPage /> },
  { path: "/pentrix/certifications/verify", element: <CertificationVerifyPage /> },
]);
