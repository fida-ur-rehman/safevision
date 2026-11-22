import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";
import Sidebar from "@/components/Sidebar";

// Public Sans (SIL Open Font License), stored in the project so the app also works offline
const sans = localFont({ src: "./fonts/PublicSans-Variable.woff2", variable: "--font-sans", weight: "100 900", display: "swap" });

export const metadata: Metadata = {
  title: "SafeVision · PPE compliance and incident analysis",
  description: "Checks construction photos for missing PPE per worker, explains the result and writes a rule-grounded, fact-checked report.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={sans.variable}>
      <body>
        <div className="shell">
          <Sidebar />
          <main className="main">{children}</main>
        </div>
      </body>
    </html>
  );
}
