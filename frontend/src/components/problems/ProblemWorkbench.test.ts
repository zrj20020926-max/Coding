import { defineComponent } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import ProblemWorkbench from '@/components/problems/ProblemWorkbench.vue'
import { getProblemLanguages } from '@/services/problems'
import { createSubmission, getSubmissionDetail, getSubmissionStatus } from '@/services/submissions'
import { useAuthStore } from '@/stores/auth'
import { useEditorStore } from '@/stores/editor'
import type { ProblemDetail } from '@/types/problem'
import type { SubmissionCreated, SubmissionDetail, SubmissionSummary } from '@/types/submission'

vi.mock('@/services/problems', async (importOriginal) => {
  const original = await importOriginal<Record<string, unknown>>()
  return { ...original, getProblemLanguages: vi.fn() }
})
vi.mock('@/services/submissions')
vi.mock('@/components/editor/CodeEditor.vue', () => {
  const component = defineComponent({
    name: 'CodeEditor',
    props: { modelValue: { type: String, required: true }, runtime: { type: String, required: true } },
    emits: ['update:modelValue', 'save', 'runSample', 'runCustom', 'submit'],
    template: `<div data-testid="fake-editor" :data-runtime="runtime">
      <textarea data-testid="source" :value="modelValue" @input="$emit('update:modelValue', $event.target.value)" />
      <button data-testid="custom-shortcut" @click="$emit('runCustom')">custom shortcut</button>
    </div>`,
  })
  return Object.assign(component, {
    default: component,
    __esModule: true,
    __isTeleport: false,
    __isKeepAlive: false,
  })
})

const problem: ProblemDetail = {
  id: 9,
  slug: 'read-a-line',
  title: '读取一整行',
  difficulty: 'easy',
  training_category: 'single-value',
  source: null,
  accepted_count: 0,
  submission_count: 0,
  acceptance_rate: 0,
  tags: [],
  description: '读取 stdin',
  input_description: '一行文本',
  output_description: '原样输出',
  data_constraints: '0 <= length <= 100',
  sample_input: 'hello\n',
  sample_output: 'hello\n',
  sample_explanation: '',
  starter_code_v8: 'const line = readline();\nprint(line);\n',
  starter_code_nodejs: "const fs = require('fs');\nconst input = fs.readFileSync(0, 'utf8');\nconsole.log(input);\n",
  time_limit_ms: 1000,
  memory_limit_mb: 128,
  created_at: '2026-08-14T00:00:00Z',
  updated_at: '2026-08-14T00:00:00Z',
}

const pending: SubmissionCreated = {
  id: 'submission-custom',
  problem: { id: 9, slug: problem.slug, title: problem.title },
  language: { id: 2, slug: 'nodejs', display_name: 'Node.js', version: '22' },
  status: 'Pending',
  mode: 'custom',
  time_used_ms: null,
  memory_used_kb: null,
  passed_case_count: 0,
  total_case_count: 0,
  score: '0.00',
  judged_at: null,
  created_at: '2026-08-14T00:00:00Z',
  updated_at: '2026-08-14T00:00:00Z',
  idempotent_replay: false,
}
const accepted: SubmissionSummary = {
  ...pending,
  status: 'Accepted',
  time_used_ms: 5,
  memory_used_kb: 2048,
  passed_case_count: 1,
  total_case_count: 1,
}
const detail: SubmissionDetail = {
  ...accepted,
  source_code: 'source',
  compiler_output: null,
  error_message: null,
  sample_output: 'first\r\n\r\nlast\n',
}

function languages() {
  return [
    {
      id: 1, slug: 'javascript-v8', display_name: 'JavaScript V8', version: 'ES2023',
      monaco_language: 'javascript', source_filename: 'main.js', runtime_mode: 'v8-compat' as const,
      input_api: 'readline()', output_api: 'print(...args)', eof_value: 'undefined', sort_order: 1,
    },
    {
      id: 2, slug: 'nodejs', display_name: 'Node.js', version: '22',
      monaco_language: 'javascript', source_filename: 'main.js', runtime_mode: 'nodejs' as const,
      input_api: "fs.readFileSync(0, 'utf8')", output_api: 'console.log/process.stdout.write',
      eof_value: null, sort_order: 2,
    },
  ]
}

