import DOMPurify from 'dompurify'
import { marked } from 'marked'

const allowedTags = [
  'p',
  'br',
  'strong',
  'em',
  'del',
  'code',
  'pre',
  'ul',
  'ol',
  'li',
  'blockquote',
  'h1',
  'h2',
  'h3',
  'h4',
  'h5',
  'h6',
  'hr',
  'table',
  'thead',
  'tbody',
  'tr',
  'th',
  'td',
  'a',
]

export function renderSafeMarkdown(source: string): string {
  const normalized = source.replace(/^[\u200B-\u200F\uFEFF]/u, '')
  const rendered = marked.parse(normalized, { async: false, breaks: true, gfm: true })
  return DOMPurify.sanitize(rendered, {
    ALLOWED_TAGS: allowedTags,
    ALLOWED_ATTR: ['href', 'title'],
  })
}
