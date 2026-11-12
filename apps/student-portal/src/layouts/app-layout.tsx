import * as DialogPrimitive from "@radix-ui/react-dialog";
import { ChevronDown, ChevronRight, LogOut, Menu, Moon, Sun, X } from "lucide-react";
import { Suspense, useEffect, useState } from "react";
import { Navigate, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { useTheme } from "@/components/theme-provider";
import { PageLoader } from "@/components/ui/page-loader";
import { Button } from "@/components/ui/button";
import { useLogout } from "@/features/auth/api/auth-hooks";
import { useMyInternshipList } from "@/features/my-internship/api/my-internship-api";
import { useMessagingUnreadCount } from "@/features/messaging/api/messaging-hooks";
import { NotificationBell } from "@/features/notifications/components/notification-bell";
import { type StudentNavItem, activeGroupId, readOpenGroups, saveOpenGroups, visibleStudentNav } from "@/layouts/student-nav";
import { useAuthStore } from "@/store/auth-store";
import { PARTICIPANT_PATH_PREFIXES, useIsParticipantOnly } from "@/lib/participant-only";
import { cn } from "@/lib/utils";

function initials(name: string): string {
  return name
    .split(" ")
    .map((part) => part[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

const linkClass = (isActive: boolean) =>
  cn(
    "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
    isActive ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted hover:text-foreground"
  );

function SidebarBody({ onNavigate }: { onNavigate?: () => void }) {
  const permissions = useAuthStore((s) => s.permissions);
  const isParticipantOnly = useIsParticipantOnly();
  const { data: internships } = useMyInternshipList();
  const { data: unreadCount } = useMessagingUnreadCount();
  const { pathname } = useLocation();
  const view = visibleStudentNav({ permissions, participantOnly: isParticipantOnly, hasInternship: !!internships && internships.length > 0 });

  const [open, setOpen] = useState<string[]>(readOpenGroups);
  const toggle = (id: string) =>
    setOpen((cur) => {
      const next = cur.includes(id) ? cur.filter((g) => g !== id) : [...cur, id];
      saveOpenGroups(next);
      return next;
    });
  // the group holding the current page opens when you arrive on it; groups you opened yourself stay as they are
  useEffect(() => {
    const id = activeGroupId(pathname);
    if (id) {
      setOpen((cur) => {
        if (cur.includes(id)) return cur;
        const next = [...cur, id];
        saveOpenGroups(next);
        return next;
      });
    }
  }, [pathname]);

  const link = (item: StudentNavItem, nested = false) => (
    <NavLink key={item.to} to={item.to} end={item.end} onClick={onNavigate} className={({ isActive }) => cn(linkClass(isActive), nested && "py-1.5")}>
      <item.icon className="h-4 w-4" />
      {item.label}
      {item.to === "/messages" && !!unreadCount && (
        <Badge variant="destructive" className="ml-auto">
          {unreadCount}
        </Badge>
      )}
    </NavLink>
  );

  return (
    <>
      <div className="flex h-16 shrink-0 items-center border-b px-6">
        <span className="text-lg font-semibold">ERPX</span>
        <span className="ml-2 text-sm text-muted-foreground">Student</span>
      </div>
      <nav aria-label="Main navigation" className="flex-1 space-y-1 overflow-y-auto p-3">
        {view.top.map((item) => link(item))}
        {view.groups.map((g) => {
          const isOpen = open.includes(g.id);
          const holdsActive = activeGroupId(pathname) === g.id;
          return (
            <div key={g.id}>
              <button
                type="button"
                id={`student-nav-${g.id}-button`}
                aria-expanded={isOpen}
                aria-controls={`student-nav-${g.id}`}
                onClick={() => toggle(g.id)}
                className={cn(
                  "flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors hover:bg-muted hover:text-foreground",
                  holdsActive ? "text-foreground" : "text-muted-foreground"
                )}
              >
                <g.icon className="h-4 w-4" />
                <span className={cn("flex-1 text-left", holdsActive && "font-semibold")}>{g.title}</span>
                {isOpen ? <ChevronDown className="h-4 w-4" aria-hidden /> : <ChevronRight className="h-4 w-4" aria-hidden />}
              </button>
              {isOpen && (
                <div id={`student-nav-${g.id}`} role="group" aria-labelledby={`student-nav-${g.id}-button`} className="ml-5 mt-1 space-y-0.5 border-l pl-3">
                  {g.items.map((item) => link(item, true))}
                </div>
              )}
            </div>
          );
        })}
        {view.bottom.map((item) => link(item))}
      </nav>
    </>
  );
}

function AppSidebar() {
  return (
    <aside aria-label="Sidebar" className="hidden w-64 shrink-0 flex-col border-r bg-card md:flex">
      <SidebarBody />
    </aside>
  );
}

function MobileNav() {
  const [open, setOpen] = useState(false);
  return (
    <DialogPrimitive.Root open={open} onOpenChange={setOpen}>
      <DialogPrimitive.Trigger asChild>
        <button
          type="button"
          aria-label="Open navigation"
          className="mr-2 flex h-9 w-9 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground md:hidden"
        >
          <Menu className="h-5 w-5" aria-hidden />
        </button>
      </DialogPrimitive.Trigger>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/60 md:hidden" />
        <DialogPrimitive.Content
          aria-describedby={undefined}
          data-testid="mobile-drawer"
          className="fixed inset-y-0 left-0 z-50 flex w-72 max-w-[85vw] flex-col border-r bg-card shadow-2xl focus:outline-none md:hidden"
        >
          <DialogPrimitive.Title className="sr-only">Navigation</DialogPrimitive.Title>
          <DialogPrimitive.Close className="absolute right-3 top-4 flex h-9 w-9 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground" aria-label="Close navigation">
            <X className="h-5 w-5" aria-hidden />
          </DialogPrimitive.Close>
          <SidebarBody onNavigate={() => setOpen(false)} />
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}

function AppTopbar() {
  const { theme, setTheme } = useTheme();
  const user = useAuthStore((s) => s.user);
  const navigate = useNavigate();
  const logout = useLogout();

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  return (
    <header className="flex h-16 items-center justify-between border-b bg-card px-4 sm:px-6">
      <div className="flex items-center">
        <MobileNav />
      </div>
      <div className="flex items-center gap-2">
        <NotificationBell />
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          aria-label="Toggle theme"
        >
          {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </Button>

        <span className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground">
          {user ? initials(user.fullName) : "?"}
        </span>
        <span className="hidden text-sm font-medium sm:inline">{user?.fullName ?? "Account"}</span>

        <Button variant="ghost" size="icon" onClick={handleLogout} aria-label="Sign out">
          <LogOut className="h-4 w-4" />
        </Button>
      </div>
    </header>
  );
}

export function AppLayout() {
  const isParticipantOnly = useIsParticipantOnly();
  const { pathname } = useLocation();
  // A participant has no business on course, schedule or cyber-range pages
  // (they would only be empty); send them to the hackathon.
  if (isParticipantOnly && !PARTICIPANT_PATH_PREFIXES.some((prefix) => pathname.startsWith(prefix))) {
    return <Navigate to="/hackathons" replace />;
  }
  return (
    <div className="flex h-screen overflow-hidden">
      <AppSidebar />
      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <AppTopbar />
        <main className="flex-1 overflow-y-auto bg-muted/20">
          {/* Single Suspense boundary for every lazily-loaded route rendered
              into this Outlet (see src/router/index.tsx). */}
          <Suspense fallback={<PageLoader />}>
            <Outlet />
          </Suspense>
        </main>
      </div>
    </div>
  );
}
