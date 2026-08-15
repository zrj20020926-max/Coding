import {
  compose,
  createSubmission,
  expect,
  getExerciseProgress,
  getProblem,
  publishDuplicateSubmissionMessage,
  readReference,
  registerThroughApi,
  replaceEditorSource,
  submitAndWait,
  test,
  waitForSubmission,
} from './support'

test('drafts, custom runs, duplicate messages and hidden data remain isolated', async ({ page }) => {
  const { token } = await registerThroughApi(page, 'e2e_isolation')
  const slug = 'js-acm-two-integers'
  await page.goto(`/problems/${slug}`)
  await replaceEditorSource(page, 'const v8DraftMarker = readline();\nprint(v8DraftMarker);\n')
  await page.waitForTimeout(700)
  await page.locator('.runtime-switcher').getByText('Node.js', { exact: true }).click()
  await replaceEditorSource(
    page,
    "const nodeDraftMarker = require('fs').readFileSync(0, 'utf8');\nconsole.log(nodeDraftMarker);\n",
  )
  await page.waitForTimeout(700)
  await page.locator('.runtime-switcher').getByText('JavaScript V8', { exact: true }).click()
  await expect(page.locator('.view-lines')).toContainText('v8DraftMarker')
  await page.reload()
  await expect(page.locator('.view-lines')).toContainText('v8DraftMarker', { timeout: 60_000 })
  await page.locator('.runtime-switcher').getByText('Node.js', { exact: true }).click()
  await expect(page.locator('.view-lines')).toContainText('nodeDraftMarker')

  const beforeCustom = await getExerciseProgress(page, token, slug)
  const problem = await getProblem(page, slug)
  const custom = await submitAndWait(
    page,
    token,
    slug,
    'nodejs',
    readReference(slug, 'nodejs'),
    'custom',
    problem.sample_input,
  )
  expect(custom.status).toBe('Accepted')
  const afterCustom = await getExerciseProgress(page, token, slug)
  expect(afterCustom.attempt_count).toBe(beforeCustom.attempt_count)

  const judged = await submitAndWait(page, token, slug, 'nodejs')
  expect(judged.status).toBe('Accepted')
  const afterJudge = await getExerciseProgress(page, token, slug)
  publishDuplicateSubmissionMessage(judged.id)
  await page.waitForTimeout(12_000)
  const afterDuplicate = await getExerciseProgress(page, token, slug)
  expect(afterDuplicate.attempt_count).toBe(afterJudge.attempt_count)

  const hiddenMetadata = await page.request.get(
    `/api/v1/admin/problems/${problem.id}/test-sets`,
    { headers: { Authorization: `Bearer ${token}` } },
  )
  expect(hiddenMetadata.status()).toBe(403)
  const publicDetail = await page.request.get(`/api/v1/problems/${slug}`)
  const serialized = JSON.stringify(await publicDetail.json())
  for (const field of ['input_object_key', 'output_object_key', 'checksum', 'test_cases']) {
    expect(serialized).not.toContain(field)
  }
})

test('active submission survives refresh, network outage and worker restart', async ({ page, context }) => {
  const { token } = await registerThroughApi(page, 'e2e_recovery')
  const slug = 'js-acm-read-negative-number'
  const before = await getExerciseProgress(page, token, slug)
  compose('stop', 'judge-service-content-test')
  try {
    await page.goto(`/problems/${slug}`)
    await replaceEditorSource(page, readReference(slug, 'javascript-v8'))
    await page.getByRole('button', { name: '正式提交' }).click()
    await expect(page.locator('.judge-result .submission-status')).toHaveText('等待判题')
    expect((await getExerciseProgress(page, token, slug)).attempt_count)
      .toBe(before.attempt_count)

    const detailLink = page.locator('.submission-detail-link')
    await expect(detailLink).toBeVisible()
    const submissionId = (await detailLink.getAttribute('href'))?.split('/').pop()
    expect(submissionId).toBeTruthy()

    await page.reload()
    await expect(page.locator('.judge-result .submission-status')).toHaveText('等待判题')
    await context.setOffline(true)
    await expect(page.getByText(/网络已断开/)).toBeVisible({ timeout: 10_000 })
    await context.setOffline(false)
    compose('up', '-d', '--no-deps', 'judge-service-content-test')

    const terminal = await waitForSubmission(page, token, submissionId ?? '', 240_000)
    expect(terminal.status).toBe('Accepted')
    await expect(page.locator('.judge-result .submission-status')).toHaveText('通过', {
      timeout: 30_000,
    })
    const after = await getExerciseProgress(page, token, slug)
    expect(after.attempt_count).toBe(before.attempt_count + 1)
  } finally {
    try {
      compose('up', '-d', '--no-deps', 'judge-service-content-test')
    } catch { /* best effort */ }
  }
})

test('controlled System Error does not count as a user attempt', async ({ page }) => {
  const { token } = await registerThroughApi(page, 'e2e_system_error')
  const slug = 'js-acm-read-one-integer'
  const before = await getExerciseProgress(page, token, slug)
  let submissionId = ''
  compose('stop', 'judge-service-content-test')
  try {
    const created = await createSubmission(page, token, slug, 'nodejs')
    submissionId = created.id
    compose(
      'exec',
      '-T',
      'postgres-content-test',
      'psql',
      '-U',
      'content_test',
      '-d',
      'codearena_content_test',
      '-c',
      "INSERT INTO languages (slug,display_name,version,monaco_language,source_filename," +
        "runtime_mode,input_api,output_api,eof_value,compile_command,run_command,docker_image," +
        "enabled,sort_order) SELECT 'e2e-unsupported','E2E Unsupported',version," +
        "monaco_language,source_filename,runtime_mode,input_api,output_api,eof_value," +
        "compile_command,run_command,docker_image,false,999 FROM languages WHERE slug='nodejs' " +
        "ON CONFLICT (slug) DO NOTHING; " +
        `UPDATE submissions SET language_id=(SELECT id FROM languages WHERE slug=` +
        `'e2e-unsupported') WHERE id='${created.id}'`,
    )
    compose('up', '-d', '--no-deps', 'judge-service-content-test')
    const terminal = await waitForSubmission(page, token, created.id, 240_000)
    expect(terminal.status).toBe('System Error')
    const after = await getExerciseProgress(page, token, slug)
    expect(after.attempt_count).toBe(before.attempt_count)
    expect(after.nodejs_attempt_count).toBe(before.nodejs_attempt_count)
  } finally {
    const restoreSubmission = submissionId
      ? `UPDATE submissions SET language_id=(SELECT id FROM languages WHERE slug='nodejs') ` +
        `WHERE id='${submissionId}'; `
      : ''
    compose(
      'exec',
      '-T',
      'postgres-content-test',
      'psql',
      '-U',
      'content_test',
      '-d',
      'codearena_content_test',
      '-c',
      `${restoreSubmission}DELETE FROM languages WHERE slug='e2e-unsupported'`,
    )
    try {
      compose('up', '-d', '--no-deps', 'judge-service-content-test')
    } catch { /* best effort */ }
  }
})
