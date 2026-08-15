import { expect, test } from './support'

interface ProblemSummary { slug: string }
interface ProblemPage {
  items: ProblemSummary[]
  pages: number
  total: number
}
interface CourseSummary { slug: string; type: string; exercise_count: number }

test('empty stack exposes imported input, output, comprehensive courses and guide', async ({ page }) => {
  const coursesResponse = await page.request.get('/api/v1/courses')
  expect(coursesResponse.ok()).toBe(true)
  const courses = await coursesResponse.json() as CourseSummary[]
  expect(courses.some((course) => course.slug === 'javascript-v8-quickstart' && course.type === 'input')).toBe(true)
  expect(courses.some((course) => course.slug === 'stdout-formats' && course.type === 'output')).toBe(true)
  expect(courses.some((course) => course.slug === 'comprehensive-io-training' && course.type === 'mixed')).toBe(true)

  const firstResponse = await page.request.get('/api/v1/problems?page=1&page_size=100&sort=oldest')
  expect(firstResponse.ok()).toBe(true)
  const first = await firstResponse.json() as ProblemPage
  const problems = [...first.items]
  for (let pageNumber = 2; pageNumber <= first.pages; pageNumber += 1) {
    const response = await page.request.get(
      `/api/v1/problems?page=${pageNumber}&page_size=100&sort=oldest`,
    )
    expect(response.ok()).toBe(true)
    problems.push(...((await response.json() as ProblemPage).items))
  }
  const outputCount = problems.filter((problem) => problem.slug.startsWith('js-acm-output-')).length
  const inputCount = problems.filter((problem) =>
    problem.slug.startsWith('js-acm-') && !problem.slug.startsWith('js-acm-output-')).length
  expect(inputCount).toBeGreaterThanOrEqual(80)
  expect(outputCount).toBeGreaterThanOrEqual(40)
  expect(problems).toHaveLength(first.total)

  await page.goto('/guide')
  await expect(page.getByRole('heading', { name: /stdin \/ stdout/ })).toBeVisible()
  await page.getByRole('link', { name: /JavaScript V8/ }).first().click()
  await expect(page).toHaveURL(/\/guide\/javascript-v8$/)
  await expect(page.getByText('readline()', { exact: true }).first()).toBeVisible()
})
