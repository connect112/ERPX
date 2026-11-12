import {
  Award,
  Bookmark,
  Briefcase,
  CalendarClock,
  ClipboardList,
  FlaskConical,
  GraduationCap,
  LayoutDashboard,
  Megaphone,
  MessageCircle,
  PartyPopper,
  Trophy,
} from "lucide-react";

export interface StudentNavItem {
  to: string;
  label: string;
  icon: typeof LayoutDashboard;
  end?: boolean;
  /**
   * Permission code required for this item to show. Omitted for items backed by ownership-gated ("me") endpoints, which any signed-in,
   * linked student can reach. Set for the Pentrix-backed items, which are permission-gated server-side.
   */
  permission?: string;
  /** shown only to a student who has been given access to an internship */
  needsInternship?: boolean;
}

export interface StudentNavGroup {
  id: string;
  title: string;
  icon: typeof LayoutDashboard;
  items: StudentNavItem[];
}

export const dashboardItem: StudentNavItem = { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true };
export const placementsItem: StudentNavItem = { to: "/placements", label: "Placements", icon: Briefcase };

export const studentGroups: StudentNavGroup[] = [
  {
    id: "learning",
    title: "Learning",
    icon: GraduationCap,
    items: [
      { to: "/courses", label: "My Courses", icon: GraduationCap },
      { to: "/my-internship", label: "My Internships", icon: ClipboardList, needsInternship: true },
      { to: "/schedule", label: "My Schedule", icon: CalendarClock },
      { to: "/bookmarks", label: "Bookmarks", icon: Bookmark },
      { to: "/transcript", label: "Transcript", icon: Award },
    ],
  },
  {
    id: "cyber-range",
    title: "Cyber Range",
    icon: FlaskConical,
    items: [
      { to: "/cyber-range", label: "Cyber Range", icon: FlaskConical, permission: "pentrix.labs.view" },
      { to: "/leaderboard", label: "Leaderboard", icon: Trophy, permission: "pentrix.leaderboard.view" },
      { to: "/achievements", label: "Achievements", icon: Award, permission: "pentrix.achievements.view" },
    ],
  },
  {
    id: "updates",
    title: "Updates",
    icon: Megaphone,
    items: [
      { to: "/announcements", label: "Announcements", icon: Megaphone },
      { to: "/messages", label: "Messages", icon: MessageCircle },
    ],
  },
];

// What a hackathon participant sees, and nothing else (the router sends them back here from any other page).
export const participantItems: StudentNavItem[] = [
  { to: "/hackathons", label: "Hackathons", icon: PartyPopper },
  { to: "/hackathon-leaderboard", label: "Leaderboard", icon: Trophy },
  { to: "/hackathon-achievements", label: "Achievements", icon: Award },
];

export interface StudentNavView {
  /** top-level links before the groups */
  top: StudentNavItem[];
  groups: StudentNavGroup[];
  /** top-level links after the groups */
  bottom: StudentNavItem[];
}

/** What this student may see: permission-gated items drop out, empty groups disappear, and a participant gets only the hackathon links. */
export function visibleStudentNav(opts: { permissions: readonly string[]; participantOnly: boolean; hasInternship: boolean }): StudentNavView {
  if (opts.participantOnly) return { top: participantItems, groups: [], bottom: [] };
  const allowed = (i: StudentNavItem) => (!i.permission || opts.permissions.includes(i.permission)) && (!i.needsInternship || opts.hasInternship);
  return {
    top: [dashboardItem],
    groups: studentGroups.map((g) => ({ ...g, items: g.items.filter(allowed) })).filter((g) => g.items.length > 0),
    bottom: [placementsItem],
  };
}

const matches = (pathname: string, item: StudentNavItem) => (item.end ? pathname === item.to : pathname === item.to || pathname.startsWith(`${item.to}/`));

/** The group that holds the current page, if any. */
export function activeGroupId(pathname: string): string | undefined {
  return studentGroups.find((g) => g.items.some((i) => matches(pathname, i)))?.id;
}

export const GROUPS_KEY = "erpx.student.nav.groups";
export function readOpenGroups(): string[] {
  try {
    const raw = JSON.parse(localStorage.getItem(GROUPS_KEY) ?? "[]") as unknown;
    return Array.isArray(raw) ? raw.filter((v): v is string => typeof v === "string") : [];
  } catch {
    return [];
  }
}
export function saveOpenGroups(ids: string[]) {
  try {
    localStorage.setItem(GROUPS_KEY, JSON.stringify(ids));
  } catch {
    /* a blocked store only means the choice is not remembered */
  }
}
