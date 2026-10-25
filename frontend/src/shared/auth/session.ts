// Individual server token, never a demo login flag. No credentials in logs/URLs.
const KEY = 'pulse_bearer'
let generation = 0
export const sessionGeneration = () => generation
export const accessToken = (): string | null => {
  try {
    return sessionStorage.getItem(KEY)
  } catch {
    return null
  }
}
export const setAccessToken = (token: string) => {
  sessionStorage.setItem(KEY, token)
  generation += 1
}
export const clearSession = () => {
  generation += 1
  try {
    sessionStorage.removeItem(KEY)
  } catch {
    /* fail closed */
  }
}
export const expireSession = () => {
  clearSession()
  window.dispatchEvent(new Event('pulse-session-expired'))
}
