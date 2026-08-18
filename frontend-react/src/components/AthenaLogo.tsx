export function AthenaLogo({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" role="img" aria-label="Athena logo" style={{ flexShrink: 0 }}>
      <rect width="32" height="32" rx="9" fill="#D97757" />
      <path
        d="M16 7.5 L23.5 24.5 H19.8 L18.3 20.8 H13.7 L12.2 24.5 H8.5 L16 7.5 Z
           M16 12.8 L14.4 17.8 H17.6 L16 12.8 Z"
        fill="#FFFFFF"
      />
    </svg>
  );
}
