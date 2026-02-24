import { Outlet, useParams, Navigate } from "react-router-dom";
import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import { Header } from "@/components/header";
import { AuthProvider } from "@/lib/auth";

const LOCALES = ["pt", "en"];

export function LocaleLayout() {
  const { locale } = useParams<{ locale: string }>();
  const { i18n } = useTranslation();

  useEffect(() => {
    if (locale && LOCALES.includes(locale) && i18n.language !== locale) {
      i18n.changeLanguage(locale);
    }
  }, [locale, i18n]);

  if (!locale || !LOCALES.includes(locale)) {
    return <Navigate to="/pt" replace />;
  }

  return (
    <AuthProvider>
      <Header />
      <main>
        <Outlet />
      </main>
    </AuthProvider>
  );
}
