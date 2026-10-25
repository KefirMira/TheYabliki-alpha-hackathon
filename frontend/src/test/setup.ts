import '@testing-library/jest-dom'
import { cleanup } from '@testing-library/react'
import { afterEach, vi } from 'vitest'
import { clearSession } from '@/shared/auth/session'

// jsdom не реализует matchMedia, а на нём держится определение мобильной
// раскладки — без заглушки компоненты с адаптивом падают в тестах.
if (!window.matchMedia) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }))
}

afterEach(() => {
  cleanup()
  clearSession()
  vi.unstubAllGlobals()
})
