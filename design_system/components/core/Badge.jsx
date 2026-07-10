import React from "react";

/**
 * QPH Badge — numeric badge in an orange square (Barlow Black). From the
 * presentation template's numbered lists. Also supports a soft variant.
 */
export function Badge({ children, color = "var(--qph-orange)", variant = "solid", style = {} }) {
  const solid = {
    background: color,
    color: "var(--qph-white)",
  };
  const soft = {
    background: "var(--qph-orange-100)",
    color: "var(--qph-orange-600)",
  };
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        minWidth: "34px",
        height: "34px",
        padding: "0 0.4rem",
        fontFamily: "var(--qph-font-display)",
        fontWeight: "var(--qph-w-black)",
        fontSize: "var(--qph-text-lg)",
        borderRadius: "var(--qph-radius-sm)",
        ...(variant === "soft" ? soft : solid),
        ...style,
      }}
    >
      {children}
    </span>
  );
}
