import * as React from "react";

export interface SwitchProps {
  /** Controlled on/off. Omit for uncontrolled (use defaultChecked). */
  checked?: boolean;
  defaultChecked?: boolean;
  onChange?: (next: boolean) => void;
  label?: string;
  disabled?: boolean;
  style?: React.CSSProperties;
}

/** Toggle switch — orange track when on, sliding white knob. */
export function Switch(props: SwitchProps): JSX.Element;
