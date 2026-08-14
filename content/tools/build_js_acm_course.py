# ruff: noqa
from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
PROBLEM_ROOT = ROOT / "problems" / "js-acm"
REFERENCE_ROOT = ROOT / "reference-solutions" / "js-acm"
TEST_ROOT = ROOT / "test-data" / "js-acm"

SCENARIOS = (
    ("minimum_boundary", "最小边界"),
    ("normal", "普通输入"),
    ("duplicates", "重复值或重复行"),
    ("special_structure", "空白、Unicode 或特殊分隔结构"),
    ("performance", "固定种子的规模压力"),
    ("counterexample", "常见错误读取方式的反例"),
)
SCORES = (10, 15, 15, 20, 20, 20)


@dataclass(frozen=True)
class Task:
    slug: str
    title: str
    chapter: str
    category: str
    mode: str
    objective: str
    minutes: int = 8


@dataclass(frozen=True)
class Chapter:
    slug: str
    title: str
    description: str
    tasks: tuple[tuple[str, str, str], ...]


CHAPTERS = (
    Chapter(
        "js-acm-single-value",
        "课程一：单值输入",
        "掌握单个标量、整行、空输入与 BigInt 的安全读取。",
        (
            ("read-one-integer", "读取一个整数", "single-int"),
            ("read-one-float", "读取一个浮点数", "single-float"),
            ("read-one-word", "读取一个单词", "single-word"),
            ("read-whole-line", "读取一整行字符串", "single-line"),
            ("read-spaced-string", "读取可能包含空格的字符串", "preserve-line"),
            ("read-negative-number", "读取负数", "negative-int"),
            ("read-bigint", "读取超出安全范围的 BigInt", "single-bigint"),
            ("handle-empty-input", "空输入处理", "empty-input"),
        ),
    ),
    Chapter(
        "js-acm-single-line-values",
        "课程二：单行多值",
        "练习空白、制表符和自定义分隔符下的 token 化。",
        (
            ("two-integers", "两个整数", "sum-space"),
            ("many-integers", "多个整数", "sum-space"),
            ("integer-and-string", "整数与字符串混合", "mixed-token"),
            ("many-floats", "多个浮点数", "sum-float"),
            ("multiple-spaces", "使用多个空格分隔", "join-whitespace"),
            ("tab-separated", "使用制表符分隔", "join-whitespace"),
            ("outer-whitespace", "行首行尾存在空白", "join-whitespace"),
            ("comma-separated", "逗号分隔输入", "sum-comma"),
            ("colon-pipe-separated", "冒号或竖线分隔输入", "join-colon-pipe"),
            ("unknown-token-count", "不定数量 token", "token-stats"),
        ),
    ),
    Chapter(
        "js-acm-multi-line",
        "课程三：多行输入",
        "使用行数组和游标组织固定行数、计数行与空行。",
        (
            ("fixed-two-lines", "固定两行", "fixed-two-lines"),
            ("fixed-three-lines", "固定三行", "fixed-three-lines"),
            ("count-then-array", "第一行是数量，第二行是数组", "count-array"),
            ("n-following-lines", "第一行 n，后续 n 行", "counted-lines"),
            ("pair-per-line", "每行两个整数", "pair-lines"),
            ("variable-fields-per-line", "每行字段数量不同", "field-counts"),
            ("multi-line-strings", "多行字符串", "all-lines"),
            ("multi-line-with-empty", "包含空行的输入", "preserve-lines"),
            ("preserve-line-spaces", "保留每行原始空格", "preserve-lines"),
            ("crlf-lf-compatible", "CRLF 和 LF 兼容", "all-lines"),
        ),
    ),
    Chapter(
        "js-acm-test-cases",
        "课程四：T 组测试数据",
        "按 T 和组内长度推进游标，并正确组织分组输出。",
        (
            ("t-one-line", "第一行 T，后续每组一行", "t-line-sums"),
            ("t-fixed-two-lines", "每组固定两行", "t-two-lines"),
            ("t-count-array", "每组第一行 n，第二行数组", "t-count-array"),
            ("t-n-records", "每组包含 n 行记录", "t-counted-records"),
            ("t-variable-length", "不同测试组长度不同", "t-variable"),
            ("t-blank-separator", "测试组之间存在空行", "t-blank-lines"),
            ("t-one-result", "输出每组一个结果", "t-line-sums"),
            ("t-case-format", "输出 Case #x 格式", "t-case-format"),
            ("t-output-blank-line", "输出组间空行", "t-blank-output"),
            ("many-test-cases", "大量测试组", "t-many"),
        ),
    ),
    Chapter(
        "js-acm-read-until-eof",
        "课程五：读取到 EOF",
        "固定 EOF 语义，分别使用 V8 readline() 与 Node 行游标读取。",
        (
            ("line-until-eof", "每行一组数据直到 EOF", "eof-lines"),
            ("pairs-until-eof", "每行两个整数直到 EOF", "eof-pairs"),
            ("two-lines-until-eof", "每组固定两行直到 EOF", "eof-two-lines"),
            ("blocks-until-eof", "第一行 n，随后 n 行，重复直到 EOF", "eof-blocks"),
            ("blank-before-eof", "EOF 前存在空行", "preserve-lines"),
            ("eof-without-newline", "文件末尾没有换行符", "eof-lines"),
            ("eof-many-newlines", "文件末尾有多个换行符", "eof-nonempty-lines"),
            ("v8-readline-eof", "V8 多次 readline() 处理 EOF", "eof-lines"),
            ("node-line-cursor-eof", "Node.js 行数组和游标处理 EOF", "eof-lines"),
            ("large-eof-data", "大量 EOF 数据", "eof-sum"),
        ),
    ),
    Chapter(
        "js-acm-sentinel",
        "课程六：哨兵结束输入",
        "识别哨兵并保证终止标记不参与计算或输出。",
        (
            ("sentinel-zero", "输入 0 结束", "sentinel-zero"),
            ("sentinel-minus-one", "输入 -1 结束", "sentinel-minus-one"),
            ("sentinel-zero-pair", "输入 0 0 结束", "sentinel-zero-pair"),
            ("sentinel-end-word", "输入 END 结束", "sentinel-end"),
            ("sentinel-multi-line-group", "每组多行，首行特定值结束", "sentinel-blocks"),
            ("sentinel-not-output", "哨兵不参与输出", "sentinel-zero"),
            ("eof-or-sentinel", "EOF 与哨兵都可能结束输入", "sentinel-end"),
        ),
    ),
    Chapter(
        "js-acm-arrays",
        "课程七：数组输入",
        "覆盖定长、不定长、多行、BigInt 与空数组。",
        (
            ("integer-array-line", "一行整数数组", "array-int"),
            ("string-array-line", "一行字符串数组", "array-string"),
            ("multi-line-arrays", "多行数组", "array-lines"),
            ("known-length-array", "已知长度数组", "array-known"),
            ("unknown-length-array", "未知长度数组", "array-unknown"),
            ("flattened-two-dimensional-array", "二维数组展开输入", "array-flat-matrix"),
            ("bigint-array", "BigInt 数组", "array-bigint"),
            ("float-array", "浮点数组", "array-float"),
            ("negative-array", "含负数数组", "array-negative"),
            ("zero-length-array", "数组长度为 0", "array-empty"),
        ),
    ),
    Chapter(
        "js-acm-matrices",
        "课程八：矩阵输入",
        "使用行列维度读取规则矩阵、字符网格和不规则二维数据。",
        (
            ("integer-matrix-nm", "n 行 m 列整数矩阵", "matrix-nm"),
            ("square-matrix", "方阵", "matrix-square"),
            ("character-matrix", "字符矩阵", "matrix-char-spaced"),
            ("compact-character-grid", "没有空格的字符网格", "matrix-char-grid"),
            ("matrix-followed-by-field", "矩阵后继续读取其他字段", "matrix-extra"),
            ("t-matrices", "T 组矩阵", "matrix-t"),
            ("ragged-two-dimensional-data", "不规则二维数据", "matrix-ragged"),
            ("large-matrix", "大型矩阵", "matrix-nm"),
            ("negative-matrix", "矩阵含负数", "matrix-negative"),
            ("float-matrix", "矩阵含浮点数", "matrix-float"),
        ),
    ),
    Chapter(
        "js-acm-strings",
        "课程九：字符串输入",
        "区分 token、整行、空串、Unicode 码点和 UTF-8 字节。",
        (
            ("string-word", "单个单词", "string-word"),
            ("string-sentence", "一整行句子", "string-sentence"),
            ("string-multiple-lines", "多行文本", "string-lines"),
            ("string-preserve-spaces", "保留空格", "preserve-line"),
            ("string-empty", "空字符串", "string-empty"),
            ("string-chinese-unicode", "Unicode 中文", "string-codepoints"),
            ("string-emoji-surrogate", "表情符号和代理对", "string-units-points"),
            ("string-character-byte", "区分字符与字节", "string-utf8-bytes"),
            ("string-comma-separated", "逗号分隔字符串", "string-csv"),
            ("string-json-safe", "JSON 风格字符串（禁止 eval）", "string-json"),
        ),
    ),
    Chapter(
        "js-acm-mixed-nested",
        "课程十：混合和嵌套格式",
        "综合使用行游标、token 游标与变长记录。",
        (
            ("student-records", "n 后跟 n 个学生记录", "mixed-students"),
            ("name-and-score", "姓名和分数", "mixed-name-score"),
            ("string-followed-array", "字符串后跟数组", "mixed-string-array"),
            ("matrix-followed-queries", "矩阵后跟查询数量", "mixed-matrix-queries"),
            ("variable-record-groups", "多组变长记录", "mixed-variable-groups"),
            ("graph-edge-list", "图的 n、m 和 m 条边", "mixed-edges"),
            ("adjacency-list-input", "邻接表式输入", "mixed-adjacency"),
            ("interval-records", "区间记录", "mixed-intervals"),
            ("command-stream", "命令流", "mixed-commands"),
            ("different-field-types", "不同类型字段组合", "mixed-types"),
        ),
    ),
    Chapter(
        "js-acm-large-input",
        "课程十一：大输入性能",
        "使用一次读取、索引游标和输出缓冲避免二次方退化。",
        (
            ("one-hundred-thousand-integers", "十万个整数", "perf-sum"),
            ("million-tokens", "百万级 token", "perf-count"),
            ("many-lines", "大量行", "perf-lines"),
            ("large-string", "大字符串", "perf-string"),
            ("large-bigint-data", "BigInt 大数据", "perf-bigint"),
            ("avoid-repeated-shift", "避免重复 shift()", "perf-sum"),
            ("use-index-cursor", "使用索引游标", "perf-pairs"),
            ("avoid-repeated-split", "避免循环中重复 split()", "perf-line-sums"),
            ("buffer-output-join", "输出缓冲数组后统一 join()", "perf-output"),
            ("efficient-recommended-pattern", "对比低效和推荐写法", "perf-count"),
        ),
    ),
)


