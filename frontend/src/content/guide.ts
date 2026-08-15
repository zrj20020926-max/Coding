import type {
  GuideCodeExample,
  GuideRuntime,
  GuideSearchResult,
  GuideSection,
  GuideSectionSlug,
  GuideTopic,
} from '@/types/guide'

const snippet = String.raw

function example(
  id: string,
  title: string,
  runtime: GuideRuntime,
  code: string,
  targetSlug: string,
  options: Pick<GuideCodeExample, 'note' | 'variant'> = {},
): GuideCodeExample {
  return { id, title, runtime, code: code.trim(), targetSlug, ...options }
}

function pairTopic(
  id: string,
  title: string,
  summary: string,
  targetSlug: string,
  v8Code: string,
  nodeCode: string,
  keywords: string[] = [],
): GuideTopic {
  return {
    id,
    title,
    summary,
    keywords,
    examples: [
      example(`${id}-v8`, `${title} · JavaScript V8`, 'javascript-v8', v8Code, targetSlug),
      example(`${id}-node`, `${title} · Node.js`, 'nodejs', nodeCode, targetSlug),
    ],
  }
}

const v8Section: GuideSection = {
  slug: 'javascript-v8',
  title: 'JavaScript V8',
  eyebrow: 'READLINE / PRINT',
  description: '逐行读取的受控 V8 兼容环境。只使用 `readline()` 和 `print()` 处理标准输入输出。',
  topics: [
    {
      id: 'v8-basics',
      title: 'readline() 与 print()',
      summary: '`readline()` 每次返回一行且不包含换行符；到达 EOF 时返回 `undefined`。`print(...args)` 用空格连接参数并追加换行。',
      keywords: ['单行', 'stdout', 'stdin', 'EOF'],
      examples: [example('v8-basic-line', '读取并输出一行', 'javascript-v8', snippet`
const line = readline();
if (line !== undefined) {
  print(line);
}`, 'js-acm-read-whole-line')],
    },
    {
      id: 'v8-lines',
      title: '多行、T 组与空行',
      summary: '固定行数直接调用多次；T 组先读取数量；空字符串 `""` 是有效空行，不能当作 EOF。',
      keywords: ['多行', 'T 组', '空行'],
      examples: [
        example('v8-three-lines', '固定三行', 'javascript-v8', snippet`
const first = readline();
const second = readline();
const third = readline();
print(first);
print(second);
print(third);`, 'js-acm-fixed-three-lines'),
        example('v8-t-cases', 'T 组测试', 'javascript-v8', snippet`
const T = Number(readline());
const out = [];
for (let caseIndex = 0; caseIndex < T; caseIndex++) {
  const values = readline().trim().split(/\s+/).map(Number);
  out.push(String(values.reduce((sum, value) => sum + value, 0)));
}
print(out.join('\n'));`, 'js-acm-t-one-line'),
      ],
    },
    {
      id: 'v8-eof',
      title: '读取到 EOF',
      summary: '必须显式比较 `undefined`。不要使用 `while (readline())`，否则空行会错误终止循环。',
      keywords: ['EOF', 'undefined', '空行'],
      examples: [example('v8-eof-loop', '安全 EOF 循环', 'javascript-v8', snippet`
const out = [];
for (let line; (line = readline()) !== undefined;) {
  out.push(line === '' ? '(empty)' : line);
}
print(out.join('\n'));`, 'js-acm-v8-readline-eof')],
    },
    {
      id: 'v8-number-bigint',
      title: 'Number 与 BigInt',
      summary: '`Number` 适合安全整数和浮点数；超过 `Number.MAX_SAFE_INTEGER` 时使用 `BigInt`，输出前调用 `toString()`。',
      keywords: ['Number', 'BigInt', '安全整数'],
      examples: [
        example('v8-number', '读取数字', 'javascript-v8', snippet`
const value = Number(readline().trim());
print(value);`, 'js-acm-read-one-float'),
        example('v8-bigint', '读取大整数', 'javascript-v8', snippet`
const value = BigInt(readline().trim());
print((value + 1n).toString());`, 'js-acm-read-bigint'),
      ],
    },
    {
      id: 'v8-array-matrix',
      title: '数组与矩阵',
      summary: '按行读取数组；矩阵通常先读取 `n m`，再读取 `n` 行。只有题目明确允许时才对行调用 `trim()`。',
      keywords: ['数组', '矩阵', 'map(Number)'],
      examples: [example('v8-matrix', 'n × m 矩阵', 'javascript-v8', snippet`
const [n, m] = readline().trim().split(/\s+/).map(Number);
const matrix = [];
for (let row = 0; row < n; row++) {
  const values = readline().trim().split(/\s+/).map(Number);
  matrix.push(values.slice(0, m));
}
print(matrix.flat().reduce((sum, value) => sum + value, 0));`, 'js-acm-integer-matrix-nm')],
    },
    {
      id: 'v8-output-buffer',
      title: '输出缓冲',
      summary: '大量结果先放入字符串数组，最后一次 `print(out.join("\\n"))`，减少逐行输出调用。',
      keywords: ['输出缓冲', 'join', '性能'],
      examples: [example('v8-buffer', '批量输出', 'javascript-v8', snippet`
const n = Number(readline());
const out = [];
for (let i = 1; i <= n; i++) {
  out.push(String(i));
}
print(out.join('\n'));`, 'js-acm-output-v8-batch-print')],
    },
    {
      id: 'v8-forbidden-api',
      title: '不可使用的 Node.js API',
      summary: 'V8 模式没有 `require`、`process`、`Buffer`、`fs`，也没有 `window` 或 `document`。混用会得到受控 Runtime Error。',
      keywords: ['require', 'process', 'Buffer', 'fs', 'DOM'],
      examples: [example('v8-forbidden', '错误：混入 Node.js API', 'javascript-v8', snippet`
// 错误示例：V8 模式中 require 未定义
const fs = require('fs');
const input = fs.readFileSync(0, 'utf8');`, 'js-acm-read-whole-line', {
        variant: 'incorrect',
        note: '请切换到 Node.js，或改用 readline()/print()。',
      })],
    },
  ],
}

