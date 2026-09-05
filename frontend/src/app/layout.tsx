import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Mycelium",
  description: "Community coordination network",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className="h-full antialiased"
    >
      <body className="min-h-full flex flex-col">
        {process.env.NEXT_PUBLIC_DEV_MOCK === "true" && (
          <aside className="border-b border-emerald-900 bg-emerald-950/50 px-6 py-3 text-center text-sm text-emerald-200">
            Sample community · Fictional people and example connections. Changes reset on refresh.
          </aside>
        )}
        {children}
      </body>
    </html>
  );
}
