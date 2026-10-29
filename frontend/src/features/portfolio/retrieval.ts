import projectsData from '../../data/projects.json'
import resumeData from '../../data/resume.json'
import type { Project, Resume } from '../../types/content'

const projects: Project[] = projectsData
const resume: Resume = resumeData

export type PortfolioPassage = {
  id: string
  title: string
  kind: 'Experience' | 'Project' | 'Profile' | 'Skills'
  text: string
  href: string
  sourceLabel: string
}

export type RetrievedPassage = PortfolioPassage & { score: number }

const passages: PortfolioPassage[] = [
  {
    id: 'profile',
    title: 'Profile',
    kind: 'Profile',
    text: resume.basics.summary,
    href: '/resume',
    sourceLabel: 'Résumé · Profile',
  },
  ...resume.experience.map((experience, experienceIndex) => ({
    id: `experience-${experienceIndex}`,
    title: `${experience.role} · ${experience.company}`,
    kind: 'Experience' as const,
    text: experience.highlights.join(' '),
    href: '/resume',
    sourceLabel: `Résumé · ${experience.company}`,
  })),
  ...projects.map((project, index) => ({
    id: `project-${index}`,
    title: project.title,
    kind: 'Project' as const,
    text: [project.context, project.description, project.contribution, project.keyDecision, project.tags.join(', ')]
      .filter(Boolean)
      .join(' '),
    href: project.githubUrl ?? '/projects#work',
    sourceLabel: project.githubUrl ? `${project.title} · GitHub` : `Portfolio · ${project.title}`,
  })),
  ...resume.skills.map((group, index) => ({
    id: `skills-${index}`,
    title: group.category,
    kind: 'Skills' as const,
    text: group.items.join(', '),
    href: '/resume',
    sourceLabel: `Résumé · ${group.category}`,
  })),
]

const STOP_WORDS = new Set(
  'a an and are as at be been build built by did do for from how i in is it my of on or the this to was what with'.split(' '),
)

function tokenize(value: string): string[] {
  return value
    .toLowerCase()
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .match(/[a-z0-9+#.]+/g)
    ?.filter((token) => token.length > 1 && !STOP_WORDS.has(token)) ?? []
}

const indexed = passages.map((passage) => {
  const tokens = tokenize(`${passage.title} ${passage.text}`)
  const frequencies = new Map<string, number>()
  for (const token of tokens) frequencies.set(token, (frequencies.get(token) ?? 0) + 1)
  return { passage, tokens, frequencies }
})

const averageLength = indexed.reduce((sum, item) => sum + item.tokens.length, 0) / indexed.length
const documentFrequency = new Map<string, number>()
for (const { frequencies } of indexed) {
  for (const token of frequencies.keys()) documentFrequency.set(token, (documentFrequency.get(token) ?? 0) + 1)
}

/** Small BM25 index built from the public résumé and project data bundled with this static site. */
export function retrievePortfolioPassages(query: string, limit = 4): RetrievedPassage[] {
  const terms = [...new Set(tokenize(query))]
  if (!terms.length) return []

  return indexed
    .map(({ passage, tokens, frequencies }) => {
      let score = 0
      for (const term of terms) {
        const frequency = frequencies.get(term) ?? 0
        if (!frequency) continue
        const docsWithTerm = documentFrequency.get(term) ?? 0
        const inverseFrequency = Math.log(1 + (indexed.length - docsWithTerm + 0.5) / (docsWithTerm + 0.5))
        const lengthNorm = frequency + 1.2 * (1 - 0.75 + 0.75 * (tokens.length / averageLength))
        score += inverseFrequency * ((frequency * 2.2) / lengthNorm)
      }
      return { ...passage, score }
    })
    .filter((item) => item.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, limit)
}

/** Selects the best sentence from retrieved evidence; the demo intentionally stays extractive. */
export function extractEvidenceSentence(text: string, query: string): string {
  const terms = new Set(tokenize(query))
  const sentences = text.match(/[^.!?]+[.!?]?/g)?.map((sentence) => sentence.trim()).filter(Boolean) ?? [text]
  return sentences
    .map((sentence, index) => ({
      sentence,
      index,
      score: tokenize(sentence).reduce((sum, token) => sum + Number(terms.has(token)), 0),
    }))
    .sort((a, b) => b.score - a.score || a.index - b.index)[0]?.sentence ?? text
}