const nodeSection: GuideSection = {
  slug: 'nodejs',
  title: 'Node.js',
  eyebrow: 'FS / STDOUT',
  description: '一次读取原始 stdin，再根据格式选择按行或按 token 解析。不要把 `trim()` 当成固定模板。',
  topics: [
    {
      id: 'node-raw-input',
      title: 'fs.readFileSync 与原始输入',
      summary: '`fs.readFileSync(0, "utf8")` 返回包括空行和末尾换行在内的原始文本。先保存 `raw`，再按题意派生 tokens 或 lines。',
      keywords: ['fs', 'stdin', '原始字符串'],
      examples: [example('node-raw', '读取原始 stdin', 'nodejs', snippet`
const fs = require('fs');
const raw = fs.readFileSync(0, 'utf8');
process.stdout.write(raw);`, 'js-acm-read-whole-line')],
    },
    {
      id: 'node-trim',
      title: 'trim() 与 trimEnd()',
      summary: '`trim()` 删除两端所有空白；`trimEnd()` 只删除末尾空白。空输入、空行和保留空格题目应直接使用 `raw`。',
      keywords: ['trim', 'trimEnd', '空输入', '空行'],
      examples: [example('node-trim-safe', '按题意选择清理方式', 'nodejs', snippet`
const fs = require('fs');
const raw = fs.readFileSync(0, 'utf8');

const allWhitespaceRemoved = raw.trim();
const onlyTrailingRemoved = raw.trimEnd();
const untouched = raw;`, 'js-acm-handle-empty-input')],
    },
    {
      id: 'node-split',
      title: '按 token 或按行拆分',
      summary: '`split(/\\s+/)` 适合忽略空白差异的 token；`split(/\\r?\\n/)` 适合保留每行结构并兼容 CRLF/LF。',
      keywords: ['split', 'token', 'CRLF', '行'],
      examples: [
        example('node-token-split', '按空白 token', 'nodejs', snippet`
const fs = require('fs');
const raw = fs.readFileSync(0, 'utf8');
const tokens = raw.trim() === '' ? [] : raw.trim().split(/\s+/);`, 'js-acm-unknown-token-count'),
        example('node-line-split', '按行并兼容 CRLF', 'nodejs', snippet`
const fs = require('fs');
const raw = fs.readFileSync(0, 'utf8');
const lines = raw.split(/\r?\n/);`, 'js-acm-crlf-lf-compatible'),
      ],
    },
    {
      id: 'node-cursors',
      title: 'token 游标与 line 游标',
      summary: '使用递增索引消费输入，避免 `shift()` 反复移动数组。按行格式和 token 格式分别维护自己的游标。',
      keywords: ['游标', 'cursor', 'shift', '性能'],
      examples: [example('node-cursor', '双游标示例', 'nodejs', snippet`
const fs = require('fs');
const raw = fs.readFileSync(0, 'utf8');
const tokens = raw.match(/\S+/g) ?? [];
let tokenIndex = 0;
const next = () => tokens[tokenIndex++];

const lines = raw.split(/\r?\n/);
let lineIndex = 0;
const nextLine = () => lines[lineIndex++];`, 'js-acm-use-index-cursor')],
    },
    {
      id: 'node-values',
      title: 'Number、BigInt、数组与矩阵',
      summary: '转换发生在读取边界。BigInt 使用 `BigInt(token)`；矩阵按已知行列数从游标连续读取。',
      keywords: ['Number', 'BigInt', '数组', '矩阵'],
      examples: [example('node-value-parser', 'token Scanner 解析矩阵', 'nodejs', snippet`
const fs = require('fs');
const tokens = fs.readFileSync(0, 'utf8').match(/\S+/g) ?? [];
let index = 0;
const next = () => tokens[index++];
const n = Number(next());
const m = Number(next());
const matrix = Array.from({ length: n }, () =>
  Array.from({ length: m }, () => Number(next())),
);
console.log(matrix.flat().reduce((sum, value) => sum + value, 0));`, 'js-acm-integer-matrix-nm')],
    },
    {
      id: 'node-output',
      title: 'console.log、stdout.write 与缓冲',
      summary: '`console.log()` 自动追加换行；`process.stdout.write()` 原样写字符串。大量输出优先收集后一次写出。',
      keywords: ['console.log', 'process.stdout.write', '输出缓冲'],
      examples: [example('node-output-buffer', '一次写出大量结果', 'nodejs', snippet`
const fs = require('fs');
const tokens = fs.readFileSync(0, 'utf8').match(/\S+/g) ?? [];
const out = tokens.map((token, index) => (index + 1) + ': ' + token);
process.stdout.write(out.join('\n'));`, 'js-acm-output-stdout-write-once')],
    },
  ],
}

