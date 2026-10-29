import { useEffect, useRef } from 'react'
import { useLocation } from 'react-router-dom'
import { useReducedMotion } from '../../hooks/useMediaQuery'

// A domain-warped noise field (fbm of fbm) tinted cyan, violet and magenta, lit by the
// cursor, with a vignette and film grain. WebGL 1 for the widest support.
const FRAGMENT = /* glsl */ `
precision highp float;
uniform vec2 u_res;
uniform float u_time;
uniform vec2 u_mouse;
uniform float u_energy;
uniform float u_intensity;

float hash(vec2 p) {
  p = fract(p * vec2(123.34, 456.21));
  p += dot(p, p + 45.32);
  return fract(p.x * p.y);
}
float noise(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), u.x),
             mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x), u.y);
}
float fbm(vec2 p) {
  float v = 0.0;
  float a = 0.5;
  mat2 m = mat2(1.6, 1.2, -1.2, 1.6);
  for (int i = 0; i < 5; i++) {
    v += a * noise(p);
    p = m * p;
    a *= 0.5;
  }
  return v;
}

void main() {
  vec2 uv = gl_FragCoord.xy / u_res;
  vec2 p = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  vec2 m = (u_mouse - 0.5 * u_res) / u_res.y;
  float t = u_time * (0.035 + 0.09 * u_energy);

  vec2 q = vec2(fbm(p * 1.3 + t), fbm(p * 1.3 - t + 3.1));
  vec2 r = vec2(fbm(p * 1.6 + 2.0 * q + vec2(1.7, 9.2) + 1.3 * t),
                fbm(p * 1.6 + 2.0 * q + vec2(8.3, 2.8) - t));
  float f = fbm(p * 1.1 + 2.2 * r);

  vec3 cyan = vec3(0.22, 0.91, 1.0);
  vec3 violet = vec3(0.48, 0.29, 1.0);
  vec3 magenta = vec3(0.68, 1.0, 0.23);
  vec3 col = mix(violet, cyan, smoothstep(0.38, 0.72, q.x));
  col = mix(col, magenta, smoothstep(0.48, 0.80, r.y));

  float glow = smoothstep(0.22, 0.82, f);
  float d = length(p - m);
  float cursor = exp(-d * d * 4.0);
  // Brighter toward the right: the copy sits on the left, the light show on the right.
  float stage = 0.35 + 0.65 * smoothstep(-0.7, 0.55, p.x);

  vec3 c = vec3(0.010, 0.010, 0.026);
  c += col * (0.08 + 0.10 * u_energy) * f * u_intensity;
  c += col * pow(glow, 1.3) * (1.05 + 0.7 * u_energy) * u_intensity * stage;
  // Hot cores where the field peaks, like light through smoke.
  c += vec3(0.85, 0.92, 1.0) * pow(glow, 5.0) * (0.35 + 0.4 * u_energy) * u_intensity * stage;
  c += col * cursor * (0.12 + 0.15 * u_energy) * (0.4 + u_intensity);
  c *= smoothstep(1.45, 0.15, length((uv - 0.5) * vec2(1.25, 1.0)));
  c += (hash(gl_FragCoord.xy + fract(u_time) * 97.0) - 0.5) * 0.03;
  gl_FragColor = vec4(c, 1.0);
}`

const VERTEX = 'attribute vec2 a;void main(){gl_Position=vec4(a,0.0,1.0);}'

function compile(gl: WebGLRenderingContext, type: number, source: string): WebGLShader | null {
  const shader = gl.createShader(type)
  if (!shader) return null
  gl.shaderSource(shader, source)
  gl.compileShader(shader)
  return gl.getShaderParameter(shader, gl.COMPILE_STATUS) ? shader : null
}

/**
 * The site's living backdrop. Renders at reduced resolution (it is soft by nature), pauses
 * while the tab is hidden, and with reduced motion draws still frames only. Without WebGL
 * a CSS gradient stands in.
 */