def build_tasks() -> list[Task]:
    tasks: list[Task] = []
    for chapter in CHAPTERS:
        for slug, title, mode in chapter.tasks:
            tasks.append(
                Task(
                    slug=f"js-acm-{slug}",
                    title=title,
                    chapter=chapter.slug,
                    category=chapter.slug.removeprefix("js-acm-"),
                    mode=mode,
                    objective=f"能够在两种 JavaScript ACM 运行模式中正确处理“{title}”，并输出规范化结果。",
                    minutes=12 if chapter.slug == "js-acm-large-input" else 8,
                )
            )
    return tasks


JS_SOLVER_CORE = r"""
const tokens = (line = '') => line.trim() === '' ? [] : line.trim().split(/\s+/);
const numbers = (line = '') => tokens(line).map(Number);
const nonempty = lines.filter((line) => line.trim() !== '');
const sum = (values) => values.reduce((answer, value) => answer + value, 0);
const sumBig = (values) => values.reduce((answer, value) => answer + BigInt(value), 0n);
let answer = '';
switch (MODE) {
  case 'single-int': answer = String(Number((lines[0] || '').trim()) + 1); break;
  case 'single-float': answer = Number((lines[0] || '').trim()).toFixed(2); break;
  case 'single-word': answer = (tokens(lines[0])[0] || '').toUpperCase(); break;
  case 'single-line': answer = lines[0] || ''; break;
  case 'preserve-line': answer = `[${lines[0] || ''}]`; break;
  case 'negative-int': answer = String(Math.abs(Number((lines[0] || '').trim()))); break;
  case 'single-bigint': answer = String(BigInt((lines[0] || '0').trim()) + 1n); break;
  case 'empty-input': answer = lines.length === 0 ? 'EMPTY' : lines[0]; break;
  case 'sum-space': answer = String(sum(numbers(lines[0]))); break;
  case 'mixed-token': {
    const values = tokens(lines[0]); answer = `${Number(values[0])}:${values.slice(1).join(' ')}`; break;
  }
  case 'sum-float': answer = sum(numbers(lines[0])).toFixed(2); break;
  case 'join-whitespace': answer = tokens(lines[0]).join('|'); break;
  case 'sum-comma': answer = String(sum((lines[0] || '').split(',').map((v) => Number(v.trim())))); break;
  case 'join-colon-pipe': answer = (lines[0] || '').split(/[:|]/).map((v) => v.trim()).join('|'); break;
  case 'token-stats': {
    const values = numbers(lines[0]); answer = `${values.length} ${sum(values)}`; break;
  }
  case 'fixed-two-lines': answer = `${lines[0] || ''}|${lines[1] || ''}`; break;
  case 'fixed-three-lines': answer = lines.slice(0, 3).join('>'); break;
  case 'count-array': {
    const n = Number((lines[0] || '0').trim()); answer = String(sum(numbers(lines[1]).slice(0, n))); break;
  }
  case 'counted-lines': {
    const n = Number((lines[0] || '0').trim()); answer = lines.slice(1, n + 1).join('|'); break;
  }
  case 'pair-lines': answer = nonempty.map((line) => String(sum(numbers(line).slice(0, 2)))).join('\n'); break;
  case 'field-counts': answer = lines.map((line) => String(tokens(line).length)).join(' '); break;
  case 'all-lines': answer = lines.join('|'); break;
  case 'preserve-lines': answer = lines.map((line) => `[${line}]`).join('\n'); break;
  case 't-line-sums': {
    const t = Number(nonempty[0] || 0); answer = nonempty.slice(1, t + 1).map((line) => String(sum(numbers(line)))).join('\n'); break;
  }
  case 't-two-lines': {
    const t = Number(nonempty[0] || 0); const out = []; let p = 1;
    for (let i = 0; i < t; i += 1) out.push(`${nonempty[p++] || ''}|${nonempty[p++] || ''}`);
    answer = out.join('\n'); break;
  }
  case 't-count-array': {
    const t = Number(nonempty[0] || 0); const out = []; let p = 1;
    for (let i = 0; i < t; i += 1) { const n = Number(nonempty[p++]); out.push(String(sum(numbers(nonempty[p++]).slice(0, n)))); }
    answer = out.join('\n'); break;
  }
  case 't-counted-records': {
    const t = Number(nonempty[0] || 0); const out = []; let p = 1;
    for (let i = 0; i < t; i += 1) { const n = Number(nonempty[p++]); out.push(nonempty.slice(p, p + n).join(',')); p += n; }
    answer = out.join('\n'); break;
  }
  case 't-variable': {
    const all = nonempty.flatMap((line) => tokens(line)); let p = 0; const t = Number(all[p++]); const out = [];
    for (let i = 0; i < t; i += 1) { const n = Number(all[p++]); out.push(String(sum(all.slice(p, p + n).map(Number)))); p += n; }
    answer = out.join('\n'); break;
  }
  case 't-blank-lines': {
    const t = Number(nonempty[0] || 0); answer = nonempty.slice(1, t + 1).map((line) => tokens(line).join('|')).join('\n'); break;
  }
  case 't-case-format': {
    const t = Number(nonempty[0] || 0); answer = nonempty.slice(1, t + 1).map((line, i) => `Case #${i + 1}: ${sum(numbers(line))}`).join('\n'); break;
  }
  case 't-blank-output': {
    const t = Number(nonempty[0] || 0); answer = nonempty.slice(1, t + 1).map((line) => String(sum(numbers(line)))).join('\n\n'); break;
  }
  case 't-many': {
    const t = Number(nonempty[0] || 0); answer = String(sum(nonempty.slice(1, t + 1).map(Number))); break;
  }
  case 'eof-lines': answer = lines.map((line) => line.toUpperCase()).join('\n'); break;
  case 'eof-nonempty-lines': answer = nonempty.map((line) => line.toUpperCase()).join('\n'); break;
  case 'eof-pairs': answer = nonempty.map((line) => String(sum(numbers(line).slice(0, 2)))).join('\n'); break;
  case 'eof-two-lines': {
    const out = []; for (let p = 0; p + 1 < lines.length; p += 2) out.push(`${lines[p]}|${lines[p + 1]}`); answer = out.join('\n'); break;
  }
  case 'eof-blocks': {
    const out = []; let p = 0; while (p < nonempty.length) { const n = Number(nonempty[p++]); out.push(nonempty.slice(p, p + n).join(',')); p += n; } answer = out.join('\n'); break;
  }
  case 'eof-sum': answer = String(sum(nonempty.flatMap((line) => numbers(line)))); break;
  case 'sentinel-zero': {
    const out = []; for (const value of nonempty.map(Number)) { if (value === 0) break; out.push(String(value * 2)); } answer = out.join('\n'); break;
  }
  case 'sentinel-minus-one': {
    const out = []; for (const value of nonempty.map(Number)) { if (value === -1) break; out.push(String(value * 2)); } answer = out.join('\n'); break;
  }
  case 'sentinel-zero-pair': {
    const out = []; for (const line of nonempty) { const [a, b] = numbers(line); if (a === 0 && b === 0) break; out.push(String(a + b)); } answer = out.join('\n'); break;
  }
  case 'sentinel-end': {
    const out = []; for (const line of lines) { if (line === 'END') break; out.push(line.toUpperCase()); } answer = out.join('\n'); break;
  }
  case 'sentinel-blocks': {
    const out = []; let p = 0; while (p < nonempty.length) { const n = Number(nonempty[p++]); if (n === 0) break; out.push(nonempty.slice(p, p + n).join(',')); p += n; } answer = out.join('\n'); break;
  }
  case 'array-int': answer = String(sum(numbers(lines[0]))); break;
  case 'array-string': answer = tokens(lines[0]).slice().reverse().join('|'); break;
  case 'array-lines': answer = nonempty.map((line) => String(sum(numbers(line)))).join('\n'); break;
  case 'array-known': {
    const values = nonempty.flatMap((line) => numbers(line)); const n = values.shift() || 0; answer = n === 0 ? 'EMPTY' : String(Math.max(...values.slice(0, n))); break;
  }
  case 'array-unknown': answer = String(numbers(lines[0]).length); break;
  case 'array-flat-matrix': {
    const values = nonempty.flatMap((line) => numbers(line)); const n = values.shift() || 0; const m = values.shift() || 0; answer = `${n}x${m}:${sum(values.slice(0, n * m))}`; break;
  }
  case 'array-bigint': answer = String(sumBig(tokens(lines[0]))); break;
  case 'array-float': {
    const values = numbers(lines[0]); answer = (values.length ? sum(values) / values.length : 0).toFixed(2); break;
  }
  case 'array-negative': answer = String(Math.min(...numbers(lines[0]))); break;
  case 'array-empty': {
    const values = nonempty.flatMap((line) => numbers(line)); const n = values.shift() || 0; answer = n === 0 ? 'EMPTY' : values.slice(0, n).join(' '); break;
  }
  case 'matrix-nm': case 'matrix-negative': {
    const [n, m] = numbers(lines[0]); const values = lines.slice(1, n + 1).flatMap(numbers).slice(0, n * m); answer = String(sum(values)); break;
  }
  case 'matrix-square': {
    const n = Number(lines[0]); const matrix = lines.slice(1, n + 1).map(numbers); answer = String(sum(matrix.map((row, i) => row[i]))); break;
  }
  case 'matrix-char-spaced': {
    const [n] = numbers(lines[0]); answer = String(lines.slice(1, n + 1).flatMap(tokens).filter((value) => value === 'X').length); break;
  }
  case 'matrix-char-grid': {
    const [n] = numbers(lines[0]); answer = String(lines.slice(1, n + 1).join('').split('').filter((value) => value === '#').length); break;
  }
  case 'matrix-extra': {
    const [n, m] = numbers(lines[0]); const total = sum(lines.slice(1, n + 1).flatMap(numbers).slice(0, n * m)); answer = `${total} ${lines[n + 1] || ''}`; break;
  }
  case 'matrix-t': {
    const values = nonempty.flatMap((line) => numbers(line)); let p = 0; const t = values[p++]; const out = [];
    for (let k = 0; k < t; k += 1) { const n = values[p++]; const m = values[p++]; out.push(String(sum(values.slice(p, p + n * m)))); p += n * m; } answer = out.join('\n'); break;
  }
  case 'matrix-ragged': {
    const n = Number(lines[0]); answer = lines.slice(1, n + 1).map((line) => String(numbers(line).length)).join(' '); break;
  }
  case 'matrix-float': {
    const [n, m] = numbers(lines[0]); answer = sum(lines.slice(1, n + 1).flatMap(numbers).slice(0, n * m)).toFixed(2); break;
  }
  case 'string-word': answer = String(Array.from(tokens(lines[0])[0] || '').length); break;
  case 'string-sentence': answer = String(tokens(lines[0]).length); break;
  case 'string-lines': answer = String(lines.reduce((total, line) => total + Array.from(line).length, 0)); break;
  case 'string-empty': answer = (lines[0] || '') === '' ? 'EMPTY' : 'NOT EMPTY'; break;
  case 'string-codepoints': answer = String(Array.from(lines[0] || '').length); break;
  case 'string-units-points': answer = `${(lines[0] || '').length} ${Array.from(lines[0] || '').length}`; break;
  case 'string-utf8-bytes': answer = `${Array.from(lines[0] || '').length} ${unescape(encodeURIComponent(lines[0] || '')).length}`; break;
  case 'string-csv': answer = (lines[0] || '').split(',').map((value) => value.trim()).join('|'); break;
  case 'string-json': {
    const value = JSON.parse(lines[0] || 'null'); answer = Array.isArray(value) ? `array:${value.length}` : `${typeof value}:${String(value.name || '')}`; break;
  }
  case 'mixed-students': case 'mixed-name-score': {
    const n = Number(lines[0]); answer = lines.slice(1, n + 1).map((line) => { const values = tokens(line); return `${values[0]}:${Number(values[1])}`; }).join('\n'); break;
  }
  case 'mixed-string-array': {
    const n = Number(lines[1]); answer = `${lines[0]}:${sum(numbers(lines[2]).slice(0, n))}`; break;
  }
  case 'mixed-matrix-queries': {
    const [n, m] = numbers(lines[0]); const total = sum(lines.slice(1, n + 1).flatMap(numbers).slice(0, n * m)); const q = Number(lines[n + 1]); answer = `${total} ${q}`; break;
  }
  case 'mixed-variable-groups': {
    const values = nonempty.flatMap((line) => tokens(line)); let p = 0; const g = Number(values[p++]); const out = []; for (let i = 0; i < g; i += 1) { const n = Number(values[p++]); out.push(values.slice(p, p + n).join(',')); p += n; } answer = out.join('\n'); break;
  }
  case 'mixed-edges': {
    const [n, m] = numbers(lines[0]); const degree = Array(n).fill(0); for (const line of lines.slice(1, m + 1)) { const [a, b] = numbers(line); degree[a - 1] += 1; degree[b - 1] += 1; } answer = degree.join(' '); break;
  }
  case 'mixed-adjacency': {
    const n = Number(lines[0]); answer = lines.slice(1, n + 1).map((line) => Math.max(0, numbers(line).length - 1)).join(' '); break;
  }
  case 'mixed-intervals': {
    const n = Number(lines[0]); answer = String(sum(lines.slice(1, n + 1).map((line) => { const [l, r] = numbers(line); return r - l; }))); break;
  }
  case 'mixed-commands': {
    const n = Number(lines[0]); answer = lines.slice(1, n + 1).map((line) => tokens(line).join(':')).join('\n'); break;
  }
  case 'mixed-types': {
    const values = tokens(lines[0]); answer = `${values[0]}|${Number(values[1])}|${Number(values[2]).toFixed(1)}|${values.slice(3).join(' ')}`; break;
  }
  case 'perf-sum': answer = String(sum(nonempty.flatMap((line) => numbers(line)))); break;
  case 'perf-count': answer = String(nonempty.flatMap((line) => tokens(line)).length); break;
  case 'perf-lines': answer = String(lines.length); break;
  case 'perf-string': answer = String(Array.from(lines.join('')).length); break;
  case 'perf-bigint': answer = String(sumBig(nonempty.flatMap((line) => tokens(line)))); break;
  case 'perf-pairs': answer = String(sum(nonempty.flatMap((line) => numbers(line)))); break;
  case 'perf-line-sums': answer = nonempty.map((line) => String(sum(numbers(line)))).join('\n'); break;
  case 'perf-output': answer = nonempty.map((line, index) => `${index + 1}:${line}`).join('\n'); break;
  default: throw new Error('unsupported training mode');
}
""".strip()


