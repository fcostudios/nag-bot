import React from "react";

/**
 * QPH IconTile — white pictogram on a color rounded square. Pass the icon as
 * children (e.g. an <i data-lucide> node or an <svg>). One figure per tile.
 */
export function IconTile({ children, color = "var(--qph-orange)", size = 56, radius = 14, style = {} }) {
  return (
    <span
      style={{
        display: "inline-grid",
        placeItems: "center",
        width: size,
        height: size,
        borderRadius: radius,
        background: color,
        color: "#ffffff",
        ...style,
      }}
    >
      {children}
    </span>
  );
}
