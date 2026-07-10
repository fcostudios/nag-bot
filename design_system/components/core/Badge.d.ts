import * as React from "react";

export interface BadgeProps {
  children?: React.ReactNode;
  /** Square fill color (solid variant). Defaults to brand orange. */
  color?: string;
  variant?: "solid" | "soft";
  style?: React.CSSProperties;
}

/** Numeric badge — Barlow Black inside an orange square (slide-template motif). */
export function Badge(props: BadgeProps): JSX.Element;
