import {
  expect,
  getExerciseProgress,
  readReference,
  registerThroughApi,
  replaceEditorSource,
  submitAndWait,
  test,
} from './support'

test('Node.js handles raw stdin formats and updates runtime-specific progress', async ({ page }) => {
  const { token } = await registerThroughApi(page, 'e2e_node')
  await page.goto('/problems/js-acm-read-one-integer')
  await page.locator('.runtime-switcher').getByText('Node.js', { exact: true }).click()
  await expect(page.getByText("fs.readFileSync(0, 'utf8')", { exact: true }).first()).toBeVisible()
  await replaceEditorSource(
    page,
    "const fs = require('fs');\nconst raw = fs.readFileSync(0, 'utf8');\nconsole.log(Number(raw) + 1);\n",
  )
  await page.getByRole('button', { name: '正式提交' }).click()
  await expect(page.locator('.judge-result .submission-status')).toHaveText('通过', {
    timeout: 180_000,
  })

  const curriculum = [
    'js-acm-handle-empty-input',
    'js-acm-multi-line-with-empty',
    'js-acm-crlf-lf-compatible',
    'js-acm-t-one-line',
    'js-acm-node-line-cursor-eof',
    'js-acm-integer-matrix-nm',
    'js-acm-read-bigint',
    'js-acm-one-hundred-thousand-integers',
  ]
  for (const slug of curriculum) {
    const result = await submitAndWait(page, token, slug, 'nodejs')
    expect(result.status, slug).toBe('Accepted')
    expect((await getExerciseProgress(page, token, slug)).nodejs_completed, slug).toBe(true)
  }
  const firstProgress = await getExerciseProgress(page, token, 'js-acm-read-one-integer')
  expect(firstProgress.nodejs_completed).toBe(true)
})

test('stdout curriculum accepts precise formats and rejects debug or wrong spaces', async ({ page }) => {
  const { token } = await registerThroughApi(page, 'e2e_output')
  const acceptedSlugs = [
    'js-acm-output-array-space-join',
    'js-acm-output-value-per-line',
    'js-acm-output-case-hash-format',
    'js-acm-output-fixed-two-decimals',
    'js-acm-output-bigint-without-suffix',
    'js-acm-output-matrix-row-output',
    'js-acm-output-blank-between-groups',
    'js-acm-output-many-results-buffer',
  ]
  for (const slug of acceptedSlugs) {
    const result = await submitAndWait(page, token, slug, 'nodejs')
    expect(result.status, slug).toBe('Accepted')
  }

  const debugSlug = 'js-acm-output-no-debug-output'
  const debugSource = `process.stdout.write('debug: extra\\n');\n${readReference(debugSlug, 'nodejs')}`
  expect((await submitAndWait(page, token, debugSlug, 'nodejs', debugSource)).status)
    .toBe('Wrong Answer')

  const spacesSlug = 'js-acm-output-values-single-space'
  const correct = readReference(spacesSlug, 'nodejs')
  const wrongSpaces = correct.replace("tokens.join(' ')", "tokens.join('  ')")
  expect(wrongSpaces).not.toBe(correct)
  expect((await submitAndWait(page, token, spacesSlug, 'nodejs', wrongSpaces)).status)
    .toBe('Wrong Answer')
})
