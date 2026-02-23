"use client";

import { useEffect } from "react";
import { useSearchParams } from "next/navigation";
import { useRouter } from "@/i18n/navigation";
import { api } from "@/lib/api";

const TOKEN_KEY = "openclaw_token";

export default function AuthCallbackPage() {
  const searchParams = useSearchParams();
  const router = useRouter();

  useEffect(() => {
    const token = searchParams.get("token");
    if (!token) {
      router.replace("/login");
      return;
    }

    localStorage.setItem(TOKEN_KEY, token);

    api
      .getMe()
      .then((user) => {
        router.replace(user.has_box ? "/dashboard" : "/setup");
      })
      .catch(() => {
        localStorage.removeItem(TOKEN_KEY);
        router.replace("/login");
      });
  }, [searchParams, router]);

  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="flex flex-col items-center gap-4">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-emerald-500 border-t-transparent" />
        <p className="text-sm text-white/50">Signing you in...</p>
      </div>
    </div>
  );
}
