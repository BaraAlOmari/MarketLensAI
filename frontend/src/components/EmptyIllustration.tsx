import { useId } from "react";

import { CATEGORY_ICON, CloseIcon, SealIcon } from "./icons";

// The empty state's illustration: MarketLens's own interface, staged. Three listing cards
// drawn exactly as the app draws them (same radius, category tile colors, text as bars), a
// lens that really magnifies the stack beneath it, and the "understood as" tokens floating
// around it. Built from semantic color tokens, so it follows light and dark; decorative only.

const W = 196; // card size, viewBox units
const H = 232;
const TILE = 110;
const LENS = { cx: 198, cy: 318, r: 53, zoom: 1.45 }; // over the price and chip

type CardProps = {
  x: number;
  y: number;
  rotate: number;
  category: "phones" | "cars" | "apartments";
  delay: number;
  shadow: string;
  recommended?: boolean;
};

function Card({ x, y, rotate, category, delay, shadow, recommended }: CardProps) {
  const Icon = CATEGORY_ICON[category];
  return (
    <g
      className="rise-in"
      style={{ transformBox: "fill-box", transformOrigin: "center", animationDelay: `${delay}ms` }}
    >
      <g transform={`translate(${x} ${y}) rotate(${rotate} ${W / 2} ${H / 2})`}>
        <rect
          width={W}
          height={H}
          rx={24}
          fill="var(--raised)"
          stroke="var(--glass-edge)"
          filter={`url(#${shadow})`}
        />
        {/* Category tile across the top, the same mix the real cards use. */}
        <path
          d={`M0 24a24 24 0 0 1 24-24h${W - 48}a24 24 0 0 1 24 24v${TILE - 24}H0Z`}
          style={{
            fill: `color-mix(in srgb, var(--cat-${category}) var(--tile-mix), var(--raised))`,
          }}
        />
        <Icon
          size={46}
          x={W / 2 - 23}
          y={TILE / 2 - 23}
          strokeWidth={1.4}
          style={{ color: `var(--cat-${category})` }}
        />
        {recommended && (
          <g transform="translate(12 12)">
            <rect width={70} height={20} rx={10} fill="var(--accent-fill)" />
            <SealIcon size={12} x={6} y={4} style={{ color: "var(--on-accent)" }} />
            <rect
              x={22}
              y={8}
              width={38}
              height={4}
              rx={2}
              fill="var(--on-accent)"
              opacity={0.85}
            />
          </g>
        )}
        {/* Title, price, condition chip and a spec, as bars. */}
        <rect x={16} y={128} width={152} height={9} rx={4.5} fill="var(--fill)" />
        <rect x={16} y={145} width={104} height={9} rx={4.5} fill="var(--fill)" />
        <rect x={16} y={168} width={84} height={13} rx={6.5} fill="var(--content)" opacity={0.82} />
        <rect x={16} y={194} width={54} height={20} rx={10} fill="var(--fill)" />
        <rect x={78} y={198} width={46} height={12} rx={6} fill="var(--fill)" />
      </g>
    </g>
  );
}

