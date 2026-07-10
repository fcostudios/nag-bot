import * as React from "react";

export interface PillProps {
  children?: React.ReactNode;
  variant?: "outline" | "filled";
  /** Border/text (outline) or fill (filled) color. Defaults to orange. */
  color?: string;
  /** Italic lettering — the brand's role-pill signature. Default true. */
  italic?: boolean;
  style?: React.CSSProperties;
}

/** Role/label pill — italic chip with pill radius (from the welcome pieces). */
export function Pill(props: PillProps): JSX.Element;