async function setup(authenticated = true) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/problems/:slug', name: 'problem-detail', component: { template: '<div />' } },
      { path: '/login', name: 'login', component: { template: '<div />' } },
      { path: '/submissions/:id', component: { template: '<div />' } },
    ],
  })
  await router.push(`/problems/${problem.slug}`)
  await router.isReady()
  if (authenticated) {
    useAuthStore().acceptSession('token', {
      id: 'user-1', username: 'student', email: 'student@example.com', nickname: 'Student',
      avatar_url: null, bio: null, is_admin: false, solved_count: 0, submission_count: 0,
      accepted_count: 0, created_at: '2026-08-14T00:00:00Z',
    })
  }
  const wrapper = mount(ProblemWorkbench, { props: { problem }, global: { plugins: [pinia, router] } })
  await flushPromises()
  return { wrapper, router }
}

describe('ProblemWorkbench', () => {
  beforeEach(() => {
    Object.defineProperty(window, 'matchMedia', {
      configurable: true,
      value: vi.fn().mockReturnValue({ matches: false }),
    })
    vi.mocked(getProblemLanguages).mockResolvedValue(languages())
    vi.mocked(createSubmission).mockResolvedValue(pending)
    vi.mocked(getSubmissionStatus).mockResolvedValue(accepted)
    vi.mocked(getSubmissionDetail).mockResolvedValue(detail)
  })

  it('switches V8 and Node.js without overwriting either runtime draft', async () => {
    const { wrapper } = await setup()
    const editorStore = useEditorStore()
    expect(wrapper.get('[data-testid="fake-editor"]').attributes('data-runtime')).toBe('javascript-v8')
    await wrapper.get('[data-testid="source"]').setValue('print("v8 draft");')

    editorStore.selectedLanguage = 'nodejs'
    await flushPromises()
    expect(wrapper.get('[data-testid="fake-editor"]').attributes('data-runtime')).toBe('nodejs')
    expect((wrapper.get('[data-testid="source"]').element as HTMLTextAreaElement).value).toContain("require('fs')")
    await wrapper.get('[data-testid="source"]').setValue('console.log("node draft");')

    editorStore.selectedLanguage = 'javascript-v8'
    await flushPromises()
    expect((wrapper.get('[data-testid="source"]').element as HTMLTextAreaElement).value).toBe('print("v8 draft");')
  })

  it('sends custom blank lines and the textarea final newline with the selected language slug', async () => {
    const { wrapper } = await setup()
    const editorStore = useEditorStore()
    editorStore.selectedLanguage = 'nodejs'
    await flushPromises()
    // HTML textarea values canonically use LF; CRLF visualization is covered by OutputDiff.
    const input = 'first\n\nlast\n'
    await wrapper.get('.custom-input-panel textarea').setValue(input)
    await wrapper.get('[data-testid="custom-shortcut"]').trigger('click')
    await flushPromises()

    expect(createSubmission).toHaveBeenCalledWith(
      expect.objectContaining({ language: 'nodejs', mode: 'custom', custom_input: input }),
      expect.any(String),
    )
    expect(wrapper.text()).toContain('实际 stdout')
  })

  it('allows empty stdin and redirects unauthenticated users back to the exercise', async () => {
    const authenticated = await setup()
    await authenticated.wrapper.get('.custom-input-panel textarea').setValue('')
    await authenticated.wrapper.get('[data-testid="custom-shortcut"]').trigger('click')
    await flushPromises()
    expect(createSubmission).toHaveBeenCalledWith(
      expect.objectContaining({ mode: 'custom', custom_input: '' }),
      expect.any(String),
    )

    vi.mocked(createSubmission).mockClear()
    const anonymous = await setup(false)
    await anonymous.wrapper.get('[data-testid="custom-shortcut"]').trigger('click')
    await flushPromises()
    expect(createSubmission).not.toHaveBeenCalled()
    expect(anonymous.router.currentRoute.value.name).toBe('login')
    expect(anonymous.router.currentRoute.value.query['redirect']).toBe(`/problems/${problem.slug}`)
  })
})
