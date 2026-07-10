import * as React from "react";

export interface ProgressProps {
  /** 0–100. */
  value?: number;
  /** Fill color. Default orange. */
  color?: string;
  /** Optional label shown above with the percentage. */
  label?: string;
  style?: React.CSSProperties;
}

/** Thin progress bar with an orange fill. */
export function Progress(props: ProgressProps): JSX.Element;
