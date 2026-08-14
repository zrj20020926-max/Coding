import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { getProblemLanguages } from '@/services/problems'
import { draftStorageKey, useEditorStore } from '@/stores/editor'
import { defaultCodeFor } from '@/types/editor'

vi.mock('@/services/problems', async (importOriginal) => {
  const original = await importOriginal<Record<string, unknown>>()
  return { ...original, getProblemLanguages: vi.fn() }
})

describe('editor store', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('isolates, restores and clears drafts by user, problem and language', () => {
    const store = useEditorStore()

    store.saveDraft('user-a', 1, 'javascript-v8', 'print(1)')
    store.saveDraft('user-a', 1, 'nodejs', 'console.log(1)')
    store.saveDraft('user-b', 1, 'javascript-v8', 'print(2)')

    expect(store.loadDraft('user-a', 1, 'javascript-v8')).toBe('print(1)')
    expect(store.loadDraft('user-a', 1, 'nodejs')).toBe('console.log(1)')
    expect(store.loadDraft('user-b', 1, 'javascript-v8')).toBe('print(2)')
    expect(store.clearDraft('user-a', 1, 'javascript-v8'))
      .toBe(defaultCodeFor('javascript-v8'))
    expect(localStorage.getItem(draftStorageKey('user-a', 1, 'javascript-v8'))).toBeNull()
  })

  it('loads judge-supported languages and replaces an unavailable selection', async () => {
    localStorage.setItem('codearena.editor.language', 'java')
    vi.mocked(getProblemLanguages).mockResolvedValue([
      {
        id: 1,
        slug: 'javascript-v8',
        display_name: 'JavaScript V8',
        version: 'ES2023',
        monaco_language: 'javascript',
        source_filename: 'main.js',
        runtime_mode: 'v8-compat',
        input_api: 'readline()',
        output_api: 'print(...args)',
        eof_value: 'undefined',
        sort_order: 1,
      },
      {
        id: 2,
        slug: 'nodejs',
        display_name: 'Node.js',
        version: '22',
        monaco_language: 'javascript',
        source_filename: 'main.js',
        runtime_mode: 'nodejs',
        input_api: "fs.readFileSync(0, 'utf8')",
        output_api: 'console.log/process.stdout.write',
        eof_value: null,
        sort_order: 2,
      },
    ])
    const store = useEditorStore()

    await store.loadLanguages()

    expect(store.selectedLanguage).toBe('javascript-v8')
    expect(store.languages.map((item) => item.slug)).toEqual(['javascript-v8', 'nodejs'])
    expect(store.languagesLoading).toBe(false)
  })

  it('moves an anonymous draft into the authenticated user scope after login', () => {
    const store = useEditorStore()
    store.saveDraft('anonymous', 7, 'javascript-v8', 'print("keep me")')

    expect(store.loadDraft('user-after-login', 7, 'javascript-v8')).toBe('print("keep me")')
    expect(localStorage.getItem(draftStorageKey('anonymous', 7, 'javascript-v8'))).toBeNull()
    expect(localStorage.getItem(draftStorageKey('user-after-login', 7, 'javascript-v8')))
      .toBe('print("keep me")')
  })

  it('provides distinct safe templates for V8 and Node.js modes', () => {
    expect(defaultCodeFor('javascript-v8')).toContain('readline()')
    expect(defaultCodeFor('javascript-v8')).toContain('print(')
    expect(defaultCodeFor('javascript-v8')).not.toContain("require('fs')")
    expect(defaultCodeFor('nodejs')).toContain("const fs = require('fs')")
    expect(defaultCodeFor('nodejs')).toContain("fs.readFileSync(0, 'utf8')")
    expect(defaultCodeFor('nodejs')).toContain('console.log(')
    expect(defaultCodeFor('nodejs')).not.toContain('.trim()')
    expect(defaultCodeFor('javascript-v8', { starter_code_v8: 'print(42);' }))
      .toBe('print(42);')
  })
})
