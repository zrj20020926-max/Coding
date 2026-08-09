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
  await page.addInitScript(() => {
    localStorage.setItem('codearena.access-token', 'e2e-access-token')
  })
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname

    if (path.endsWith('/users/me')) return fulfillJson(route, user)
    if (path.endsWith('/languages')) return fulfillJson(route, [language])
    if (path.endsWith('/tags')) return fulfillJson(route, problemSummary.tags)
    if (path.endsWith('/problems/7')) return fulfillJson(route, problemDetail)
    if (path.endsWith('/problems')) {
      return fulfillJson(route, {
        items: [problemSummary], total: 1, page: 1, page_size: 100, pages: 1,
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
