import { ref } from 'vue'
import { defineStore } from 'pinia'

import {
  createComment,
  createDiscussion,
  deleteComment,
  deleteDiscussion,
  editComment,
  editDiscussion,
  getCollection,
  getCollections,
  getDailyChallenge,
  getDiscussion,
  getDiscussions,
  reportContent,
} from '@/services/content'
import { getApiErrorMessage } from '@/services/http'
import type {
  CollectionDetail,
  CollectionSummary,
  DailyChallenge,
  Discussion,
  DiscussionComment,
  DiscussionDetail,
} from '@/types/content'

export const useContentStore = defineStore('content', () => {
  const collections = ref<CollectionSummary[]>([])
  const collectionsTotal = ref(0)
  const collectionsLoading = ref(false)
  const collectionsError = ref('')
  const collection = ref<CollectionDetail | null>(null)
  const collectionLoading = ref(false)
  const collectionError = ref('')
  const daily = ref<DailyChallenge | null>(null)
  const dailyLoading = ref(false)
  const discussions = ref<Discussion[]>([])
  const discussionsTotal = ref(0)
  const discussionsLoading = ref(false)
  const discussionsError = ref('')
  const discussionDetail = ref<DiscussionDetail | null>(null)
  const discussionLoading = ref(false)
  const discussionError = ref('')

  async function loadCollections(page: number, pageSize: number): Promise<void> {
    collectionsLoading.value = true
    collectionsError.value = ''
    try {
      const result = await getCollections(page, pageSize)
      collections.value = result.items
      collectionsTotal.value = result.total
    } catch (error) {
      collections.value = []
      collectionsError.value = getApiErrorMessage(error, '题单加载失败')
    } finally {
      collectionsLoading.value = false
    }
  }

  async function loadCollection(slug: string, page: number, pageSize: number): Promise<void> {
    collectionLoading.value = true
    collectionError.value = ''
    try {
      collection.value = await getCollection(slug, page, pageSize)
    } catch (error) {
      collection.value = null
      collectionError.value = getApiErrorMessage(error, '题单详情加载失败')
    } finally {
      collectionLoading.value = false
    }
  }

  async function loadDaily(): Promise<void> {
    dailyLoading.value = true
    try {
      daily.value = await getDailyChallenge()
    } catch {
      daily.value = null
    } finally {
      dailyLoading.value = false
    }
  }

  async function loadDiscussions(problemId: number, page: number, pageSize: number): Promise<void> {
    discussionsLoading.value = true
    discussionsError.value = ''
    try {
      const result = await getDiscussions(problemId, page, pageSize)
      discussions.value = result.items
      discussionsTotal.value = result.total
    } catch (error) {
      discussions.value = []
      discussionsError.value = getApiErrorMessage(error, '讨论加载失败')
    } finally {
      discussionsLoading.value = false
    }
  }

  async function addDiscussion(problemId: number, title: string, content: string): Promise<Discussion> {
    const created = await createDiscussion(problemId, { title, content })
    discussions.value = [created, ...discussions.value]
    discussionsTotal.value += 1
    return created
  }

  async function loadDiscussion(id: number, page: number, pageSize: number): Promise<void> {
    discussionLoading.value = true
    discussionError.value = ''
    try {
      discussionDetail.value = await getDiscussion(id, page, pageSize)
    } catch (error) {
      discussionDetail.value = null
      discussionError.value = getApiErrorMessage(error, '讨论详情加载失败')
    } finally {
      discussionLoading.value = false
    }
  }

  async function addComment(content: string, parentId?: number): Promise<DiscussionComment> {
    if (!discussionDetail.value) throw new Error('discussion is not loaded')
    const created = await createComment(discussionDetail.value.discussion.id, content, parentId)
    discussionDetail.value.comments.items.push(created)
    discussionDetail.value.comments.total += 1
    if (created.review_status === 'approved') {
      discussionDetail.value.discussion.comment_count += 1
    }
    return created
  }

  async function updateCurrentDiscussion(title: string, content: string): Promise<void> {
    if (!discussionDetail.value) return
    discussionDetail.value.discussion = await editDiscussion(
      discussionDetail.value.discussion.id,
      { title, content },
    )
  }

  async function removeCurrentDiscussion(): Promise<void> {
    if (!discussionDetail.value) return
    await deleteDiscussion(discussionDetail.value.discussion.id)
  }

  async function updateCurrentComment(commentId: number, content: string): Promise<void> {
    const updated = await editComment(commentId, content)
    if (!discussionDetail.value) return
    discussionDetail.value.comments.items = discussionDetail.value.comments.items.map((comment) =>
      comment.id === commentId ? updated : comment,
    )
  }

  async function removeCurrentComment(commentId: number): Promise<void> {
    await deleteComment(commentId)
    if (!discussionDetail.value) return
    const comment = discussionDetail.value.comments.items.find((item) => item.id === commentId)
    if (comment) {
      comment.deleted = true
      comment.content = '[该评论已删除]'
      comment.can_edit = false
    }
  }

  return {
    collections,
    collectionsTotal,
    collectionsLoading,
    collectionsError,
    collection,
    collectionLoading,
    collectionError,
    daily,
    dailyLoading,
    discussions,
    discussionsTotal,
    discussionsLoading,
    discussionsError,
    discussionDetail,
    discussionLoading,
    discussionError,
    loadCollections,
    loadCollection,
    loadDaily,
    loadDiscussions,
    addDiscussion,
    loadDiscussion,
    addComment,
    updateCurrentDiscussion,
    removeCurrentDiscussion,
    updateCurrentComment,
    removeCurrentComment,
    reportContent,
  }
})
