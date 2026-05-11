import { describe, expect, it } from 'vitest'
import {
  buildCaseReport,
  evidenceStatusTone,
  filterEvidence,
  normalizeWorkspace,
} from '../caseWorkspace'

describe('normalizeWorkspace', () => {
  it('sorts timeline newest first and provides safe defaults', () => {
    const workspace = normalizeWorkspace({
      case: { name: 'Source case' },
      evidence: [{ title: 'Lead', status: 'verified', confidence: 91 }],
      sources: [{ url: 'https://example.com' }],
      timeline: [
        { title: 'Old', at: '2026-01-01T00:00:00Z' },
        { title: 'New', at: '2026-01-02T00:00:00Z' },
      ],
    })

    expect(workspace.case.name).toBe('Source case')
    expect(workspace.stats.evidence).toBe(1)
    expect(workspace.sources).toHaveLength(1)
    expect(workspace.timeline[0].title).toBe('New')
  })
})

describe('filterEvidence', () => {
  const evidence = [
    { title: 'Original source', status: 'verified', tags: ['source'], confidence: 91 },
    { title: 'Weak lead', status: 'rejected', tags: ['lead'], confidence: 20 },
  ]

  it('filters by query, status, and minimum confidence', () => {
    const result = filterEvidence(evidence, { query: 'source', status: 'verified', minConfidence: 80 })
    expect(result).toHaveLength(1)
    expect(result[0].title).toBe('Original source')
  })
})

describe('evidenceStatusTone', () => {
  it('returns a professional tone for known statuses', () => {
    expect(evidenceStatusTone('verified').label).toBe('Verified')
    expect(evidenceStatusTone('needs_review').label).toBe('Needs Review')
  })
})

describe('buildCaseReport', () => {
  it('includes provenance and AI disclaimer language', () => {
    const report = buildCaseReport({
      case: { name: 'Report case', status: 'active' },
      stats: { evidence: 1, verified_evidence: 1 },
      evidence: [{ title: 'Known source', status: 'verified', confidence: 90, source_url: 'https://example.com' }],
      timeline: [],
    })

    expect(report).toContain('# VISION Case Report')
    expect(report).toContain('AI outputs are investigative aids')
    expect(report).toContain('https://example.com')
  })
})
