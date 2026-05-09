import type { Metadata } from "next";
import { Geist } from "next/font/google";
import "./globals.css";
import Link from "next/link";

const geist = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "CRM Job Agent",
  description: "Znajdź polskie firmy AI",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pl" className={`${geist.variable} h-full`}>
      <body className="min-h-full bg-gray-50 text-gray-900 font-sans">
        <nav className="bg-white border-b border-gray-200 px-6 py-3 flex gap-6">
          <Link href="/" className="font-semibold text-blue-600 hover:text-blue-800">
            Odkrywanie
          </Link>
          <Link href="/crm" className="text-gray-600 hover:text-gray-900">
            CRM
          </Link>
        </nav>
        <main className="p-6">{children}</main>
      </body>
    </html>
  );
}