export function EmptyIllustration() {
  const raw = useId().replace(/[^a-zA-Z0-9_-]/g, "");
  const id = (name: string) => `ml-${raw}-${name}`;
  const { cx, cy, r, zoom } = LENS;
  // Where the handle leaves the rim, pointing down and to the right.
  const hx = cx + (r + 5) * Math.SQRT1_2;
  const hy = cy + (r + 5) * Math.SQRT1_2;

  const tokens = [
    { label: "iPhone 17", left: "63%", top: "7%", delay: 520 },
    { label: "Under 2,000 QAR", left: "66%", top: "45%", delay: 600 },
    { label: "Like new or good", left: "-4%", top: "73%", delay: 680 },
  ];

  return (
    <div
      aria-hidden="true"
      className="relative mx-auto aspect-[440/420] w-full max-w-[440px] select-none"
    >
      <svg viewBox="0 0 440 420" className="absolute inset-0 h-full w-full overflow-visible">
        <defs>
          <filter id={id("shadow")} x="-25%" y="-20%" width="150%" height="150%">
            <feDropShadow dx="0" dy="10" stdDeviation="14" floodColor="#000" floodOpacity="0.1" />
          </filter>
          <radialGradient id={id("ground")}>
            <stop offset="0" stopColor="#000" stopOpacity="0.12" />
            <stop offset="1" stopColor="#000" stopOpacity="0" />
          </radialGradient>
          <linearGradient id={id("rim")} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" style={{ stopColor: "var(--lens-hi)" }} />
            <stop offset="0.55" style={{ stopColor: "var(--lens-mid)" }} />
            <stop offset="1" style={{ stopColor: "var(--lens-lo)" }} />
          </linearGradient>
          <linearGradient id={id("handle")} x1="0" y1="0" x2="1" y2="0">
            <stop offset="0" style={{ stopColor: "var(--lens-hi)" }} />
            <stop offset="0.5" style={{ stopColor: "var(--lens-mid)" }} />
            <stop offset="1" style={{ stopColor: "var(--lens-lo)" }} />
          </linearGradient>
          <radialGradient id={id("glass")} cx="0.3" cy="0.25" r="0.9">
            <stop offset="0" stopColor="#fff" style={{ stopOpacity: "var(--lens-sheen)" }} />
            <stop offset="0.6" stopColor="#fff" stopOpacity="0.04" />
            <stop offset="1" stopColor="#fff" stopOpacity="0" />
          </radialGradient>
          <clipPath id={id("lens")}>
            <circle cx={cx} cy={cy} r={r} />
          </clipPath>
        </defs>

        <ellipse cx="214" cy="392" rx="170" ry="16" fill={`url(#${id("ground")})`} />

        {/* The stack: back to front. */}
        <g id={id("scene")}>
          <Card x={196} y={20} rotate={9} category="apartments" delay={0} shadow={id("shadow")} />
          <Card x={34} y={60} rotate={-8} category="cars" delay={90} shadow={id("shadow")} />
          <Card
            x={122}
            y={134}
            rotate={0}
            category="phones"
            delay={180}
            shadow={id("shadow")}
            recommended
          />
        </g>

        {/* The lens: the same scene, scaled up about its center and clipped to the glass. */}
        <g
          className="pop-in"
          style={{ transformBox: "fill-box", transformOrigin: "center", animationDelay: "360ms" }}
        >
          <g transform={`translate(${hx} ${hy}) rotate(-45)`}>
            <rect x={-15} y={-4} width={30} height={18} rx={7} fill={`url(#${id("rim")})`} />
            <rect x={-11} y={12} width={22} height={70} rx={11} fill={`url(#${id("handle")})`} />
          </g>
          <g clipPath={`url(#${id("lens")})`}>
            <rect x={cx - r} y={cy - r} width={r * 2} height={r * 2} fill="var(--surface)" />
            <use
              href={`#${id("scene")}`}
              transform={`translate(${cx} ${cy}) scale(${zoom}) translate(${-cx} ${-cy})`}
            />
            <circle cx={cx} cy={cy} r={r} fill={`url(#${id("glass")})`} />
          </g>
          <circle cx={cx} cy={cy} r={r + 0.5} fill="none" stroke="#000" strokeOpacity="0.18" />
          <circle
            cx={cx}
            cy={cy}
            r={r + 5}
            fill="none"
            stroke={`url(#${id("rim")})`}
            strokeWidth={10}
          />
          {/* Specular highlight on the glass, upper left. */}
          <path
            d={`M${cx - r * 0.74} ${cy - r * 0.2}A${r * 0.78} ${r * 0.78} 0 0 1 ${cx - r * 0.2} ${cy - r * 0.74}`}
            fill="none"
            stroke="#fff"
            strokeOpacity="0.75"
            strokeWidth={3.5}
            strokeLinecap="round"
          />
        </g>
      </svg>

      {/* The "understood as" tokens, in the app's own token style. */}
      {tokens.map((t) => (
        <span
          key={t.label}
          className="pop-in absolute flex h-8 items-center gap-1 rounded-full bg-accent-surface ps-3 pe-2.5 text-footnote font-semibold whitespace-nowrap text-accent shadow-[var(--glass-shadow)]"
          style={{ left: t.left, top: t.top, animationDelay: `${t.delay}ms` }}
        >
          {t.label}
          <CloseIcon size={11} />
        </span>
      ))}
    </div>
  );
}
