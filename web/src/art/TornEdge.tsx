/** Torn bottom edge, drawn once and stretched. */
export function TornEdge() {
  const teeth = Array.from(
    { length: 40 },
    (_, i) => `L${i * 10 + 5} ${i % 2 ? 2 : 8} L${(i + 1) * 10} ${i % 3 ? 4 : 1}`,
  ).join(" ");
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 400 10"
      preserveAspectRatio="none"
      className="block h-[10px] w-full"
    >
      <path d={`M0 0 ${teeth} L400 0 Z`} fill="var(--c-surface)" />
    </svg>
  );
}
