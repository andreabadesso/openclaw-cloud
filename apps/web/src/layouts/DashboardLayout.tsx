import { useEffect } from "react";
import { Outlet } from "react-router-dom";
import {
  LayoutDashboard,
  Plug,
  BarChart3,
  Settings,
  LogOut,
} from "lucide-react";
import { useAuth } from "@/lib/auth";
import { Link, usePathname, useRouter } from "@/i18n/navigation";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Overview", icon: LayoutDashboard },
  { href: "/dashboard/connections", label: "Connections", icon: Plug },
  { href: "/dashboard/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/dashboard/settings", label: "Settings", icon: Settings },
] as const;

export function DashboardLayout() {
  const { user, isLoading, isAuthenticated, logout } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace("/login");
    }
  }, [isLoading, isAuthenticated, router]);

  useEffect(() => {
    if (!isLoading && isAuthenticated && user && !user.has_box) {
      router.replace("/setup");
    }
  }, [isLoading, isAuthenticated, user, router]);

  if (isLoading) {
    return (
      <div className="dashboard-layout fixed inset-0 z-40 bg-[#0a0a0a]">
        <div className="flex h-screen">
          {/* Sidebar skeleton */}
          <aside className="flex w-56 flex-col border-r border-white/[0.06] bg-[#0a0a0a] p-4">
            <div className="skeleton h-6 w-32" />
            <div className="mt-8 space-y-2">
              {[...Array(4)].map((_, i) => (
                <div key={i} className="skeleton h-9 w-full" />
              ))}
            </div>
          </aside>
          {/* Content skeleton */}
          <main className="flex-1 p-8">
            <div className="skeleton mb-6 h-8 w-48" />
            <div className="grid grid-cols-2 gap-6">
              {[...Array(4)].map((_, i) => (
                <div key={i} className="skeleton h-40 w-full" />
              ))}
            </div>
          </main>
        </div>
      </div>
    );
  }

  if (!isAuthenticated || !user) return null;

  const initials = user.name
    ? user.name.charAt(0).toUpperCase()
    : user.email.charAt(0).toUpperCase();

  return (
    <div className="dashboard-layout fixed inset-0 z-40 bg-[#0a0a0a]">
      <div className="flex h-screen">
        {/* Sidebar */}
        <aside className="flex w-56 flex-shrink-0 flex-col border-r border-white/[0.06] bg-[#0a0a0a]">
          {/* Logo */}
          <div className="flex h-16 items-center px-5">
            <Link href="/" className="flex items-center gap-0.5">
              <span className="text-[15px] font-semibold tracking-tight text-white/90">
                OpenClaw
              </span>
              <span className="text-[15px] font-semibold tracking-tight text-gradient">
                Cloud
              </span>
            </Link>
          </div>

          {/* Navigation */}
          <nav className="flex-1 px-3 py-2">
            <ul className="space-y-1">
              {NAV_ITEMS.map((item) => {
                const isActive =
                  item.href === "/dashboard"
                    ? pathname === "/dashboard"
                    : pathname.startsWith(item.href);
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      className={`nav-item ${isActive ? "active" : ""}`}
                    >
                      <item.icon className="h-4 w-4 flex-shrink-0" />
                      {item.label}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </nav>

          {/* User section */}
          <div className="border-t border-white/[0.06] p-4">
            <div className="flex items-center gap-3">
              {user.avatar_url ? (
                <img
                  src={user.avatar_url}
                  alt=""
                  className="h-8 w-8 rounded-full"
                />
              ) : (
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-emerald-500/20 text-xs font-medium text-emerald-400">
                  {initials}
                </div>
              )}
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-white/80">
                  {user.name ?? "User"}
                </p>
                <p className="truncate text-xs text-white/40">{user.email}</p>
              </div>
              <button
                onClick={logout}
                className="rounded-md p-1.5 text-white/30 transition-colors hover:bg-white/[0.06] hover:text-white/60"
                title="Logout"
              >
                <LogOut className="h-4 w-4" />
              </button>
            </div>
          </div>
        </aside>

        {/* Main content */}
        <main className="flex-1 overflow-y-auto">
          <div className="mx-auto max-w-5xl p-8">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
