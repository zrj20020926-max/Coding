<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, shallowRef, watch } from 'vue'
import * as monaco from 'monaco-editor/esm/vs/editor/editor.api'
import 'monaco-editor/esm/vs/editor/browser/coreCommands'
import 'monaco-editor/esm/vs/editor/browser/widget/codeEditor/codeEditorWidget'
import 'monaco-editor/esm/vs/editor/contrib/bracketMatching/browser/bracketMatching'
import 'monaco-editor/esm/vs/editor/contrib/clipboard/browser/clipboard'
import 'monaco-editor/esm/vs/editor/contrib/comment/browser/comment'
import 'monaco-editor/esm/vs/editor/contrib/contextmenu/browser/contextmenu'
import 'monaco-editor/esm/vs/editor/contrib/find/browser/findController'
import 'monaco-editor/esm/vs/editor/contrib/folding/browser/folding'
import 'monaco-editor/esm/vs/editor/contrib/format/browser/formatActions'
import 'monaco-editor/esm/vs/editor/contrib/hover/browser/hoverContribution'
import 'monaco-editor/esm/vs/editor/contrib/indentation/browser/indentation'
import 'monaco-editor/esm/vs/editor/contrib/linesOperations/browser/linesOperations'
import 'monaco-editor/esm/vs/editor/contrib/snippet/browser/snippetController2'
import 'monaco-editor/esm/vs/editor/contrib/suggest/browser/suggestController'
import 'monaco-editor/esm/vs/editor/contrib/tokenization/browser/tokenization'
import 'monaco-editor/esm/vs/editor/contrib/wordOperations/browser/wordOperations'
import 'monaco-editor/esm/vs/base/browser/ui/codicons/codiconStyles'
import 'monaco-editor/esm/vs/basic-languages/javascript/javascript.contribution'
import EditorWorker from 'monaco-editor/esm/vs/editor/editor.worker?worker'

const props = defineProps<{
  modelValue: string
  language: string
  theme: 'light' | 'dark'
  fontSize: number
  modelId: string
  runtime: 'javascript-v8' | 'nodejs'
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
  save: []
  runSample: []
  runCustom: []
  submit: []
}>()

const container = shallowRef<HTMLElement | null>(null)
let editor: monaco.editor.IStandaloneCodeEditor | null = null
let model: monaco.editor.ITextModel | null = null
let resizeObserver: ResizeObserver | null = null
const disposables: monaco.IDisposable[] = []
let completionDisposable: monaco.IDisposable | null = null
let formattingDisposable: monaco.IDisposable | null = null

;(self as typeof self & {
  MonacoEnvironment?: { getWorker: () => Worker }
}).MonacoEnvironment = {
  getWorker: () => new EditorWorker(),
}

function registerCompletions(language: string, runtime: 'javascript-v8' | 'nodejs'): monaco.IDisposable {
  const suggestions = runtime === 'javascript-v8'
    ? [
        ['readline', 'const ${1:line} = readline();'],
        ['readints', 'const ${1:values} = readline().trim().split(/\\s+/).map(Number);'],
        ['read-eof', 'for (let ${1:line}; (${1:line} = readline()) !== undefined;) {\n\t${2:// 处理每行}\n}'],
        ['print', 'print(${1:value});'],
      ]
    : [
        ['node-stdin', "const input = require('fs').readFileSync(0, 'utf8');"],
        ['tokens', "const tokens = require('fs').readFileSync(0, 'utf8').trim().split(/\\s+/);"],
        ['lines', "const lines = require('fs').readFileSync(0, 'utf8').split(/\\r?\\n/);"],
        ['scanner', "const data = require('fs').readFileSync(0, 'utf8').trim().split(/\\s+/);\nlet cursor = 0;\nconst next = () => data[cursor++];"],
      ]
  return monaco.languages.registerCompletionItemProvider(language, {
    triggerCharacters: ['.', ' '],
    provideCompletionItems(textModel, position) {
      const word = textModel.getWordUntilPosition(position)
      const range = new monaco.Range(
        position.lineNumber,
        word.startColumn,
        position.lineNumber,
        word.endColumn,
      )
      return {
        suggestions: suggestions.map(([label, insertText]) => ({
          label: label ?? '',
          kind: monaco.languages.CompletionItemKind.Snippet,
          insertText: insertText ?? '',
          insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
          range,
        })),
      }
    },
  })
}

