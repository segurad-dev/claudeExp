# 03. Архитектура

Документ описывает техническую архитектуру HealthTracker по модели C4 (контекст → контейнеры → компоненты → код), обосновывает выбор технологий, раскрывает схему деплоя, аутентификацию, безопасность и ключевые абстракции.

## 1. C4, уровень 1 — системный контекст

```
           ┌─────────────────┐
           │    Пациент      │
           │  (браузер телефона
           │  или десктопа)  │
           └───────┬─────────┘
                   │ HTTPS
                   ▼
           ┌─────────────────┐
           │  HealthTracker  │
           │    (система)    │
           └─────────────────┘
                   │
                   ▼
           ┌─────────────────┐
           │   Let's Encrypt │
           │  (только для    │
           │   выпуска сертов)│
           └─────────────────┘
```

Система — единый self-hosted веб-сервис. Единственный внешний сервис — Let's Encrypt для автоматического выпуска TLS-сертификатов (только исходящие запросы, никаких данных о пользователях не передаётся).

## 2. C4, уровень 2 — контейнеры

```
┌───────────────────────────────────────────────────────────────────┐
│  Docker Compose host                                              │
│                                                                   │
│  ┌─────────────┐    ┌──────────────┐    ┌──────────────────┐     │
│  │    Caddy    │───▶│     web      │    │       api        │     │
│  │ (reverse    │    │ (static SPA: │    │ (Fastify + TS)   │     │
│  │  proxy, TLS)│    │  React build)│    │ :3000            │     │
│  │ :80, :443   │    │  nginx-alpine│    │                  │     │
│  └─────────────┘    └──────────────┘    └────────┬─────────┘     │
│         │                                         │                │
│         │ / → web                                  │ PSQL         │
│         │ /api/* → api                             ▼               │
│         │                                ┌──────────────────┐     │
│         └────────────────────────────────│       db         │     │
│                                          │  (PostgreSQL 16) │     │
│                                          │  :5432 (internal)│     │
│                                          └──────────────────┘     │
│                                                                   │
│  Volumes:                                                         │
│  - db_data       → /var/lib/postgresql/data                       │
│  - storage       → /app/storage (загруженные файлы пользователей) │
│  - caddy_data    → /data (сертификаты Let's Encrypt)              │
│  - backups       → /backups (автоматические бэкапы БД + storage)  │
└───────────────────────────────────────────────────────────────────┘
```

### 2.1. Описание контейнеров

**caddy** — реверс-прокси. Проксирует `/` на web и `/api/*` на api. Автоматически получает и обновляет TLS-сертификаты через Let's Encrypt. Терминирует HTTPS, apстрим-связь по HTTP во внутренней сети.

**web** — статический фронт. `nginx:alpine`, отдающий билд React+Vite (`dist/`). Имеет fallback на `index.html` для SPA-роутинга. Минимум логики, только отдача ассетов.

**api** — Fastify-приложение на Node 20 + TypeScript. Отвечает за все API-эндпоинты (`/api/v1/*`), аутентификацию, работу с БД, файлами. При старте применяет миграции Prisma и выполняет seed (идемпотентно). Монтирует volume `storage/`. Имеет healthcheck на `/api/v1/healthz`.

**db** — PostgreSQL 16. Доступна только во внутренней сети Compose. Монтирует volume `db_data`.

### 2.2. Dev-вариант (локальный запуск без Docker)

```
┌─────────────┐     ┌──────────────┐
│ Vite dev    │     │ Fastify dev  │
│ server :5173│────▶│  :3000       │
│             │proxy│              │
└─────────────┘     └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
                    │ SQLite       │
                    │ ./dev.db     │
                    └──────────────┘
```

В dev-режиме:
- Vite отдаёт фронт на `:5173` с HMR, проксирует `/api/*` на `:3000`.
- Fastify запускается через `tsx watch`, подхватывает изменения.
- БД — SQLite файл `./prisma/dev.db`. Prisma-схема одна, диалект меняется через переменную.
- Файлы хранятся в `./storage/`.
- Cookies — `Secure: false` (так как HTTP на localhost).

## 3. C4, уровень 3 — компоненты

### 3.1. Backend (api)