def _repeat_lines(line: str, count: int) -> str:
    return "\n".join(line for _ in range(count)) + "\n"


def _write_utf8(path: Path, content: str) -> None:
    path.write_bytes(content.replace("\r\n", "\n").encode())


def cases_for(mode: str) -> list[str]:
    banks: dict[str, list[str]] = {
        "single-int": ["7\n", "-3\n", "0\n", "  42  \n", "999999\n", "+8\n", "-0\n", "2147483647"],
        "single-float": ["3.5\n", "-0.125\n", "0\n", "  12.345  \n", "99999.999\n", ".5\n", "-8.0\n", "1e3"],
        "single-word": ["hello\n", "CodeArena\n", "a\n", "  spaced  \n", "x" * 1000 + "\n", "重复\n", "word\textra\n", "last"],
        "single-line": ["hello world\n", "原样文本\n", "a\n", " leading and trailing \n", "x" * 10000 + "\n", "重复 重复\n", "tab\tinside\n", "no-newline"],
        "preserve-line": ["hello world\n", "  keep me  \n", "\n", "\ttext\t\n", "x" * 10000 + "\n", "中 文\n", "three   spaces\n", " tail "],
        "negative-int": ["-7\n", "-100\n", "0\n", "  -42  \n", "-999999\n", "-1\n", "-0\n", "-2147483648"],
        "single-bigint": ["9007199254740993\n", "123456789012345678901234567890\n", "0\n", "  -9007199254740995 \n", "9" * 1000 + "\n", "11111111111111111111\n", "-1\n", "99999999999999999999"],
        "empty-input": ["", "hello\n", "\n", "  \n", "x" * 10000, "中文\n", "\r\n", "tail"],
        "sum-space": ["1 2\n", "10 -3 5\n", "0 0 0\n", "  7   8  \n", " ".join("1" for _ in range(10000)) + "\n", "5 5 5\n", "-9 4\n", "100 -100"],
        "mixed-token": ["7 apple\n", "0 hello world\n", "-1 x\n", "  42   spaced text  \n", "9 " + "x" * 10000 + "\n", "8 重复 重复\n", "3 a\tb\n", "5 tail value"],
        "sum-float": ["1.5 2.25\n", "-1.25 0.5 2\n", "0 0\n", "  3.5   4.25 \n", " ".join("0.1" for _ in range(10000)) + "\n", "2.5 2.5\n", ".5 -.25\n", "1e2 0.5"],
        "join-whitespace": ["a b c\n", "one   two\n", "x x x\n", "  left\tmiddle  right \n", " ".join(str(i) for i in range(10000)) + "\n", "中 文\n", "a\t\tb\n", "tail value"],
        "sum-comma": ["1,2,3\n", "10, -3, 5\n", "0,0\n", " 7 , 8 , 9 \n", ",".join("1" for _ in range(10000)) + "\n", "5,5,5\n", "-9,4\n", "100,-100"],
        "join-colon-pipe": ["a:b|c\n", "name:score|level\n", "x|x:x\n", " left : middle | right \n", "|".join(str(i) for i in range(10000)) + "\n", "中:文\n", "a::b\n", "tail|value"],
        "token-stats": ["1 2 3\n", "10 -3 5 8\n", "0\n", "  7   8  \n", " ".join("1" for _ in range(10000)) + "\n", "5 5 5\n", "-9 4\n", "100 -100"],
        "fixed-two-lines": ["alpha\nbeta\n", "1 2\nhello world\n", "x\nx\n", "  left  \nright\n", "x" * 5000 + "\ny" * 5000 + "\n", "中文\n🙂\n", "\nsecond\n", "first\nlast"],
        "fixed-three-lines": ["a\nb\nc\n", "one two\n3\nend\n", "x\nx\nx\n", "  a  \n\nb\n", "a" * 3000 + "\nb\nc\n", "中\n文\n🙂\n", "\n\nthird\n", "first\nsecond\nlast"],
        "count-array": ["3\n1 2 3\n", "5\n10 -2 0 4 8\n", "0\n\n", "4\n 1   2  3 4 \n", "10000\n" + " ".join("1" for _ in range(10000)) + "\n", "3\n5 5 5\n", "2\n9 100 777\n", "1\n-8"],
        "counted-lines": ["2\na\nb\n", "3\none\ntwo words\nthree\n", "1\nx\n", "3\nfirst\n\nthird\n", "1000\n" + _repeat_lines("x", 1000), "3\nsame\nsame\nsame\n", "2\n  raw  \nlast\n", "1\ntail"],
        "pair-lines": ["1 2\n3 4\n", "10 -2\n0 8\n5 5\n", "0 0\n", " 1   2 \n", _repeat_lines("1 1", 10000), "5 5\n5 5\n", "-9 4\n", "100 -100"],
        "field-counts": ["a b\nc d e\n", "one\n1 2 3 4\n", "x x\n", "  a   b c \n\n", _repeat_lines("1 2 3 4 5", 5000), "same same\n", "\nvalue\n", "last field"],
        "all-lines": ["a\nb\n", "one two\nthree\n", "x\n", " first \nsecond\n", _repeat_lines("line", 10000), "重复\n重复\n", "a\r\nb\r\n", "no\nfinal"],
        "preserve-lines": ["a\n\nb\n", "  first  \nsecond\n", "\n", "\t\n spaced \n", _repeat_lines("line", 10000), "重复\n重复\n", "a\r\n\r\nb\r\n", "last\n"],
        "eof-lines": ["a\nb\n", "one two\nthree\n", "x\n", " first \nsecond\n", _repeat_lines("line", 10000), "repeat\nrepeat\n", "a\r\nb\r\n", "no-final-newline"],
        "eof-nonempty-lines": ["a\nb\n", "one\n\nthree\n", "x\n", "\nfirst\n", _repeat_lines("line", 10000), "repeat\nrepeat\n", "a\n\n\n", "tail\n\n\n"],
        "eof-pairs": ["1 2\n3 4\n", "10 -2\n0 8\n", "0 0\n", " 1   2 \n", _repeat_lines("1 1", 10000), "5 5\n5 5\n", "-9 4\n", "100 -100"],
        "eof-two-lines": ["a\nb\nc\nd\n", "one\ntwo words\n", "x\nx\n", "\nsecond\n", _repeat_lines("line", 10000), "same\nsame\n", "  raw  \nlast\n", "first\nlast"],
        "eof-blocks": ["2\na\nb\n1\nc\n", "1\none\n3\na\nb\nc\n", "1\nx\n", "2\nfirst\n\n", "1000\n" + _repeat_lines("x", 1000), "2\nsame\nsame\n", "1\n raw \n", "1\ntail"],
        "eof-sum": ["1\n2\n", "10 -2\n3\n", "0\n", " 1   2 \n", _repeat_lines("1 1 1 1", 25000), "5\n5\n", "-9\n4\n", "100\n-100"],
        "sentinel-zero": ["1\n2\n0\n", "10\n-2\n0\n99\n", "0\n", " 7 \n0\n", _repeat_lines("1", 10000) + "0\n", "5\n5\n0\n", "-9\n0\n", "100\n0"],
        "sentinel-minus-one": ["1\n2\n-1\n", "10\n0\n-1\n99\n", "-1\n", " 7 \n-1\n", _repeat_lines("1", 10000) + "-1\n", "5\n5\n-1\n", "-9\n-1\n", "100\n-1"],
        "sentinel-zero-pair": ["1 2\n0 0\n", "10 -2\n3 4\n0 0\n", "0 0\n", " 7  8 \n0 0\n", _repeat_lines("1 1", 10000) + "0 0\n", "5 5\n5 5\n0 0\n", "0 5\n0 0\n", "100 -100\n0 0"],
        "sentinel-end": ["a\nb\nEND\n", "hello world\nEND\nafter\n", "END\n", "  raw  \nEND\n", _repeat_lines("line", 10000) + "END\n", "same\nsame\nEND\n", "end\nEND\n", "tail\nEND"],
        "sentinel-blocks": ["2\na\nb\n0\n", "1\none\n2\na\nb\n0\n", "0\n", "2\nfirst\n\n0\n", "1000\n" + _repeat_lines("x", 1000) + "0\n", "2\nsame\nsame\n0\n", "1\n raw \n0\n", "1\ntail\n0"],
        "array-int": ["1 2 3\n", "10 -2 0 8\n", "0\n", " 1   2 \n", " ".join("1" for _ in range(10000)) + "\n", "5 5 5\n", "-9 4\n", "100 -100"],
        "array-string": ["a b c\n", "one two words\n", "x\n", "  left   right \n", " ".join(str(i) for i in range(10000)) + "\n", "same same\n", "中 文\n", "last value"],
        "array-lines": ["1 2\n3 4\n", "10 -2 0\n8\n", "0\n", " 1   2 \n", _repeat_lines("1 1", 10000), "5 5\n5 5\n", "-9 4\n", "100 -100"],
        "array-known": ["3\n1 9 2\n", "5\n10 -2 0 8 4\n", "1\n0\n", "4\n 1   2 3 4 \n", "10000\n" + " ".join(str(i) for i in range(10000)) + "\n", "3\n5 5 5\n", "2\n-9 -4 100\n", "1\n100"],
        "array-unknown": ["1 2 3\n", "10 -2 0 8\n", "0\n", " 1   2 \n", " ".join("1" for _ in range(10000)) + "\n", "5 5 5\n", "-9 4\n", "100 -100"],
        "array-flat-matrix": ["2 2\n1 2 3 4\n", "2 3\n10 -2 0 8 4 1\n", "1 1\n0\n", "2 2\n 1   2 3 4 \n", "100 100\n" + " ".join("1" for _ in range(10000)) + "\n", "2 2\n5 5 5 5\n", "1 2\n-9 4\n", "1 1\n100"],
        "array-bigint": ["9007199254740993 2\n", "12345678901234567890 -10\n", "0\n", " 1   2 \n", " ".join("999999999999999999" for _ in range(10000)) + "\n", "5 5 5\n", "-9007199254740993 4\n", "100000000000000000000"],
        "array-float": ["1.5 2.5\n", "10 -2 0.5\n", "0\n", " 1   2 \n", " ".join("0.1" for _ in range(10000)) + "\n", "5.5 5.5\n", "-9.25 4\n", "100.5 -100"],
        "array-negative": ["-1 -2 -3\n", "10 -2 0 8\n", "0\n", " -1   -2 \n", " ".join(str(-i) for i in range(10000)) + "\n", "-5 -5 -5\n", "-9 4\n", "100 -100"],
        "array-empty": ["0\n\n", "3\n1 2 3\n", "1\n0\n", "2\n 1   2 \n", "10000\n" + " ".join("1" for _ in range(10000)) + "\n", "3\n5 5 5\n", "0\n", "1\n100"],
    }
    if mode in banks:
        return banks[mode]
    return structured_cases(mode)


