import { useState } from "react";
import { Button, Dialog, DialogBody, Callout, Spinner, Tag } from "@blueprintjs/core";
import { useAppStore } from "../store/useAppStore";
import { buildAnalyzeReq, fetchSuggestBolts } from "../api/client";
import type { BoltCandidate } from "../api/client";

/** Bolt auto-suggest: evaluates every library bolt of the same thread
 * standard against the current joint + loads, and applies the pick. */
export function SuggestBoltsDialog({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  const { boltConfig, jointConfig, loadCases, standard, fos, setBoltConfig } = useAppStore();
  const [candidates, setCandidates] = useState<BoltCandidate[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const compute = async () => {
    setLoading(true);
    setError(null);
    try {
      const req = buildAnalyzeReq(boltConfig, jointConfig, loadCases, standard, fos);
      setCandidates(await fetchSuggestBolts(req));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Suggestion sweep failed");
    } finally {
      setLoading(false);
    }
  };

  const apply = (c: BoltCandidate) => {
    setBoltConfig({
      designation: c.designation,
      assembly_torque_Nmm: c.recommended
        ? Math.round(c.recommended.torque / 100) * 100
        : boltConfig.assembly_torque_Nmm,
      use_target_preload: false,
    });
    onClose();
  };

  return (
    <Dialog
      isOpen={isOpen}
      onClose={onClose}
      title="Suggest bolt size"
      className="bp5-dark"
      style={{ width: 640 }}
      onOpening={() => { if (!candidates) compute(); }}
    >
      <DialogBody>
        <p style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 0 }}>
          Every {boltConfig.designation.startsWith("M") ? "ISO metric" : "Unified"} size is
          evaluated against the current joint, loads, grade ({boltConfig.grade}) and
          coating. A size passes when an allowable torque window exists; the listed
          torque maximises the worst margin. Head geometry uses the library default
          (hex) for candidates.
        </p>
        {error && <Callout intent="danger" style={{ marginBottom: 10 }}>{error}</Callout>}
        {loading && <Spinner size={28} />}
        {candidates && (
          <div style={{ maxHeight: 420, overflowY: "auto" }}>
            <table className="margins-table" style={{ width: "100%" }}>
              <thead>
                <tr>
                  <th>Size</th>
                  <th>Result</th>
                  <th>Torque window [N·m]</th>
                  <th>Best min MS</th>
                  <th>Governing check</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {candidates.map((c) => {
                  const ms = c.recommended?.min_ms ?? c.best_min_ms;
                  return (
                    <tr key={c.designation}>
                      <td className="mono">{c.designation}</td>
                      <td>
                        <Tag minimal intent={c.passes ? "success" : "danger"}>
                          {c.passes ? "PASS" : "fail"}
                        </Tag>
                      </td>
                      <td className="mono">
                        {c.window
                          ? `${(c.window.t_lo / 1000).toFixed(1)} – ${(c.window.t_hi / 1000).toFixed(1)}`
                          : "—"}
                        {c.recommended && (
                          <span style={{ color: "var(--text-muted)" }}>
                            {" "}(rec {(c.recommended.torque / 1000).toFixed(1)})
                          </span>
                        )}
                      </td>
                      <td className={`mono ms-value ${ms != null && ms >= 0 ? "pass" : "fail"}`}>
                        {ms != null ? `${ms >= 0 ? "+" : ""}${ms.toFixed(3)}` : "—"}
                      </td>
                      <td style={{ fontSize: 11, color: "var(--text-muted)" }}>{c.governing}</td>
                      <td>
                        {c.passes && (
                          <Button small minimal intent="primary" onClick={() => apply(c)}>
                            Apply
                          </Button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </DialogBody>
    </Dialog>
  );
}
