import {
  expect,
  getExerciseProgress,
  registerAndLoginThroughBrowser,
  replaceEditorSource,
  submitAndWait,
  test,
} from './support'

test('JavaScript V8 completes real sample, judge, runtime failure and curriculum progress', async ({ page }) => {
  const { token } = await registerAndLoginThroughBrowser(page, 'e2e_v8')
  await page.goto('/problems/js-acm-read-one-integer')
  await replaceEditorSource(
    page,
    'const value = Number(readline());\nprint(value + 1);\n',
  )
  await page.getByRole('button', { name: '运行公开样例' }).click()
  await expect(page.locator('.judge-result .submission-status')).toHaveText('通过', {
    timeout: 180_000,
  })
  await expect(page.getByText('期望 stdout')).toBeVisible()
  await expect(page.getByText('实际 stdout')).toBeVisible()

  await page.getByRole('button', { name: '正式提交' }).click()
  await expect(page.locator('.judge-result .submission-status')).toHaveText('通过', {
    timeout: 180_000,
  })
  await expect(page.getByText('隐藏测试输入和标准输出不会返回浏览器')).toBeVisible()

  await replaceEditorSource(page, "const fs = require('fs');\nprint(fs.readFileSync(0, 'utf8'));\n")
  await page.getByRole('button', { name: '正式提交' }).click()
  await expect(page.locator('.judge-result .submission-status')).toHaveText('运行错误', {
    timeout: 180_000,
  })
  await expect(page.getByText(/require is unavailable/)).toBeVisible()

  const curriculum = [
    'js-acm-fixed-three-lines',
    'js-acm-t-one-line',
    'js-acm-line-until-eof',
    'js-acm-integer-matrix-nm',
    'js-acm-read-bigint',
  ]
  for (const slug of curriculum) {
    const result = await submitAndWait(page, token, slug, 'javascript-v8')
    expect(result.status, slug).toBe('Accepted')
    expect((await getExerciseProgress(page, token, slug)).v8_completed, slug).toBe(true)
  }
  const firstProgress = await getExerciseProgress(page, token, 'js-acm-read-one-integer')
  expect(firstProgress.v8_completed).toBe(true)
  expect(firstProgress.v8_attempt_count).toBe(2)
})
