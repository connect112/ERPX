import { createBrowserRouter } from "react-router-dom";

import { AppLayout } from "@/layouts/app-layout";
import { LoginPage } from "@/features/auth/pages/login-page";
import { DashboardPage } from "@/features/dashboard/pages/dashboard-page";
import { MyCoursesPage } from "@/features/courses/pages/my-courses-page";
import { CourseDetailPage } from "@/features/courses/pages/course-detail-page";
import { MyBookmarksPage } from "@/features/bookmarks/pages/my-bookmarks-page";
import { MyTranscriptPage } from "@/features/transcripts/pages/my-transcript-page";
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
      { path: "courses", element: <MyCoursesPage /> },
      { path: "courses/:courseId", element: <CourseDetailPage /> },
      { path: "bookmarks", element: <MyBookmarksPage /> },
      { path: "transcript", element: <MyTranscriptPage /> },
    ],
  },
]);
