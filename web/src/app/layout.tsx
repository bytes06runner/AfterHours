import type { Metadata } from "next";
import { Bodoni_Moda, Hanken_Grotesk } from "next/font/google";
import "./globals.css";

const display = Bodoni_Moda({ variable: "--font-display", subsets: ["latin"], display: "swap" });
const text = Hanken_Grotesk({ variable: "--font-text", subsets: ["latin"], display: "swap" });

export const metadata: Metadata = {
  title: "Afterhours",
  description: "A lending vault for Stock Tokens that pulls back before the market closes.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${display.variable} ${text.variable}`}>
      <body>{children}</body>
    </html>
  );
}
