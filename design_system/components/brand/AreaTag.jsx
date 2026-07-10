import React from "react";

/** Area → color + label map (corporate services). */
export const QPH_AREAS = {
  "responsabilidad-social": { label: "Responsabilidad Social", color: "var(--qph-area-responsabilidad-social)", soft: "#ece7fa", ink: "#5b3fb0" },
  "tecnologia": { label: "Tecnología", color: "var(--qph-area-tecnologia)", soft: "#e6e4f5", ink: "#241d79" },
  "nomina": { label: "Nómina", color: "var(--qph-area-nomina)", soft: "#fdf1cc", ink: "#8a6c00" },
  "proyectos-procesos": { label: "Proyectos y Procesos", color: "var(--qph-area-proyectos-procesos)", soft: "#dfe5e8", ink: "#253237" },
  "administracion": { label: "Administración", color: "var(--qph-area-administracion)", soft: "#fbe7cf", ink: "#c96f12" },
  "seguridad-informacion": { label: "Seguridad de la Información", color: "var(--qph-area-seguridad-informacion)", soft: "#d6e1ea", ink: "#003559" },
  "salud": { label: "Salud", color: "var(--qph-area-salud)", soft: "#e7f7f4", ink: "#0e8f82" },
};

/**
 * QPH AreaTag — hashtag-style label for a corporate service area, in that
 * area's color (the comunicado motif: `#TECNOLOGÍA`).
 */
export function AreaTag({ area = "administracion", hash = true, variant = "text", style = {} }) {
  const a = QPH_AREAS[area] || QPH_AREAS.administracion;
  const label = (hash ? "#" : "") + a.label.toUpperCase();
  if (variant === "soft") {
    return (
      <span style={{ display: "inline-flex", alignItems: "center", fontSize: "var(--qph-text-xs)", fontWeight: "var(--qph-w-bold)", textTransform: "uppercase", letterSpacing: "var(--qph-tracking-wide)", padding: "0.3rem 0.7rem", borderRadius: "var(--qph-radius-pill)", background: a.soft, color: a.ink, ...style }}>
        {label}
      </span>
    );
  }
  return (
    <span style={{ fontWeight: "var(--qph-w-black)", textTransform: "uppercase", letterSpacing: "0.02em", fontSize: "var(--qph-text-sm)", color: a.color, ...style }}>
      {label}
    </span>
  );
}
