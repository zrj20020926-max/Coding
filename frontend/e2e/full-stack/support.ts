import { randomUUID } from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { expect, test as base } from '@playwright/test'
import type { APIResponse, Page } from '@playwright/test'

export const TERMINAL_STATUSES = new Set([
  'Accepted',
  'Wrong Answer',
  'Compile Error',
  'Runtime Error',
  'Time Limit Exceeded',
  'Memory Limit Exceeded',
  'Output Limit Exceeded',
  'System Error',
])

export type RuntimeSlug = 'javascript-v8' | 'nodejs'

export interface ProblemDetail {
  id: number
  slug: string
  title: string
  sample_input: string
  sample_output: string
  starter_code_v8: string
  starter_code_nodejs: string
}

export interface SubmissionSummary {
  id: string
  status: string
  mode: 'sample' | 'custom' | 'judge'
  passed_case_count: number
  total_case_count: number
}

interface ExerciseProgress {
  progress?: {
    attempt_count: number
    v8_attempt_count: number
    nodejs_attempt_count: number
    v8_completed: boolean
    nodejs_completed: boolean
  }
}

const repositoryRoot = resolve(dirname(fileURLToPath(import.meta.url)), '../../..')
const composeProject = process.env['FULL_STACK_COMPOSE_PROJECT'] ?? 'codearena-full-stack-e2e'

export const test = base.extend<{ safeFailureArtifact: void }>({
  safeFailureArtifact: [
    async ({ page }, use, testInfo) => {
      await use()
      if (testInfo.status === testInfo.expectedStatus || page.isClosed()) return
      try {
        await page.setContent(
          `<main><h1>Full-stack E2E failed</h1><p>${escapeHtml(testInfo.title)}</p></main>`,
        )
        await page.screenshot({ path: testInfo.outputPath('failure-summary.png'), fullPage: true })
      } catch {
        // Artifact collection must not mask the original test failure.
      }
    },
    { auto: true },
  ],
})

export { expect }

function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (character) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  })[character] ?? character)
}

function requireOk(response: APIResponse, operation: string): void {
  if (!response.ok()) {
    throw new Error(`${operation} failed with HTTP ${response.status()}`)
  }
}

export async function registerAndLoginThroughBrowser(
  page: Page,
  prefix: string,
): Promise<{ username: string; password: string; token: string }> {
  const suffix = `${Date.now()}_${randomUUID().slice(0, 8)}`
  const username = `${prefix}_${suffix}`.slice(0, 32)
  const password = `E2e-${randomUUID()}-Aa1!`
  await page.goto('/register')
  await page.getByLabel('昵称').fill('全栈训练用户')
  await page.getByLabel('用户名').fill(username)
  await page.getByLabel('邮箱').fill(`${username}@example.com`)
  await page.getByLabel('密码', { exact: true }).fill(password)
  await page.getByLabel('确认密码').fill(password)
  await page.getByRole('button', { name: '创建账号' }).click()
  await expect(page).toHaveURL(/\/profile$/)

  await page.getByRole('button', { name: '退出', exact: true }).click()
  await expect(page.getByRole('link', { name: '登录', exact: true })).toBeVisible()
  await page.goto('/login')
  await page.getByLabel('用户名或邮箱').fill(username)
  await page.getByLabel('密码').fill(password)
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page).toHaveURL(/\/profile$/)
  const token = await page.evaluate(() => localStorage.getItem('codearena.access-token') ?? '')
  expect(token).not.toBe('')
  return { username, password, token }
}

export async function registerThroughApi(
  page: Page,
  prefix: string,
): Promise<{ token: string; userId: string }> {
  const suffix = `${Date.now()}_${randomUUID().slice(0, 8)}`
  const username = `${prefix}_${suffix}`.slice(0, 32)
  const password = `E2e-${randomUUID()}-Aa1!`
  const response = await page.request.post('/api/v1/auth/register', {
    data: {
      username,
      email: `${username}@example.com`,
      password,
      nickname: '全栈 API 用户',
    },
  })
  requireOk(response, 'register')
  const body = await response.json() as { access_token: string; user: { id: string } }
  await page.goto('/')
  await page.evaluate(
    (token) => localStorage.setItem('codearena.access-token', token),
    body.access_token,
  )
  await page.reload()
  return { token: body.access_token, userId: body.user.id }
}

