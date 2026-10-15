// Shapes of the portfolio content in src/data/*.json.

export interface Project {
  title: string
  description: string
  tags: string[]
  githubUrl: string
  liveUrl?: string
  /** In-site route to an interactive demo of the project, e.g. "/lab". */
  demo?: string
  /** Headline number for the project's scene on the home page. */
  metric?: { value: string; label: string }
  /** Card image under public/: an architecture diagram or a screenshot, e.g. "/diagrams/foo.svg". */
  diagram?: string
}

export interface Link {
  label: string
  url: string
}

export interface Experience {
  role: string
  company: string
  location: string
  start: string
  end: string
  highlights: string[]
}

export interface Education {
  school: string
  degree: string
  start: string
  end: string
  details?: string
}

export interface ResumeProject {
  name: string
  description: string
  tech: string[]
  url?: string
}

export interface SkillGroup {
  category: string
  items: string[]
}

export interface Resume {
  basics: {
    name: string
    title: string
    location: string
    summary: string
    links: Link[]
  }
  experience: Experience[]
  education: Education[]
  certifications: string[]
  projects: ResumeProject[]
  skills: SkillGroup[]
}

/** A project with a design doc but no code yet (src/data/planned.json). Shown as "in development". */
export interface PlannedProject {
  title: string
  summary: string
  /** One-phrase skill area it demonstrates, e.g. "LLM integration". */
  focus: string
  tags: string[]
  /** Repo holding the design doc (README only until code lands). */
  designDocUrl?: string
}

/** Headline numbers on the home hero (src/data/highlights.json). */
export interface Highlight {
  value: number
  label: string
  decimals?: number
  prefix?: string
  suffix?: string
}
