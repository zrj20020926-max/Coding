import { expect, test } from '@playwright/test'
import type { Page, Route } from '@playwright/test'

const user = {
  id: '11111111-1111-4111-8111-111111111111',
  username: 'candidate',
  email: 'candidate@example.com',
  nickname: '求职者',
  avatar_url: null,
  bio: null,
  solved_count: 0,
  submission_count: 0,
  accepted_count: 0,
  created_at: '2026-08-09T00:00:00Z',
}

const problemSummary = {
  id: 7,
  slug: 'a-plus-b',
  title: 'A+B 问题',
  difficulty: 'easy',
  source: 'CodeArena',
  accepted_count: 80,
  submission_count: 100,
  acceptance_rate: 80,
  tags: [{ id: 1, slug: 'math', name: '数学' }],
  solved: false,
  attempted: false,
  attempt_count: 0,
  favorited: false,
}

const problemDetail = {
  ...problemSummary,
  description: '读取两个整数并输出它们的和。',
  input_description: '一行两个整数。',
  output_description: '输出两数之和。',
  sample_input: '1 2\n',
  sample_output: '3\n',
  time_limit_ms: 1000,
  memory_limit_mb: 128,
  created_at: '2026-08-09T00:00:00Z',
  updated_at: '2026-08-09T00:00:00Z',
}

const language = {
  id: 1,
  slug: 'python',
  display_name: 'Python',
  version: '3.12',
  monaco_language: 'python',
  source_filename: 'main.py',
  sort_order: 1,
}

function submission(id: string, mode: 'sample' | 'judge') {
  return {
    id,
    problem: { id: 7, slug: 'a-plus-b', title: 'A+B 问题' },
    language: { id: 1, slug: 'python', display_name: 'Python', version: '3.12' },
    status: 'Accepted',
    mode,
    time_used_ms: 9,
    memory_used_kb: 2048,
    passed_case_count: mode === 'sample' ? 1 : 8,
    total_case_count: mode === 'sample' ? 1 : 8,
    score: '100.00',
    judged_at: '2026-08-09T00:00:01Z',
    created_at: '2026-08-09T00:00:00Z',
    updated_at: '2026-08-09T00:00:01Z',
  }
}

async function fulfillJson(route: Route, body: unknown, status = 200): Promise<void> {
  await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
}