const inputSection: GuideSection = {
  slug: 'input-patterns',
  title: '常见输入模板',
  eyebrow: 'INPUT PATTERNS',
  description: '每种格式分别提供 V8 和 Node.js 模板。选择与判题运行模式完全一致的代码块。',
  topics: [
    pairTopic('one-integer', '一个整数', '读取一个安全范围内整数并原样输出。', 'js-acm-read-one-integer', snippet`
const n = Number(readline().trim());
print(n);`, snippet`
const fs = require('fs');
const raw = fs.readFileSync(0, 'utf8');
const n = Number(raw.trim());
console.log(n);`, ['Number', '单值']),
    pairTopic('two-integers', '两个整数', '用正则空白拆分，兼容多个空格和 Tab。', 'js-acm-two-integers', snippet`
const [a, b] = readline().trim().split(/\s+/).map(Number);
print(a + b);`, snippet`
const fs = require('fs');
const [a, b] = fs.readFileSync(0, 'utf8').trim().split(/\s+/).map(Number);
console.log(a + b);`, ['多个空格', 'Tab']),
    pairTopic('one-line-array', '一行数组', '已知或未知长度的一行数字数组。', 'js-acm-integer-array-line', snippet`
const values = readline().trim().split(/\s+/).map(Number);
print(values.join(' '));`, snippet`
const fs = require('fs');
const raw = fs.readFileSync(0, 'utf8').trim();
const values = raw === '' ? [] : raw.split(/\s+/).map(Number);
console.log(values.join(' '));`, ['数组', '空数组']),
    pairTopic('multiple-lines', '多行输入', '读取固定三行，保持每行边界。', 'js-acm-fixed-three-lines', snippet`
const lines = [readline(), readline(), readline()];
print(lines.join('\n'));`, snippet`
const fs = require('fs');
const lines = fs.readFileSync(0, 'utf8').split(/\r?\n/);
console.log(lines.slice(0, 3).join('\n'));`, ['多行', 'line cursor']),
    pairTopic('test-cases', 'T 组测试', '第一行是组数，每组后续一行。', 'js-acm-t-one-line', snippet`
const T = Number(readline());
const out = [];
for (let i = 0; i < T; i++) {
  const values = readline().trim().split(/\s+/).map(Number);
  out.push(String(values.reduce((a, b) => a + b, 0)));
}
print(out.join('\n'));`, snippet`
const fs = require('fs');
const tokens = fs.readFileSync(0, 'utf8').match(/\S+/g) ?? [];
let index = 0;
const T = Number(tokens[index++]);
const out = [];
for (let i = 0; i < T; i++) {
  const a = Number(tokens[index++]);
  const b = Number(tokens[index++]);
  out.push(String(a + b));
}
process.stdout.write(out.join('\n'));`, ['T 组', '批量输出']),
    pairTopic('until-eof', '读取到 EOF', '空行不是 EOF；V8 检查 undefined，Node.js 用行数组游标。', 'js-acm-line-until-eof', snippet`
const out = [];
for (let line; (line = readline()) !== undefined;) {
  out.push(line);
}
print(out.join('\n'));`, snippet`
const fs = require('fs');
const raw = fs.readFileSync(0, 'utf8');
const lines = raw.split(/\r?\n/);
if (lines.at(-1) === '') lines.pop();
process.stdout.write(lines.join('\n'));`, ['EOF', 'undefined']),
    pairTopic('sentinel', '哨兵结束', '遇到 0 停止，哨兵本身不参与输出。', 'js-acm-sentinel-zero', snippet`
const out = [];
for (let line; (line = readline()) !== undefined;) {
  const value = Number(line.trim());
  if (value === 0) break;
  out.push(String(value));
}
print(out.join('\n'));`, snippet`
const fs = require('fs');
const tokens = fs.readFileSync(0, 'utf8').match(/\S+/g) ?? [];
const out = [];
for (const token of tokens) {
  const value = Number(token);
  if (value === 0) break;
  out.push(String(value));
}
process.stdout.write(out.join('\n'));`, ['哨兵', 'sentinel']),
    pairTopic('matrix', '矩阵', '第一行 n m，随后 n 行 m 列整数。', 'js-acm-integer-matrix-nm', snippet`
const [n, m] = readline().trim().split(/\s+/).map(Number);
const matrix = [];
for (let i = 0; i < n; i++) {
  matrix.push(readline().trim().split(/\s+/).map(Number).slice(0, m));
}
print(matrix.map((row) => row.join(' ')).join('\n'));`, snippet`
const fs = require('fs');
const tokens = fs.readFileSync(0, 'utf8').match(/\S+/g) ?? [];
let index = 0;
const n = Number(tokens[index++]);
const m = Number(tokens[index++]);
const matrix = Array.from({ length: n }, () =>
  Array.from({ length: m }, () => Number(tokens[index++])),
);
process.stdout.write(matrix.map((row) => row.join(' ')).join('\n'));`, ['矩阵', 'n m']),
    pairTopic('character-grid', '字符网格', '每行字符连续排列，不能按空白 token 拆散。', 'js-acm-compact-character-grid', snippet`
const [n] = readline().trim().split(/\s+/).map(Number);
const grid = [];
for (let i = 0; i < n; i++) grid.push([...readline()]);
print(grid.map((row) => row.join('')).join('\n'));`, snippet`
const fs = require('fs');
const lines = fs.readFileSync(0, 'utf8').split(/\r?\n/);
const n = Number(lines[0]);
const grid = lines.slice(1, n + 1).map((line) => [...line]);
process.stdout.write(grid.map((row) => row.join('')).join('\n'));`, ['字符矩阵', '网格']),
    pairTopic('mixed-records', '混合记录', '第一行 n，随后每行是姓名和分数。', 'js-acm-student-records', snippet`
const n = Number(readline());
const records = [];
for (let i = 0; i < n; i++) {
  const [name, score] = readline().trim().split(/\s+/);
  records.push({ name, score: Number(score) });
}
print(records.map(({ name, score }) => name + ':' + score).join('\n'));`, snippet`
const fs = require('fs');
const lines = fs.readFileSync(0, 'utf8').trimEnd().split(/\r?\n/);
const n = Number(lines[0]);
const records = lines.slice(1, n + 1).map((line) => {
  const [name, score] = line.trim().split(/\s+/);
  return { name, score: Number(score) };
});
process.stdout.write(records.map(({ name, score }) => name + ':' + score).join('\n'));`, ['记录', '字符串', '数字']),
    pairTopic('bigint', 'BigInt', '超过安全整数范围时，全程使用 BigInt 并输出十进制字符串。', 'js-acm-read-bigint', snippet`
const value = BigInt(readline().trim());
print((value + 1n).toString());`, snippet`
const fs = require('fs');
const value = BigInt(fs.readFileSync(0, 'utf8').trim());
console.log((value + 1n).toString());`, ['BigInt', '大整数']),
    pairTopic('large-scanner', '大输入 Scanner', '使用数组和递增游标，避免 shift()；输出统一缓冲。', 'js-acm-million-tokens', snippet`
const tokens = [];
for (let line; (line = readline()) !== undefined;) {
  const current = line.match(/\S+/g);
  if (current) tokens.push(...current);
}
let index = 0;
const next = () => tokens[index++];
const count = Number(next() ?? 0);
let sum = 0;
for (let i = 0; i < count; i++) sum += Number(next());
print(sum);`, snippet`
const fs = require('fs');
const tokens = fs.readFileSync(0, 'utf8').match(/\S+/g) ?? [];
let index = 0;
const next = () => tokens[index++];
const count = Number(next() ?? 0);
let sum = 0;
for (let i = 0; i < count; i++) sum += Number(next());
process.stdout.write(String(sum));`, ['Scanner', '游标', '性能']),
  ],
}

