type BrandLogoProps = {
  /** Visual size preset */
  size?: "sidebar" | "login" | "sm";
  className?: string;
};

const SIZE = {
  sidebar: { src: "/brand/seeds-logo-sidebar.png", className: "h-9 w-auto" },
  login: { src: "/brand/seeds-logo.png", className: "mx-auto h-14 w-auto sm:h-16" },
  sm: { src: "/brand/seeds-logo-sidebar.png", className: "h-7 w-auto" },
} as const;

/** Wordmark oficial Seeds (crema sobre transparente) para fondos oscuros. */
export function BrandLogo({ size = "sidebar", className = "" }: BrandLogoProps) {
  const cfg = SIZE[size];
  return (
    <img
      src={cfg.src}
      alt="Seeds"
      className={`${cfg.className} ${className}`.trim()}
      decoding="async"
    />
  );
}
