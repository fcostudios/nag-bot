import React from "react";

/**
 * QPH Select — labeled dropdown matching the Input styling.
 */
export function Select({ label, hint, id, children, style = {}, ...rest }) {
  const selId = id || (label ? "sel-" + label.replace(/\s+/g, "-").toLowerCase() : undefined);
  const [focus, setFocus] = React.useState(false);
  return (
    <div style={{ display: "grid", gap: "0.35rem", ...style }}>
      {label && (
        <label htmlFor={selId} style={{ fontSize: "var(--qph-text-sm)", fontWeight: "var(--qph-w-semibold)", color: "var(--qph-gray-700)" }}>
          {label}
        </label>
      )}
      <select
        id={selId}
        onFocus={() => setFocus(true)}
        onBlur={() => setFocus(false)}
        style={{
          fontFamily: "var(--qph-font-body)",
          fontSize: "var(--qph-text-base)",
          padding: "0.6rem 0.8rem",
          border: `1.5px solid ${focus ? "var(--qph-orange)" : "var(--border-default)"}`,
          borderRadius: "var(--qph-radius-md)",
          color: "var(--qph-gray-700)",
          background: "var(--qph-white)",
          outline: "none",
          boxShadow: focus ? "0 0 0 3px var(--qph-orange-100)" : "none",
          transition: "var(--transition)",
          width: "100%",
          appearance: "none",
          backgroundImage:
            "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='8' viewBox='0 0 12 8'%3E%3Cpath d='M1 1l5 5 5-5' stroke='%23949394' stroke-width='1.6' fill='none' stroke-linecap='round'/%3E%3C/svg%3E\")",
          backgroundRepeat: "no-repeat",
          backgroundPosition: "right 0.8rem center",
          paddingRight: "2rem",
        }}
        {...rest}
      >
        {children}
      </select>
      {hint && <span style={{ fontSize: "var(--qph-text-xs)", color: "var(--qph-gray-300)" }}>{hint}</span>}
    </div>
  );
}
