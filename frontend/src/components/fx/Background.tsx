import { useEffect, useRef } from 'react'
import { useReducedMotion } from '../../hooks/useMediaQuery'

interface Particle {
  x: number
  y: number
  vx: number
  vy: number
  r: number
}

const LINK_DISTANCE = 130
const MOUSE_DISTANCE = 190

/** Fixed, decorative backdrop: aurora blobs, a fading grid, grain and a live particle network. */
export function Background() {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const reduced = useReducedMotion()

  useEffect(() => {
    const canvas = canvasRef.current
    const ctx = canvas?.getContext('2d')
    if (!canvas || !ctx) return

    const dpr = Math.min(window.devicePixelRatio || 1, 2)
    const mouse = { x: -9999, y: -9999 }
    let particles: Particle[] = []
    let width = 0
    let height = 0
    let frame = 0
    let dark = document.documentElement.classList.contains('dark')

    const resize = () => {
      width = innerWidth
      height = innerHeight
      canvas.width = width * dpr
      canvas.height = height * dpr
      canvas.style.width = `${width}px`
      canvas.style.height = `${height}px`
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      const count = Math.min(110, Math.floor((width * height) / 14_000))
      particles = Array.from({ length: count }, () => ({
        x: Math.random() * width,
        y: Math.random() * height,
        vx: (Math.random() - 0.5) * 0.35,
        vy: (Math.random() - 0.5) * 0.35,
        r: 0.8 + Math.random() * 1.6,
      }))
    }

    const draw = () => {
      ctx.clearRect(0, 0, width, height)
      const rgb = dark ? '52, 211, 153' : '15, 118, 110'
      const linkAlpha = dark ? 0.22 : 0.14

      for (const p of particles) {
        if (!reduced) {
          p.x += p.vx
          p.y += p.vy
          if (p.x < 0 || p.x > width) p.vx *= -1
          if (p.y < 0 || p.y > height) p.vy *= -1
          // Gentle pull toward the cursor.
          const dx = mouse.x - p.x
          const dy = mouse.y - p.y
          const d = Math.hypot(dx, dy)
          if (d < MOUSE_DISTANCE && d > 1) {
            p.x += (dx / d) * 0.25
            p.y += (dy / d) * 0.25
          }
        }
        ctx.beginPath()
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2)
        ctx.fillStyle = `rgba(${rgb}, ${dark ? 0.7 : 0.45})`
        ctx.fill()
      }

      for (let i = 0; i < particles.length; i++) {
        const a = particles[i]
        for (let j = i + 1; j < particles.length; j++) {
          const b = particles[j]
          const d = Math.hypot(a.x - b.x, a.y - b.y)
          if (d < LINK_DISTANCE) {
            ctx.strokeStyle = `rgba(${rgb}, ${(1 - d / LINK_DISTANCE) * linkAlpha})`
            ctx.lineWidth = 0.8
            ctx.beginPath()
            ctx.moveTo(a.x, a.y)
            ctx.lineTo(b.x, b.y)
            ctx.stroke()
          }
        }
        const dm = Math.hypot(a.x - mouse.x, a.y - mouse.y)
        if (dm < MOUSE_DISTANCE) {
          ctx.strokeStyle = `rgba(34, 211, 238, ${(1 - dm / MOUSE_DISTANCE) * 0.5})`
          ctx.lineWidth = 1
          ctx.beginPath()
          ctx.moveTo(a.x, a.y)
          ctx.lineTo(mouse.x, mouse.y)
          ctx.stroke()
        }
      }
    }

    const loop = () => {
      if (!document.hidden) draw()
      frame = requestAnimationFrame(loop)
    }

    const onMove = (e: PointerEvent) => {
      mouse.x = e.clientX
      mouse.y = e.clientY
    }
    const onLeave = () => {
      mouse.x = mouse.y = -9999
    }
    const themeObserver = new MutationObserver(() => {
      dark = document.documentElement.classList.contains('dark')
      if (reduced) draw()
    })

    resize()
    themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] })
    window.addEventListener('resize', resize)
    if (reduced) {
      draw()
    } else {
      window.addEventListener('pointermove', onMove, { passive: true })
      document.addEventListener('pointerleave', onLeave)
      frame = requestAnimationFrame(loop)
    }
    return () => {
      cancelAnimationFrame(frame)
      themeObserver.disconnect()
      window.removeEventListener('resize', resize)
      window.removeEventListener('pointermove', onMove)
      document.removeEventListener('pointerleave', onLeave)
    }
  }, [reduced])

  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      <div className="animate-aurora absolute -top-1/3 -left-1/4 size-[70vmax] rounded-full bg-emerald-400/25 blur-[120px] dark:bg-emerald-500/20" />
      <div
        className="animate-aurora absolute -right-1/4 top-1/4 size-[60vmax] rounded-full bg-cyan-300/25 blur-[120px] dark:bg-cyan-500/15"
        style={{ animationDelay: '-8s' }}
      />
      <div
        className="animate-aurora absolute -bottom-1/3 left-1/4 size-[55vmax] rounded-full bg-violet-400/20 blur-[120px] dark:bg-violet-600/20"
        style={{ animationDelay: '-15s' }}
      />
      <div
        className="absolute inset-0 opacity-[0.5] dark:opacity-[0.35]"
        style={{
          backgroundImage:
            'linear-gradient(to right, rgb(120 130 150 / 0.12) 1px, transparent 1px), linear-gradient(to bottom, rgb(120 130 150 / 0.12) 1px, transparent 1px)',
          backgroundSize: '56px 56px',
          maskImage: 'radial-gradient(ellipse 80% 60% at 50% 0%, #000 40%, transparent 100%)',
          WebkitMaskImage: 'radial-gradient(ellipse 80% 60% at 50% 0%, #000 40%, transparent 100%)',
        }}
      />
      <canvas ref={canvasRef} className="absolute inset-0" />
      <div
        className="absolute inset-0 opacity-[0.035] mix-blend-overlay dark:opacity-[0.06]"
        style={{
          backgroundImage:
            "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='160'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E\")",
        }}
      />
    </div>
  )
}
