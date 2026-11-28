/**
 * Одноразовое сообщение для следующего экрана («Участник добавлен», …).
 * Хранится в sessionStorage, а не в адресе: в тексте бывают ФИО участников.
 */
const KEY = "acc_flash";

export function setFlash(text: string) {
  try {
    sessionStorage.setItem(KEY, text);
  } catch {
    /* приватный режим — сообщение просто не покажем */
  }
}

export function takeFlash(): string | null {
  try {
    const v = sessionStorage.getItem(KEY);
    if (v !== null) sessionStorage.removeItem(KEY);
    return v;
  } catch {
    return null;
  }
}
