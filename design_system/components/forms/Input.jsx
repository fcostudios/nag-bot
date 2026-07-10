import React from "react";

/**
 * QPH Input — labeled text field; orange focus ring.
 */
export function Input({ label, hint, error, id, style = {}, ...rest }) {
  const inputId = id || (label ? "in-" + label.replace(/\s+/g, "-").toLowerCase() : undefined);
  const [focus, setFocus] = React.useState(false);
  const borderColor = error ? "var(--qph-danger)" : focus ? "var(--qph-orange)" : "var(--border-default)";
  return (
    <div style={{ display: "grid", gap: "0.35rem", ...style }}>
      {label && (
        <label htmlFor={inputId} style={{ fontSize: "var(--qph-text-sm)", fontWeight: "var(--qph-w-semibold)", color: "var(--qph-gray-700)" }}>
          {label}
        </label>
      )}
      <input
        id={inputId}
        onFocus={() => setFocus(true)}
        onBlur={() => setFocus(false)}
        style={{
          fontFamily: "var(--qph-font-body)",
          fontSize: "var(--qph-text-base)",
          padding: "0.6rem 0.8rem",
          border: `1.5px solid ${borderColor}`,
          borderRadius: "var(--qph-radius-md)",
          color: "var(--qph-gray-700)",
          background: "var(--qph-white)",
          outline: "none",
          boxShadow: focus ? "0 0 0 3px var(--qph-orange-100)" : "none",
          transition: "var(--transition)",
          width: "100%",
        }}
        {...rest}
      />
      {(hint || error) && (
        <span style={{ fontSize: "var(--qph-text-xs)", color: error ? "var(--qph-danger)" : "var(--qph-gray-300)" }}>
          {error || hint}
        </span>
      )}
    </div>
  );
}
