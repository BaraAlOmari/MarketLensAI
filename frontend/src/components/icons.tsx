// Symbols drawn to read like SF Symbols (sf-symbols.md): one 24-unit grid, a regular-weight
// stroke with round caps and joins, outline next to text, fill where a symbol needs emphasis
// (status, a selected state, a badge). Filled symbols cut their inner marks out with evenodd,
// so they work on any background. All use currentColor and are decorative (aria-hidden):
// every control that shows one also has a text label.

import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement> & { size?: number };

function Icon({ size = 20, children, ...rest }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      {...rest}
    >
      {children}
    </svg>
  );
}

/** A filled symbol: no stroke, inner marks are holes (fill-rule evenodd). */
function Solid({ size = 20, children, ...rest }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="currentColor"
      fillRule="evenodd"
      clipRule="evenodd"
      aria-hidden="true"
      focusable="false"
      {...rest}
    >
      {children}
    </svg>
  );
}

// Categories (iphone, laptopcomputer, car, sofa, building.2, house).

export const PhoneIcon = (p: IconProps) => (
  <Icon {...p}>
    <rect x="6.5" y="2.25" width="11" height="19.5" rx="2.75" />
    <rect x="10" y="4.25" width="4" height="1.4" rx="0.7" fill="currentColor" stroke="none" />
  </Icon>
);

export const LaptopIcon = (p: IconProps) => (
  <Icon {...p}>
    <rect x="4.5" y="5" width="15" height="10.5" rx="1.75" />
    <path d="M2.25 18.25h19.5" />
    <path d="M10.5 18.25h3" strokeWidth={2.4} />
  </Icon>
);

export const CarIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M3.75 17v-3.6c0-.6.15-1.2.45-1.73l1.9-3.43A2.5 2.5 0 0 1 8.28 7h7.44a2.5 2.5 0 0 1 2.18 1.24l1.9 3.43c.3.53.45 1.13.45 1.73V17" />
    <path d="M3.75 13.25h16.5M6.4 11l1.3-2.4M17.6 11l-1.3-2.4" />
    <path d="M3.75 17h16.5" />
    <path d="M5.75 17v1.25M18.25 17v1.25" strokeWidth={2.6} />
    <circle cx="7.25" cy="14.9" r="0.9" fill="currentColor" stroke="none" />
    <circle cx="16.75" cy="14.9" r="0.9" fill="currentColor" stroke="none" />
  </Icon>
);

export const SofaIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M5.25 10.5V8.25A2.75 2.75 0 0 1 8 5.5h8a2.75 2.75 0 0 1 2.75 2.75v2.25" />
    <path d="M3 12.5a2 2 0 0 1 4 0v1.75h10V12.5a2 2 0 0 1 4 0v3.75a1.5 1.5 0 0 1-1.5 1.5h-15A1.5 1.5 0 0 1 3 16.25Z" />
    <path d="M5.5 17.75v1.25M18.5 17.75v1.25" />
  </Icon>
);

export const BuildingIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M4.5 21V5.5A1.5 1.5 0 0 1 6 4h7a1.5 1.5 0 0 1 1.5 1.5V21" />
    <path d="M14.5 10H18a1.5 1.5 0 0 1 1.5 1.5V21" />
    <path d="M3 21h18" />
    <path d="M7.75 7.5h1M10.75 7.5h1M7.75 11h1M10.75 11h1M7.75 14.5h1M10.75 14.5h1M16.75 13.5h.5M16.75 17h.5" />
  </Icon>
);

export const HouseIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M3.25 10.5 12 3.5l8.75 7" />
    <path d="M5.5 9v10.5a1 1 0 0 0 1 1h11a1 1 0 0 0 1-1V9" />
    <path d="M10 20.5v-5a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1v5" />
  </Icon>
);

export const CATEGORY_ICON: Record<string, (p: IconProps) => React.ReactElement> = {
  phones: PhoneIcon,
  laptops: LaptopIcon,
  cars: CarIcon,
  furniture: SofaIcon,
  apartments: BuildingIcon,
  villas: HouseIcon,
};

// Interface symbols.

/** magnifyingglass */
export const MagnifyingGlassIcon = (p: IconProps) => (
  <Icon {...p} strokeWidth={2}>
    <circle cx="10.5" cy="10.5" r="6.25" />
    <path d="m15.25 15.25 5 5" />
  </Icon>
);

/** sparkles: generated content (generative-ai.md: make AI involvement clear). */
export const SparklesIcon = (p: IconProps) => (
  <Solid {...p}>
    <path d="M10 3.5c.45 3.6 2.05 5.2 5.75 5.75-3.7.55-5.3 2.15-5.75 5.75-.45-3.6-2.05-5.2-5.75-5.75C7.95 8.7 9.55 7.1 10 3.5Z" />
    <path d="M17.5 13.25c.25 1.95 1.05 2.75 3 3-1.95.25-2.75 1.05-3 3-.25-1.95-1.05-2.75-3-3 1.95-.25 2.75-1.05 3-3Z" />
    <path d="M17 3c.17 1.2.68 1.71 1.9 1.9-1.22.17-1.73.68-1.9 1.9-.17-1.22-.68-1.73-1.9-1.9C16.32 4.71 16.83 4.2 17 3Z" />
  </Solid>
);