async function mockApi(page: Page, submittedModes: string[]): Promise<void> {
  let favorited = false
  const discussion = {
    id: 42,
    problem_id: 7,
    author: { id: user.id, nickname: user.nickname, avatar_url: null },
    title: '前缀和解题讨论',
    content: '<img src=x onerror=alert(1)> **安全思路**',
    is_pinned: true,
    is_locked: false,
    comment_count: 0,
    review_status: 'approved',
    created_at: '2026-08-10T00:00:00Z',
    updated_at: '2026-08-10T00:00:00Z',
    can_edit: true,
  }
  const comments: Array<Record<string, unknown>> = []
  await page.addInitScript(() => {
    localStorage.setItem('codearena.access-token', 'e2e-access-token')
  })
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname

    if (path.endsWith('/users/me/training')) {
      return fulfillJson(route, {
        counters: { solved_count: 1, submission_count: 2, accepted_count: 1 },
        recent_submissions: [submission('judge-submission', 'judge')],
        solved_problems: [{
          id: 7,
          slug: 'a-plus-b',
          title: 'A+B 问题',
          difficulty: 'easy',
          attempt_count: 2,
          first_accepted_at: '2026-08-09T00:00:01Z',
        }],
        difficulty_stats: [
          { difficulty: 'easy', total_count: 10, attempted_count: 2, solved_count: 1 },
          { difficulty: 'medium', total_count: 5, attempted_count: 0, solved_count: 0 },
          { difficulty: 'hard', total_count: 3, attempted_count: 0, solved_count: 0 },
        ],
        tag_stats: [{
          tag: problemSummary.tags[0], total_count: 4, attempted_count: 2, solved_count: 1,
        }],
      })
    }
    if (path.endsWith('/users/me')) return fulfillJson(route, user)
    if (path.endsWith('/daily-challenge')) {
      return fulfillJson(route, {
        challenge_date: '2026-08-10',
        timezone: 'Asia/Shanghai',
        problem: problemSummary,
      })
    }
    if (path.endsWith('/collections/interview-top')) {
      return fulfillJson(route, {
        id: 1,
        slug: 'interview-top',
        title: '数组 TOP 50',
        description: '**字节高频**数组训练',
        company: '字节',
        cover_url: null,
        problem_count: 1,
        solved_count: 0,
        completion_rate: 0,
        problems: [{ sequence: 0, problem: problemSummary }],
        page: 1,
        page_size: 20,
        pages: 1,
      })
    }
    if (path.endsWith('/collections')) {
      return fulfillJson(route, {
        items: [{
          id: 1,
          slug: 'interview-top',
          title: '数组 TOP 50',
          description: '字节高频数组训练',
          company: '字节',
          cover_url: null,
          problem_count: 1,
          solved_count: 0,
          completion_rate: 0,
        }],
        total: 1,
        page: 1,
        page_size: 12,
        pages: 1,
      })
    }
    if (path.endsWith('/languages')) return fulfillJson(route, [language])
    if (path.endsWith('/tags')) return fulfillJson(route, problemSummary.tags)
    if (path.endsWith('/problems/7/favorite')) {
      favorited = request.method() === 'POST'
      return fulfillJson(route, { problem_id: 7, favorited })
    }
    if (path.endsWith('/favorites') && request.method() === 'GET') {
      return fulfillJson(route, {
        items: favorited ? [{ ...problemSummary, favorited: true }] : [],
        total: favorited ? 1 : 0,
        page: 1,
        page_size: 20,
        pages: favorited ? 1 : 0,
      })
    }
    if (path.endsWith('/problems/7/discussions')) {
      if (request.method() === 'POST') {
        const payload = request.postDataJSON() as { title: string; content: string }
        return fulfillJson(route, { ...discussion, id: 43, ...payload }, 201)
      }
      return fulfillJson(route, {
        items: [discussion], total: 1, page: 1, page_size: 10, pages: 1,
      })
    }
    if (path.endsWith('/discussions/42/comments') && request.method() === 'POST') {
      const payload = request.postDataJSON() as { content: string; parent_id?: number }
      const comment = {
        id: 51,
        discussion_id: 42,
        parent_id: payload.parent_id ?? null,
        depth: 0,
        author: discussion.author,
        content: payload.content,
        deleted: false,
        review_status: 'approved',
        created_at: '2026-08-10T00:01:00Z',
        updated_at: '2026-08-10T00:01:00Z',
        can_edit: true,
      }
      comments.push(comment)
      return fulfillJson(route, comment, 201)
    }
    if (path.endsWith('/discussions/42')) {
      return fulfillJson(route, {
        discussion: { ...discussion, comment_count: comments.length },
        comments: {
          items: comments, total: comments.length, page: 1, page_size: 30,
          pages: comments.length ? 1 : 0,
        },
      })
    }
    if (path.endsWith('/problems/7')) {
      return fulfillJson(route, { ...problemDetail, favorited })
    }
    if (path.endsWith('/problems')) {
      return fulfillJson(route, {
        items: [{ ...problemSummary, favorited }], total: 1, page: 1, page_size: 100, pages: 1,
      })
    }
    if (path.endsWith('/submissions') && request.method() === 'POST') {
      const payload = request.postDataJSON() as { mode: 'sample' | 'judge' }
      submittedModes.push(payload.mode)
      return fulfillJson(route, {
        ...submission(`${payload.mode}-submission`, payload.mode),
        status: 'Pending',
        time_used_ms: null,
        memory_used_kb: null,
        passed_case_count: 0,
        total_case_count: 0,
        judged_at: null,
        idempotent_replay: false,
      }, 202)
    }
    const match = path.match(/\/submissions\/(sample|judge)-submission(\/status)?$/)
    if (match) {
      const mode = match[1] as 'sample' | 'judge'
      const result = submission(`${mode}-submission`, mode)
      return fulfillJson(route, match[2] ? result : {
        ...result,
        source_code: 'print(sum(map(int, input().split())))',
        compiler_output: null,
        error_message: null,
        sample_output: mode === 'sample' ? '3\n' : null,
      })
    }
    if (path.endsWith('/submissions') && request.method() === 'GET') {
      return fulfillJson(route, {
        items: [submission('judge-submission', 'judge')],
        total: 1,
        page: 1,
        page_size: 20,
        pages: 1,
      })
    }
    return fulfillJson(route, { detail: { code: 'not_found', message: path } }, 404)
  })
}

