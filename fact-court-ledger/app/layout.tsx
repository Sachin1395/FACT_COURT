import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Fact Court — cross-document fact analysis",
  description:
    "Upload documents, inspect extracted facts, and investigate how they corroborate, contradict, or reconcile across sources.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
