export type LineEnding = 'LF' | 'CRLF' | 'CR' | 'NONE'

export interface VisibleOutputLine {
  content: string
  visibleContent: string
  ending: LineEnding
  raw: string
}

function visibleWhitespace(value: string): string {
  return value.replace(/ /g, '·').replace(/\t/g, '⇥')
}

export function splitVisibleOutput(value: string): VisibleOutputLine[] {
  if (value === '') {
    return [{ content: '', visibleContent: '∅', ending: 'NONE', raw: '' }]
  }
  const lines: VisibleOutputLine[] = []
  let content = ''
  for (let index = 0; index < value.length; index += 1) {
    const character = value[index]
    if (character === '\r') {
      const crlf = value[index + 1] === '\n'
      const ending: LineEnding = crlf ? 'CRLF' : 'CR'
      const raw = `${content}${crlf ? '\r\n' : '\r'}`
      lines.push({ content, visibleContent: visibleWhitespace(content), ending, raw })
      content = ''
      if (crlf) index += 1
    } else if (character === '\n') {
      lines.push({ content, visibleContent: visibleWhitespace(content), ending: 'LF', raw: `${content}\n` })
      content = ''
    } else {
      content += character
    }
  }
  if (content !== '') {
    lines.push({ content, visibleContent: visibleWhitespace(content), ending: 'NONE', raw: content })
  }
  return lines
}

export function normalizeExactOutput(value: string): string {
  const normalizedLines = value.replace(/\r\n?/g, '\n').split('\n').map((line) => line.trimEnd())
  return normalizedLines.join('\n').trimEnd()
}

export interface OutputDiffSummary {
  rawEqual: boolean
  checkerEquivalent: boolean
  message: string
}

export function summarizeOutputDiff(expected: string, actual: string): OutputDiffSummary {
  if (expected === actual) {
    return { rawEqual: true, checkerEquivalent: true, message: '输出逐字符一致' }
  }
  const checkerEquivalent = normalizeExactOutput(expected) === normalizeExactOutput(actual)
  if (checkerEquivalent) {
    return {
      rawEqual: false,
      checkerEquivalent: true,
      message: '原始换行或行尾空白不同；按 exact 比较器规范化后等价',
    }
  }
  if (expected.trimEnd() === actual.trimEnd()) {
    return { rawEqual: false, checkerEquivalent: false, message: '末尾换行或空白数量不同' }
  }
  const expectedLines = splitVisibleOutput(expected)
  const actualLines = splitVisibleOutput(actual)
  const mismatch = Array.from(
    { length: Math.max(expectedLines.length, actualLines.length) },
    (_, index) => index,
  ).find((index) => expectedLines[index]?.raw !== actualLines[index]?.raw)
  return {
    rawEqual: false,
    checkerEquivalent: false,
    message: mismatch === undefined ? '输出格式不同' : `第 ${mismatch + 1} 行开始不同`,
  }
}
