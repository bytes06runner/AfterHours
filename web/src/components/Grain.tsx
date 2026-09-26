/** Paper grain by day, film grain by night: a single turbulence filter, no images. */
export function Grain() {
  return (
    <svg aria-hidden="true" className="grain" width="100%" height="100%">
      <filter id="grain-filter">
        <feTurbulence type="fractalNoise" baseFrequency="0.8" numOctaves="2" stitchTiles="stitch" />
        <feColorMatrix type="saturate" values="0" />
      </filter>
      <rect width="100%" height="100%" filter="url(#grain-filter)" />
    </svg>
  );
}