def structured_cases(mode: str) -> list[str]:
    banks: dict[str, list[str]] = {
        "t-line-sums": ["2\n1 2\n3 4\n", "3\n10 -2\n0 8\n5 5\n", "1\n0\n", "2\n 1   2 \n3\t4\n", "10000\n" + _repeat_lines("1 1", 10000), "3\n5 5\n5 5\n5 5\n", "2\n-9 4\n0 0\n", "1\n100 -100"],
        "t-two-lines": ["2\na\nb\nc\nd\n", "1\nhello world\n42\n", "1\nx\nx\n", "2\n first \n\nthird\nfourth\n", "1000\n" + _repeat_lines("line", 2000), "2\nsame\nsame\nsame\nsame\n", "1\n中\n🙂\n", "1\nfirst\nlast"],
        "t-count-array": ["2\n3\n1 2 3\n2\n4 5\n", "1\n5\n10 -2 0 4 8\n", "1\n0\n\n", "2\n2\n 1  2 \n1\n3\n", "1000\n" + "1\n1\n" * 1000, "2\n3\n5 5 5\n3\n5 5 5\n", "1\n2\n9 100 777\n", "1\n1\n-8"],
        "t-counted-records": ["2\n2\na\nb\n1\nc\n", "1\n3\none\ntwo words\nthree\n", "1\n1\nx\n", "1\n3\nfirst\n\nthird\n", "1\n1000\n" + _repeat_lines("x", 1000), "1\n3\nsame\nsame\nsame\n", "1\n2\n raw \nlast\n", "1\n1\ntail"],
        "t-variable": ["2\n3 1 2 3\n2 4 5\n", "3\n1 10\n4 -2 0 4 8\n2 5 5\n", "1\n0\n", "2\n2   1 2\n1\t3\n", "1000\n" + "1 1\n" * 1000, "2\n3 5 5 5\n3 5 5 5\n", "1\n2 -9 4\n", "1\n1 100"],
        "t-blank-lines": ["2\n\na b\n\nc d\n", "3\none\n\ntwo words\n\nthree\n", "1\n\nx\n", "2\n\n first \n\nsecond\n", "1000\n\n" + "line\n\n" * 1000, "2\n\nsame\n\nsame\n", "2\n\n中\n\n🙂\n", "1\n\ntail"],
        "t-case-format": ["2\n1 2\n3 4\n", "3\n10 -2\n0 8\n5 5\n", "1\n0\n", "2\n 1   2 \n3\t4\n", "10000\n" + _repeat_lines("1 1", 10000), "3\n5 5\n5 5\n5 5\n", "2\n-9 4\n0 0\n", "1\n100 -100"],
        "t-blank-output": ["2\n1 2\n3 4\n", "3\n10 -2\n0 8\n5 5\n", "1\n0\n", "2\n 1   2 \n3\t4\n", "1000\n" + _repeat_lines("1 1", 1000), "3\n5 5\n5 5\n5 5\n", "2\n-9 4\n0 0\n", "1\n100 -100"],
        "t-many": ["3\n1\n2\n3\n", "5\n10\n-2\n0\n8\n4\n", "1\n0\n", "3\n 1 \n2\n3\n", "100000\n" + _repeat_lines("1", 100000), "3\n5\n5\n5\n", "2\n-9\n4\n", "1\n100"],
        "matrix-nm": ["2 3\n1 2 3\n4 5 6\n", "2 2\n10 -2\n0 8\n", "1 1\n0\n", "2 2\n 1   2 \n3\t4\n", "200 200\n" + _repeat_lines(" " .join(["1"] * 200), 200), "2 3\n5 5 5\n5 5 5\n", "1 2\n-9 4\n", "1 1\n100"],
        "matrix-negative": ["2 2\n-1 -2\n-3 -4\n", "2 3\n10 -2 0\n8 -4 1\n", "1 1\n0\n", "2 2\n -1   -2 \n-3\t-4\n", "200 200\n" + _repeat_lines(" " .join(["-1"] * 200), 200), "2 2\n-5 -5\n-5 -5\n", "1 2\n-9 4\n", "1 1\n-100"],
        "matrix-square": ["2\n1 2\n3 4\n", "3\n1 2 3\n4 5 6\n7 8 9\n", "1\n0\n", "2\n 1   2 \n3\t4\n", "200\n" + _repeat_lines(" " .join(["1"] * 200), 200), "3\n5 5 5\n5 5 5\n5 5 5\n", "2\n-9 4\n3 -2\n", "1\n100"],
        "matrix-char-spaced": ["2 3\nX . X\n. X .\n", "2 2\na b\nX X\n", "1 1\nX\n", "2 2\n X   . \n.\tX\n", "200 200\n" + _repeat_lines(" " .join(["X"] * 200), 200), "2 2\nX X\nX X\n", "1 2\n中 X\n", "1 1\n."],
        "matrix-char-grid": ["2 3\n#.#\n.##\n", "2 2\n..\n##\n", "1 1\n#\n", "2 3\n###\n...\n", "200 200\n" + _repeat_lines("#" * 200, 200), "2 2\n##\n##\n", "1 3\n#.#\n", "1 1\n."],
        "matrix-extra": ["2 2\n1 2\n3 4\nDONE\n", "1 3\n10 -2 8\nquery\n", "1 1\n0\nend\n", "2 2\n 1  2 \n3 4\nnext field\n", "200 200\n" + _repeat_lines(" " .join(["1"] * 200), 200) + "tail\n", "2 2\n5 5\n5 5\nsame\n", "1 2\n-9 4\n中\n", "1 1\n100\nlast"],
        "matrix-t": ["2\n2 2\n1 2\n3 4\n1 3\n5 6 7\n", "1\n2 2\n10 -2\n0 8\n", "1\n1 1\n0\n", "2\n1 2\n 1   2 \n1 1\n3\n", "100\n" + "1 1\n1\n" * 100, "2\n2 2\n5 5\n5 5\n1 1\n5\n", "1\n1 2\n-9 4\n", "1\n1 1\n100"],
        "matrix-ragged": ["3\n1 2\n3\n4 5 6\n", "2\n10 -2 0 8\n4\n", "1\n0\n", "3\n 1   2 \n\n3\n", "10000\n" + _repeat_lines("1 2 3", 10000), "3\n5 5\n5 5\n5 5\n", "2\n-9 4\n0\n", "1\n100"],
        "matrix-float": ["2 2\n1.5 2.5\n3.25 4.75\n", "1 3\n10 -2 0.5\n", "1 1\n0\n", "2 2\n 1.5   2.5 \n3\t4\n", "200 200\n" + _repeat_lines(" " .join(["0.1"] * 200), 200), "2 2\n5.5 5.5\n5.5 5.5\n", "1 2\n-9.25 4\n", "1 1\n100.125"],
        "string-word": ["hello\n", "CodeArena\n", "a\n", "  spaced  \n", "x" * 100000 + "\n", "重复重复\n", "🙂🙂\n", "last"],
        "string-sentence": ["hello world\n", "one two three\n", "single\n", "  many   spaces  \n", " ".join("word" for _ in range(100000)) + "\n", "重复 重复\n", "中 文 🙂\n", "last sentence"],
        "string-lines": ["a\nb\n", "one two\nthree\n", "\n", "  spaces  \n", _repeat_lines("x" * 100, 10000), "重复\n重复\n", "中\n🙂\n", "no\nfinal"],
        "string-empty": ["\n", "text\n", "", "  \n", "x" * 100000 + "\n", "重复\n", "🙂\n", "tail"],
        "string-codepoints": ["中文\n", "汉字测试\n", "a\n", "中 文\n", "汉" * 100000 + "\n", "重复重复\n", "🙂中文\n", "尾"],
        "string-units-points": ["🙂\n", "a🙂b\n", "a\n", "🙂 🙂\n", "🙂" * 100000 + "\n", "🙂🙂\n", "中文🙂\n", "尾🙂"],
        "string-utf8-bytes": ["abc\n", "中文\n", "a\n", "a 🙂 中\n", "汉" * 100000 + "\n", "重复重复\n", "🙂🙂\n", "tail中文"],
        "string-csv": ["a,b,c\n", "one, two words,three\n", "x\n", " left , middle , right \n", ",".join(str(i) for i in range(10000)) + "\n", "same,same\n", "中,文,🙂\n", "last,value"],
        "string-json": ["[1,2,3]\n", "{\"name\":\"CodeArena\"}\n", "[]\n", " {\"name\":\"spaced\"} \n", "[" + ",".join("1" for _ in range(10000)) + "]\n", "[5,5,5]\n", "{\"name\":\"中文\"}\n", "{\"name\":\"tail\"}"],
        "mixed-students": ["2\nAlice 90\nBob 80\n", "3\nA 100\nB 0\nC 75\n", "1\nX 0\n", "2\n张三   88\n李四\t92\n", "10000\n" + "\n".join(f"S{i} {i % 101}" for i in range(10000)) + "\n", "2\nSame 5\nSame 5\n", "1\n中文 99\n", "1\nTail 100"],
        "mixed-name-score": ["2\nAlice 90\nBob 80\n", "3\nA 100\nB 0\nC 75\n", "1\nX 0\n", "2\n张三   88\n李四\t92\n", "10000\n" + "\n".join(f"S{i} {i % 101}" for i in range(10000)) + "\n", "2\nSame 5\nSame 5\n", "1\n中文 99\n", "1\nTail 100"],
        "mixed-string-array": ["numbers\n3\n1 2 3\n", "values here\n5\n10 -2 0 4 8\n", "empty\n0\n\n", " spaced title \n2\n 1   2 \n", "large\n10000\n" + " ".join("1" for _ in range(10000)) + "\n", "same\n3\n5 5 5\n", "中文\n2\n-9 4\n", "tail\n1\n100"],
        "mixed-matrix-queries": ["2 2\n1 2\n3 4\n3\n", "1 3\n10 -2 8\n2\n", "1 1\n0\n0\n", "2 2\n 1  2 \n3 4\n1\n", "200 200\n" + _repeat_lines(" " .join(["1"] * 200), 200) + "10000\n", "2 2\n5 5\n5 5\n5\n", "1 2\n-9 4\n2\n", "1 1\n100\n1"],
        "mixed-variable-groups": ["2\n3 a b c\n2 d e\n", "3\n1 one\n4 a b c d\n2 x y\n", "1\n0\n", "2\n2   a b\n1\tc\n", "1000\n" + "1 x\n" * 1000, "2\n3 same same same\n3 same same same\n", "1\n2 中 🙂\n", "1\n1 tail"],
        "mixed-edges": ["3 2\n1 2\n2 3\n", "4 3\n1 2\n1 3\n1 4\n", "1 0\n", "3 2\n 1   2 \n2\t3\n", "10000 9999\n" + "\n".join(f"{i} {i + 1}" for i in range(1, 10000)) + "\n", "2 2\n1 2\n1 2\n", "3 1\n1 3\n", "2 1\n1 2"],
        "mixed-adjacency": ["3\n1 2 3\n2 1\n3 1\n", "2\n1 2\n2 1\n", "1\n1\n", "3\n1   2 3\n2\t1\n3\n", "10000\n" + "\n".join(f"{i}" for i in range(1, 10001)) + "\n", "2\n1 2 2\n2 1 1\n", "2\n1 2\n2\n", "1\n1"],
        "mixed-intervals": ["2\n1 3\n5 9\n", "3\n-10 -2\n0 8\n5 5\n", "1\n0 0\n", "2\n 1   2 \n3\t4\n", "10000\n" + _repeat_lines("1 2", 10000), "3\n5 5\n5 5\n5 5\n", "1\n-9 4\n", "1\n-100 100"],
        "mixed-commands": ["3\nSET a 1\nGET a\nEND\n", "2\nPUSH hello world\nPOP\n", "1\nNOP\n", "2\n SET   x  1 \nGET\tx\n", "10000\n" + _repeat_lines("GET key", 10000), "2\nGET x\nGET x\n", "1\nPRINT 中文\n", "1\nLAST value"],
        "mixed-types": ["alice 18 95.5 hello world\n", "bob 0 -1.25 text\n", "x 1 0 a\n", "  name   42  3.5   spaced text \n", "user 999999 1.1 " + "x" * 10000 + "\n", "same 5 5.0 same\n", "中文 8 9.5 表情 🙂\n", "tail 1 2.0 end"],
    }
    if mode in banks:
        return banks[mode]
    if mode == "perf-sum":
        return ["1 2 3\n", "10 -2 8\n", "0\n", " 1   2 \n", " ".join("1" for _ in range(100000)) + "\n", "5 5 5\n", "-9 4\n", " ".join(str(i % 10) for i in range(200000))]
    if mode == "perf-count":
        return ["a b c\n", "one two\nthree\n", "x\n", "  a   b \n", " ".join("x" for _ in range(1_000_000)) + "\n", "same same\n", "中 文 🙂\n", " ".join("x" for _ in range(200000))]
    if mode == "perf-lines":
        return ["a\nb\n", "one\ntwo\nthree\n", "x\n", "\nline\n", _repeat_lines("line", 100000), "same\nsame\n", "中\n文\n", _repeat_lines("tail", 20000).rstrip("\n")]
    if mode == "perf-string":
        return ["abc\n", "hello world\n", "\n", "  spaces  \n", "x" * 1_000_000 + "\n", "same" * 1000 + "\n", "中文🙂" * 10000 + "\n", "tail" * 50000]
    if mode == "perf-bigint":
        return ["9007199254740993 2\n", "12345678901234567890 -10\n", "0\n", " 1   2 \n", " ".join("999999999999999999" for _ in range(100000)) + "\n", "5 5 5\n", "-9007199254740993 4\n", " ".join("1" for _ in range(200000))]
    if mode == "perf-pairs":
        return ["1 2\n3 4\n", "10 -2\n8 4\n", "0 0\n", " 1   2 \n", _repeat_lines("1 1", 100000), "5 5\n5 5\n", "-9 4\n", _repeat_lines("1 -1", 50000).rstrip("\n")]
    if mode == "perf-line-sums":
        return ["1 2\n3 4\n", "10 -2 8\n4\n", "0\n", " 1   2 \n", _repeat_lines("1 1 1 1", 50000), "5 5\n5 5\n", "-9 4\n", _repeat_lines("1 -1", 20000).rstrip("\n")]
    if mode == "perf-output":
        return ["a\nb\n", "one\ntwo\nthree\n", "x\n", "\nline\n", _repeat_lines("line", 50000), "same\nsame\n", "中\n文\n", _repeat_lines("tail", 20000).rstrip("\n")]
    raise ValueError(f"missing case bank for {mode}")


