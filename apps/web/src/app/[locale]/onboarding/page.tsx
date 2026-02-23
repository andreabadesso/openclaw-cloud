"use client";

import { useRouter } from "@/i18n/navigation";
import { useEffect } from "react";

export default function OnboardingPage() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/setup");
  }, [router]);
  return null;
}
