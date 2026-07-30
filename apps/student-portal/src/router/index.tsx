import { lazy } from "react";
import { createBrowserRouter } from "react-router-dom";

import { AppLayout } from "@/layouts/app-layout";
import { LoginPage } from "@/features/auth/pages/login-page";
const DashboardPage = lazy(() => import("@/features/dashboard/pages/dashboard-page").then((m) => ({ default: m.DashboardPage })));
const MyCoursesPage = lazy(() => import("@/features/courses/pages/my-courses-page").then((m) => ({ default: m.MyCoursesPage })));
const CourseDetailPage = lazy(() => import("@/features/courses/pages/course-detail-page").then((m) => ({ default: m.CourseDetailPage })));
const MyBookmarksPage = lazy(() => import("@/features/bookmarks/pages/my-bookmarks-page").then((m) => ({ default: m.MyBookmarksPage })));
const MyTranscriptPage = lazy(() => import("@/features/transcripts/pages/my-transcript-page").then((m) => ({ default: m.MyTranscriptPage })));
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
