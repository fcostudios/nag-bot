import * as React from "react";

/**
 * The "corporativo." logo — full wordmark with the orange infinity "co" ligature and final orange period.
 * @startingPoint section="Brand" subtitle="corporativo. logo — positive / negative / white" viewport="700x160"
 */
export interface LogoProps {
  /** "positive" (gray+orange, on light) · "negative" (white+orange, on dark) · "white" (all white, on orange/colored). */
  variant?: "positive" | "negative" | "white";
  /** Pixel height of the wordmark. Default 32. */
  height?: number;
  /** Render only the infinity "co" mark — favicon / app-icon sizes only. */
  markOnly?: boolean;
  /** @deprecated legacy QPH API — showName={false} maps to markOnly. */
  showName?: boolean;
  style?: React.CSSProperties;
}

/** The "corporativo." wordmark logo. Always use the full wordmark; mark alone only at favicon sizes. */
export function Logo(props: LogoProps): JSX.Element;