CATEGORY_MAP = {
    "single-value": "single-value",
    "single-line-values": "single-line-multiple-values",
    "multi-line": "multi-line",
    "test-cases": "test-cases",
    "read-until-eof": "read-until-eof",
    "sentinel": "sentinel",
    "arrays": "array-input",
    "matrices": "matrix-input",
    "strings": "string-input",
    "mixed-nested": "mixed-input",
    "large-input": "large-input",
}


def reference_source(task: Task, runtime: str) -> str:
    header = f"const MODE = {json.dumps(task.mode)};\n"
    if runtime == "javascript-v8":
        wrapper = r"""
const lines = [];
for (let line = readline(); line !== undefined; line = readline()) lines.push(line);
""".strip()
        footer = "\nprint(answer);\n"
    else:
        wrapper = r"""
const fs = require('fs');
const input = fs.readFileSync(0, 'utf8').replace(/\r\n/g, '\n');
const lines = input === '' ? [] : input.split('\n');
if (lines.length > 0 && lines[lines.length - 1] === '') lines.pop();
""".strip()
        footer = "\nprocess.stdout.write(answer + '\\n');\n"
    return f"{header}{wrapper}\n{JS_SOLVER_CORE}{footer}"


def run_node_reference(source: Path, stdin: str) -> str:
    completed = subprocess.run(
        ["node", str(source)],
        input=stdin.encode(),
        capture_output=True,
        check=False,
        timeout=30,
    )
    if completed.returncode:
        raise RuntimeError(f"Node.js reference failed for {source.parent.name}")
    return completed.stdout.decode()


