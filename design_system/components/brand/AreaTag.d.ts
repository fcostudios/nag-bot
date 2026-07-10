import * as React from "react";

export type QphArea =
  | "responsabilidad-social"
  | "tecnologia"
  | "nomina"
  | "proyectos-procesos"
  | "administracion"
  | "seguridad-informacion"
  | "salud";

export interface AreaTagProps {
  area?: QphArea;
  /** Prefix with "#" (comunicado style). Default true. */
  hash?: boolean;
  /** "text" (bold colored hashtag) or "soft" (tinted pill). */
  variant?: "text" | "soft";
  style?: React.CSSProperties;
}

/** Hashtag-style label for a corporate area, in that area's color. */
export function AreaTag(props: AreaTagProps): JSX.Element;

/** area key → { label, color, soft, ink } */
export declare const QPH_AREAS: Record<QphArea, { label: string; color: string; soft: string; ink: string }>;
