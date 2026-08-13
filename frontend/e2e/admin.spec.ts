import { expect, test } from '@playwright/test'

const user = {
  id: '00000000-0000-0000-0000-000000000001', username: 'operator', email: 'operator@example.com',
  nickname: '内容管理员', avatar_url: null, bio: null, is_admin: true, solved_count: 0,
  submission_count: 0, accepted_count: 0, created_at: '2026-08-12T00:00:00Z',
}
const problem = {
  id: 1, slug: 'admin-demo', title: '管理演示题', difficulty: 'easy', source: null,
  accepted_count: 0, submission_count: 0, acceptance_rate: 0, tags: [], description: '题目描述',
  input_description: '输入', output_description: '输出', data_constraints: '1 <= n <= 10',
  sample_input: '1', sample_output: '1', sample_explanation: '解释', time_limit_ms: 1000,
  memory_limit_mb: 256, created_at: '2026-08-12T00:00:00Z', updated_at: '2026-08-12T00:00:00Z',
  visibility: 'draft', created_by: user.id,
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('codearena.access-token', 'e2e-admin-token'))
  await page.route('**/api/v1/users/me', (route) => route.fulfill({ json: user }))
  await page.route('**/api/v1/problems/tags', (route) => route.fulfill({ json: [] }))
  await page.route('**/api/v1/admin/problems?**', (route) => route.fulfill({ json: { items: [problem], total: 1, page: 1, page_size: 20, pages: 1 } }))
  await page.route('**/api/v1/admin/problems/1/test-sets', (route) => route.fulfill({ json: [] }))
  await page.route('**/api/v1/admin/problems/1/readiness', (route) => route.fulfill({ json: { ready: false, issues: [{ code: 'NO_ACTIVE_TEST_SET', message: '题目缺少活动测试集' }] } }))
  await page.route('**/api/v1/admin/problems/1', (route) => route.fulfill({ json: problem }))
})

test('administrator navigates from dashboard to problem editor and sees publish gate', async ({ page }) => {
  await page.goto('/admin')
  await expect(page.getByRole('heading', { name: '管理控制台' })).toBeVisible()
  await page.getByRole('link', { name: '题目管理' }).first().click()
  await expect(page.getByRole('heading', { name: '题目管理' })).toBeVisible()
  await page.getByRole('button', { name: '编辑' }).click()
  await expect(page.getByText('NO_ACTIVE_TEST_SET')).toBeVisible()
  await expect(page.getByText('题目缺少活动测试集')).toBeVisible()
})
