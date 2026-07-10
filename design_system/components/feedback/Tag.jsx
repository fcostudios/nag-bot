import React from "react";

/**
 * QPH Tag — small uppercase status/category chip. Pass a color for a tinted
 * fill, or use the soft default. Use area colors for area tags.
 */
export function Tag({ children, color, bg, style = {} }) {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "0.4rem",
        fontSize: "var(--qph-text-xs)",
        fontWeight: "var(--qph-w-bold)",
        textTransform: "uppercase",
        letterSpacing: "var(--qph-tracking-wide)",
        padding: "0.3rem 0.7rem",
        borderRadius: "var(--qph-radius-pill)",
        background: bg || "var(--qph-orange-100)",
        color: color || "var(--qph-orange-600)",
        ...style,
      }}
    >
      {children}
    </span>
  );
}
