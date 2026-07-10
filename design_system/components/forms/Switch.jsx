import React from "react";

/**
 * QPH Switch — orange when on; pill track with sliding knob.
 */
export function Switch({ checked, defaultChecked = false, onChange, label, disabled = false, style = {} }) {
  const isControlled = checked !== undefined;
  const [on, setOn] = React.useState(defaultChecked);
  const value = isControlled ? checked : on;

  function toggle() {
    if (disabled) return;
    if (!isControlled) setOn(!value);
    onChange && onChange(!value);
  }

  return (
    <label
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "0.6rem",
        fontSize: "var(--qph-text-sm)",
        color: "var(--qph-gray-700)",
        cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.5 : 1,
        ...style,
      }}
      onClick={toggle}
    >
      <span
        style={{
          position: "relative",
          width: "42px",
          height: "24px",
          borderRadius: "999px",
          background: value ? "var(--qph-orange)" : "var(--qph-gray-100)",
          transition: "var(--transition)",
          flex: "none",
        }}
      >
        <span
          style={{
            position: "absolute",
            top: "3px",
            left: value ? "21px" : "3px",
            width: "18px",
            height: "18px",
            borderRadius: "50%",
            background: "var(--qph-white)",
            transition: "var(--transition)",
            boxShadow: "var(--qph-shadow-sm)",
          }}
        />
      </span>
      {label && <span>{label}</span>}
    </label>
  );
}
