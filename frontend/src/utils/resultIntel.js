export function clusterIntel(cluster = {}) {
  const top = cluster.top_result || {}
  const match = cluster.match_strength || {}
  const credibility = cluster.source_credibility || {}
  const score = Math.round(match.score ?? top.similarity_pct ?? (cluster.rank_score || 0) * 100 ?? 0)

  return {
    score,
    matchLabel: match.label || (score >= 85 ? 'Strong' : score >= 60 ? 'Possible' : 'Needs Review'),
    match,
    source_credibility: credibility,
    credibilityLabel: credibility.label || 'Unknown',
    credibilityScore: credibility.score ?? null,
    lane: cluster.triage_lane || (cluster.saved ? 'saved' : cluster.hidden ? 'rejected' : score >= 85 ? 'strong_match' : 'needs_review'),
    nextSteps: Array.isArray(cluster.next_steps) ? cluster.next_steps : [],
    contradictionHints: Array.isArray(cluster.contradiction_hints) ? cluster.contradiction_hints : [],
    locationClues: Array.isArray(cluster.location_clues) ? cluster.location_clues : [],
    entities: cluster.entities || {},
    provenance: cluster.provenance_summary || {
      source_url: top.url,
      source_domain: top.source_domain,
      cluster_size: cluster.cluster_size,
      engines: cluster.engines || [],
    },
  }
}

export function laneTone(lane) {
  const tones = {
    strong_match: { label: 'Strong Match', color: 'var(--green)', bg: 'rgba(48,209,88,0.12)' },
    possible_match: { label: 'Possible Match', color: 'var(--blue)', bg: 'rgba(10,132,255,0.12)' },
    needs_review: { label: 'Needs Review', color: 'var(--orange)', bg: 'rgba(255,159,10,0.12)' },
    rejected: { label: 'Rejected', color: 'var(--red)', bg: 'rgba(255,69,58,0.12)' },
    saved: { label: 'Saved', color: 'var(--green)', bg: 'rgba(48,209,88,0.12)' },
  }
  return tones[lane] || tones.needs_review
}

export function normalizeBrowserPlan(raw = {}) {
  return {
    mode: raw.mode || 'bounded_browser_assist',
    objective: raw.objective || 'Inspect approved source pages and extract cross-reference clues',
    pages_to_visit: Array.isArray(raw.pages_to_visit) ? raw.pages_to_visit : [],
    inspect_for: Array.isArray(raw.inspect_for) ? raw.inspect_for : [],
    artifacts_to_save: Array.isArray(raw.artifacts_to_save) ? raw.artifacts_to_save : [],
    safety_note: raw.safety_note || 'Browser Assist only visits approved URLs.',
    experimental_desktop_control: raw.experimental_desktop_control || { available: false },
  }
}
