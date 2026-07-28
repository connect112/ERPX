import { createBrowserRouter } from "react-router-dom";

import { AppLayout } from "@/layouts/app-layout";
import { LoginPage } from "@/features/auth/pages/login-page";
import { DashboardPage } from "@/features/dashboard/pages/dashboard-page";
import { MyBatchesPage } from "@/features/batches/pages/my-batches-page";
import { BatchDetailPage } from "@/features/batches/pages/batch-detail-page";
import { AssignmentGradingPage } from "@/features/batches/pages/assignment-grading-page";
import { AttendancePage } from "@/features/attendance/pages/attendance-page";
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
