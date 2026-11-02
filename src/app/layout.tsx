import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: "سازنده ویدیو تفاوت‌یابی یوتیوب",
  description: "ساخت ویدیوی MP4 واقعی Spot the Difference برای یوتیوب",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="fa" dir="rtl">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;600;800&family=Fredoka:wght@600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="min-h-screen text-[#3a1f6b] antialiased">{children}</body>
    </html>
  );
}
