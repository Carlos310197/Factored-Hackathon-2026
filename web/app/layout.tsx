import type { Metadata } from "next";
import { Hanken_Grotesk, Schibsted_Grotesk } from "next/font/google";
import "./globals.css";
import { customerFromCookies, staffFromCookies } from "@/lib/server/session";

const schibsted = Schibsted_Grotesk({ subsets: ["latin"], weight: ["400", "600", "800"], variable: "--font-schibsted" });
const hanken = Hanken_Grotesk({ subsets: ["latin"], weight: ["400", "600", "700"], variable: "--font-hanken" });

export const metadata: Metadata = { title: "LATAM Bank · demo", description: "Synthetic data · labeled test identities" };

/** Customer pages speak the customer's language; staff pages are English. */
async function pageLang(): Promise<string> {
  const c = await customerFromCookies();
  if (c) return c.lang;
  return (await staffFromCookies()) ? "en" : "es";
}

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang={await pageLang()} className={`${schibsted.variable} ${hanken.variable}`}>
      <body>{children}</body>
    </html>
  );
}
