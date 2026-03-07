import type { MarginStatus } from "../../types";

interface Props {
  status: MarginStatus;
}

export function StatusTag({ status }: Props) {
  const cls = status === "PASS" ? "pass" : status === "FAIL" ? "fail" : "warning";
  return <span className={`status-tag ${cls}`}>{status}</span>;
}