def common_errors(task: Task) -> list[str]:
    errors = [
        "在 JavaScript V8 模式中误用 require、process、fs 或 Buffer。",
        "在 Node.js 模式中直接调用未定义的 readline() 或 print()。",
    ]
    if "empty" in task.mode or "line" in task.mode or "eof" in task.mode:
        errors.append("无条件 trim() 导致空行、前导空格或末尾结构丢失。")
    else:
        errors.append("只按单个空格 split(' ') 导致连续空白产生空 token。")
    if task.category in {"test-cases", "read-until-eof", "mixed-nested", "large-input"}:
        errors.append("使用 shift() 反复移动大数组，造成不必要的二次方开销。")
    else:
        errors.append("输出调试文字、额外空格或错误的分隔符导致 Wrong Answer。")
    return errors


def hints(task: Task) -> tuple[str, str]:
    if task.category in {"single-value", "single-line-values"}:
        v8 = "调用一次 `readline()`；只有题意允许时才 `trim()`，空白 token 用 `/\\s+/` 拆分。"
        node = "读取原始 stdin 后按题意处理第一行；不要在模板阶段无条件 `trim()`。"
    elif task.category in {"multi-line", "read-until-eof", "sentinel"}:
        v8 = "循环调用 `readline()`，并用 `line === undefined` 判断 EOF；空字符串不是 EOF。"
        node = "统一 CRLF 后建立行数组，用整数游标前进；不要用 `shift()` 消耗大数组。"
    else:
        v8 = "按行读取后使用 token 或行游标；将输出先放入数组，最后用 `print(out.join('\\n'))`。"
        node = "一次读取 stdin，使用索引游标组织 token/行；将输出缓存后一次写入 stdout。"
    return v8, node


