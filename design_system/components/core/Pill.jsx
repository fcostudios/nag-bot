import React from "react";

/**
 * QPH Pill — role/label chip with the pill radius. Italic by default (the
 * "bienvenidas" role-pill signature). Outline or filled.
 */
export function Pill({ children, variant = "outline", color = "var(--qph-orange)", italic = true, style = {} }) {
  const outline = {
    border: `1px solid ${color}`,
    color: color,
    background: "transparent",
  };
  const filled = {
    border: `1px solid ${color}`,
    color: "var(--qph-white)",
    background: color,
  };
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        borderRadius: "var(--qph-radius-pill)",
        padding: "0.25rem 1rem",
        fontSize: "var(--qph-text-sm)",
        fontStyle: italic ? "italic" : "normal",
        fontFamily: "var(--qph-font-body)",
        lineHeight: 1.4,
        ...(variant === "filled" ? filled : outline),
        ...style,
      }}
    >
      {children}
    </span>
  );
}