```
┌──────────────────────────────────────────────────────────────┐
│                         Fastify app                          │
│                                                              │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │  Plugins    │  │  Middlewares │  │     Routes       │   │
│  │  - swagger  │  │  - cors      │  │  - /auth         │   │
│  │  - cookie   │  │  - csrf      │  │  - /profile      │   │
│  │  - rate-    │  │  - session   │  │  - /metrics      │   │
│  │    limit    │  │    guard     │  │  - /measurements │   │
│  │  - multipart│  │  - error-    │  │  - /attachments  │   │
│  │    (uploads)│  │    handler   │  │  - /export       │   │
│  └─────────────┘  └──────────────┘  └────────┬─────────┘   │
│                                               │              │
│                                               ▼              │
│                                   ┌──────────────────┐      │
│                                   │    Services      │      │
│                                   │  - authService   │      │
│                                   │  - measurement   │      │
│                                   │  - metric        │      │
│                                   │  - export        │      │
│                                   │  - storage       │      │
│                                   └────────┬─────────┘      │
│                                            │                 │
│                                            ▼                 │
│                                   ┌──────────────────┐      │
│                                   │  Prisma client   │      │
│                                   └────────┬─────────┘      │
└────────────────────────────────────────────┼─────────────────┘
                                             ▼
                                     PostgreSQL / SQLite
```

**Route-layer** — тонкий слой, отвечающий только за контракт: парсинг запроса, валидация через Zod, вызов сервиса, сериализация ответа. Никакой бизнес-логики.

**Service-layer** — бизнес-логика. Получает валидированные DTO, работает с Prisma, возвращает доменные объекты. Сервисы независимы от Fastify — их можно тестировать без HTTP.

**Plugins**:
- `@fastify/cookie` — работа с httpOnly cookies.
- `@fastify/swagger` + `@fastify/swagger-ui` — генерация OpenAPI из Zod-схем через `fastify-type-provider-zod`.
- `@fastify/rate-limit` — защита от брутфорса на `/auth/login`.
- `@fastify/multipart` — приём файлов.
- `@fastify/cors` — CORS (по сути не нужен, но настроен строго на origin web-контейнера).
- `@fastify/helmet` — безопасные заголовки.

**Custom middlewares**:
- `sessionGuard` — извлекает `sid` из cookie, проверяет сессию в БД, прикрепляет `request.user`. На защищённых эндпоинтах.
- `csrfGuard` — double-submit cookie проверка для небезопасных методов.
- `errorHandler` — унифицированная сериализация ошибок в `{ error: { code, message, details } }`.

### 3.2. Frontend (web)

