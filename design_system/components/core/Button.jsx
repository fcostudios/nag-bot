import React from "react";

/**
 * QPH Button — orange is the single primary action; one primary per view.
 */
export function Button({
  variant = "primary",
  size = "md",
  disabled = false,
  type = "button",
  iconLeft = null,
  iconRight = null,
  children,
  style = {},
  ...rest
}) {
  const base = {
    fontFamily: "var(--qph-font-body)",
    fontWeight: "var(--qph-w-bold)",
    border: "0",
    borderRadius: "var(--qph-radius-md)",
    cursor: disabled ? "not-allowed" : "pointer",
    transition: "var(--transition)",
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    gap: "0.5rem",
    textDecoration: "none",
    lineHeight: 1,
    whiteSpace: "nowrap",
    opacity: disabled ? 0.45 : 1,
  };

  const sizes = {
    sm: { fontSize: "var(--qph-text-sm)", padding: "0.4rem 0.9rem" },
    md: { fontSize: "var(--qph-text-base)", padding: "0.7rem 1.4rem" },
    lg: { fontSize: "var(--qph-text-lg)", padding: "0.9rem 1.8rem" },
  };

  const variants = {
    primary: { background: "var(--qph-orange)", color: "var(--qph-white)" },
    secondary: {
      background: "transparent",
      color: "var(--qph-gray-700)",
      border: "1.5px solid var(--qph-gray-500)",
    },
    ghost: {
      background: "transparent",
      color: "var(--qph-orange)",
      border: "1.5px solid transparent",
    },
    dark: { background: "var(--qph-ink)", color: "var(--qph-white)" },
  };

  const hoverBg = {
    primary: "var(--qph-orange-600)",
    secondary: "var(--qph-bg-subtle)",
    ghost: "var(--qph-orange-100)",
    dark: "#000",
  };

  const merged = { ...base, ...sizes[size], ...variants[variant], ...style };

  return (
    <button
      type={type}
      disabled={disabled}
      style={merged}
      onMouseEnter={(e) => {
        if (disabled) return;
        e.currentTarget.style.background = hoverBg[variant];
      }}
      onMouseLeave={(e) => {
        if (disabled) return;
        e.currentTarget.style.background = variants[variant].background;
      }}
      {...rest}
    >
      {iconLeft}
      {children}
      {iconRight}
    </button>
  );
}
