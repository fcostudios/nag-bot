import React from "react";

/**
 * QPH Card — white surface, hairline border, lg radius, soft gray-tinted
 * shadow. Optional hover lift.
 */
export function Card({ children, hover = false, padding = "var(--qph-space-6)", style = {}, ...rest }) {
  const [raised, setRaised] = React.useState(false);
  return (
    <div
      style={{
        background: "var(--surface-card)",
        border: "1px solid var(--border-default)",
        borderRadius: "var(--radius-card)",
        boxShadow: raised ? "var(--qph-shadow-md)" : "var(--qph-shadow-sm)",
        padding,
        transition: "var(--transition)",
        transform: raised ? "translateY(-2px)" : "none",
        ...style,
      }}
      onMouseEnter={() => hover && setRaised(true)}
      onMouseLeave={() => hover && setRaised(false)}
      {...rest}
    >
      {children}
    </div>
  );
}
