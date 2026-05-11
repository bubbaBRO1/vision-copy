import { describe, it, expect } from 'vitest'
import { scoreToLabel, scoreToColor, scoreToClass, resultScore } from '../confidence'

describe('scoreToLabel', () => {
  it('returns Very High for 90+', () => expect(scoreToLabel(95)).toBe('Very High'))
  it('returns High for 70-89', () => expect(scoreToLabel(75)).toBe('High'))
  it('returns Moderate for 50-69', () => expect(scoreToLabel(55)).toBe('Moderate'))
  it('returns Low for 30-49', () => expect(scoreToLabel(35)).toBe('Low'))
  it('returns Speculative for below 30', () => expect(scoreToLabel(0)).toBe('Speculative'))
})

describe('scoreToColor', () => {
  it('returns green for 90+', () => expect(scoreToColor(90)).toBe('#00ff88'))
  it('returns cyan for 70-89', () => expect(scoreToColor(70)).toBe('#00cfff'))
  it('returns red for 0', () => expect(scoreToColor(0)).toBe('#ff3366'))
})

describe('scoreToClass', () => {
  it('returns conf-very-high for 90+', () => expect(scoreToClass(92)).toBe('conf-very-high'))
  it('returns conf-speculative for 0', () => expect(scoreToClass(0)).toBe('conf-speculative'))
})

describe('resultScore', () => {
  it('ranks TinEye 100% match highest', () => {
    const tineye = resultScore({ similarity_pct: 100, engine: 'TinEyeScraper' })
    const google = resultScore({ similarity_pct: 100, engine: 'GoogleLensScraper' })
    expect(tineye).toBeGreaterThan(google)
  })

  it('returns higher score for higher similarity same engine', () => {
    const high = resultScore({ similarity_pct: 90, engine: 'GoogleLensScraper' })
    const low = resultScore({ similarity_pct: 10, engine: 'GoogleLensScraper' })
    expect(high).toBeGreaterThan(low)
  })

  it('handles missing similarity_pct gracefully', () => {
    const score = resultScore({ engine: 'TinEyeScraper' })
    expect(score).toBeGreaterThanOrEqual(0)
  })
})