/** checkmark.seal.fill: a recommended listing. */
export function SealIcon({ size = 14, ...rest }: IconProps) {
  // A 12-point seal (alternating radii) with the check cut out.
  const points = Array.from({ length: 24 }, (_, i) => {
    const r = i % 2 === 0 ? 10 : 8.4;
    const a = (Math.PI * 2 * i) / 24 - Math.PI / 2;
    return `${(12 + r * Math.cos(a)).toFixed(2)} ${(12 + r * Math.sin(a)).toFixed(2)}`;
  });
  return (
    <Solid size={size} {...rest}>
      <path d={`M${points.join("L")}Z M7.9 12.3l2.6 2.6 5.6-5.8-1.1-1.1-4.5 4.7-1.5-1.5Z`} />
    </Solid>
  );
}

/** mappin, filled with the head cut out. */
export const PinIcon = (p: IconProps) => (
  <Solid {...p}>
    <path d="M12 2.5a7 7 0 0 0-7 7c0 4.9 5.6 10.9 6.3 11.6a1 1 0 0 0 1.4 0C13.4 20.4 19 14.4 19 9.5a7 7 0 0 0-7-7Zm0 4.5a2.5 2.5 0 1 1 0 5 2.5 2.5 0 0 1 0-5Z" />
  </Solid>
);

/** arrow.up, bold: inside the send button's filled circle. */
export const ArrowUpIcon = (p: IconProps) => (
  <Icon {...p} strokeWidth={2.6}>
    <path d="M12 19V5.5M6 11.25 12 5.25l6 6" />
  </Icon>
);

/** stop.fill: cancel the search in progress. */
export const StopIcon = (p: IconProps) => (
  <Solid {...p}>
    <rect x="6.5" y="6.5" width="11" height="11" rx="2.5" />
  </Solid>
);

/** xmark */
export const CloseIcon = (p: IconProps) => (
  <Icon {...p} strokeWidth={2.2}>
    <path d="M7 7l10 10M17 7 7 17" />
  </Icon>
);

/** xmark.circle.fill: close a sheet. */
export const CloseCircleIcon = (p: IconProps) => (
  <Solid {...p}>
    <path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Zm-3.3 5.6a.9.9 0 0 0-1.27 1.27L10.73 12l-3.3 3.13a.9.9 0 1 0 1.27 1.27L12 13.27l3.3 3.13a.9.9 0 0 0 1.27-1.27L13.27 12l3.3-3.13a.9.9 0 0 0-1.27-1.27L12 10.73Z" />
  </Solid>
);

/** square.and.pencil: a new search. */
export const ComposeIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M11.5 4.5H7A2.5 2.5 0 0 0 4.5 7v10A2.5 2.5 0 0 0 7 19.5h10a2.5 2.5 0 0 0 2.5-2.5v-4.5" />
    <path d="M17.6 3.9a1.9 1.9 0 0 1 2.7 2.7l-7.4 7.4-3.4.7.7-3.4Z" />
  </Icon>
);

/** exclamationmark.triangle.fill */
export const AlertIcon = (p: IconProps) => (
  <Solid {...p}>
    <path d="M10.27 3.5a2 2 0 0 1 3.46 0l8 13.75A2 2 0 0 1 20 20.25H4a2 2 0 0 1-1.73-3L10.27 3.5ZM12 8.25a1 1 0 0 0-1 1v4.25a1 1 0 1 0 2 0V9.25a1 1 0 0 0-1-1Zm0 7.25a1.15 1.15 0 1 0 0 2.3 1.15 1.15 0 0 0 0-2.3Z" />
  </Solid>
);

/** chevron.forward (mirrors in right-to-left). */
export const ChevronIcon = (p: IconProps) => (
  <Icon {...p} strokeWidth={2} className={`rtl:-scale-x-100 ${p.className ?? ""}`}>
    <path d="m9.5 6 6 6-6 6" />
  </Icon>
);

/** iOS-style activity indicator: eight spokes, the newest darkest. Still under Reduce Motion. */
export function ActivityIndicator({ size = 18 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true" className="activity">
      {Array.from({ length: 8 }, (_, i) => (
        <rect
          key={i}
          x="11"
          y="2"
          width="2"
          height="6"
          rx="1"
          fill="currentColor"
          opacity={0.25 + (0.75 * (i + 1)) / 8}
          transform={`rotate(${i * 45} 12 12)`}
        />
      ))}
    </svg>
  );
}

/** sun.max */
export const SunIcon = (p: IconProps) => (
  <Icon {...p}>
    <circle cx="12" cy="12" r="4" />
    <path d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.3 5.3l1.4 1.4M17.3 17.3l1.4 1.4M5.3 18.7l1.4-1.4M17.3 6.7l1.4-1.4" />
  </Icon>
);

/** moon */
export const MoonIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5Z" />
  </Icon>
);

/** circle.lefthalf.filled: "Match system". */
export const AutoIcon = (p: IconProps) => (
  <Icon {...p}>
    <circle cx="12" cy="12" r="8" />
    <path d="M12 4a8 8 0 0 0 0 16Z" fill="currentColor" />
  </Icon>
);
