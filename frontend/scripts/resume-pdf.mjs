// Renders src/data/resume.json to public/resume.pdf with headless Chrome, so the
// downloadable résumé always matches the site. No dependencies: Node + a local Chrome.
//
//   npm run resume:pdf                 # uses Google Chrome's default macOS path
//   CHROME=/usr/bin/chromium npm run resume:pdf
import { execFileSync } from 'node:child_process'
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = fileURLToPath(new URL('..', import.meta.url))
const resume = JSON.parse(readFileSync(join(root, 'src/data/resume.json'), 'utf8'))
const out = join(root, 'public/resume.pdf')
const chrome = process.env.CHROME ?? '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'

const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c])
const link = (l) => {
  const text = l.url.replace(/^mailto:/, '').replace(/^https?:\/\/(www\.)?/, '')
  return `<a href="${esc(l.url)}">${esc(text)}</a>`
}
const { basics } = resume

const html = `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>${esc(basics.name)} résumé</title>
<style>
  @page { size: A4; margin: 8mm 12mm; }
  * { box-sizing: border-box; }
  body { font: 9pt/1.28 -apple-system, "Helvetica Neue", Arial, sans-serif; color: #111; margin: 0; }
  a { color: #0b5e4f; text-decoration: none; }
  h1 { font-size: 19pt; margin: 0; letter-spacing: -0.01em; }
  .title { font-size: 10.5pt; color: #333; margin: 2px 0 4px; }
  .contact { font-size: 9pt; color: #333; }
  .contact span + span::before { content: " · "; color: #999; }
  h2 { font-size: 10.5pt; text-transform: uppercase; letter-spacing: 0.08em; color: #0b5e4f;
       border-bottom: 1px solid #cfd8d6; padding-bottom: 2px; margin: 7px 0 3px; }
  .summary { margin: 0; }
  .item { margin-bottom: 4px; break-inside: avoid; }
  .row { display: flex; justify-content: space-between; gap: 12px; }
  .row b { font-weight: 650; }
  .meta { color: #444; white-space: nowrap; }
  .sub { color: #444; font-style: italic; }
  ul { margin: 2px 0 0; padding-left: 15px; }
  li { margin: 1px 0; }
  .tech { color: #444; font-size: 8.8pt; }
  .skills div { margin: 1.5px 0; }
  .skills b { font-weight: 650; }
</style></head><body>
  <h1>${esc(basics.name)}</h1>
  <div class="title">${esc(basics.title)}</div>
  <div class="contact"><span>${esc(basics.location)}</span>${basics.links.map((l) => `<span>${link(l)}</span>`).join('')}</div>

  <h2>Summary</h2>
  <p class="summary">${esc(basics.summary)}</p>

  <h2>Education</h2>
  ${resume.education.map((e) => `<div class="item"><div class="row"><span><b>${esc(e.school)}</b>, ${esc(e.degree)}</span><span class="meta">${esc(e.start)} – ${esc(e.end)}</span></div></div>`).join('')}

  <h2>Experience</h2>
  ${resume.experience.map((j) => `<div class="item">
    <div class="row"><span><b>${esc(j.role)}</b>, ${esc(j.company)} <span class="sub">· ${esc(j.location)}</span></span><span class="meta">${esc(j.start)} – ${esc(j.end)}</span></div>
    <ul>${j.highlights.map((h) => `<li>${esc(h)}</li>`).join('')}</ul></div>`).join('')}

  <h2>Projects</h2>
  ${resume.projects.map((p) => `<div class="item">
    <div class="row"><span><b>${esc(p.name)}</b></span>${p.url ? `<span class="meta"><a href="${esc(p.url)}">GitHub ↗</a></span>` : ''}</div>
    <div>${esc(p.description)} <span class="tech">${p.tech.map(esc).join(' · ')}</span></div></div>`).join('')}

  <h2>Skills</h2>
  <div class="skills">${resume.skills.map((g) => `<div><b>${esc(g.category)}:</b> ${g.items.map(esc).join(', ')}</div>`).join('')}
    ${resume.certifications.length ? `<div><b>Certifications:</b> ${resume.certifications.map(esc).join('; ')}</div>` : ''}</div>
</body></html>`

const dir = mkdtempSync(join(tmpdir(), 'resume-'))
try {
  const page = join(dir, 'resume.html')
  writeFileSync(page, html)
  if (process.env.RESUME_HTML) writeFileSync(process.env.RESUME_HTML, html)
  execFileSync(chrome, ['--headless', '--disable-gpu', '--no-pdf-header-footer', `--print-to-pdf=${out}`, `file://${page}`], {
    stdio: 'ignore',
  })
  console.log(`wrote ${out}`)
} finally {
  rmSync(dir, { recursive: true, force: true })
}
