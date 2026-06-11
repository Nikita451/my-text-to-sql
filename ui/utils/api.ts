/**
 * Возвращает правильный базовый URL бэкенда в зависимости от среды выполнения.
 * На сервере (внутри Docker) возвращает внутреннее имя сервиса 'http://agent:8000'.
 * В браузере (у клиента) возвращает 'http://localhost:8000'.
 */
export function getBaseApiUrl(): string {
  // 1. Если код выполняется в браузере (у клиента) — берем переменную с префиксом NEXT_PUBLIC_
  if (typeof window !== 'undefined') {
    return process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  }

  // 2. Если код выполняется на сервере Node.js (в Docker или локально) — берем SERVER_API_URL.
  // Если её нет (запуск вне докера), плавно откатываемся на NEXT_PUBLIC_API_URL
  return process.env.SERVER_API_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
}

