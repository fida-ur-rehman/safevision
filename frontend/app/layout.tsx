import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";
import Topbar from "@/components/Topbar";

// Public Sans (SIL Open Font License) is stored in the project so the app also works offline.
const sans = localFont({ src: "./fonts/PublicSans-Variable.woff2", variable: "--font-sans", weight: "100 900", display: "swap" });

export const metadata: Metadata = {
  title: "SafeVision: PPE compliance and incident analysis",
  description: "Checks construction photos for missing PPE per worker, explains the result and writes a rule-grounded, fact-checked report.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={sans.variable}>
      <body>
        <Topbar />
        <main className="main">{children}</main>
        <footer className="foot no-print">
          SafeVision supports a safety officer and does not replace one. Every finding should be confirmed on site.
        </footer>
      </body>
    </html>
  );
}