const outputSection: GuideSection = {
  slug: 'output-patterns',
  title: '常见输出模板',
  eyebrow: 'OUTPUT PATTERNS',
  description: 'stdout 只包含题目要求的结果。明确空格、换行、小数精度和批量输出策略。',
  topics: [
    pairTopic('output-array', '数组空格连接', '不要直接输出数组对象，使用 join 明确分隔符。', 'js-acm-output-array-space-join', snippet`
const values = readline().trim().split(/\s+/).map(Number);
print(values.join(' '));`, snippet`
const fs = require('fs');
const values = fs.readFileSync(0, 'utf8').trim().split(/\s+/).map(Number);
console.log(values.join(' '));`, ['join', '空格']),
    pairTopic('output-lines', '每项单独一行', '先构造字符串数组，再用换行连接。', 'js-acm-output-array-one-per-line', snippet`
const values = readline().trim().split(/\s+/);
print(values.join('\n'));`, snippet`
const fs = require('fs');
const values = fs.readFileSync(0, 'utf8').trim().split(/\s+/);
process.stdout.write(values.join('\n'));`, ['换行', 'join']),
    pairTopic('output-case', 'Case #x 格式', '序号通常从 1 开始，冒号和空格必须完全匹配。', 'js-acm-output-case-hash-format', snippet`
const T = Number(readline());
const out = [];
for (let i = 1; i <= T; i++) out.push('Case #' + i + ': ' + readline());
print(out.join('\n'));`, snippet`
const fs = require('fs');
const lines = fs.readFileSync(0, 'utf8').trimEnd().split(/\r?\n/);
const T = Number(lines[0]);
const out = [];
for (let i = 1; i <= T; i++) out.push('Case #' + i + ': ' + lines[i]);
process.stdout.write(out.join('\n'));`, ['Case', '格式']),
    pairTopic('output-decimal', '固定两位小数', '`toFixed(2)` 返回字符串；注意题目对舍入和 `-0` 的具体规则。', 'js-acm-output-fixed-two-decimals', snippet`
const value = Number(readline());
print(Object.is(value, -0) ? '0.00' : value.toFixed(2));`, snippet`
const fs = require('fs');
const value = Number(fs.readFileSync(0, 'utf8').trim());
console.log(Object.is(value, -0) ? '0.00' : value.toFixed(2));`, ['toFixed', '小数', '-0']),
    pairTopic('output-bigint', 'BigInt 输出', 'BigInt 转为字符串后输出，不会带 JavaScript 源码中的 `n` 后缀。', 'js-acm-output-bigint-without-suffix', snippet`
const value = BigInt(readline().trim());
print(value.toString());`, snippet`
const fs = require('fs');
const value = BigInt(fs.readFileSync(0, 'utf8').trim());
process.stdout.write(value.toString());`, ['BigInt', 'n 后缀']),
    pairTopic('output-buffer', '大量输出缓冲', '避免循环内频繁输出；先 push，最后一次 join。', 'js-acm-output-many-results-buffer', snippet`
const n = Number(readline());
const out = [];
for (let i = 0; i < n; i++) out.push(String(i));
print(out.join('\n'));`, snippet`
const fs = require('fs');
const n = Number(fs.readFileSync(0, 'utf8').trim());
const out = [];
for (let i = 0; i < n; i++) out.push(String(i));
process.stdout.write(out.join('\n'));`, ['缓冲', '性能']),
  ],
}