export function ShaderBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const reduced = useReducedMotion()
  const { pathname } = useLocation()
  // The home hero gets the full show; reading pages get a calmer field.
  const intensityTarget = useRef(1)
  useEffect(() => {
    intensityTarget.current = pathname === '/projects' || pathname === '/' ? 1 : 0.55
  }, [pathname])

  useEffect(() => {
    const canvas = canvasRef.current
    const gl = canvas?.getContext('webgl', { antialias: false, alpha: false, powerPreference: 'low-power' })
    if (!canvas || !gl) return
    const vs = compile(gl, gl.VERTEX_SHADER, VERTEX)
    const fs = compile(gl, gl.FRAGMENT_SHADER, FRAGMENT)
    const program = gl.createProgram()
    if (!vs || !fs || !program) return
    gl.attachShader(program, vs)
    gl.attachShader(program, fs)
    gl.linkProgram(program)
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) return
    gl.useProgram(program)
    canvas.dataset.ready = ''

    // One triangle that covers the screen.
    const buffer = gl.createBuffer()
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer)
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW)
    const attr = gl.getAttribLocation(program, 'a')
    gl.enableVertexAttribArray(attr)
    gl.vertexAttribPointer(attr, 2, gl.FLOAT, false, 0, 0)
    const u = {
      res: gl.getUniformLocation(program, 'u_res'),
      time: gl.getUniformLocation(program, 'u_time'),
      mouse: gl.getUniformLocation(program, 'u_mouse'),
      energy: gl.getUniformLocation(program, 'u_energy'),
      intensity: gl.getUniformLocation(program, 'u_intensity'),
    }

    const small = matchMedia('(max-width: 640px)').matches
    const scale = (small ? 0.35 : 0.5) * Math.min(devicePixelRatio || 1, 1.5)
    const mouse = { x: innerWidth * 0.7, y: innerHeight * 0.4 }
    const smooth = { x: mouse.x, y: mouse.y, energy: 0, intensity: intensityTarget.current }
    const started = performance.now()
    let frame = 0

    const resize = () => {
      canvas.width = Math.max(1, Math.round(innerWidth * scale))
      canvas.height = Math.max(1, Math.round(innerHeight * scale))
      gl.viewport(0, 0, canvas.width, canvas.height)
    }
    const draw = (now: number) => {
      const k = reduced ? 1 : 0.06
      smooth.x += (mouse.x - smooth.x) * k
      smooth.y += (mouse.y - smooth.y) * k
      smooth.energy += (0 - smooth.energy) * (reduced ? 1 : 0.03)
      smooth.intensity += (intensityTarget.current - smooth.intensity) * (reduced ? 1 : 0.04)
      gl.uniform2f(u.res, canvas.width, canvas.height)
      gl.uniform1f(u.time, reduced ? 40 : (now - started) / 1000 + 40)
      gl.uniform2f(u.mouse, smooth.x * scale, (innerHeight - smooth.y) * scale)
      gl.uniform1f(u.energy, smooth.energy)
      gl.uniform1f(u.intensity, smooth.intensity)
      gl.drawArrays(gl.TRIANGLES, 0, 3)
    }
    const loop = (now: number) => {
      draw(now)
      frame = requestAnimationFrame(loop)
    }
    const start = () => {
      cancelAnimationFrame(frame)
      if (reduced) draw(performance.now())
      else if (!document.hidden) frame = requestAnimationFrame(loop)
    }
    const onMove = (e: PointerEvent) => {
      mouse.x = e.clientX
      mouse.y = e.clientY
    }
    const onResize = () => {
      resize()
      if (reduced) draw(performance.now())
    }

    resize()
    start()
    addEventListener('resize', onResize)
    addEventListener('pointermove', onMove, { passive: true })
    document.addEventListener('visibilitychange', start)
    return () => {
      cancelAnimationFrame(frame)
      removeEventListener('resize', onResize)
      removeEventListener('pointermove', onMove)
      document.removeEventListener('visibilitychange', start)
      delete canvas.dataset.ready
    }
  }, [reduced])

  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 overflow-hidden bg-[var(--bg)]">
      {/* Fallback when WebGL is unavailable: the canvas stays transparent until ready. */}
      <div className="shader-fallback absolute inset-0" />
      <canvas ref={canvasRef} className="shader-canvas absolute inset-0 size-full" />
      <svg className="neural-mesh absolute inset-0 size-full" viewBox="0 0 1440 900" preserveAspectRatio="xMidYMid slice">
        <defs>
          <linearGradient id="mesh-signal" x1="0" y1="0" x2="1" y2="1">
            <stop stopColor="#55e8ff" stopOpacity="0.05" />
            <stop offset="0.5" stopColor="#9876ff" stopOpacity="0.72" />
            <stop offset="1" stopColor="#b7ff55" stopOpacity="0.08" />
          </linearGradient>
          <radialGradient id="mesh-node">
            <stop stopColor="#fff" />
            <stop offset="0.3" stopColor="#55e8ff" />
            <stop offset="1" stopColor="#9876ff" stopOpacity="0.12" />
          </radialGradient>
        </defs>
        <g className="mesh-links" stroke="url(#mesh-signal)" fill="none">
          <path d="M-30 210 115 120 248 206 390 96 520 185 650 104 784 205 922 105 1060 190 1200 92 1470 205" />
          <path d="M-20 500 115 390 248 470 390 350 520 445 650 335 784 462 922 346 1060 442 1200 328 1470 480" />
          <path d="M-20 780 115 670 248 748 390 638 520 725 650 622 784 744 922 632 1060 720 1200 616 1470 765" />
          <path d="m115 120 0 270m133-184v264m142-374v288m130-199v260m130-341v287m134-186v281m138-358v281m138-196v274m140-372v288" />
          <path d="m248 206 142 144m130 95 130-110m134 127 138-116m138 96 140-114M115 390l133 80m142-120 130 95m130-110 134 127m138-116 138 96m140-114 270 152" />
          <path className="mesh-packet" d="M-30 210 115 120 248 206 390 96 520 185 650 104 784 205 922 105 1060 190 1200 92 1470 205" />
          <path className="mesh-packet mesh-packet-delay" d="M-20 780 115 670 248 748 390 638 520 725 650 622 784 744 922 632 1060 720 1200 616 1470 765" />
        </g>
        <g className="mesh-nodes" fill="url(#mesh-node)">
          <circle cx="115" cy="120" r="5" /><circle cx="248" cy="206" r="4" /><circle cx="390" cy="96" r="6" />
          <circle cx="520" cy="185" r="4" /><circle cx="650" cy="104" r="5" /><circle cx="784" cy="205" r="7" />
          <circle cx="922" cy="105" r="4" /><circle cx="1060" cy="190" r="6" /><circle cx="1200" cy="92" r="5" />
          <circle cx="115" cy="390" r="6" /><circle cx="248" cy="470" r="4" /><circle cx="390" cy="350" r="5" />
          <circle cx="520" cy="445" r="7" /><circle cx="650" cy="335" r="4" /><circle cx="784" cy="462" r="5" />
          <circle cx="922" cy="346" r="6" /><circle cx="1060" cy="442" r="4" /><circle cx="1200" cy="328" r="7" />
          <circle cx="115" cy="670" r="4" /><circle cx="248" cy="748" r="6" /><circle cx="390" cy="638" r="4" />
          <circle cx="520" cy="725" r="5" /><circle cx="650" cy="622" r="7" /><circle cx="784" cy="744" r="4" />
          <circle cx="922" cy="632" r="5" /><circle cx="1060" cy="720" r="7" /><circle cx="1200" cy="616" r="4" />
        </g>
      </svg>
      <div className="absolute inset-0 bg-[linear-gradient(to_bottom,transparent_60%,var(--bg))]" />
    </div>
  )
}
