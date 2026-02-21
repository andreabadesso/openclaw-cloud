"use client";

import Link from "next/link";

export default function OnboardingPage() {
  return (
    <section className="flex flex-col items-center px-4 py-24 text-center">
      <div className="mx-auto max-w-lg rounded-lg border border-border bg-card p-8">
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-emerald-600/10 text-3xl">
          🚧
        </div>
        <h1 className="mt-6 text-2xl font-bold">Onboarding Coming Soon</h1>
        <p className="mt-4 text-muted-foreground">
          The conversational onboarding agent is being built. In the meantime,
          you can provision an agent manually through the admin panel.
        </p>
        <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:justify-center">
          <Link
            href="/admin"
            className="inline-flex items-center justify-center rounded-md bg-emerald-600 px-6 py-2.5 text-sm font-medium text-white hover:bg-emerald-700"
          >
            Go to Admin Panel
          </Link>
          <Link
            href="/"
            className="inline-flex items-center justify-center rounded-md bg-secondary px-6 py-2.5 text-sm font-medium text-secondary-foreground hover:bg-secondary/80"
          >
            Back to Home
          </Link>
        </div>
      </div>
    </section>
  );
}
