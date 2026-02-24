import { useEffect } from "react";
import { useRouter } from "@/i18n/navigation";

export default function OnboardingPage() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/setup");
  }, [router]);
  return null;
}
