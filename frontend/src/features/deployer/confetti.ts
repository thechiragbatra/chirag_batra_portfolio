// Dependency-free confetti burst on a temporary full-screen canvas.
import { prefersReducedMotion } from '../../hooks/useMediaQuery'

const COLORS = ['#34d399', '#22d3ee', '#a78bfa', '#f472b6', '#fbbf24', '#ffffff']

interface Piece {
  x: number
  y: number
  vx: number
  vy: number
  size: number
  rotation: number
  spin: number
  color: string
  shape: 0 | 1
}

/** Fire from (x, y) in viewport pixels; defaults to the screen center. */
export function confetti(origin?: { x: number; y: number }, count = 160): void {
  if (prefersReducedMotion()) return
  const canvas = document.createElement('canvas')
  const dpr = Math.min(window.devicePixelRatio || 1, 2)
  canvas.width = innerWidth * dpr
  canvas.height = innerHeight * dpr
  Object.assign(canvas.style, {
    position: 'fixed',
    inset: '0',
    width: '100vw',
    height: '100vh',
    pointerEvents: 'none',
    zIndex: '60',
  })
  canvas.setAttribute('aria-hidden', 'true')
  document.body.appendChild(canvas)
  const ctx = canvas.getContext('2d')
  if (!ctx) {
    canvas.remove()
    return
  }
  ctx.scale(dpr, dpr)

  const ox = origin?.x ?? innerWidth / 2
  const oy = origin?.y ?? innerHeight / 3
  const pieces: Piece[] = Array.from({ length: count }, () => {
    const angle = Math.random() * Math.PI * 2
    const speed = 4 + Math.random() * 9
    return {
      x: ox,
      y: oy,
      vx: Math.cos(angle) * speed,
      vy: Math.sin(angle) * speed - 6,
      size: 5 + Math.random() * 6,
      rotation: Math.random() * Math.PI,
      spin: (Math.random() - 0.5) * 0.35,
      color: COLORS[Math.floor(Math.random() * COLORS.length)],
      shape: Math.random() < 0.6 ? 0 : 1,
    }
  })

  const start = performance.now()
  const duration = 2600
  const frame = (now: number) => {
    const t = now - start
    ctx.clearRect(0, 0, innerWidth, innerHeight)
    ctx.globalAlpha = Math.max(0, 1 - t / duration)
    for (const p of pieces) {
      p.vx *= 0.985
      p.vy = p.vy * 0.985 + 0.32
      p.x += p.vx
      p.y += p.vy
      p.rotation += p.spin
      ctx.save()
      ctx.translate(p.x, p.y)
      ctx.rotate(p.rotation)
      ctx.fillStyle = p.color
      if (p.shape === 0) ctx.fillRect(-p.size / 2, -p.size / 4, p.size, p.size / 2)
      else {
        ctx.beginPath()
        ctx.arc(0, 0, p.size / 3, 0, Math.PI * 2)
        ctx.fill()
      }
      ctx.restore()
    }
    if (t < duration) requestAnimationFrame(frame)
    else canvas.remove()
  }
  requestAnimationFrame(frame)
}
