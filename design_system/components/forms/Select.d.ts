import * as React from "react";

export interface SelectProps {
  label?: string;
  hint?: string;
  id?: string;
  value?: string;
  defaultValue?: string;
  disabled?: boolean;
  onChange?: (e: React.ChangeEvent<HTMLSelectElement>) => void;
  children?: React.ReactNode;
  style?: React.CSSProperties;
}

/** Labeled dropdown with a custom chevron, matching Input styling. */
export function Select(props: SelectProps): JSX.Element;
