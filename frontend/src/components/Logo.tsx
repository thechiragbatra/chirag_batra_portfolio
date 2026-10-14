/** Brand mark: a "D" inside a slowly rotating conic ring. */
export function Logo({ className = 'size-8' }: { className?: string }) {
  return (
    <span className={`relative inline-grid place-items-center ${className}`} aria-hidden>
      <span
        className="absolute inset-0 rounded-[10px] [animation:spin-angle_6s_linear_infinite]"
        style={{
          background: 'conic-gradient(from var(--angle), var(--glow-a), var(--glow-b), var(--glow-c), var(--glow-a))',
        }}
      />
      <span className="absolute inset-[2px] rounded-[8px] bg-white dark:bg-ink" />
      <span className="font-display text-aurora relative text-[0.95em] font-bold">D</span>
    </span>
  )
}
