import * as React from "react";

/**
 * Surface card — white, hairline border, 16px radius, soft gray-tinted shadow.
 * @startingPoint section="Core" subtitle="Surface card with optional hover lift" viewport="700x220"
 */
export interface CardProps {
  children?: React.ReactNode;
  /** Lift + deepen shadow on hover. Default false. */
  hover?: boolean;
  /** Inner padding (CSS value). Default --qph-space-6. */
  padding?: string;
  style?: React.CSSProperties;
}

/** Surface card — white, hairline border, 16px radius, soft gray-tinted shadow. */
export function Card(props: CardProps): JSX.Element;
