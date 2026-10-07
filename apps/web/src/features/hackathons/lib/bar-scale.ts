/**
 * The bar chart is scaled to the leading team: the top score fills the chart and every other bar
 * is its share of that, so when a team pulls ahead everyone else's bar gets shorter.
 */
export function topScore(scores: number[]): number {
  return Math.max(1, ...scores);
}

/** Bar height as a percentage of the chart (a thin sliver for zero so every team still shows). */
export function barPercent(score: number, top: number): number {
  return Math.max(2, Math.round((Math.max(0, score) / Math.max(1, top)) * 100));
}
