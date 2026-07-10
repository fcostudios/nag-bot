import * as React from "react";

export interface IconTileProps {
  /** The pictogram (white). e.g. a Lucide <i> or an <svg>. */
  children?: React.ReactNode;
  /** Tile fill — orange, a gray, or an area color. */
  color?: string;
  /** Square size in px. Default 56. */
  size?: number;
  /** Corner radius in px. Default 14. */
  radius?: number;
  style?: React.CSSProperties;
}

/** Colored rounded square holding a single white pictogram (brand icon style). */
export function IconTile(props: IconTileProps): JSX.Element;
