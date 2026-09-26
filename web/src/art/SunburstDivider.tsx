/** SunburstDivider: a half sunburst between two stepped rules. Decorative. */
export function SunburstDivider({ className = "" }: { className?: string }) {
  const rays = Array.from({ length: 11 }, (_, i) => {
    const a = Math.PI - (i * Math.PI) / 10;
    return {
      x2: 60 + Math.cos(a) * 36,
      y2: 44 - Math.sin(a) * 36,
      x1: 60 + Math.cos(a) * 12,
      y1: 44 - Math.sin(a) * 12,
    };
  });
  return (
    <div aria-hidden="true" className={`flex items-end gap-0 ${className}`}>
      <svg className="h-[48px] flex-1" preserveAspectRatio="none" viewBox="0 0 100 48">
        <path
          d="M0 43 H96 M0 47 H88"
          stroke="var(--c-rule)"
          strokeWidth={1.25}
          vectorEffect="non-scaling-stroke"
        />
      </svg>
      <svg className="h-[48px] w-[120px] shrink-0" viewBox="0 0 120 48">
        {rays.map((r, i) => (
          <line key={i} {...r} stroke="var(--c-brass)" strokeWidth={2} />
        ))}
        <path
          d="M24 44 A36 36 0 0 1 96 44"
          fill="none"
          stroke="var(--c-brass)"
          strokeWidth={1.25}
        />
        <path d="M0 44 H120" stroke="var(--c-rule)" strokeWidth={1.25} />
      </svg>
      <svg className="h-[48px] flex-1" preserveAspectRatio="none" viewBox="0 0 100 48">
        <path
          d="M4 43 H100 M12 47 H100"
          stroke="var(--c-rule)"
          strokeWidth={1.25}
          vectorEffect="non-scaling-stroke"
        />
      </svg>
    </div>
  );
}
