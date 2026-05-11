export function normalizeWorkspace(raw = {}) {
  const evidence = Array.isArray(raw.evidence) ? raw.evidence : []
  const timeline = Array.isArray(raw.timeline) ? [...raw.timeline] : []
  timeline.sort((a, b) => new Date(b.at || 0) - new Date(a.at || 0))

  return {
    case: {
      id: raw.case?.id || null,
      name: raw.case?.name || 'Untitled Case',
      description: raw.case?.description || '',
      notes: raw.case?.notes || '',
      status: raw.case?.status || 'active',
      created_at: raw.case?.created_at || null,
      updated_at: raw.case?.updated_at || null,
    },
    stats: {
      searches: raw.stats?.searches ?? (raw.searches?.length || 0),
      evidence: raw.stats?.evidence ?? evidence.length,
      verified_evidence: raw.stats?.verified_evidence ?? evidence.filter((item) => item.status === 'verified').length,
      entities: raw.stats?.entities ?? (raw.entities?.length || 0),
      ai_insights: raw.stats?.ai_insights ?? (raw.ai_insights?.length || 0),
      browser_artifacts: raw.stats?.browser_artifacts ?? (raw.browser_artifacts?.length || 0),
      avg_confidence: raw.stats?.avg_confidence ?? null,
    },
    searches: Array.isArray(raw.searches) ? raw.searches : [],
    evidence,
    entities: Array.isArray(raw.entities) ? raw.entities : [],
    reports: Array.isArray(raw.reports) ? raw.reports : [],
    ai_insights: Array.isArray(raw.ai_insights) ? raw.ai_insights : [],
    browser_artifacts: Array.isArray(raw.browser_artifacts) ? raw.browser_artifacts : [],
    timeline,
  }
}

export function filterEvidence(evidence = [], filters = {}) {
  const query = (filters.query || '').trim().toLowerCase()
  const status = filters.status || 'all'
  const minConfidence = Number(filters.minConfidence || 0)

  return evidence.filter((item) => {
    const haystack = [
      item.title,
      item.summary,
      item.notes,
      item.source_url,
      ...(item.tags || []),
    ].join(' ').toLowerCase()
    if (query && !haystack.includes(query)) return false
    if (status !== 'all' && item.status !== status) return false
    if ((item.confidence ?? 0) < minConfidence) return false
    return true
  })
}

export function evidenceStatusTone(status) {
  const tones = {
    verified: { label: 'Verified', color: 'var(--green)', bg: 'rgba(48,209,88,0.12)' },
    needs_review: { label: 'Needs Review', color: 'var(--orange)', bg: 'rgba(255,159,10,0.12)' },
    rejected: { label: 'Rejected', color: 'var(--red)', bg: 'rgba(255,69,58,0.12)' },
    lead: { label: 'Lead', color: 'var(--blue)', bg: 'rgba(10,132,255,0.12)' },
  }
  return tones[status] || { label: status || 'Unknown', color: 'var(--text-secondary)', bg: 'var(--surface-3)' }
}

export function buildCaseReport(workspace = {}) {
  const data = normalizeWorkspace(workspace)
  const lines = [
    '# VISION Case Report',
    '',
    `**Case:** ${data.case.name}`,
    `**Status:** ${data.case.status}`,
    '',
    '> AI outputs are investigative aids, not proof. Verify every important claim against the evidence and source provenance.',
    '',
    '## Summary',
    '',
    `- Searches: ${data.stats.searches}`,
    `- Evidence: ${data.stats.evidence}`,
    `- Verified evidence: ${data.stats.verified_evidence}`,
    '',
    '## Evidence',
    '',
  ]

  data.evidence.forEach((item) => {
    lines.push(`### ${item.title || 'Untitled evidence'}`)
    lines.push('')
    lines.push(`- Status: ${item.status || 'needs_review'}`)
    lines.push(`- Confidence: ${item.confidence ?? 'n/a'}`)
    lines.push(`- Source: ${item.source_url || 'n/a'}`)
    if (item.summary) lines.push(`- Summary: ${item.summary}`)
    if (item.notes) lines.push(`- Notes: ${item.notes}`)
    lines.push('')
  })

  return lines.join('\n')
}
