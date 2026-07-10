import * as React from "react";

export interface AlertProps {
  tone?: "success" | "warning" | "danger" | "info";
  title?: string;
  children?: React.ReactNode;
  style?: React.CSSProperties;
}

/** Inline alert — gray panel, colored left border + status dot. */
export function Alert(props: AlertProps): JSX.Element;
