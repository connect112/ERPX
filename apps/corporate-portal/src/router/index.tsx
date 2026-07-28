import { createBrowserRouter } from "react-router-dom";

import { AppLayout } from "@/layouts/app-layout";
import { LoginPage } from "@/features/auth/pages/login-page";
import { DashboardPage } from "@/features/dashboard/pages/dashboard-page";
import { MyTicketsPage } from "@/features/tickets/pages/my-tickets-page";
import { TicketDetailPage } from "@/features/tickets/pages/ticket-detail-page";
import { MyProjectsPage } from "@/features/projects/pages/my-projects-page";
import { MyContractsPage } from "@/features/contracts/pages/my-contracts-page";
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
