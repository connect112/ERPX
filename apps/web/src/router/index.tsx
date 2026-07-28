import { createBrowserRouter } from "react-router-dom";

import { AccountSettingsPage } from "@/features/auth/pages/account-settings-page";
import { ForgotPasswordPage } from "@/features/auth/pages/forgot-password-page";
import { LoginPage } from "@/features/auth/pages/login-page";
import { RegisterPage } from "@/features/auth/pages/register-page";
import { ResetPasswordPage } from "@/features/auth/pages/reset-password-page";
import { VerifyEmailPage } from "@/features/auth/pages/verify-email-page";
import { AccountDetailPage } from "@/features/accounting/ledger/pages/account-detail-page";
import { AccountsListPage } from "@/features/accounting/ledger/pages/accounts-list-page";
import { BankAccountDetailPage } from "@/features/accounting/bank/pages/bank-account-detail-page";
import { BankAccountsListPage } from "@/features/accounting/bank/pages/bank-accounts-list-page";
import { CustomersListPage } from "@/features/accounting/customers/pages/customers-list-page";
import { ExpenseDetailPage } from "@/features/accounting/expenses/pages/expense-detail-page";
import { ExpensesListPage } from "@/features/accounting/expenses/pages/expenses-list-page";
import { GSTPage } from "@/features/accounting/gst/pages/gst-page";
import { InvoiceCreatePage } from "@/features/accounting/invoices/pages/invoice-create-page";
import { InvoiceDetailPage } from "@/features/accounting/invoices/pages/invoice-detail-page";
import { InvoicesListPage } from "@/features/accounting/invoices/pages/invoices-list-page";
import { JournalDetailPage } from "@/features/accounting/journals/pages/journal-detail-page";
import { JournalsListPage } from "@/features/accounting/journals/pages/journals-list-page";
import { PaymentsListPage } from "@/features/accounting/payments/pages/payments-list-page";
import { ReceiptsListPage } from "@/features/accounting/receipts/pages/receipts-list-page";
import { ReportsPage } from "@/features/accounting/reports/pages/reports-page";
import { TDSPage } from "@/features/accounting/tds/pages/tds-page";
import { VendorDetailPage } from "@/features/accounting/vendors/pages/vendor-detail-page";
import { VendorsListPage } from "@/features/accounting/vendors/pages/vendors-list-page";
import { AdmissionsListPage } from "@/features/crm/admissions/pages/admissions-list-page";
import { LeadDetailPage } from "@/features/crm/leads/pages/lead-detail-page";
import { LeadsListPage } from "@/features/crm/leads/pages/leads-list-page";
import { CategoriesListPage } from "@/features/courses/categories/pages/categories-list-page";
import { CourseDetailPage } from "@/features/courses/pages/course-detail-page";
import { CoursesListPage } from "@/features/courses/pages/courses-list-page";
import { LearningPathDetailPage } from "@/features/courses/learning-paths/pages/learning-path-detail-page";
import { LearningPathsListPage } from "@/features/courses/learning-paths/pages/learning-paths-list-page";
import { DashboardPage } from "@/features/dashboard/pages/dashboard-page";
import { QuestionBankPage } from "@/features/examinations/question-bank/pages/question-bank-page";
import { AnnouncementsListPage } from "@/features/lms/announcements/pages/announcements-list-page";
import { BadgesListPage } from "@/features/lms/badges/pages/badges-list-page";
import { CertificateVerifyPage } from "@/features/lms/certificates/pages/certificate-verify-page";
import { AchievementsListPage } from "@/features/pentrix/achievements/pages/achievements-list-page";
import { CertificationVerifyPage } from "@/features/pentrix/certifications/pages/certification-verify-page";
import { ChallengeDetailPage } from "@/features/pentrix/challenges/pages/challenge-detail-page";
import { ChallengesListPage } from "@/features/pentrix/challenges/pages/challenges-list-page";
import { LabDetailPage } from "@/features/pentrix/labs/pages/lab-detail-page";
import { LabsListPage } from "@/features/pentrix/labs/pages/labs-list-page";
import { LeaderboardPage } from "@/features/pentrix/leaderboard/pages/leaderboard-page";
import { StudentDetailPage } from "@/features/students/pages/student-detail-page";
import { StudentsListPage } from "@/features/students/pages/students-list-page";
import { EmployeeDetailPage } from "@/features/employees/pages/employee-detail-page";
import { EmployeesListPage } from "@/features/employees/pages/employees-list-page";
import { HRSettingsPage } from "@/features/hr/pages/hr-settings-page";
import { AttendancePage } from "@/features/attendance/pages/attendance-page";
import { LeaveApplicationsPage } from "@/features/leave/pages/leave-applications-page";
import { LeaveTypesPage } from "@/features/leave/pages/leave-types-page";
import { PayrollRunDetailPage } from "@/features/payroll/pages/payroll-run-detail-page";
import { PayrollRunsPage } from "@/features/payroll/pages/payroll-runs-page";
import { SalaryComponentsPage } from "@/features/payroll/pages/salary-components-page";
import { InventorySettingsPage } from "@/features/inventory/categories/pages/inventory-settings-page";
import { ItemDetailPage } from "@/features/inventory/items/pages/item-detail-page";
import { ItemsListPage } from "@/features/inventory/items/pages/items-list-page";
import { AssetCategoriesPage } from "@/features/assets/categories/pages/asset-categories-page";
import { AssetDetailPage } from "@/features/assets/assets/pages/asset-detail-page";
import { AssetsListPage } from "@/features/assets/assets/pages/assets-list-page";
import { DepreciationRunDetailPage } from "@/features/assets/depreciation/pages/depreciation-run-detail-page";
import { DepreciationRunsPage } from "@/features/assets/depreciation/pages/depreciation-runs-page";
import { PurchaseOrderCreatePage } from "@/features/procurement/purchase-orders/pages/purchase-order-create-page";
import { PurchaseOrderDetailPage } from "@/features/procurement/purchase-orders/pages/purchase-order-detail-page";
import { PurchaseOrdersListPage } from "@/features/procurement/purchase-orders/pages/purchase-orders-list-page";
import { ClientDetailPage } from "@/features/corporate/clients/pages/client-detail-page";
import { ClientsListPage } from "@/features/corporate/clients/pages/clients-list-page";
import { ProjectDetailPage } from "@/features/corporate/projects/pages/project-detail-page";
import { CorporateReportsPage } from "@/features/corporate/reports/pages/corporate-reports-page";
import { CampaignDetailPage } from "@/features/marketing/campaigns/pages/campaign-detail-page";
import { CampaignsListPage } from "@/features/marketing/campaigns/pages/campaigns-list-page";
import { CouponDetailPage } from "@/features/marketing/coupons/pages/coupon-detail-page";
import { CouponsListPage } from "@/features/marketing/coupons/pages/coupons-list-page";
import { LandingPageDetailPage } from "@/features/marketing/landing-pages/pages/landing-page-detail-page";
import { LandingPagesListPage } from "@/features/marketing/landing-pages/pages/landing-pages-list-page";
import { ReferralProgramsPage } from "@/features/marketing/referrals/pages/referral-programs-page";
import { ReferralsListPage } from "@/features/marketing/referrals/pages/referrals-list-page";
import { MarketingOverviewPage } from "@/features/marketing/analytics/pages/marketing-overview-page";
import { WorkshopDetailPage } from "@/features/workshops/pages/workshop-detail-page";
import { WorkshopsListPage } from "@/features/workshops/pages/workshops-list-page";
import { HackathonDetailPage } from "@/features/hackathons/pages/hackathon-detail-page";
import { HackathonsListPage } from "@/features/hackathons/pages/hackathons-list-page";
import { CompaniesListPage } from "@/features/placements/pages/companies-list-page";
import { PostingDetailPage } from "@/features/placements/pages/posting-detail-page";
import { PostingsListPage } from "@/features/placements/pages/postings-list-page";
import { InternshipsListPage } from "@/features/internships/pages/internships-list-page";
import { PostingDetailPage as InternshipPostingDetailPage } from "@/features/internships/pages/posting-detail-page";
import { PostingsListPage as InternshipPostingsListPage } from "@/features/internships/pages/postings-list-page";
import { ProfilesListPage as AlumniProfilesListPage } from "@/features/alumni/pages/profiles-list-page";
import { EventsListPage as AlumniEventsListPage } from "@/features/alumni/pages/events-list-page";
import { EventDetailPage as AlumniEventDetailPage } from "@/features/alumni/pages/event-detail-page";
import { ReferralsListPage as AlumniReferralsListPage } from "@/features/alumni/pages/referrals-list-page";
import { AlbumsListPage as MediaAlbumsListPage } from "@/features/media/pages/albums-list-page";
import { AlbumDetailPage as MediaAlbumDetailPage } from "@/features/media/pages/album-detail-page";
import { WorkflowsListPage } from "@/features/workflow/pages/workflows-list-page";
import { WorkflowDetailPage } from "@/features/workflow/pages/workflow-detail-page";
import { RequestsListPage } from "@/features/workflow/pages/requests-list-page";
import { MyApprovalsPage } from "@/features/workflow/pages/my-approvals-page";
import { BroadcastPage } from "@/features/notifications/pages/broadcast-page";
import { CommunicationLogPage } from "@/features/communication/pages/communication-log-page";
import { EventsListPage } from "@/features/events/pages/events-list-page";
import { BackupsPage } from "@/features/backups/pages/backups-page";
import { IntegrationsPage } from "@/features/integrations/pages/integrations-page";
import { MonitoringPage } from "@/features/monitoring/pages/monitoring-page";
import { OrganizationDetailPage } from "@/features/organizations/pages/organization-detail-page";
import { OrganizationsListPage } from "@/features/organizations/pages/organizations-list-page";
import { UserDetailPage } from "@/features/users/pages/user-detail-page";
import { UsersListPage } from "@/features/users/pages/users-list-page";
import { RoleDetailPage } from "@/features/authorization/pages/role-detail-page";
import { RolesListPage } from "@/features/authorization/pages/roles-list-page";
import { AuditLogListPage } from "@/features/audit/pages/audit-log-list-page";
import { BatchDetailPage } from "@/features/batches/pages/batch-detail-page";
import { BatchesListPage } from "@/features/batches/pages/batches-list-page";
import { ClassroomsListPage } from "@/features/classrooms/pages/classrooms-list-page";
import { TrainersListPage } from "@/features/trainers/pages/trainers-list-page";
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
