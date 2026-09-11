import { LayoutDashboard, LogOut, Moon, Sun, Wallet } from "lucide-react";
import { Suspense } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";

import { useTheme } from "@/components/theme-provider";
import { PageLoader } from "@/components/ui/page-loader";
import { Button } from "@/components/ui/button";
import { useLogout } from "@/features/auth/api/auth-hooks";
import { useAuthStore } from "@/store/auth-store";
import { cn } from "@/lib/utils";

interface NavItem {
  to: string;
  label: string;
  icon: typeof LayoutDashboard;
  end: boolean;
}

// Both self-service endpoints (/employees/me, /payroll/payslips/me) are
// ownership-gated, not permission-gated — see modules/employees/
// dependencies.py's docstring — so there's no permission-filtering here
// the way student-portal's equivalent list has for its Pentrix items.
const navItems: NavItem[] = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/payslips", label: "My Payslips", icon: Wallet, end: false },
];

function initials(name: string): string {
  return name
    .split(" ")
    .map((part) => part[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

function AppSidebar() {
  return (
    <aside className="flex w-64 flex-col border-r bg-card">
      <div className="flex h-16 items-center border-b px-6">
        <span className="text-lg font-semibold">ERPX</span>
        <span className="ml-2 text-sm text-muted-foreground">Employee</span>
      </div>
      <nav className="flex-1 space-y-1 overflow-y-auto p-3">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground"
              )
            }
          >
            <item.icon className="h-4 w-4" />
            {item.label}
          </NavLink>
        ))}
      </nav>
    </aside>
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
    <header className="flex h-16 items-center justify-between border-b bg-card px-6">
      <div />
      <div className="flex items-center gap-2">
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
  return (
    <div className="flex h-screen overflow-hidden">
      <AppSidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
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
