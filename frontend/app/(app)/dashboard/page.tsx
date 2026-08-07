"use client";

import { useState } from "react";
import { Sidebar } from "@/components/dashboard/sidebar";
import { Header } from "@/components/dashboard/header";
import { OverviewSection } from "@/components/dashboard/sections/overview";
import { IngestionSection } from "@/components/dashboard/sections/ingestion";
import { NetworkSection } from "@/components/dashboard/sections/network";
import { AnomaliesSection } from "@/components/dashboard/sections/anomalies";
import { TimelineSection } from "@/components/dashboard/sections/timeline";
import { ReportsSection } from "@/components/dashboard/sections/reports";
import { SettingsSection } from "@/components/dashboard/sections/settings";
import { SearchSection } from "@/components/dashboard/sections/search";
import { CopilotSection } from "@/components/dashboard/sections/copilot";
import { InvestigationsSection } from "@/components/dashboard/sections/investigations";

export type Section = "overview" | "ingestion" | "network" | "anomalies" | "timeline" | "reports" | "settings" | "search" | "copilot" | "investigations";

export default function Dashboard() {
  const [activeSection, setActiveSection] = useState<Section>("overview");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  const renderSection = () => {
    switch (activeSection) {
      case "overview":
        return <OverviewSection />;
      case "ingestion":
        return <IngestionSection />;
      case "network":
        return <NetworkSection />;
      case "anomalies":
        return <AnomaliesSection />;
      case "timeline":
        return <TimelineSection />;
      case "reports":
        return <ReportsSection />;
      case "settings":
        return <SettingsSection />;
      case "search":
        return <SearchSection />;
      case "copilot":
        return <CopilotSection />;
      case "investigations":
        return <InvestigationsSection />;
      default:
        return <OverviewSection />;
    }
  };

  return (
    <div className="flex min-h-screen bg-background">
      <Sidebar
        activeSection={activeSection}
        onSectionChange={setActiveSection}
        collapsed={sidebarCollapsed}
        onCollapsedChange={setSidebarCollapsed}
      />
      <div
        className={`flex-1 flex flex-col transition-all duration-300 ease-out ${
          sidebarCollapsed ? "ml-[72px]" : "ml-[260px]"
        }`}
      >
        <Header activeSection={activeSection} />
        <main className="flex-1 p-6 overflow-auto">
          <div
            key={activeSection}
            className="animate-in fade-in slide-in-from-bottom-4 duration-500"
          >
            {renderSection()}
          </div>
        </main>
      </div>
    </div>
  );
}
