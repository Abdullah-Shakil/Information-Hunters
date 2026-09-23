import type { Metadata } from "next";
import { Fraunces, IBM_Plex_Mono, Outfit } from "next/font/google";
import "./globals.css";

const serif = Fraunces({ subsets: ["latin"], variable: "--font-serif", weight: ["500", "600"] });
const sans = Outfit({ subsets: ["latin"], variable: "--font-sans", weight: ["400", "500", "600"] });
const mono = IBM_Plex_Mono({ subsets: ["latin"], variable: "--font-mono", weight: ["400", "500"] });

export const metadata: Metadata = {
  title: "Information Hunters",
  description: "Find UK local-service businesses that may need a website or CRM.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en-GB">
      <body className={`${serif.variable} ${sans.variable} ${mono.variable}`}>{children}</body>
    </html>
  );
}
