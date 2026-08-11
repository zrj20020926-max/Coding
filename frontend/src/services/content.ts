import { http } from '@/services/http'
import type {
  CollectionDetail,
  CollectionPage,
  DailyChallenge,
  Discussion,
  DiscussionComment,
  DiscussionDetail,
  DiscussionPage,
} from '@/types/content'

export async function getCollections(page: number, pageSize: number): Promise<CollectionPage> {
  return (
    await http.get<CollectionPage>('/collections', {
      params: { page, page_size: pageSize },
    })
  ).data
}

export async function getCollection(
  slug: string,
  page: number,
  pageSize: number,
): Promise<CollectionDetail> {
  return (
    await http.get<CollectionDetail>(`/collections/${slug}`, {
      params: { page, page_size: pageSize },
    })
  ).data
}

export async function getDailyChallenge(): Promise<DailyChallenge> {
  return (await http.get<DailyChallenge>('/daily-challenge')).data
}

export async function getDiscussions(
  problemId: number,
  page: number,
  pageSize: number,
): Promise<DiscussionPage> {
  return (
    await http.get<DiscussionPage>(`/problems/${problemId}/discussions`, {
      params: { page, page_size: pageSize },
    })
  ).data
}

export async function createDiscussion(
  problemId: number,
  payload: { title: string; content: string },
): Promise<Discussion> {
  return (await http.post<Discussion>(`/problems/${problemId}/discussions`, payload)).data
}

export async function getDiscussion(
  discussionId: number,
  commentsPage: number,
  commentsPageSize: number,
): Promise<DiscussionDetail> {
  return (
    await http.get<DiscussionDetail>(`/discussions/${discussionId}`, {
      params: { comments_page: commentsPage, comments_page_size: commentsPageSize },
    })
  ).data
}

export async function createComment(
  discussionId: number,
  content: string,
  parentId?: number,
): Promise<DiscussionComment> {
  return (
    await http.post<DiscussionComment>(`/discussions/${discussionId}/comments`, {
      content,
      parent_id: parentId,
    })
  ).data
}

export async function editDiscussion(
  discussionId: number,
  payload: { title?: string; content?: string },
): Promise<Discussion> {
  return (await http.patch<Discussion>(`/discussions/${discussionId}`, payload)).data
}

export async function deleteDiscussion(discussionId: number): Promise<void> {
  await http.delete(`/discussions/${discussionId}`)
}

export async function editComment(commentId: number, content: string): Promise<DiscussionComment> {
  return (await http.patch<DiscussionComment>(`/comments/${commentId}`, { content })).data
}

export async function deleteComment(commentId: number): Promise<void> {
  await http.delete(`/comments/${commentId}`)
}

export async function reportContent(
  target: 'discussion' | 'comment',
  id: number,
  reason: string,
): Promise<void> {
  const path = target === 'discussion' ? `/discussions/${id}/reports` : `/comments/${id}/reports`
  await http.post(path, { reason })
}
