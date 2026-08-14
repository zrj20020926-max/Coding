import { ref, watch } from 'vue'
import { defineStore } from 'pinia'

import { getProblemLanguages } from '@/services/problems'
import { defaultCodeFor } from '@/types/editor'
import type { JudgeLanguage } from '@/types/editor'

const FONT_SIZE_KEY = 'codearena.editor.font-size'
const LANGUAGE_KEY = 'codearena.editor.language'

interface StoredDraft {
  source: string
  starterCodeVersion: string
  savedAt: string
}

export interface DraftLoadResult {
  source: string
  templateChanged: boolean
  restoredVersion: string | null
}

function initialFontSize(): number {
  const value = Number.parseInt(localStorage.getItem(FONT_SIZE_KEY) ?? '', 10)
  return Number.isInteger(value) && value >= 12 && value <= 22 ? value : 14
}

/** Stable, non-cryptographic version used only to scope local drafts to a starter template. */
export function starterCodeVersion(source: string): string {
  let hash = 0x811c9dc5
  for (let index = 0; index < source.length; index += 1) {
    hash ^= source.charCodeAt(index)
    hash = Math.imul(hash, 0x01000193)
  }
  return `v1-${(hash >>> 0).toString(16).padStart(8, '0')}`
}

export function draftStorageKey(
  userId: string,
  exerciseId: number,
  runtime: string,
  version: string,
): string {
  return `codearena.draft.${userId}.${exerciseId}.${runtime}.${version}`
}

function draftIndexKey(userId: string, exerciseId: number, runtime: string): string {
  return `codearena.draft-index.${userId}.${exerciseId}.${runtime}`
}

export function customInputStorageKey(
  userId: string,
  exerciseId: number,
  runtime: string,
  version: string,
): string {
  return `codearena.custom-input.${userId}.${exerciseId}.${runtime}.${version}`
}

function customInputBackupKey(
  userId: string,
  exerciseId: number,
  runtime: string,
  version: string,
): string {
  return `${customInputStorageKey(userId, exerciseId, runtime, version)}.backup`
}

function readVersionIndex(userId: string, exerciseId: number, runtime: string): string[] {
  const raw = localStorage.getItem(draftIndexKey(userId, exerciseId, runtime))
  if (!raw) return []
  try {
    const parsed = JSON.parse(raw) as unknown
    return Array.isArray(parsed) && parsed.every((item) => typeof item === 'string')
      ? parsed
      : []
  } catch {
    return []
  }
}

function rememberVersion(userId: string, exerciseId: number, runtime: string, version: string): void {
  const versions = readVersionIndex(userId, exerciseId, runtime).filter((item) => item !== version)
  versions.push(version)
  localStorage.setItem(draftIndexKey(userId, exerciseId, runtime), JSON.stringify(versions.slice(-10)))
}

function parseDraft(raw: string | null, version: string): StoredDraft | null {
  if (raw === null) return null
  try {
    const parsed = JSON.parse(raw) as Partial<StoredDraft>
    if (typeof parsed.source === 'string' && typeof parsed.starterCodeVersion === 'string') {
      return {
        source: parsed.source,
        starterCodeVersion: parsed.starterCodeVersion,
        savedAt: typeof parsed.savedAt === 'string' ? parsed.savedAt : '',
      }
    }
  } catch {
    // Legacy values were stored as plain source text.
  }
  return { source: raw, starterCodeVersion: version, savedAt: '' }
}

