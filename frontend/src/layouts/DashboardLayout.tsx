import type { ReactNode } from "react";
import Header from "../components/Header";

interface DashboardLayoutProps {
  children: ReactNode;
}

/**
 * Application shell: persistent top header with the global lottery
 * selector and a scrollable main content area. The Sidebar group
 * (U2) will slot into this layout's left region.
 */
export default function DashboardLayout({ children }: DashboardLayoutProps) {
  return (
    <div className="flex h-screen flex-col bg-gray-50">
      <Header />
      <main className="flex-1 overflow-y-auto">{children}</main>
    </div>
  );
}