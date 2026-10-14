// Shapes of the portfolio content in src/data/*.json.

export interface Project {
  title: string
  description: string
  tags: string[]
  githubUrl: string
  liveUrl?: string
  /** Path under public/, e.g. "/diagrams/foo.svg". */
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
  projects: ResumeProject[]
  skills: SkillGroup[]
}
