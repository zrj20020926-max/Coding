import { ref, watch } from 'vue'
import { defineStore } from 'pinia'

import { getProblemLanguages } from '@/services/problems'
import { defaultCodeFor } from '@/types/editor'
import type { JudgeLanguage } from '@/types/editor'

const FONT_SIZE_KEY = 'codearena.editor.font-size'
const LANGUAGE_KEY = 'codearena.editor.language'

function initialFontSize(): number {
  const value = Number.parseInt(localStorage.getItem(FONT_SIZE_KEY) ?? '', 10)
  return Number.isInteger(value) && value >= 12 && value <= 22 ? value : 14
}

export function draftStorageKey(
  userId: string,
  problemId: number,
  language: string,
): string {
  return `codearena.draft.${userId}.${problemId}.${language}`
}

export const useEditorStore = defineStore('editor', () => {
  const languages = ref<JudgeLanguage[]>([])
  const languagesLoading = ref(false)
  const languagesError = ref('')
  const selectedLanguage = ref(localStorage.getItem(LANGUAGE_KEY) ?? 'javascript-v8')
  const fontSize = ref(initialFontSize())

  watch(selectedLanguage, (value) => localStorage.setItem(LANGUAGE_KEY, value))
  watch(fontSize, (value) => localStorage.setItem(FONT_SIZE_KEY, String(value)))

  async function loadLanguages(): Promise<void> {
    if (languages.value.length || languagesLoading.value) return
    languagesLoading.value = true
    languagesError.value = ''
    try {
      languages.value = await getProblemLanguages()
      if (!languages.value.some((item) => item.slug === selectedLanguage.value)) {
        selectedLanguage.value = languages.value[0]?.slug ?? 'javascript-v8'
      }
    } catch {
      languagesError.value = '可用语言加载失败'
      languages.value = []
    } finally {
      languagesLoading.value = false
    }
  }

  function loadDraft(userId: string, problemId: number, language: string): string {
    const key = draftStorageKey(userId, problemId, language)
    const ownDraft = localStorage.getItem(key)
    if (ownDraft !== null) return ownDraft
    if (userId !== 'anonymous') {
      const anonymousKey = draftStorageKey('anonymous', problemId, language)
      const anonymousDraft = localStorage.getItem(anonymousKey)
      if (anonymousDraft !== null) {
        localStorage.setItem(key, anonymousDraft)
        localStorage.removeItem(anonymousKey)
        return anonymousDraft
      }
    }
    return defaultCodeFor(language)
  }

  function saveDraft(
    userId: string,
    problemId: number,
    language: string,
    sourceCode: string,
  ): void {
    localStorage.setItem(draftStorageKey(userId, problemId, language), sourceCode)
  }

  function clearDraft(userId: string, problemId: number, language: string): string {
    localStorage.removeItem(draftStorageKey(userId, problemId, language))
    return defaultCodeFor(language)
  }

  return {
    languages,
    languagesLoading,
    languagesError,
    selectedLanguage,
    fontSize,
    loadLanguages,
    loadDraft,
    saveDraft,
    clearDraft,
  }
})
