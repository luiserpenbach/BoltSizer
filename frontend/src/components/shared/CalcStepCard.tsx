import { useState } from "react";
import { Icon } from "@blueprintjs/core";
import "katex/dist/katex.min.css";
// @ts-expect-error react-katex has no types
import { InlineMath } from "react-katex";
import type { CalcStep } from "../../types";

interface Props {
  step: CalcStep;
  index: number;
}

export function CalcStepCard({ step, index }: Props) {
  const [open, setOpen] = useState(false);

  return (
    <div className="calc-step-card">
      <div className="calc-step-header" onClick={() => setOpen(!open)}>
        <span>
          <span className="mono" style={{ color: "var(--accent)", marginRight: 8 }}>
            {String(index + 1).padStart(2, "0")}
          </span>
          {step.step}
        </span>
        <Icon icon={open ? "chevron-up" : "chevron-down"} size={12} color="var(--text-muted)" />
      </div>
      {open && (
        <div className="calc-step-body">
          {step.formula_latex && (
            <div className="calc-formula">
              <InlineMath math={step.formula_latex} />
            </div>
          )}
          {step.substitution && (
            <div className="calc-sub">→ {step.substitution}</div>
          )}
          {step.result && <div className="calc-result">{step.result}</div>}
          {step.explanation && (
            <div className="calc-explanation">{step.explanation}</div>
          )}
        </div>
      )}
    </div>
  );
}
