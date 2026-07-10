import React from "react";

const TONES = {
  success: "var(--qph-success)",
  warning: "var(--qph-warning)",
  danger: "var(--qph-danger)",
  info: "var(--qph-info)",
};

/**
 * QPH Alert — subtle gray panel with a colored left border + status dot.
 */
export function Alert({ tone = "info", title, children, style = {} }) {
  const color = TONES[tone] || TONES.info;
  return (
    <div
      style={{
        display: "flex",
        gap: "0.8rem",
        padding: "var(--qph-space-4)",
        borderRadius: "var(--qph-radius-md)",
        borderLeft: `4px solid ${color}`,
        background: "var(--qph-bg-subtle)",
        fontSize: "var(--qph-text-sm)",
        alignItems: "flex-start",
        ...style,
      }}
    >
      <span style={{ width: "10px", height: "10px", borderRadius: "50%", background: color, marginTop: "5px", flex: "none" }} />
      <div>
        {title && <b style={{ display: "block", marginBottom: "2px", color: "var(--qph-gray-700)" }}>{title}</b>}
        <span style={{ color: "var(--qph-gray-500)" }}>{children}</span>
      </div>
    </div>
  );
}
