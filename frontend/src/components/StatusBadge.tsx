import { AlertTriangle, CheckCircle2, Clock, XCircle } from "lucide-react";

interface StatusBadgeProps {
  status: string;
  size?: "sm" | "md";
}

export function StatusBadge({ status, size = "sm" }: StatusBadgeProps) {
  const normalized = status.toUpperCase();
  const base =
    size === "md"
      ? "inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold tracking-wide"
      : "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11px] font-semibold tracking-wide";

  if (normalized === "PASS") {
    return (
      <span className={`${base} bg-emerald-500/15 text-emerald-300 ring-1 ring-inset ring-emerald-500/30`}>
        <CheckCircle2 className="h-3.5 w-3.5" />
        PASS
      </span>
    );
  }
  if (normalized === "FAIL") {
    return (
      <span className={`${base} bg-rose-500/15 text-rose-300 ring-1 ring-inset ring-rose-500/30`}>
        <XCircle className="h-3.5 w-3.5" />
        FAIL
      </span>
    );
  }
  if (normalized === "MANUAL_REVIEW") {
    return (
      <span className={`${base} bg-amber-500/15 text-amber-300 ring-1 ring-inset ring-amber-500/30`}>
        <AlertTriangle className="h-3.5 w-3.5" />
        MANUAL REVIEW
      </span>
    );
  }
  return (
    <span className={`${base} bg-slate-500/15 text-slate-300 ring-1 ring-inset ring-slate-500/30`}>
      <Clock className="h-3.5 w-3.5" />
      {normalized}
    </span>
  );
}

export function SeverityBadge({ severity }: { severity: string }) {
  const s = severity.toUpperCase();
  if (s === "CRITICAL") {
    return (
      <span className="rounded bg-rose-500/20 px-2 py-0.5 text-[10px] font-bold tracking-wider text-rose-300 ring-1 ring-rose-500/30">
        CRITICAL
      </span>
    );
  }
  if (s === "WARNING") {
    return (
      <span className="rounded bg-amber-500/20 px-2 py-0.5 text-[10px] font-bold tracking-wider text-amber-300 ring-1 ring-amber-500/30">
        WARNING
      </span>
    );
  }
  return (
    <span className="rounded bg-sky-500/20 px-2 py-0.5 text-[10px] font-bold tracking-wider text-sky-300 ring-1 ring-sky-500/30">
      INFO
    </span>
  );
}
