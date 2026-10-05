import type { Metadata } from "next";
import { Hanken_Grotesk, Schibsted_Grotesk } from "next/font/google";
import "./globals.css";

const schibsted = Schibsted_Grotesk({ subsets: ["latin"], weight: ["400", "600", "800"], variable: "--font-schibsted" });
const hanken = Hanken_Grotesk({ subsets: ["latin"], weight: ["400", "600", "700"], variable: "--font-hanken" });

export const metadata: Metadata = { title: "LATAM Bank · demo", description: "Synthetic data · labeled test identities" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es" className={`${schibsted.variable} ${hanken.variable}`}>
      <body>{children}</body>
    </html>
  );
}