def io_contract(task: Task) -> tuple[str, str]:
    mode = task.mode
    contracts = {
        "single-int": ("一行一个十进制整数 n。", "输出 n + 1。"),
        "single-float": ("一行一个十进制浮点数 x。", "输出 x，保留两位小数。"),
        "single-word": ("一行一个不含空白的单词。", "输出该单词的大写形式。"),
        "single-line": ("一行任意 UTF-8 文本，行内可以含空格。", "原样输出这一逻辑行。"),
        "preserve-line": ("一行文本；行首、行尾和行内空格都是数据。", "用一对方括号包住原始行后输出。"),
        "negative-int": ("一行一个不大于 0 的整数 n。", "输出 n 的绝对值。"),
        "single-bigint": ("一行一个可超出 Number 安全范围的十进制整数。", "使用 BigInt 输出该整数加一。"),
        "empty-input": ("标准输入可能完全没有字节，也可能包含一行文本。", "无逻辑行时输出 EMPTY，否则输出第一行。"),
        "sum-space": ("一行包含若干空白分隔的整数。", "输出所有整数之和。"),
        "mixed-token": ("一行先给整数 id，随后是一个或多个字符串 token。", "输出 id:文本，文本 token 之间用单个空格连接。"),
        "sum-float": ("一行包含若干空白分隔的浮点数。", "输出总和并保留两位小数。"),
        "join-whitespace": ("一行包含若干由空格或制表符分隔的 token，外侧可有空白。", "按顺序用竖线连接 token。"),
        "sum-comma": ("一行包含若干逗号分隔的整数，逗号两侧可有空格。", "输出所有整数之和。"),
        "join-colon-pipe": ("一行由冒号或竖线分隔若干字段。", "去掉字段外侧空白后用竖线连接。"),
        "token-stats": ("一行包含不定数量的空白分隔整数。", "输出 token 数量和整数总和，中间一个空格。"),
        "fixed-two-lines": ("固定两行文本，两行都可能含空格。", "用竖线连接两行。"),
        "fixed-three-lines": ("固定三行文本。", "用大于号依次连接三行。"),
        "count-array": ("第一行整数 n；第二行至少包含 n 个整数。", "输出第二行前 n 个整数之和。"),
        "counted-lines": ("第一行整数 n；随后恰有 n 行原始文本。", "用竖线连接这 n 行。"),
        "pair-lines": ("输入含若干非空行，每行两个整数。", "每行输出对应两个整数之和。"),
        "field-counts": ("输入含若干行，每行字段数可以不同，空行字段数为 0。", "按行输出字段数量，数量之间一个空格。"),
        "all-lines": ("读取所有逻辑行直到 EOF，兼容 LF 与 CRLF。", "用竖线连接全部逻辑行。"),
        "preserve-lines": ("读取所有逻辑行直到 EOF；空行和每行外侧空格必须保留。", "每行用方括号包住并逐行输出。"),
        "t-line-sums": ("第一行 T；随后 T 个非空行，每行若干整数。", "按组逐行输出该行整数之和。"),
        "t-two-lines": ("第一行 T；每组固定包含两行文本。", "每组用竖线连接两行，逐组输出。"),
        "t-count-array": ("第一行 T；每组第一行 n，下一行至少 n 个整数。", "每组输出前 n 个整数之和。"),
        "t-counted-records": ("第一行 T；每组先给 n，随后 n 行记录。", "组内记录用逗号连接，每组输出一行。"),
        "t-variable": ("第一行 T；每组先给 n，随后紧跟 n 个整数，组长可不同。", "每组输出 n 个整数之和。"),
        "t-blank-lines": ("第一行 T；空行可作为组间分隔，每组有效数据占一个非空行。", "忽略组间空行，组内 token 用竖线连接。"),
        "t-case-format": ("第一行 T；随后 T 行整数数据。", "输出 Case #x: sum，x 从 1 开始。"),
        "t-blank-output": ("第一行 T；随后 T 行整数数据。", "每组输出整数和，相邻两组输出之间保留一个空行。"),
        "t-many": ("第一行 T；随后 T 行各一个整数。", "输出所有测试组整数的总和。"),
        "eof-lines": ("每行一组字符串数据，持续读取到 EOF。", "将每行转为大写后逐行输出。"),
        "eof-nonempty-lines": ("读取到 EOF，末尾可能有多个空行。", "跳过空行，将其余行转为大写后输出。"),
        "eof-pairs": ("每个非空行两个整数，组数未知，读取到 EOF。", "每组输出两个整数之和。"),
        "eof-two-lines": ("每组固定两行，组数未知，读取到 EOF。", "每组用竖线连接两行后输出。"),
        "eof-blocks": ("重复读取 n 和随后的 n 行记录，直到 EOF。", "每块记录用逗号连接后输出一行。"),
        "eof-sum": ("包含大量整数行，不提供数量，读取到 EOF。", "输出全部整数之和。"),
        "sentinel-zero": ("每行一个整数；读到单独的 0 或 EOF 时结束。", "哨兵前每个整数乘二后逐行输出，0 不输出。"),
        "sentinel-minus-one": ("每行一个整数；读到单独的 -1 或 EOF 时结束。", "哨兵前每个整数乘二后逐行输出，-1 不输出。"),
        "sentinel-zero-pair": ("每行两个整数；读到 0 0 或 EOF 时结束。", "哨兵前每组输出两数之和。"),
        "sentinel-end": ("每行一段文本；读到完全等于 END 的行或 EOF 时结束。", "将哨兵前文本转为大写后逐行输出。"),
        "sentinel-blocks": ("重复读取 n 和随后 n 行；n=0 或 EOF 表示结束。", "每块记录用逗号连接，n=0 不输出。"),
        "array-int": ("一行不定长整数数组。", "输出数组元素之和。"),
        "array-string": ("一行不定长字符串数组，元素由空白分隔。", "逆序后用竖线输出。"),
        "array-lines": ("每行一个整数数组，行数由 EOF 决定。", "逐行输出每个数组的元素和。"),
        "array-known": ("第一项为长度 n，随后至少 n 个整数，可跨行。", "n=0 输出 EMPTY，否则输出前 n 项最大值。"),
        "array-unknown": ("一行未知长度的整数数组。", "输出数组长度。"),
        "array-flat-matrix": ("先给 n m，随后给按行展开的 n×m 个整数。", "输出 n×m:sum。"),
        "array-bigint": ("一行若干可能超出安全范围的整数。", "用 BigInt 输出数组总和。"),
        "array-float": ("一行若干浮点数。", "输出平均值并保留两位小数。"),
        "array-negative": ("一行若干整数，可能含负数。", "输出最小值。"),
        "array-empty": ("第一项为 n，随后 n 个整数；n 可以为 0。", "n=0 输出 EMPTY，否则原顺序输出数组。"),
        "matrix-nm": ("第一行 n m；随后 n 行，每行 m 个整数。", "输出矩阵所有元素之和。"),
        "matrix-negative": ("第一行 n m；随后 n×m 个可能为负的整数。", "输出矩阵所有元素之和。"),
        "matrix-square": ("第一行 n；随后 n 行，每行 n 个整数。", "输出主对角线元素之和。"),
        "matrix-char-spaced": ("第一行 n m；随后 n 行，每行 m 个空白分隔字符。", "输出字符 X 的数量。"),
        "matrix-char-grid": ("第一行 n m；随后 n 行长度为 m 的紧凑字符网格。", "输出字符 # 的数量。"),
        "matrix-extra": ("先给 n m 和 n 行整数矩阵，矩阵后再给一行文本字段。", "输出矩阵元素和与尾随字段，中间一个空格。"),
        "matrix-t": ("第一行 T；每组先给 n m，再给 n×m 个整数。", "每组输出矩阵元素和。"),
        "matrix-ragged": ("第一行 n；随后 n 行，每行整数数量可不同。", "依次输出每行元素个数。"),
        "matrix-float": ("第一行 n m；随后 n 行，每行 m 个浮点数。", "输出元素总和并保留两位小数。"),
        "string-word": ("一行一个不含空白的字符串。", "按 Unicode 码点输出长度。"),
        "string-sentence": ("一行句子，单词由任意连续空白分隔。", "输出单词数量。"),
        "string-lines": ("读取多行文本直到 EOF。", "输出全部行的 Unicode 码点总数，不计换行符。"),
        "string-empty": ("输入第一行可能为空，也可能完全没有输入。", "第一行为空或不存在时输出 EMPTY，否则输出 NOT EMPTY。"),
        "string-codepoints": ("一行 UTF-8 中文或其他 Unicode 文本。", "输出 Unicode 码点数量。"),
        "string-units-points": ("一行可能包含表情符号的文本。", "输出 UTF-16 code unit 数和 Unicode 码点数。"),
        "string-utf8-bytes": ("一行合法 UTF-8 文本。", "输出 Unicode 码点数与 UTF-8 字节数。"),
        "string-csv": ("一行逗号分隔字符串，字段外侧可有空格。", "去掉字段外侧空格后用竖线连接。"),
        "string-json": ("一行合法 JSON 数组或含 name 字段的对象，禁止 eval。", "数组输出 array:长度；对象输出 object:name。"),
        "mixed-students": ("第一行 n；随后 n 行，每行姓名和整数分数。", "逐行输出 姓名:分数。"),
        "mixed-name-score": ("第一行 n；随后 n 行姓名与分数记录。", "逐行输出 姓名:分数。"),
        "mixed-string-array": ("第一行标题；第二行 n；第三行至少 n 个整数。", "输出 标题:前n项之和。"),
        "mixed-matrix-queries": ("先给 n m 和 n 行矩阵，随后一行查询数量 q。", "输出矩阵元素和与 q。"),
        "mixed-variable-groups": ("第一项为组数 g；每组先给 n，再给 n 个字符串字段。", "每组字段用逗号连接后输出。"),
        "mixed-edges": ("第一行 n m；随后 m 行无向边 u v。", "按顶点 1..n 输出每个顶点度数。"),
        "mixed-adjacency": ("第一行 n；随后 n 行以顶点编号开头，后跟邻接点。", "输出每行邻接点数量。"),
        "mixed-intervals": ("第一行 n；随后 n 行整数区间 l r。", "输出所有 r-l 的总和。"),
        "mixed-commands": ("第一行 n；随后 n 行变长命令及参数。", "将每条命令的字段用冒号连接后逐行输出。"),
        "mixed-types": ("一行依次给字符串、整数、浮点数和剩余文本。", "按指定类型格式化为 name|int|float(1位)|text。"),
        "perf-sum": ("输入含最多 20 万个空白分隔整数。", "输出全部整数之和。"),
        "perf-count": ("输入含最多 100 万个空白分隔 token。", "输出 token 数量。"),
        "perf-lines": ("输入含最多 10 万个逻辑行。", "输出逻辑行数量。"),
        "perf-string": ("输入为最长 100 万 Unicode 码点的大字符串。", "输出去除换行后的码点数量。"),
        "perf-bigint": ("输入含最多 10 万个 BigInt 十进制 token。", "输出 BigInt 总和。"),
        "perf-pairs": ("输入含大量整数对，按行或 token 游标读取。", "输出所有整数总和。"),
        "perf-line-sums": ("输入含大量行，每行多个整数。", "缓冲并逐行输出每行整数和。"),
        "perf-output": ("输入含大量文本行。", "输出 行号:原行，行号从 1 开始。"),
    }
    try:
        return contracts[mode]
    except KeyError as exc:
        raise ValueError(f"missing I/O contract for {mode}") from exc


