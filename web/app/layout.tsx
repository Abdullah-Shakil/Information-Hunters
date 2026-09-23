import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Information Hunters",
  description: "Find UK local-service businesses that may need a website or CRM.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en-GB">
      <body>{children}</body>
    </html>
  );
}
