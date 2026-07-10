import * as React from "react";

export interface TagProps {
  children?: React.ReactNode;
  /** Text color. Default orange-600. */
  color?: string;
  /** Background fill. Default orange-100. */
  bg?: string;
  style?: React.CSSProperties;
}

/** Small uppercase status/category chip (pill radius). */
export function Tag(props: TagProps): JSX.Element;