```
┌──────────────────────────────────────────────────────────────┐
│                      React app (Vite)                        │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │    Pages     │  │  Components  │  │    Services      │   │
│  │  - Login     │  │  - AnalyteChart│ │  - apiClient   │   │
│  │  - Register  │  │  - Measurement│ │  - authStore    │   │
│  │  - List      │  │    Form      │  │  - useAuth hook │   │
│  │  - Detail    │  │  - Value     │  │                  │   │
│  │  - Chart     │  │    Input     │  │                  │   │
│  │  - Profile   │  │  - Reference │  │                  │   │
│  │  - Export    │  │    Band      │  │                  │   │
│  └──────┬───────┘  └──────────────┘  └────────┬─────────┘   │
│         │                                      │              │
│         ▼                                      ▼              │
│  ┌──────────────┐                    ┌──────────────────┐   │
│  │ React Router │                    │ TanStack Query   │   │
│  └──────────────┘                    │ (кеш + invalid)  │   │
│                                      └────────┬─────────┘   │
│                                               │               │
│                                               ▼               │
│                                      ┌──────────────────┐   │
│                                      │ fetch wrapper    │   │
│                                      │ (credentials:    │   │
│                                      │  include, CSRF)  │   │
│                                      └──────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

**Pages** — верхнеуровневые экраны, каждый — отдельный роут.
**Components** — переиспользуемые блоки. Ключевые:
- `<AnalyteChart/>` — абстракция над графиком (см. раздел 7).
- `<MeasurementForm/>` — форма создания/редактирования замера.
- `<ValueInput/>` — одна строка «показатель × значение × единица» с автокомплитом и флагом отклонения.
- `<ReferenceBand/>` — SVG-компонент зелёной полосы на графике.
**Services** — точки интеграции:
- `apiClient` — обёртка над `fetch` с `credentials: 'include'` и CSRF-токеном.
- `authStore` (Zustand) — хранит текущего пользователя, методы login/logout.
- `useAuth` — хук для проверки состояния авторизации.

## 4. Обоснование стека

Детальное обсуждение альтернатив было проведено на этапе проектирования. Здесь — финальные решения с кратким обоснованием.

| Слой | Выбор | Ключевое обоснование |
| --- | --- | --- |
| Фронт-фреймворк | React 18 | Максимальная экосистема готовых компонентов (shadcn/ui, Radix), зрелость для долгоживущего проекта |
| Сборщик | Vite | Быстрый dev-сервер на esbuild, чистый SPA-билд для self-hosted |
| UI | Tailwind + shadcn/ui | Полный контроль над кодом компонентов, легко кастомизировать под макет |
| Графики | Recharts | Декларативный React-API, быстрый старт; архитектурно — абстракция для будущей миграции на ECharts |
| Формы | React Hook Form + Zod | Минимум ререндеров; общая валидация с бэком через Zod |
| Server state | TanStack Query | Стандарт де-факто для REST + React |
| Local state | Zustand | 1.5 КБ, без boilerplate, достаточен для локального state |
| Router | React Router v6 | Консервативный проверенный выбор |
| Backend | Node + Fastify + TS | Один язык с фронтом (shared Zod-схемы), скорость Fastify, отличный TS-саппорт |
| ORM | Prisma | Быстрый onboarding, богатая экосистема, простые миграции |
| БД | SQLite dev / Postgres prod | Минимум администрирования в dev, индустриальный стандарт в prod |
| Auth | Session cookies + bcrypt | Проще и безопаснее JWT для single-server self-hosted |
| Валидация | Zod | Совместим со всем TS-миром, общая схема фронт-бэк |
| API-контракт | REST + OpenAPI 3.1 | Свобода в выборе клиентов, автогенерация документации |
| Файлы | Локальная ФС + `StorageProvider` | Минимум зависимостей; абстракция позволит перейти на S3 |
| Proxy | Caddy | Автоматический Let's Encrypt, конфиг на 5 строк |
| Orchestration | Docker Compose | Простейший способ развернуть multi-container self-hosted |

## 5. Аутентификация и сессии

### 5.1. Модель

Выбрана модель **stateful session cookies**:
- Сессия — запись в таблице `Session` с случайным `id` (32 байта = 256 бит энтропии, base64url).
- `sid` передаётся клиенту в cookie `healthtracker_sid`.
- Cookie атрибуты: `httpOnly; Secure; SameSite=Strict; Path=/; Max-Age=2592000` (30 дней).
- На каждый защищённый запрос middleware валидирует `sid`, обновляет `lastSeenAt`, если прошло более 5 минут.
- Logout удаляет запись из `Session` и сбрасывает cookie.

### 5.2. Регистрация

```
1. POST /api/v1/auth/register { email, password, name, sex, birthDate }
2. api: валидация Zod → проверка уникальности e-mail →
   bcrypt.hash(password, 12) → INSERT User + Profile →
   создание Session → Set-Cookie
3. Ответ 201 { user: { id, email, name } }
```

### 5.3. Вход

```
1. POST /api/v1/auth/login { email, password }
2. api: SELECT User WHERE email → bcrypt.compare →
   при успехе: INSERT Session → Set-Cookie
   при неудаче: ответ 401 после постоянной задержки (constant-time)
