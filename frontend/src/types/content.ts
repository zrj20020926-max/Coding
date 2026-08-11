import type { ProblemSummary } from '@/types/problem'

export type ReviewStatus = 'pending' | 'approved' | 'rejected'

export interface CollectionSummary {
  id: number
  slug: string
  title: string
  description: string | null
  company: string | null
  cover_url: string | null
  problem_count: number
  solved_count?: number
  completion_rate?: number
}

export interface CollectionPage {
  items: CollectionSummary[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface CollectionProblem {
  sequence: number
  problem: ProblemSummary
}

export interface CollectionDetail extends CollectionSummary {
  problems: CollectionProblem[]
  page: number
  page_size: number
  pages: number
}

export interface DailyChallenge {
  challenge_date: string
  timezone: string
  problem: ProblemSummary
}

export interface ContentAuthor {
  id: string
  nickname: string
  avatar_url: string | null
}

export interface Discussion {
  id: number
  problem_id: number
  author: ContentAuthor | null
  title: string
  content: string
  is_pinned: boolean
  is_locked: boolean
  comment_count: number
  review_status: ReviewStatus
  created_at: string
  updated_at: string
  can_edit: boolean
}

export interface DiscussionPage {
  items: Discussion[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface DiscussionComment {
  id: number
  discussion_id: number
  parent_id: number | null
  depth: number
  author: ContentAuthor | null
  content: string
  deleted: boolean
  review_status: ReviewStatus
  created_at: string
  updated_at: string
  can_edit: boolean
}

export interface CommentPage {
  items: DiscussionComment[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface DiscussionDetail {
  discussion: Discussion
  comments: CommentPage
}