function normalizeSource(source: string): string {
  const lines = source.replace(/\r\n?/g, '\n').split('\n')
  while (lines[lines.length - 1] === '') lines.pop()
  return `${lines.map((line) => line.replace(/\t/g, '    ').trimEnd()).join('\n')}\n`
}

function registerFormatter(language: string): monaco.IDisposable {
  return monaco.languages.registerDocumentFormattingEditProvider(language, {
    provideDocumentFormattingEdits(textModel) {
      return [{ range: textModel.getFullModelRange(), text: normalizeSource(textModel.getValue()) }]
    },
  })
}

function formatDocument(): void {
  void editor?.getAction('editor.action.formatDocument')?.run()
}

onMounted(async () => {
  await nextTick()
  if (!container.value) return
  const uri = monaco.Uri.parse(`inmemory://codearena/${encodeURIComponent(props.modelId)}`)
  model = monaco.editor.getModel(uri)
    ?? monaco.editor.createModel(props.modelValue, props.language, uri)
  editor = monaco.editor.create(container.value, {
    model,
    theme: props.theme === 'dark' ? 'vs-dark' : 'vs',
    fontSize: props.fontSize,
    fontFamily: "'DM Mono', 'JetBrains Mono', Consolas, monospace",
    fontLigatures: true,
    automaticLayout: false,
    minimap: { enabled: false },
    scrollBeyondLastLine: false,
    smoothScrolling: true,
    wordWrap: 'on',
    tabSize: 4,
    insertSpaces: true,
    formatOnPaste: true,
    suggestOnTriggerCharacters: true,
    quickSuggestions: { comments: false, strings: true, other: true },
    padding: { top: 16, bottom: 16 },
    ariaLabel: 'CodeArena ACM 代码编辑器',
  })
  disposables.push(
    model.onDidChangeContent(() => emit('update:modelValue', model?.getValue() ?? '')),
  )
  editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => emit('save'))
  editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter, () => emit('runSample'))
  editor.addCommand(
    monaco.KeyMod.CtrlCmd | monaco.KeyMod.Alt | monaco.KeyCode.Enter,
    () => emit('runCustom'),
  )
  editor.addCommand(
    monaco.KeyMod.CtrlCmd | monaco.KeyMod.Shift | monaco.KeyCode.Enter,
    () => emit('submit'),
  )
  completionDisposable = registerCompletions(props.language, props.runtime)
  formattingDisposable = registerFormatter(props.language)
  editor.addCommand(
    monaco.KeyMod.Shift | monaco.KeyMod.Alt | monaco.KeyCode.KeyF,
    formatDocument,
  )
  resizeObserver = new ResizeObserver(() => editor?.layout())
  resizeObserver.observe(container.value)
  editor.focus()
})

watch(
  () => props.modelValue,
  (value) => {
    if (model && model.getValue() !== value) model.setValue(value)
  },
)
watch(
  () => props.language,
  (value) => {
    if (!model) return
    monaco.editor.setModelLanguage(model, value)
    completionDisposable?.dispose()
    completionDisposable = registerCompletions(value, props.runtime)
    formattingDisposable?.dispose()
    formattingDisposable = registerFormatter(value)
  },
)
watch(
  () => props.runtime,
  (value) => {
    completionDisposable?.dispose()
    completionDisposable = registerCompletions(props.language, value)
  },
)
watch(
  () => props.theme,
  (value) => monaco.editor.setTheme(value === 'dark' ? 'vs-dark' : 'vs'),
)
watch(
  () => props.fontSize,
  (value) => editor?.updateOptions({ fontSize: value }),
)

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  disposables.forEach((disposable) => disposable.dispose())
  completionDisposable?.dispose()
  formattingDisposable?.dispose()
  editor?.dispose()
  model?.dispose()
})
</script>

<template>
  <div class="code-editor-shell">
    <button class="editor-format-button" type="button" @click="formatDocument">
      格式化代码
    </button>
    <div ref="container" class="code-editor" data-testid="code-editor"></div>
  </div>
</template>
