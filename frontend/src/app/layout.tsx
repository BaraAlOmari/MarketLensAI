import type { Metadata, Viewport } from "next";
import { Inter, Noto_Sans_Arabic } from "next/font/google";
import { THEME_SCRIPT } from "@/lib/theme";

import "./globals.css";

// SF Pro may only be used on Apple platforms, so Apple devices get the real system font
// (see --font-sans) and everyone else gets Inter, the closest open design. Its optical-size
// axis gives SF's text/display split; Arabic glyphs come from Noto Sans Arabic.
const inter = Inter({
  subsets: ["latin"],
  axes: ["opsz"],
  display: "swap",
  variable: "--font-inter",
});

const arabic = Noto_Sans_Arabic({
  subsets: ["arabic"],
  display: "swap",
  preload: false, // only fetched when Arabic text is on screen (unicode-range)
  variable: "--font-arabic",
});

export const metadata: Metadata = {
  title: "MarketLens",
  description: "Search Qatar's marketplace in your own words, in English or Arabic.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover", // lay out to the edges; bars pad for the safe areas themselves
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f2f2f7" },
    { media: "(prefers-color-scheme: dark)", color: "#000000" },
  ],
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    // suppressHydrationWarning: THEME_SCRIPT may set data-theme before React hydrates.
    <html
      lang="en"
      className={`${inter.variable} ${arabic.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <body className="flex min-h-full flex-col">
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
        {children}
      </body>
    </html>
  );
}
