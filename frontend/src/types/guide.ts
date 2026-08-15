export type GuideRuntime = 'javascript-v8' | 'nodejs'
export type GuideSectionSlug =
  | 'javascript-v8'
  | 'nodejs'
  | 'input-patterns'
  | 'output-patterns'
  | 'common-errors'
  | 'performance'

export interface GuideCodeExample {
  id: string
  title: string
  runtime: GuideRuntime
  code: string
  targetSlug: string
  note?: string
  variant?: 'recommended' | 'incorrect'
}

export interface GuideTopic {
  id: string
  title: string
  summary: string
  keywords: string[]
  examples: GuideCodeExample[]
}

export interface GuideSection {
  slug: GuideSectionSlug
  title: string
  eyebrow: string
  description: string
  topics: GuideTopic[]
}

export interface GuideSearchResult {
  section: GuideSection
  topic: GuideTopic
}