3. Rate-limit: 5 попыток на 15 минут по (ip + email)
```

### 5.4. CSRF

Double-submit cookie:
- При первой загрузке страницы сервер выставляет cookie `csrf_token` (не httpOnly) с случайным значением.
- Фронт читает cookie, передаёт значение в заголовке `X-CSRF-Token` на все небезопасные запросы (POST/PUT/PATCH/DELETE).
- Middleware `csrfGuard` сравнивает заголовок с cookie; при несовпадении — 403.

SameSite=Strict на session cookie уже защищает от большинства CSRF-атак; double-submit — второй контур защиты (defense in depth).

### 5.5. Выход

```
1. POST /api/v1/auth/logout
2. api: DELETE Session WHERE id = sid; Set-Cookie expires in past
3. Ответ 204
```

### 5.6. Смена пароля и инвалидация

При смене пароля (US-04) все сессии пользователя, кроме текущей, удаляются: `DELETE Session WHERE userId = ? AND id != currentSid`.

Также делаем отдельный эндпоинт `POST /api/v1/auth/sessions/revoke-all`, который удаляет все сессии пользователя.

## 6. Безопасность

### 6.1. Заголовки

Через `@fastify/helmet`:
- `Content-Security-Policy: default-src 'self'; img-src 'self' data:; script-src 'self'; style-src 'self' 'unsafe-inline'` (unsafe-inline для Tailwind — допустимо для self-hosted).
- `Strict-Transport-Security: max-age=31536000; includeSubDomains` (в prod).
- `X-Content-Type-Options: nosniff`.
- `X-Frame-Options: DENY`.
- `Referrer-Policy: same-origin`.
- `Permissions-Policy: camera=(), microphone=(), geolocation=()` (для будущего нативного контекста — отключим лишние API).

### 6.2. Валидация входных данных

Все входы валидируются Zod-схемами через `fastify-type-provider-zod`. Если схема не совпадает — 400 с детальным сообщением об ошибке. Невалидные данные не доходят до сервис-слоя.

### 6.3. Защита файлов

Загруженные файлы:
1. При upload сохраняются на диск под `storage/{userId}/{measurementId}/{sha256}.{ext}`.
2. В БД пишется запись `Attachment` с путём, `mimeType`, `sizeBytes`, `originalFilename`.
3. Для скачивания — эндпоинт `GET /api/v1/attachments/:id`, который:
   - проверяет сессию и принадлежность файла пользователю;
   - отдаёт файл с правильным Content-Type и Content-Disposition;
   - проверяет, что `mimeType` в whitelist (защита от XSS через `text/html` или `application/javascript`).
4. Проверка содержимого: magic bytes (через `file-type`) сравниваются с `mimeType`; при несоответствии — 415.

### 6.4. Rate limiting

- `/auth/login`, `/auth/register` — 5 запросов / 15 минут / IP.
- Остальные эндпоинты — 100 запросов / минуту / сессия.
- При превышении — 429 Too Many Requests с заголовком `Retry-After`.

### 6.5. Логирование

- Все запросы логируются Pino с уровнем INFO: метод, путь, статус, время, userId (если авторизован).
- Ошибки — уровень ERROR с stack trace.
- **Запрещено** логировать: пароли, session id, CSRF-токены, тело запросов к `/auth/*`, содержимое замеров.
- Логи пишутся в stdout; Docker собирает через `docker compose logs`; опционально направляется в файл через logging driver.

### 6.6. Хранение секретов

- `.env.example` в репо — шаблон, без реальных значений.
- `.env` — в `.gitignore`, содержит `SESSION_SECRET`, `DATABASE_URL`, `DOMAIN` и т.д.
- `SESSION_SECRET` используется только для подписывания cookie (cookie-signer в Fastify), не для шифрования session id (он уже случайный).
- В prod рекомендация — монтировать `.env` как Docker secret.

### 6.7. Бэкапы и шифрование диска

Ответственность оператора:
- Включить шифрование диска на хосте (LUKS, FileVault, BitLocker).
- Настроить регулярные бэкапы `backups/`.
- Хранить бэкапы в зашифрованном виде (рекомендация в [08_OPERATIONS.md](./08_OPERATIONS.md)).

## 7. Абстракция графика

Принципиальное архитектурное решение: весь код, использующий графическую библиотеку, изолирован внутри компонента `<AnalyteChart/>`. Все страницы (Chart page, PDF-отчёт) используют только этот компонент через публичный интерфейс.

### 7.1. Интерфейс

```typescript
type AnalyteChartProps = {
  // Режим отображения
  mode: 'single' | 'normalized';

  // Данные: массив серий
  series: Array<{
    metricId: string;
    metricName: string;
    unit: string;
    color: string;
    points: Array<{
      measurementId: string;
      date: Date;
      value: number;
      // Для single-режима — ссылка на референс этого показателя
      reference?: { min: number; max: number };
    }>;
  }>;

  // Опционально, для single-режима — референсная полоса
  referenceBand?: { min: number; max: number };

  // Интервалы между точками показывать?
  showIntervals?: boolean;

  // Период отображения
  dateRange: { from: Date; to: Date };

  // Обработчики
  onPointClick?: (measurementId: string) => void;
  onLegendToggle?: (metricId: string, visible: boolean) => void;
};
```

### 7.2. Реализация

В MVP — `RechartsAnalyteChart.tsx`, использующий Recharts. Компонент `<AnalyteChart/>` — просто ре-экспорт Recharts-реализации через фасад:

```typescript
// apps/web/src/components/AnalyteChart/index.tsx
export { RechartsAnalyteChart as AnalyteChart } from './RechartsAnalyteChart';
```

Когда понадобится ECharts — пишется `EChartsAnalyteChart.tsx` с тем же интерфейсом, меняется только импорт в `index.tsx`.

### 7.3. Что уходит в абстракцию, что остаётся

Внутри `<AnalyteChart/>`:
- расчёт шкал, доменов;
- рендеринг линий, точек, tooltip;
- отображение референсной полосы;
- отображение интервалов между точками;
- обработка кликов, легенды.

Снаружи (в вызывающем коде):
- получение данных (TanStack Query);
- нормализация значений для режима 'normalized' (см. раздел 7.4);
- логика выбора показателей;
- навигация по клику на точку.

### 7.4. Нормализация для режима 'normalized'

Когда пользователь выбирает несколько показателей для сравнения (US-16), значения нормализуются до графика:

```
normalizedValue = value / midReference * 100

где midReference = (referenceMin + referenceMax) / 2
```

Референсная полоса показывается как единая зона (например, 80–120%, если ширина референса — 40% от середины; для каждого показателя это своя ширина, поэтому визуализация показывает **самую узкую из полос** с аннотацией).

Tooltip всегда показывает оригинальное, ненормализованное значение и единицу.

## 8. Абстракция хранилища файлов

Аналогично графику, работа с файлами инкапсулирована в `StorageProvider`:

```typescript
interface StorageProvider {
  save(userId: string, measurementId: string, file: Buffer, ext: string): Promise<{
    sha256: string;
    path: string;
    sizeBytes: number;
  }>;
  read(path: string): Promise<Buffer>;
  delete(path: string): Promise<void>;
  exists(path: string): Promise<boolean>;
}
```

В MVP — `LocalFilesystemProvider`, использующий `fs/promises`. Когда понадобится S3 — `S3Provider`, меняется инстанциация в DI-контейнере.

## 9. Стратегия конфигурации

### 9.1. Переменные окружения

```env
# Server
NODE_ENV=production
PORT=3000
DOMAIN=health.example.com

# Database
DATABASE_URL=postgresql://postgres:password@db:5432/healthtracker

# Sessions
SESSION_SECRET=<min 32 random chars>
SESSION_COOKIE_NAME=healthtracker_sid
SESSION_TTL_DAYS=30

# Storage
STORAGE_ROOT=/app/storage
STORAGE_MAX_FILE_MB=10
STORAGE_MAX_USER_GB=1

# Features
FEATURE_REGISTRATION_OPEN=true     # если false — регистрация только через admin
FEATURE_BACKUP_CRON=true           # ежедневный бэкап
BACKUP_RETENTION_DAYS=14

# Observability
LOG_LEVEL=info                      # debug, info, warn, error
```

### 9.2. Семантика конфигурации

- Конфиг загружается один раз при старте через Zod-схему; приложение не стартует, если конфиг невалиден.
- В dev — `.env.development`, в prod — `.env` или Docker secrets.
- Секреты **никогда** не попадают в логи и в ответы API.

## 10. Нагрузка и масштабирование

MVP рассчитан на несколько десятков пользователей. Если появится необходимость в масштабировании:

- **Вертикально**: увеличить ресурсы VPS, перейти на PostgreSQL с индексами (уже заложено).
- **Горизонтально**: ключевое ограничение — локальная ФС для файлов. Придётся перейти на S3/MinIO через `StorageProvider` и несколько инстансов api за балансировщиком.
- **Кеширование**: Redis для сессий, если api инстансов > 1.

В MVP об этом не думаем; однократного докеризованного инстанса хватит надолго.

## 11. Наблюдаемость (observability)

MVP:
- Healthcheck `GET /api/v1/healthz` → 200 с `{ status: 'ok', db: 'ok' }`.
- Readiness `GET /api/v1/readyz` → 200, когда миграции применены.
- Логи Pino в stdout.
- Docker collect logs.

Будущее (не в MVP):
- Метрики Prometheus на `/metrics`.
- Sentry для фронта и бэка.
- OpenTelemetry-трейсинг.

## 12. Ключевые архитектурные решения (ADR)

Решения, которые стоит зафиксировать как отдельные ADR (architecture decision records) в `docs/adr/`:

- ADR-001: Session cookies вместо JWT.
- ADR-002: REST + OpenAPI вместо tRPC.
- ADR-003: Абстракция `<AnalyteChart/>` для будущей миграции на ECharts.
- ADR-004: Prisma + SQLite в dev / PostgreSQL в prod.
- ADR-005: Монорепозиторий pnpm с shared Zod-пакетом.
- ADR-006: Локальная ФС + `StorageProvider` вместо S3 в MVP.
- ADR-007: Normalized-режим графика через `% от середины нормы`.

ADR пишутся кратко (1 страница на каждый): контекст, решение, последствия, альтернативы. Создание этих файлов — задача первых дней разработки.