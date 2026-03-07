import { Tabs, Tab, Icon } from "@blueprintjs/core";
import { useAppStore } from "../../store/useAppStore";
import type { ReactNode } from "react";

const STEPS = [
  { id: 0, label: "Bolt Selection", icon: "wrench" as const },
  { id: 1, label: "Joint Geometry", icon: "social-media" as const },
  { id: 2, label: "Loading", icon: "lightning" as const },
  { id: 3, label: "Results", icon: "chart" as const },
  { id: 4, label: "Report", icon: "document" as const },
];

interface Props {
  children: ReactNode;
}

export function AppShell({ children }: Props) {
  const { currentStep, setCurrentStep, results } = useAppStore();

  const isStepEnabled = (id: number) => {
    if (id <= 2) return true;
    if (id === 3) return results !== null;
    if (id === 4) return results !== null;
    return false;
  };

  return (
    <div className="app-shell bp5-dark">
      {/* Top bar */}
      <div className="app-topbar">
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Icon icon="wrench" color="var(--accent)" size={16} />
          <span className="app-brand">
            Bolt<span className="brand-accent">Sizer</span>
          </span>
        </div>
        <span className="app-title" style={{ marginLeft: 8 }}>
          VDI 2230 Bolt Analysis
        </span>
        <div style={{ flex: 1 }} />
        <span
          style={{ fontSize: 11, color: "var(--text-muted)", fontFamily: "monospace" }}
        >
          ECSS-E-HB-32-23A
        </span>
      </div>

      {/* Step navigation */}
      <div className="step-nav">
        <Tabs
          id="step-tabs"
          selectedTabId={currentStep}
          onChange={(id) => {
            const n = id as number;
            if (isStepEnabled(n)) setCurrentStep(n);
          }}
          animate
          renderActiveTabPanelOnly={false}
        >
          {STEPS.map((s) => (
            <Tab
              key={s.id}
              id={s.id}
              disabled={!isStepEnabled(s.id)}
              title={
                <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <Icon icon={s.icon} size={12} />
                  {s.label}
                </span>
              }
            />
          ))}
        </Tabs>
      </div>

      {/* Page content */}
      <div className="main-content">{children}</div>
    </div>
  );
}
