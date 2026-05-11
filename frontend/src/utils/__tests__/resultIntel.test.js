import { describe, expect, it } from 'vitest'
import { clusterIntel, laneTone, normalizeBrowserPlan } from '../resultIntel'

describe('clusterIntel', () => {
  it('normalizes match, credibility, clue, and provenance fields', () => {
    const intel = clusterIntel({
      cluster_size: 2,
      match_strength: { label: 'Very strong', score: 93 },
      source_credibility: { label: 'Strong', score: 82 },
      triage_lane: 'strong_match',
      top_result: { url: 'https://example.com/source', source_domain: 'example.com' },
      next_steps: ['Capture source page'],
      location_clues: [{ label: 'Seattle' }],
    })

    expect(intel.score).toBe(93)
    expect(intel.matchLabel).toBe('Very strong')
    expect(intel.credibilityLabel).toBe('Strong')
    expect(intel.lane).toBe('strong_match')
    expect(intel.provenance.source_url).toBe('https://example.com/source')
  })
})

describe('laneTone', () => {
  it('returns professional labels for triage lanes', () => {
    expect(laneTone('strong_match').label).toBe('Strong Match')
    expect(laneTone('rejected').label).toBe('Rejected')
  })
})

describe('normalizeBrowserPlan', () => {
  it('provides safe defaults for mission plans', () => {
    const plan = normalizeBrowserPlan({ pages_to_visit: ['https://example.com'] })
    expect(plan.mode).toBe('bounded_browser_assist')
    expect(plan.pages_to_visit).toHaveLength(1)
    expect(plan.experimental_desktop_control.available).toBe(false)
  })
})
