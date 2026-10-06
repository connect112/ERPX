import { lazy } from "react";
import { createBrowserRouter } from "react-router-dom";

import { AppLayout } from "@/layouts/app-layout";
import { LoginPage } from "@/features/auth/pages/login-page";
import { ResetPasswordPage } from "@/features/auth/pages/reset-password-page";
const DashboardPage = lazy(() => import("@/features/dashboard/pages/dashboard-page").then((m) => ({ default: m.DashboardPage })));
const MyCoursesPage = lazy(() => import("@/features/courses/pages/my-courses-page").then((m) => ({ default: m.MyCoursesPage })));
const CourseDetailPage = lazy(() => import("@/features/courses/pages/course-detail-page").then((m) => ({ default: m.CourseDetailPage })));
const MyBookmarksPage = lazy(() => import("@/features/bookmarks/pages/my-bookmarks-page").then((m) => ({ default: m.MyBookmarksPage })));
const MyTranscriptPage = lazy(() => import("@/features/transcripts/pages/my-transcript-page").then((m) => ({ default: m.MyTranscriptPage })));
const CyberRangePage = lazy(() => import("@/features/pentrix/pages/cyber-range-page").then((m) => ({ default: m.CyberRangePage })));
const LeaderboardPage = lazy(() => import("@/features/leaderboard/pages/leaderboard-page").then((m) => ({ default: m.LeaderboardPage })));
const AchievementsPage = lazy(() => import("@/features/achievements/pages/achievements-page").then((m) => ({ default: m.AchievementsPage })));
const MySchedulePage = lazy(() => import("@/features/schedule/pages/my-schedule-page").then((m) => ({ default: m.MySchedulePage })));
const PlacementsPage = lazy(() => import("@/features/placements/pages/placements-page").then((m) => ({ default: m.PlacementsPage })));
const AnnouncementsPage = lazy(() => import("@/features/announcements/pages/announcements-page").then((m) => ({ default: m.AnnouncementsPage })));
const MessagingPage = lazy(() => import("@/features/messaging/pages/messaging-page").then((m) => ({ default: m.MessagingPage })));
const HackathonsPage = lazy(() => import("@/features/hackathons/pages/hackathons-page").then((m) => ({ default: m.HackathonsPage })));
const HackathonLeaderboardPage = lazy(() => import("@/features/hackathons/pages/hackathon-leaderboard-page").then((m) => ({ default: m.HackathonLeaderboardPage })));
const HackathonAchievementsPage = lazy(() => import("@/features/hackathons/pages/hackathon-achievements-page").then((m) => ({ default: m.HackathonAchievementsPage })));
const HackathonDetailPage = lazy(() => import("@/features/hackathons/pages/hackathon-detail-page").then((m) => ({ default: m.HackathonDetailPage })));
// Workshops/Internships routes remain intentionally removed — see the
// comment in layouts/app-layout.tsx. Hackathons are enabled for events that
// onboard their participants as students.
import { ProtectedRoute } from "@/router/protected-route";

export const router = createBrowserRouter([
  {
    path: "/login",
    element: <LoginPage />,
  },
  {
    path: "/reset-password",
    element: <ResetPasswordPage />,
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
      { path: "schedule", element: <MySchedulePage /> },
      { path: "placements", element: <PlacementsPage /> },
      { path: "announcements", element: <AnnouncementsPage /> },
      { path: "messages", element: <MessagingPage /> },
      { path: "hackathons", element: <HackathonsPage /> },
      { path: "hackathons/:hackathonId", element: <HackathonDetailPage /> },
      { path: "hackathon-leaderboard", element: <HackathonLeaderboardPage /> },
      { path: "hackathon-achievements", element: <HackathonAchievementsPage /> },
      {
        path: "cyber-range",
        element: (
          <ProtectedRoute permission="pentrix.labs.view">
            <CyberRangePage />
          </ProtectedRoute>
        ),
      },
      {
        path: "leaderboard",
        element: (
          <ProtectedRoute permission="pentrix.leaderboard.view">
            <LeaderboardPage />
          </ProtectedRoute>
        ),
      },
      {
        path: "achievements",
        element: (
          <ProtectedRoute permission="pentrix.achievements.view">
            <AchievementsPage />
          </ProtectedRoute>
        ),
      },
    ],
  },
]);
