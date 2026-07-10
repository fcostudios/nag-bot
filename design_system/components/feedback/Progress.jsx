import React from "react";

/**
 * QPH Progress — thin track with an orange fill.
 */
export function Progress({ value = 0, color = "var(--qph-orange)", label, style = {} }) {
  const pct = Math.max(0, Math.min(100, value));
  return (
    <div style={{ ...style }}>
      {label && (
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: "var(--qph-text-sm)", fontWeight: "var(--qph-w-semibold)", marginBottom: "0.4rem", color: "var(--qph-gray-700)" }}>
          <span>{label}</span>
          <span style={{ color: "var(--qph-gray-300)" }}>{pct}%</span>
        </div>
      )}
      <div style={{ height: "10px", background: "var(--qph-bg-subtle)", borderRadius: "999px", overflow: "hidden" }}>
        <span style={{ display: "block", height: "100%", width: pct + "%", background: color, borderRadius: "999px", transition: "width var(--qph-duration-lg) var(--qph-ease)" }} />
      </div>
    </div>
  );
}