def starter_code(task: Task, runtime: str) -> str:
    if runtime == "javascript-v8":
        return (
            "const lines = [];\n"
            "for (let line = readline(); line !== undefined; line = readline()) {\n"
            "  lines.push(line);\n"
            "}\n\n"
            f"// TODO: {task.title}\n"
            "print(lines.length);\n"
        )
    return (
        "const fs = require('fs');\n\n"
        "const input = fs.readFileSync(0, 'utf8');\n"
        "const lines = input.replace(/\\r\\n/g, '\\n').split('\\n');\n\n"
        f"// TODO: {task.title}；请按题意决定是否移除末尾空行\n"
        "console.log(lines.length);\n"
    )


def write_problem(
    task: Task,
    chapter_order: int,
    prerequisite: str | None,
) -> Path:
    inputs = cases_for(task.mode)
    if len(inputs) != 8:
        raise RuntimeError(f"{task.slug} must have exactly two public and six hidden cases")
    reference_directory = REFERENCE_ROOT / task.slug
    reference_directory.mkdir(parents=True, exist_ok=True)
    v8_path = reference_directory / "solution-v8.js"
    node_path = reference_directory / "solution-nodejs.js"
    _write_utf8(v8_path, reference_source(task, "javascript-v8"))
    _write_utf8(node_path, reference_source(task, "nodejs"))

    outputs = [run_node_reference(node_path, stdin) for stdin in inputs]
    input_description, output_description = io_contract(task)
    test_directory = TEST_ROOT / task.slug
    test_directory.mkdir(parents=True, exist_ok=True)
    hidden_cases = []
    for index, ((scenario, label), stdin, stdout, score) in enumerate(
        zip(SCENARIOS, inputs[2:], outputs[2:], SCORES), 1
    ):
        input_path = test_directory / f"{index:02d}.in"
        output_path = test_directory / f"{index:02d}.out"
        input_path.write_bytes(stdin.encode())
        output_path.write_bytes(stdout.encode())
        checksum = hashlib.sha256(stdin.encode() + b"\0" + stdout.encode()).hexdigest()
        hidden_cases.append(
            {
                "sequence": index,
                "score": score,
                "scenario": scenario,
                "scenario_description": f"{label}：验证“{task.title}”的格式边界与游标推进。",
                "input_file": f"js-acm/{task.slug}/{index:02d}.in",
                "output_file": f"js-acm/{task.slug}/{index:02d}.out",
                "checksum": checksum,
            }
        )

    v8_hint, node_hint = hints(task)
    samples = [
        {
            "input": stdin,
            "output": stdout,
            "explanation": f"按“{task.title}”的规则解析输入，并得到上述规范化输出。",
        }
        for stdin, stdout in zip(inputs[:2], outputs[:2])
    ]
    constraints = (
        "输入为 UTF-8 文本；逻辑行使用 LF 或 CRLF。除 BigInt 专项外，整数绝对值不超过 "
        "10^9；普通练习输入不超过 10^5 个 token，大输入专项按题面可达到 10^6 个 token。"
    )
    document = {
        "slug": task.slug,
        "title": task.title,
        "description": (
            f"本练习只训练 **{task.title}** 的 stdin 解析。计算步骤保持简单："
            "按照输入结构读取数据，再输出题目要求的规范化结果。"
        ),
        "difficulty": (
            "hard" if task.category in {"mixed-nested", "large-input"} else
            "medium" if task.category in {"test-cases", "read-until-eof", "matrices"} else
            "easy"
        ),
        "training_category": CATEGORY_MAP[task.category],
        "tags": ["stdin", "stdout", task.category, "javascript-v8", "nodejs"],
        "input_description": input_description,
        "output_description": output_description + " 不得包含提示语或调试信息。",
        "data_constraints": constraints,
        "sample_input": samples[0]["input"],
        "sample_output": samples[0]["output"],
        "sample_explanation": samples[0]["explanation"],
        "samples": samples,
        "learning_objective": task.objective,
        "v8_hint": v8_hint,
        "nodejs_hint": node_hint,
        "common_errors": common_errors(task),
        "chapter": task.chapter,
        "chapter_order": chapter_order,
        "prerequisites": [prerequisite] if prerequisite else [],
        "estimated_minutes": task.minutes,
        "starter_code_v8": starter_code(task, "javascript-v8"),
        "starter_code_nodejs": starter_code(task, "nodejs"),
        "time_limit_ms": 3000 if task.category == "large-input" else 1000,
        "memory_limit_mb": 256,
        "source": "CodeArena JavaScript ACM 原创课程",
        "publish": True,
        "reference_solutions": {
            "javascript_v8": f"reference-solutions/js-acm/{task.slug}/solution-v8.js",
            "nodejs": f"reference-solutions/js-acm/{task.slug}/solution-nodejs.js",
        },
        "test_set": {
            "version": 1,
            "checker_type": "exact",
            "cases": hidden_cases,
        },
    }
    problem_path = PROBLEM_ROOT / f"{task.slug}.yaml"
    problem_path.parent.mkdir(parents=True, exist_ok=True)
    _write_utf8(
        problem_path,
        yaml.safe_dump(document, allow_unicode=True, sort_keys=False, width=100),
    )
    return problem_path


def write_catalog(tasks: list[Task], paths: list[Path]) -> None:
    tags = [
        {"slug": "stdin", "name": "标准输入"},
        {"slug": "stdout", "name": "标准输出"},
        {"slug": "javascript-v8", "name": "JavaScript V8"},
        {"slug": "nodejs", "name": "Node.js"},
    ] + [
        {"slug": chapter.slug.removeprefix("js-acm-"), "name": chapter.title.split("：", 1)[1]}
        for chapter in CHAPTERS
    ]
    _write_utf8(
        ROOT / "tags.yaml",
        yaml.safe_dump({"tags": tags}, allow_unicode=True, sort_keys=False),
    )
    collections = []
    for chapter in CHAPTERS:
        slugs = [task.slug for task in tasks if task.chapter == chapter.slug]
        collections.append(
            {
                "slug": chapter.slug,
                "title": chapter.title,
                "description": chapter.description,
                "company": "CodeArena",
                "is_public": True,
                "problems": slugs,
            }
        )
    _write_utf8(
        ROOT / "collections.yaml",
        yaml.safe_dump({"collections": collections}, allow_unicode=True, sort_keys=False),
    )
    daily = [
        {"date": "today" if index == 0 else f"today+{index}", "problem": task.slug}
        for index, task in enumerate(tasks[:14])
    ]
    _write_utf8(
        ROOT / "daily-challenges.yaml",
        yaml.safe_dump({"daily_challenges": daily}, allow_unicode=True, sort_keys=False),
    )
    manifest = {
        "schema_version": 1,
        "timezone": "Asia/Shanghai",
        "tags": "tags.yaml",
        "problems": [path.relative_to(ROOT).as_posix() for path in paths],
        "collections": "collections.yaml",
        "daily_challenges": "daily-challenges.yaml",
        "test_data_directory": "test-data",
    }
    _write_utf8(
        ROOT / "manifest.yaml",
        yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False),
    )


def main() -> int:
    tasks = build_tasks()
    if len(tasks) != 105 or len({task.slug for task in tasks}) != len(tasks):
        raise RuntimeError("course must contain exactly 105 unique exercises")
    paths: list[Path] = []
    previous: str | None = None
    for chapter in CHAPTERS:
        chapter_tasks = [task for task in tasks if task.chapter == chapter.slug]
        for order, task in enumerate(chapter_tasks, 1):
            paths.append(write_problem(task, order, previous))
            previous = task.slug
    write_catalog(tasks, paths)
    report = {
        "status": "success",
        "chapters": len(CHAPTERS),
        "problems": len(tasks),
        "public_samples": len(tasks) * 2,
        "hidden_cases": len(tasks) * 6,
        "reference_solutions": len(tasks) * 2,
    }
    print(json.dumps(report, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
