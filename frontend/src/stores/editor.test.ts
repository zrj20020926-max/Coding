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

    store.saveDraft('user-a', 1, 'python', 'print(1)')
    store.saveDraft('user-a', 1, 'cpp', 'cout << 1;')
    store.saveDraft('user-b', 1, 'python', 'print(2)')

    expect(store.loadDraft('user-a', 1, 'python')).toBe('print(1)')
    expect(store.loadDraft('user-a', 1, 'cpp')).toBe('cout << 1;')
    expect(store.loadDraft('user-b', 1, 'python')).toBe('print(2)')
    expect(store.clearDraft('user-a', 1, 'python')).toBe(defaultCodeFor('python'))
    expect(localStorage.getItem(draftStorageKey('user-a', 1, 'python'))).toBeNull()
  })

  it('loads judge-supported languages and replaces an unavailable selection', async () => {
    localStorage.setItem('codearena.editor.language', 'java')
    vi.mocked(getProblemLanguages).mockResolvedValue([
      {
        id: 1,
        slug: 'python',
        display_name: 'Python',
        version: '3.12',
        monaco_language: 'python',
        source_filename: 'main.py',
        sort_order: 1,
      },
    ])
    const store = useEditorStore()

    await store.loadLanguages()

    expect(store.selectedLanguage).toBe('python')
    expect(store.languages).toHaveLength(1)
    expect(store.languagesLoading).toBe(false)
  })
})
