export interface JudgeLanguage {
  id: number
  slug: string
  display_name: string
  version: string
  monaco_language: string
  source_filename: string
  runtime_mode: 'v8-compat' | 'nodejs'
  input_api: string
  output_api: string
  eof_value: string | null
  sort_order: number
}

export const DEFAULT_CODE_TEMPLATES: Readonly<Record<string, string>> = {
  'javascript-v8': `// JavaScript V8：只能使用 readline() 逐行读取，print() 输出
const line = readline();
// 在这里处理输入
print(line);
`,
  nodejs: `// Node.js：一次读取原始 stdin，按题意决定是否 trim
const fs = require('fs');

const input = fs.readFileSync(0, 'utf8');
// 在这里处理输入
console.log(input);
`,
}

export interface ProblemStarterCode {
  starter_code_v8?: string | null
  starter_code_nodejs?: string | null
}

export function defaultCodeFor(language: string, problem?: ProblemStarterCode): string {
  if (language === 'javascript-v8' && problem?.starter_code_v8) {
    return problem.starter_code_v8
  }
  if (language === 'nodejs' && problem?.starter_code_nodejs) {
    return problem.starter_code_nodejs
  }
  return DEFAULT_CODE_TEMPLATES[language] ?? ''
}
