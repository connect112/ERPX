import { lazy } from "react";
import { createBrowserRouter } from "react-router-dom";

import { AppLayout } from "@/layouts/app-layout";
import { LoginPage } from "@/features/auth/pages/login-page";
const DashboardPage = lazy(() => import("@/features/dashboard/pages/dashboard-page").then((m) => ({ default: m.DashboardPage })));
const MyTicketsPage = lazy(() => import("@/features/tickets/pages/my-tickets-page").then((m) => ({ default: m.MyTicketsPage })));
const TicketDetailPage = lazy(() => import("@/features/tickets/pages/ticket-detail-page").then((m) => ({ default: m.TicketDetailPage })));
const MyProjectsPage = lazy(() => import("@/features/projects/pages/my-projects-page").then((m) => ({ default: m.MyProjectsPage })));
const MyContractsPage = lazy(() => import("@/features/contracts/pages/my-contracts-page").then((m) => ({ default: m.MyContractsPage })));
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
      { path: "tickets", element: <MyTicketsPage /> },
      { path: "tickets/:ticketId", element: <TicketDetailPage /> },
      { path: "projects", element: <MyProjectsPage /> },
      { path: "contracts", element: <MyContractsPage /> },
    ],
  },
]);