test('home does not load Monaco and the problem page completes sample and judge flows', async ({ page }) => {
  const submittedModes: string[] = []
  await mockApi(page, submittedModes)

  await page.goto('/')
  await expect(page.getByRole('link', { name: '题库', exact: true }).first()).toBeVisible()
  expect(await page.evaluate(() => performance.getEntriesByType('resource')
    .some((entry) => entry.name.toLowerCase().includes('monaco')))).toBe(false)

  await page.goto('/problems/a-plus-b')
  await expect(page.getByRole('heading', { name: 'A+B 问题' })).toBeVisible()
  await expect(page.locator('.monaco-editor')).toBeVisible({ timeout: 30_000 })

  await page.getByRole('button', { name: '运行公开样例' }).click()
  const programOutput = page.locator('.diagnostic-block').filter({ hasText: '程序输出' })
  await expect(programOutput).toBeVisible()
  await expect(programOutput.locator('code')).toHaveText('3')

  await page.getByRole('button', { name: '正式提交' }).click()
  await expect.poll(() => submittedModes).toEqual(['sample', 'judge'])
  await expect(page.getByText('8 / 8')).toBeVisible()
})

test('personal history opens a safe submission detail', async ({ page }) => {
  await mockApi(page, [])

  await page.goto('/submissions')
  await expect(page.getByRole('heading', { name: '提交记录' })).toBeVisible()
  await page.getByRole('link', { name: /A\+B 问题/ }).click()
  await expect(page.getByRole('heading', { name: '提交代码' })).toBeVisible()
  await expect(page.getByText('print(sum(map(int, input().split())))')).toBeVisible()
  await expect(page.locator('body')).not.toContainText('object_key')
})

test('favorite catalog flow and training profile stay user scoped', async ({ page }) => {
  await mockApi(page, [])

  await page.goto('/problems')
  await page.getByRole('button', { name: '收藏 A+B 问题' }).click()
  await expect(page.getByRole('button', { name: '取消收藏 A+B 问题' })).toBeVisible()

  await page.goto('/favorites')
  await expect(page.getByRole('heading', { name: '我的收藏' })).toBeVisible()
  await expect(page.getByRole('link', { name: /A\+B 问题/ })).toBeVisible()
  await page.getByRole('button', { name: '取消收藏 A+B 问题' }).click()
  await expect(page.getByText('还没有收藏题目')).toBeVisible()

  await page.goto('/profile')
  await expect(page.getByRole('heading', { name: '难度进度' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '标签统计' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '最近提交' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '已解决题目' })).toBeVisible()
  await expect(page.getByText('数学')).toBeVisible()
})

test('daily challenge, curated collection and sanitized discussion flow', async ({ page }) => {
  await mockApi(page, [])

  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'A+B 问题' })).toBeVisible()
  await expect(page.getByText('2026-08-10 · Asia/Shanghai')).toBeVisible()

  await page.goto('/collections')
  await page.getByRole('link', { name: /数组 TOP 50/ }).click()
  await expect(page.getByRole('heading', { name: '数组 TOP 50' })).toBeVisible()
  await expect(page.getByRole('link', { name: /A\+B 问题/ })).toBeVisible()

  await page.goto('/problems/a-plus-b')
  await expect(page.getByRole('heading', { name: '题目讨论' })).toBeVisible()
  await page.getByRole('button', { name: '发起讨论' }).click()
  await page.getByLabel('标题').fill('新的解题讨论')
  await page.getByLabel('内容（支持 Markdown）').fill('使用 **哈希表**')
  await page.getByRole('button', { name: '发布讨论' }).click()
  await expect(page.getByRole('heading', { name: '新的解题讨论' })).toBeVisible()

  await page.goto('/discussions/42')
  await expect(page.getByRole('heading', { name: '前缀和解题讨论' })).toBeVisible()
  await expect(page.getByText('安全思路')).toBeVisible()
  await expect(page.locator('.discussion-thread img')).toHaveCount(0)
  await page.getByPlaceholder('友善讨论，支持 Markdown').fill('边界条件也很重要')
  await page.getByRole('button', { name: '发表评论' }).click()
  await expect(page.getByText('边界条件也很重要')).toBeVisible()
})
