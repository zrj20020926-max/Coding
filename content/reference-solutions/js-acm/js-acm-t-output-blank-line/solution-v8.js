const MODE = "t-blank-output";
const lines = [];
for (let line = readline(); line !== undefined; line = readline()) lines.push(line);
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
print(answer);
