import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });
const jetbrainsMono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-jetbrains" });

// Nearly every page here is session-aware (auth redirects, per-user data),
// so static prerendering buys nothing and the SessionProvider client tree
// doesn't prerender cleanly anyway — render everything per-request instead.
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Identity — Finance & Fitness",
  description: "Unified finance tracking, investment screening, and fitness planning.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${jetbrainsMono.variable}`}>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
