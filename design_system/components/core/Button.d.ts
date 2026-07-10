import * as React from "react";

/**
 * Props for the QPH primary action button.
 * @startingPoint section="Core" subtitle="Buttons — primary, secondary, ghost, dark" viewport="700x150"
 */
export interface ButtonProps {
  /** Visual style. Primary = orange (one per view). */
  variant?: "primary" | "secondary" | "ghost" | "dark";
  size?: "sm" | "md" | "lg";
  disabled?: boolean;
  type?: "button" | "submit" | "reset";
  /** Element rendered before the label (e.g. an icon). */
  iconLeft?: React.ReactNode;
  /** Element rendered after the label. */
  iconRight?: React.ReactNode;
  children?: React.ReactNode;
  style?: React.CSSProperties;
  onClick?: (e: React.MouseEvent<HTMLButtonElement>) => void;
}

/** QPH primary action button. Orange = primary; one primary action per view. */
export function Button(props: ButtonProps): JSX.Element;