function errorTopic(
  id: string,
  title: string,
  summary: string,
  runtime: GuideRuntime,
  badCode: string,
  fixedCode: string,
  targetSlug: string,
  keywords: string[] = [],
): GuideTopic {
  return {
    id,
    title,
    summary,
    keywords,
    examples: [
      example(`${id}-bad`, '错误示例', runtime, badCode, targetSlug, { variant: 'incorrect' }),
      example(`${id}-fixed`, '推荐写法', runtime, fixedCode, targetSlug, { variant: 'recommended' }),
    ],
  }
}

const errorsSection: GuideSection = {
  slug: 'common-errors',
  title: '常见错误',
  eyebrow: 'WRONG ANSWER CLINIC',
  description: '用最小反例识别输入解析和输出格式错误。错误示例也可复制，但不能一键带入工作台。',
  topics: [
    errorTopic('blind-trim', '盲目 trim() 导致空输入异常', '空输入调用 `trim().split(...)` 可能得到 `[""]`，或让后续读取错误。先判断原始输入。', 'nodejs', snippet`
const tokens = require('fs').readFileSync(0, 'utf8').trim().split(/\s+/);
console.log(tokens.length); // 空输入错误输出 1`, snippet`
const raw = require('fs').readFileSync(0, 'utf8');
const tokens = raw.trim() === '' ? [] : raw.trim().split(/\s+/);
console.log(tokens.length);`, 'js-acm-handle-empty-input', ['trim', '空输入']),
    errorTopic('split-space', "split(' ') 无法处理多个空格", '连续空格会生成空 token，Tab 也不会被拆分。用 `/\\s+/`。', 'nodejs', snippet`
const values = '1  2\t3'.split(' ').map(Number);`, snippet`
const values = '1  2\t3'.trim().split(/\s+/).map(Number);`, 'js-acm-multiple-spaces', ['split', '多个空格', 'Tab']),
    errorTopic('unsafe-number', 'Number 超出安全整数范围', '超过 `2^53 - 1` 的整数不能由 Number 精确表示。', 'javascript-v8', snippet`
const value = Number(readline());
print(value + 1);`, snippet`
const value = BigInt(readline().trim());
print((value + 1n).toString());`, 'js-acm-read-bigint', ['Number', 'BigInt', 'MAX_SAFE_INTEGER']),
    errorTopic('mixed-bigint', 'BigInt 与 Number 混合运算', '`1n + 1` 会抛出 TypeError。参与同一运算的值必须统一类型。', 'nodejs', snippet`
const total = 1n + 1;`, snippet`
const total = 1n + BigInt(1);
console.log(total.toString());`, 'js-acm-read-bigint', ['BigInt', 'TypeError']),
    errorTopic('array-shift', 'Array.shift() 解析大量 token', '每次 shift 都可能移动剩余元素，数据量大时退化。使用递增游标。', 'nodejs', snippet`
while (tokens.length) {
  const value = tokens.shift();
}`, snippet`
let index = 0;
while (index < tokens.length) {
  const value = tokens[index++];
}`, 'js-acm-avoid-repeated-shift', ['shift', '游标', '性能']),
    errorTopic('repeat-split', '循环中重复 split', '同一行或全文不要在循环中反复拆分。预处理一次后复用。', 'nodejs', snippet`
for (let i = 0; i < n; i++) {
  const value = raw.split(/\s+/)[i];
}`, snippet`
const tokens = raw.match(/\S+/g) ?? [];
for (let i = 0; i < n; i++) {
  const value = tokens[i];
}`, 'js-acm-avoid-repeated-split', ['split', '性能']),
    errorTopic('array-console', 'console.log 输出数组格式错误', '`console.log([1, 2])` 输出带括号和逗号的调试格式，不是 ACM 要求的空格序列。', 'nodejs', snippet`
console.log([1, 2, 3]); // [ 1, 2, 3 ]`, snippet`
console.log([1, 2, 3].join(' ')); // 1 2 3`, 'js-acm-output-array-space-join', ['console.log', '数组', 'join']),
    errorTopic('debug-output', '输出调试文字', 'stdout 中任何提示语或调试信息都会参与比较并造成 Wrong Answer。', 'javascript-v8', snippet`
print('answer is:', answer);`, snippet`
print(answer);`, 'js-acm-output-no-debug-output', ['debug', 'Wrong Answer']),
    errorTopic('ignore-crlf', '忽略 CRLF', "只按 `\\n` 拆行时可能残留 `\\r`。使用 `/\\r?\\n/`。", 'nodejs', snippet`
const lines = raw.split('\n');`, snippet`
const lines = raw.split(/\r?\n/);`, 'js-acm-crlf-lf-compatible', ['CRLF', 'LF']),
    errorTopic('empty-line', '错误处理空行', '空字符串是有效行，不能用 truthy 判断代替 EOF 判断。', 'javascript-v8', snippet`
let line;
while ((line = readline())) {
  print(line);
}`, snippet`
for (let line; (line = readline()) !== undefined;) {
  print(line);
}`, 'js-acm-multi-line-with-empty', ['空行', 'EOF']),
    errorTopic('eof-overrun', 'EOF 循环越界', 'Node 行游标必须检查索引；V8 必须检查 `undefined`。', 'nodejs', snippet`
while (true) {
  console.log(lines[index++].trim());
}`, snippet`
while (index < lines.length) {
  console.log(lines[index++]);
}`, 'js-acm-node-line-cursor-eof', ['EOF', '越界']),
    errorTopic('runtime-mixing', 'V8 与 Node.js API 混用', '运行模式决定可用全局 API。V8 使用 readline/print；Node.js 使用 fs/console/process。', 'javascript-v8', snippet`
const input = require('fs').readFileSync(0, 'utf8');
console.log(input);`, snippet`
const input = readline();
print(input);`, 'js-acm-read-whole-line', ['V8', 'Node.js', 'require', 'readline']),
  ],
}

