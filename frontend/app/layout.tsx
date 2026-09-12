import "./globals.css";
import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "RoomBridge",
  description: "Needs-preserving AI mediation — a research prototype",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header className="flex items-center gap-6 px-6 py-3 border-b border-[#e5e2d8] bg-white">
          <Link href="/" className="font-semibold tracking-tight text-[15px]">
            Room<span className="text-stated">Bridge</span>
          </Link>
          <nav className="flex gap-4 text-sm text-neutral-600">
            <Link href="/workbench" className="hover:text-ink">Workbench</Link>
            <Link href="/demo" className="hover:text-ink">Demo</Link>
          </nav>
          <span className="ml-auto text-[11px] text-neutral-400">
            research prototype · synthetic data · local
          </span>
        </header>
        <main>{children}</main>
      </body>
    </html>
  );
}
