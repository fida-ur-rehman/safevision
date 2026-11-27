import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";
import Topbar from "@/components/Topbar";

// Fonts are stored in the project (SIL Open Font License) so the app also works offline.
// Public Sans for text; Barlow Semi Condensed, a typeface modelled on road and site signage, for headings and figures.
const sans = localFont({ src: "./fonts/PublicSans-Variable.woff2", variable: "--font-sans", weight: "100 900", display: "swap" });
const sign = localFont({
  src: [
    { path: "./fonts/BarlowSemiCondensed-600.woff2", weight: "600" },
    { path: "./fonts/BarlowSemiCondensed-700.woff2", weight: "700" },
  ],
  variable: "--font-sign", display: "swap",
});

export const metadata: Metadata = {
  title: "SafeVision: PPE compliance and incident analysis",
  description: "Checks construction photos for missing PPE per worker, explains the result and writes a rule-grounded, fact-checked report.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${sans.variable} ${sign.variable}`}>
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