const performanceSection: GuideSection = {
  slug: 'performance',
  title: '大输入与性能',
  eyebrow: 'FAST I/O',
  description: '性能优化首先减少重复解析和输出调用。保持线性游标，并控制中间字符串和输出缓冲大小。',
  topics: [
    {
      id: 'perf-scanner',
      title: 'Node.js 高性能 Scanner',
      summary: '一次读取、一次 token 化、递增索引消费。`match(/\\S+/g) ?? []` 能安全处理空输入。',
      keywords: ['Scanner', '大输入', '游标'],
      examples: [example('perf-node-scanner', 'Node.js Scanner', 'nodejs', snippet`
const fs = require('fs');
const tokens = fs.readFileSync(0, 'utf8').match(/\S+/g) ?? [];
let index = 0;
const next = () => tokens[index++];
const nextNumber = () => Number(next());
const nextBigInt = () => BigInt(next());`, 'js-acm-million-tokens')],
    },
    {
      id: 'perf-v8-reader',
      title: 'V8 大量行读取',
      summary: 'V8 无法一次读取全文；逐行调用 readline，每行只 split 一次，并及时聚合结果。',
      keywords: ['V8', 'readline', '大量行'],
      examples: [example('perf-v8-lines', '逐行线性处理', 'javascript-v8', snippet`
let total = 0;
for (let line; (line = readline()) !== undefined;) {
  const tokens = line.match(/\S+/g);
  if (!tokens) continue;
  for (const token of tokens) total += Number(token);
}
print(total);`, 'js-acm-large-eof-data')],
    },
    pairTopic('perf-output', '批量输出与内存权衡', '中等输出一次 join；极大输出可分批 flush，始终遵守平台输出上限。', 'js-acm-output-large-output-memory-tradeoff', snippet`
const out = [];
for (let i = 0; i < 100000; i++) out.push(String(i));
print(out.join('\n'));`, snippet`
const chunks = [];
for (let i = 0; i < 100000; i++) chunks.push(String(i));
process.stdout.write(chunks.join('\n'));`, ['输出缓冲', '内存', '输出限制']),
    {
      id: 'perf-complexity',
      title: '避免隐性平方复杂度',
      summary: '循环内 `shift()`、重复 `split()`、反复拼接超长字符串都可能放大成本。优先数组 push、索引游标和最终 join。',
      keywords: ['复杂度', 'shift', 'split', 'join'],
      examples: [example('perf-cursor-output', '线性解析与输出', 'nodejs', snippet`
const fs = require('fs');
const tokens = fs.readFileSync(0, 'utf8').match(/\S+/g) ?? [];
const out = [];
for (let index = 0; index < tokens.length; index++) {
  out.push(index + ': ' + tokens[index]);
}
process.stdout.write(out.join('\n'));`, 'js-acm-efficient-recommended-pattern')],
    },
  ],
}

export const GUIDE_SECTIONS: readonly GuideSection[] = [
  v8Section,
  nodeSection,
  inputSection,
  outputSection,
  errorsSection,
  performanceSection,
]

export const GUIDE_SECTION_BY_SLUG = Object.fromEntries(
  GUIDE_SECTIONS.map((section) => [section.slug, section]),
) as Record<GuideSectionSlug, GuideSection>

function searchableText(section: GuideSection, topic: GuideTopic): string {
  return [
    section.title,
    section.description,
    topic.title,
    topic.summary,
    ...topic.keywords,
    ...topic.examples.flatMap((item) => [item.title, item.code, item.note ?? '', item.runtime]),
  ].join('\n').toLocaleLowerCase('zh-CN')
}

export function searchGuide(query: string): GuideSearchResult[] {
  const terms = query.trim().toLocaleLowerCase('zh-CN').split(/\s+/).filter(Boolean)
  if (!terms.length) return []
  return GUIDE_SECTIONS.flatMap((section) =>
    section.topics
      .filter((topic) => {
        const haystack = searchableText(section, topic)
        return terms.every((term) => haystack.includes(term))
      })
      .map((topic) => ({ section, topic })),
  )
}
