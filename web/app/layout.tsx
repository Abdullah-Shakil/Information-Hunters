import type { Metadata } from "next";
import { IBM_Plex_Mono, IBM_Plex_Sans, Space_Grotesk } from "next/font/google";
import "./globals.css";

const display = Space_Grotesk({ subsets: ["latin"], variable: "--font-display", weight: ["500", "600", "700"] });
const sans = IBM_Plex_Sans({ subsets: ["latin"], variable: "--font-body", weight: ["400", "500", "600", "700"] });
const mono = IBM_Plex_Mono({ subsets: ["latin"], variable: "--font-mono", weight: ["400", "500"] });

export const metadata: Metadata = {
  title: "Information Hunters",
  description: "Find UK local-service businesses that may need a website or CRM.",
};

const themeBoot = `(function(){try{var k='ih-theme';var t=localStorage.getItem(k);if(t==='light')t='day';if(t==='dark')t='night';if(t!=='day'&&t!=='night'){t=window.matchMedia('(prefers-color-scheme: dark)').matches?'night':'day'}document.documentElement.setAttribute('data-theme',t);document.documentElement.style.colorScheme=t==='night'?'dark':'light'}catch(e){}})();`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en-GB" data-theme="day" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeBoot }} />
      </head>
      <body className={`${display.variable} ${sans.variable} ${mono.variable}`}>{children}</body>
    </html>
  );
}
