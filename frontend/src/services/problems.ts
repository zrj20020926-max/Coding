import { http } from '@/services/http'
import type { ProblemDetail, ProblemListParams, ProblemPage, ProblemTag } from '@/types/problem'

export class ProblemNotFoundError extends Error {
  constructor(slug: string) {
    super(`题目 ${slug} 不存在或尚未发布`)
    this.name = 'ProblemNotFoundError'
  }
}

export async function getProblems(params: ProblemListParams): Promise<ProblemPage> {
  const { data } = await http.get<ProblemPage>('/problems', { params })
  return data
}

export async function getProblemTags(): Promise<ProblemTag[]> {
  const { data } = await http.get<ProblemTag[]>('/tags')
  return data
}

export async function getProblemBySlug(slug: string): Promise<ProblemDetail> {
  let pageNumber = 1
  let matchId: number | undefined
  do {
    const page = await getProblems({
      q: slug,
      page: pageNumber,
      page_size: 100,
      sort: 'newest',
    })
    matchId = page.items.find((problem) => problem.slug === slug)?.id
    if (matchId !== undefined || pageNumber >= page.pages) break
    pageNumber += 1
  } while (matchId === undefined)

  if (matchId === undefined) throw new ProblemNotFoundError(slug)
  const { data } = await http.get<ProblemDetail>(`/problems/${matchId}`)
  return data
}