function storeDraft(
  userId: string,
  exerciseId: number,
  runtime: string,
  version: string,
  source: string,
): void {
  const value: StoredDraft = {
    source,
    starterCodeVersion: version,
    savedAt: new Date().toISOString(),
  }
  localStorage.setItem(draftStorageKey(userId, exerciseId, runtime, version), JSON.stringify(value))
  rememberVersion(userId, exerciseId, runtime, version)
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
      languages.value = (await getProblemLanguages()).filter((item) =>
        item.slug === 'javascript-v8' || item.slug === 'nodejs',
      )
      if (!languages.value.some((item) => item.slug === selectedLanguage.value)) {
        selectedLanguage.value = languages.value[0]?.slug ?? 'javascript-v8'
      }
    } catch {
      languagesError.value = '可用运行模式加载失败'
      languages.value = []
    } finally {
      languagesLoading.value = false
    }
  }

  function loadDraft(
    userId: string,
    exerciseId: number,
    runtime: string,
    version: string,
    starterCode?: string | null,
  ): DraftLoadResult {
    const exactKey = draftStorageKey(userId, exerciseId, runtime, version)
    const exact = parseDraft(localStorage.getItem(exactKey), version)
    if (exact !== null) {
      return { source: exact.source, templateChanged: false, restoredVersion: version }
    }

    if (userId !== 'anonymous') {
      const anonymousKey = draftStorageKey('anonymous', exerciseId, runtime, version)
      const anonymous = parseDraft(localStorage.getItem(anonymousKey), version)
      if (anonymous !== null) {
        storeDraft(userId, exerciseId, runtime, version, anonymous.source)
        localStorage.removeItem(anonymousKey)
        return { source: anonymous.source, templateChanged: false, restoredVersion: version }
      }
    }

    // Migrate the previous three-dimensional plain-text key once.
    const legacyKey = `codearena.draft.${userId}.${exerciseId}.${runtime}`
    const legacy = localStorage.getItem(legacyKey)
    if (legacy !== null) {
      storeDraft(userId, exerciseId, runtime, version, legacy)
      localStorage.removeItem(legacyKey)
      return { source: legacy, templateChanged: true, restoredVersion: null }
    }

    const priorVersions = readVersionIndex(userId, exerciseId, runtime)
      .filter((item) => item !== version)
    const priorVersion = priorVersions[priorVersions.length - 1]
    if (priorVersion) {
      const prior = parseDraft(
        localStorage.getItem(draftStorageKey(userId, exerciseId, runtime, priorVersion)),
        priorVersion,
      )
      if (prior !== null) {
        return { source: prior.source, templateChanged: true, restoredVersion: priorVersion }
      }
    }

    return {
      source: starterCode ?? defaultCodeFor(runtime),
      templateChanged: false,
      restoredVersion: null,
    }
  }

  function saveDraft(
    userId: string,
    exerciseId: number,
    runtime: string,
    version: string,
    sourceCode: string,
  ): void {
    storeDraft(userId, exerciseId, runtime, version, sourceCode)
  }

  function clearDraft(
    userId: string,
    exerciseId: number,
    runtime: string,
    version: string,
    starterCode?: string | null,
  ): string {
    localStorage.removeItem(draftStorageKey(userId, exerciseId, runtime, version))
    return starterCode ?? defaultCodeFor(runtime)
  }

  function loadCustomInput(
    userId: string,
    exerciseId: number,
    runtime: string,
    version: string,
    fallback: string,
  ): string {
    const key = customInputStorageKey(userId, exerciseId, runtime, version)
    const value = localStorage.getItem(key)
    if (value !== null) return value
    if (userId !== 'anonymous') {
      const anonymousKey = customInputStorageKey('anonymous', exerciseId, runtime, version)
      const anonymousValue = localStorage.getItem(anonymousKey)
      if (anonymousValue !== null) {
        localStorage.setItem(key, anonymousValue)
        localStorage.removeItem(anonymousKey)
        return anonymousValue
      }
    }
    return fallback
  }

  function saveCustomInput(
    userId: string,
    exerciseId: number,
    runtime: string,
    version: string,
    value: string,
  ): void {
    localStorage.setItem(customInputStorageKey(userId, exerciseId, runtime, version), value)
  }

  function clearCustomInput(
    userId: string,
    exerciseId: number,
    runtime: string,
    version: string,
    currentValue: string,
  ): string {
    localStorage.setItem(customInputBackupKey(userId, exerciseId, runtime, version), currentValue)
    saveCustomInput(userId, exerciseId, runtime, version, '')
    return ''
  }

  function restoreCustomInput(
    userId: string,
    exerciseId: number,
    runtime: string,
    version: string,
    fallback: string,
  ): string {
    return localStorage.getItem(customInputBackupKey(userId, exerciseId, runtime, version))
      ?? localStorage.getItem(customInputStorageKey(userId, exerciseId, runtime, version))
      ?? fallback
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
    loadCustomInput,
    saveCustomInput,
    clearCustomInput,
    restoreCustomInput,
  }
})
