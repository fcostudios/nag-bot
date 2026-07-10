import * as React from "react";

export interface InputProps {
  label?: string;
  hint?: string;
  error?: string;
  id?: string;
  type?: string;
  placeholder?: string;
  value?: string;
  defaultValue?: string;
  disabled?: boolean;
  onChange?: (e: React.ChangeEvent<HTMLInputElement>) => void;
  style?: React.CSSProperties;
}

/** Labeled text input with orange focus ring and optional hint/error. */
export function Input(props: InputProps): JSX.Element;