function authorization(token: string): Record<string, string> {
  return { Authorization: `Bearer ${token}` }
}

export async function getProblem(page: Page, slug: string): Promise<ProblemDetail> {
  const response = await page.request.get(`/api/v1/problems/${slug}`)
  requireOk(response, `load problem ${slug}`)
  return await response.json() as ProblemDetail
}

export function readReference(slug: string, runtime: RuntimeSlug): string {
  const courseDirectory = slug.startsWith('js-acm-output-')
    ? 'js-acm-output'
    : 'js-acm'
  const filename = runtime === 'javascript-v8' ? 'solution-v8.js' : 'solution-nodejs.js'
  return readFileSync(
    resolve(repositoryRoot, 'content', 'reference-solutions', courseDirectory, slug, filename),
    'utf8',
  )
}

export async function submitAndWait(
  page: Page,
  token: string,
  slug: string,
  runtime: RuntimeSlug,
  source = readReference(slug, runtime),
  mode: 'judge' | 'custom' = 'judge',
  customInput?: string,
): Promise<SubmissionSummary> {
  const created = await createSubmission(
    page, token, slug, runtime, source, mode, customInput,
  )
  return await waitForSubmission(page, token, created.id)
}

export async function createSubmission(
  page: Page,
  token: string,
  slug: string,
  runtime: RuntimeSlug,
  source = readReference(slug, runtime),
  mode: 'judge' | 'custom' = 'judge',
  customInput?: string,
): Promise<SubmissionSummary> {
  const problem = await getProblem(page, slug)
  const response = await page.request.post('/api/v1/submissions', {
    headers: {
      ...authorization(token),
      'Idempotency-Key': `full-stack-${randomUUID()}`,
    },
    data: {
      problem_id: problem.id,
      language: runtime,
      source_code: source,
      mode,
      ...(mode === 'custom' ? { custom_input: customInput ?? problem.sample_input } : {}),
    },
  })
  requireOk(response, `submit ${slug}/${runtime}`)
  return await response.json() as SubmissionSummary
}

export async function waitForSubmission(
  page: Page,
  token: string,
  submissionId: string,
  timeoutMs = 180_000,
): Promise<SubmissionSummary> {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    const response = await page.request.get(`/api/v1/submissions/${submissionId}/status`, {
      headers: authorization(token),
    })
    requireOk(response, 'poll submission')
    const summary = await response.json() as SubmissionSummary
    if (TERMINAL_STATUSES.has(summary.status)) return summary
    await new Promise((resolvePromise) => setTimeout(resolvePromise, 500))
  }
  throw new Error('submission polling timed out')
}

export async function getExerciseProgress(
  page: Page,
  token: string,
  slug: string,
): Promise<NonNullable<ExerciseProgress['progress']>> {
  const response = await page.request.get(`/api/v1/exercises/${slug}`, {
    headers: authorization(token),
  })
  requireOk(response, `load exercise progress ${slug}`)
  const body = await response.json() as ExerciseProgress
  if (!body.progress) throw new Error('authenticated exercise progress is missing')
  return body.progress
}

export async function replaceEditorSource(page: Page, source: string): Promise<void> {
  const editor = page.getByTestId('code-editor')
  await expect(editor).toBeVisible({ timeout: 60_000 })
  await editor.click()
  await page.keyboard.press('Control+A')
  await page.keyboard.insertText(source)
  // Monaco virtualizes lines outside the viewport. Return to the first line so
  // the assertion observes rendered text even for long reference solutions.
  await page.keyboard.press('Control+Home')
  await expect(page.locator('.view-lines')).toContainText(source.split('\n')[0] ?? '')
}

export function compose(...args: string[]): string {
  return execFileSync(
    'docker',
    [
      'compose',
      '-p',
      composeProject,
      '-f',
      'docker-compose.content-test.yml',
      ...args,
    ],
    {
      cwd: repositoryRoot,
      encoding: 'utf8',
      env: { ...process.env, FULL_STACK_FRONTEND_PORT: process.env['FULL_STACK_FRONTEND_PORT'] ?? '18080' },
    },
  )
}

export function publishDuplicateSubmissionMessage(submissionId: string): void {
  compose(
    'exec',
    '-T',
    'redis-content-test',
    'redis-cli',
    'XADD',
    'codearena:judge:content-acceptance',
    '*',
    'payload',
    JSON.stringify({ submission_id: submissionId }),
  )
}
