/// <reference types="node" />

import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'

const styles = readFileSync('src/styles/main.css', 'utf8')

describe('guide responsive layout', () => {
  it('switches from a sticky desktop directory to a mobile chapter selector', () => {
    expect(styles).toContain('.guide-sidebar { position: sticky')
    expect(styles).toContain('@media (max-width: 900px)')
    expect(styles).toContain('.guide-mobile-section-select { display: grid')
    expect(styles).toContain('.guide-sidebar { display: none')
    expect(styles).toContain('.guide-code-grid.is-pair { grid-template-columns: 1fr')
  })
})
