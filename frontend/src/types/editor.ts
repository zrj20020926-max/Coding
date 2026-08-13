export interface JudgeLanguage {
  id: number
  slug: string
  display_name: string
  version: string
  monaco_language: string
  source_filename: string
  sort_order: number
}

export const DEFAULT_CODE_TEMPLATES: Readonly<Record<string, string>> = {
  'javascript-v8': `// JavaScript V8：只能使用 readline() 逐行读取，print() 输出
const line = readline();
// 在这里处理输入
print(line);
`,
  nodejs: `// Node.js：一次读取完整 stdin，按题意解析
const input = require('fs').readFileSync(0, 'utf8').trimEnd();
// 在这里处理输入
console.log(input);
`,
}

export function defaultCodeFor(language: string): string {
  return DEFAULT_CODE_TEMPLATES[language] ?? ''
}
