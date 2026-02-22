import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
});

export const metadata: Metadata = {
  title: "OpenClaw Cloud",
  description:
    "Agentes de IA especializados para o seu nicho. Via Telegram, em segundos.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html className="dark" suppressHydrationWarning>
      <body className={`${inter.variable} font-sans noise`}>{children}</body>
    </html>
  );
}
