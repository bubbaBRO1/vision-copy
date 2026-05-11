export function scoreToColor(score) {
  if (score >= 80) return '#00ff88'
  if (score >= 60) return '#00cfff'
  if (score >= 40) return '#ffaa00'
  return '#ff3366'
}

export function scoreToLabel(score) {
  if (score >= 80) return 'Very High'
  if (score >= 60) return 'High'
  if (score >= 40) return 'Moderate'
  if (score >= 20) return 'Low'
  return 'Speculative'
}

export function scoreToClass(score) {
  if (score >= 80) return 'conf-very-high'
  if (score >= 60) return 'conf-high'
  if (score >= 40) return 'conf-moderate'
  if (score >= 20) return 'conf-low'
  return 'conf-speculative'
}

const ENGINE_WEIGHTS = {
  TinEyeScraper: 1.0,
  GoogleLensScraper: 0.9,
  YandexScraper: 0.85,
  SauceNAOScraper: 0.8,
  BingVisualScraper: 0.7,
  IQDBScraper: 0.65,
}

export function resultScore(r) {
  const sim = (r.similarity_pct || 0) / 100
  const engineWeight = ENGINE_WEIGHTS[r.engine] || 0.5
  return sim * 0.7 + engineWeight * 0.3
}
