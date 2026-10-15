// One icon language: 24-unit grid, 1.75 stroke, round caps, currentColor so every icon follows
// the text it sits next to in light, dark and increased contrast (icons.md, dark-mode.md).
// Icons are decorative here; every control that uses one also has a text label.

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
      strokeWidth={1.75}
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

export const PhoneIcon = (p: IconProps) => (
  <Icon {...p}>
    <rect x="7" y="2.5" width="10" height="19" rx="2.5" />
    <path d="M11 18.5h2" />
  </Icon>
);

export const LaptopIcon = (p: IconProps) => (
  <Icon {...p}>
    <rect x="4.5" y="5" width="15" height="10" rx="1.5" />
    <path d="M2.5 19h19" />
  </Icon>
);

export const CarIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M4 16v-3.5l1.8-4.6A2 2 0 0 1 7.7 6.5h8.6a2 2 0 0 1 1.9 1.4L20 12.5V16" />
    <path d="M3.5 16h17" />
    <circle cx="7.5" cy="16.5" r="1.8" />
    <circle cx="16.5" cy="16.5" r="1.8" />
  </Icon>
);

export const SofaIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M5.5 11V8.5A2.5 2.5 0 0 1 8 6h8a2.5 2.5 0 0 1 2.5 2.5V11" />
    <path d="M3.5 13a2 2 0 0 1 4 0v1.5h9V13a2 2 0 0 1 4 0v4.5h-17Z" />
    <path d="M5.5 17.5v1.5M18.5 17.5v1.5" />
  </Icon>
);

export const BuildingIcon = (p: IconProps) => (
  <Icon {...p}>
    <rect x="5.5" y="3" width="13" height="18" rx="1.5" />
    <path d="M9 7h1.5M13.5 7H15M9 11h1.5M13.5 11H15M9 15h1.5M13.5 15H15M10.5 21v-2.5h3V21" />
  </Icon>
);

export const HouseIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M3.5 11 12 4l8.5 7" />
    <path d="M5.5 9.5V20h13V9.5" />
    <path d="M10 20v-5h4v5" />
  </Icon>
);

export const PinIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M12 21s6-5.6 6-10.5A6 6 0 0 0 6 10.5C6 15.4 12 21 12 21Z" />
    <circle cx="12" cy="10.5" r="2" />
  </Icon>
);

export const ArrowUpIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M12 18.5V6M6.5 11.5 12 6l5.5 5.5" strokeWidth={2.5} />
  </Icon>
);

export const CloseIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M7 7l10 10M17 7 7 17" />
  </Icon>
);

export const ComposeIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M12 5H6.5A2.5 2.5 0 0 0 4 7.5v10A2.5 2.5 0 0 0 6.5 20h10a2.5 2.5 0 0 0 2.5-2.5V12" />
    <path d="M17.5 3.5a2.1 2.1 0 0 1 3 3L13 14l-4 1 1-4Z" />
  </Icon>
);

export const AlertIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M12 4 2.8 19.5h18.4Z" />
    <path d="M12 10v4M12 17h.01" />
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

export const ChevronIcon = (p: IconProps) => (
  <Icon {...p} className={`rtl:-scale-x-100 ${p.className ?? ""}`}>
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

export const SunIcon = (p: IconProps) => (
  <Icon {...p}>
    <circle cx="12" cy="12" r="4" />
    <path d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.3 5.3l1.4 1.4M17.3 17.3l1.4 1.4M5.3 18.7l1.4-1.4M17.3 6.7l1.4-1.4" />
  </Icon>
);

export const MoonIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5Z" />
  </Icon>
);

/** "Match system": a circle, half filled (like SF Symbols' circle.lefthalf.filled). */
export const AutoIcon = (p: IconProps) => (
  <Icon {...p}>
    <circle cx="12" cy="12" r="8" />
    <path d="M12 4a8 8 0 0 0 0 16Z" fill="currentColor" />
  </Icon>
);
