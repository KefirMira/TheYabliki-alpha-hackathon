/**
 * Хранилище браузера: sessionStorage или localStorage («запомнить меня»).
 * Чтение — сначала sessionStorage, затем localStorage. Недоступность
 * хранилища (приватный режим, запрет сайта) не роняет интерфейс.
 */

export function storageSave(key: string, value: string, rememberMe = true) {
  try {
    const storage = rememberMe ? localStorage : sessionStorage
    storage.setItem(key, value)
  } catch (error) {
    console.warn('Не удалось сохранить значение в хранилище:', error)
  }
}

export function storageGet(key: string): string | null {
  try {
    return sessionStorage.getItem(key) ?? localStorage.getItem(key)
  } catch {
    return null
  }
}

export function storageDelete(key: string) {
  try {
    sessionStorage.removeItem(key)
    localStorage.removeItem(key)
  } catch (error) {
    console.warn('Не удалось удалить значение из хранилища:', error)
  }
}
