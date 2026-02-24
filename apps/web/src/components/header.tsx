import { useTranslation } from "react-i18next";
import { useParams } from "react-router-dom";
import { Link, usePathname, useRouter } from "@/i18n/navigation";
import { useAuth } from "@/lib/auth";

export function Header() {
  const { t } = useTranslation();
  const { locale } = useParams<{ locale: string }>();
  const pathname = usePathname();
  const router = useRouter();
  const { user, isAuthenticated } = useAuth();

  const currentLocale = locale ?? "pt";
  const otherLocale = currentLocale === "pt" ? "en" : "pt";

  function handleLocaleSwitch() {
    router.replace(pathname, { locale: otherLocale });
  }

  return (
    <header className="fixed top-0 left-0 right-0 z-50 border-b border-white/[0.06] bg-[#0a0a0a]/80 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
        <Link href="/" className="flex items-center gap-0.5">
          <span className="text-[15px] font-semibold tracking-tight text-white/90">
            OpenClaw
          </span>
          <span className="text-[15px] font-semibold tracking-tight text-gradient">
            Cloud
          </span>
        </Link>

        <nav className="flex items-center gap-1">
          {isAuthenticated ? (
            <>
              <Link
                href="/dashboard"
                className="rounded-lg px-3 py-1.5 text-[13px] text-white/50 transition-colors hover:text-white/80"
              >
                {t("header.dashboard")}
              </Link>

              <button
                onClick={handleLocaleSwitch}
                className="ml-2 rounded-md border border-white/[0.08] bg-white/[0.03] px-2.5 py-1 text-[11px] font-medium tracking-wider text-white/40 transition-all hover:border-white/[0.15] hover:text-white/70"
              >
                {otherLocale.toUpperCase()}
              </button>

              {/* Avatar */}
              <div className="ml-2 flex h-8 w-8 items-center justify-center overflow-hidden rounded-full border border-white/[0.08] bg-white/[0.06]">
                {user?.avatar_url ? (
                  <img
                    src={user.avatar_url}
                    alt=""
                    className="h-full w-full object-cover"
                  />
                ) : (
                  <span className="text-[12px] font-medium text-white/60">
                    {(user?.name ?? user?.email ?? "?").charAt(0).toUpperCase()}
                  </span>
                )}
              </div>

              <Link
                href="/dashboard"
                className="btn-cta ml-2 inline-flex items-center rounded-lg bg-emerald-500 px-4 py-1.5 text-[13px] font-medium text-black transition-all hover:bg-emerald-400"
              >
                {t("header.dashboard")}
              </Link>
            </>
          ) : (
            <>
              <Link
                href="/#pricing"
                className="rounded-lg px-3 py-1.5 text-[13px] text-white/50 transition-colors hover:text-white/80"
              >
                {t("header.pricing")}
              </Link>

              <button
                onClick={handleLocaleSwitch}
                className="ml-2 rounded-md border border-white/[0.08] bg-white/[0.03] px-2.5 py-1 text-[11px] font-medium tracking-wider text-white/40 transition-all hover:border-white/[0.15] hover:text-white/70"
              >
                {otherLocale.toUpperCase()}
              </button>

              <Link
                href="/login"
                className="ml-2 rounded-lg px-3 py-1.5 text-[13px] text-white/50 transition-colors hover:text-white/80"
              >
                {t("header.login")}
              </Link>

              <Link
                href="/login"
                className="btn-cta ml-2 inline-flex items-center rounded-lg bg-emerald-500 px-4 py-1.5 text-[13px] font-medium text-black transition-all hover:bg-emerald-400"
              >
                {t("header.getStarted")}
              </Link>
            </>
          )}
        </nav>
      </div>
    </header>
  );
}
