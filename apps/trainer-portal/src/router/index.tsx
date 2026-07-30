import { lazy } from "react";
import { createBrowserRouter } from "react-router-dom";

import { AppLayout } from "@/layouts/app-layout";
import { LoginPage } from "@/features/auth/pages/login-page";
const DashboardPage = lazy(() => import("@/features/dashboard/pages/dashboard-page").then((m) => ({ default: m.DashboardPage })));
const MyBatchesPage = lazy(() => import("@/features/batches/pages/my-batches-page").then((m) => ({ default: m.MyBatchesPage })));
const BatchDetailPage = lazy(() => import("@/features/batches/pages/batch-detail-page").then((m) => ({ default: m.BatchDetailPage })));
const AssignmentGradingPage = lazy(() => import("@/features/batches/pages/assignment-grading-page").then((m) => ({ default: m.AssignmentGradingPage })));
const AttendancePage = lazy(() => import("@/features/attendance/pages/attendance-page").then((m) => ({ default: m.AttendancePage })));
import { ProtectedRoute } from "@/router/protected-route";

export const router = createBrowserRouter([
  {
    path: "/login",
    element: <LoginPage />,
  },
  {
    path: "/",
    element: (
      <ProtectedRoute>
        <AppLayout />
      </ProtectedRoute>
    ),
    children: [
      { index: true, element: <DashboardPage /> },
      { path: "batches", element: <MyBatchesPage /> },
      { path: "batches/:batchId", element: <BatchDetailPage /> },
      { path: "batches/:batchId/assignments/:assignmentId", element: <AssignmentGradingPage /> },
      { path: "attendance", element: <AttendancePage /> },
    ],
  },
]);
