# 05. REST API

Документ описывает публичный REST-интерфейс HealthTracker. API версионируется через префикс пути (`/api/v1/`). OpenAPI 3.1 спецификация генерируется из Zod-схем через `@fastify/swagger` и доступна на `/api/v1/docs`.

## 1. Общие конвенции

### 1.1. Базовый URL

- Production: `https://{DOMAIN}/api/v1`
- Dev: `http://localhost:3000/api/v1`

### 1.2. Аутентификация

Все эндпоинты, кроме `/auth/register`, `/auth/login`, `/healthz`, `/readyz`, требуют активной сессии.

Сессия идентифицируется cookie `healthtracker_sid`. При отсутствии или истечении — ответ `401 Unauthorized`.

### 1.3. CSRF

Все небезопасные методы (POST, PUT, PATCH, DELETE) требуют заголовок `X-CSRF-Token`, значение которого должно совпадать с cookie `csrf_token`.

Cookie `csrf_token` (не httpOnly) выставляется сервером при первом ответе.

### 1.4. Формат данных

- Content-Type запросов и ответов — `application/json; charset=utf-8`, кроме загрузки файлов (`multipart/form-data`).
- Даты — ISO 8601 (`2026-04-24T14:30:00.000Z`).
- Числа — без локализации, точка как разделитель.
- `null` передаётся явно; поле `undefined` эквивалентно отсутствующему.

### 1.5. Пагинация

Для списочных эндпоинтов:
- Параметры: `?page=0&pageSize=50`.
- Максимум `pageSize` — 100.
- Ответ содержит метаданные:

```json
{
  "data": [ ... ],
  "pagination": {
    "page": 0,
    "pageSize": 50,
    "totalItems": 137,
    "totalPages": 3
  }
}
```

### 1.6. Ошибки

Единый формат:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Не удалось проверить данные",
    "details": [
      { "path": ["email"], "message": "Неверный формат e-mail" }
    ]
  }
}
```

Коды ошибок:

| code                      | HTTP | Описание                                       |
| ------------------------- | ---- | ---------------------------------------------- |
| `VALIDATION_ERROR`        | 400  | Ошибка валидации входных данных                |
| `UNAUTHENTICATED`         | 401  | Нет сессии или она истекла                     |
| `FORBIDDEN`               | 403  | Доступ к ресурсу запрещён (включая CSRF)       |
| `NOT_FOUND`               | 404  | Ресурс не найден                               |
| `CONFLICT`                | 409  | Нарушение уникальности (e.g. занятый e-mail)   |
| `UNSUPPORTED_MEDIA_TYPE`  | 415  | Неверный Content-Type или MIME файла           |
| `PAYLOAD_TOO_LARGE`       | 413  | Файл превышает лимит                           |
| `TOO_MANY_REQUESTS`       | 429  | Rate limit                                     |
| `INTERNAL_ERROR`          | 500  | Неожиданная ошибка сервера                     |

### 1.7. Идемпотентность

POST-запросы не идемпотентны (ожидаемо).
PUT и DELETE — идемпотентны.
Все мутации выполняются в транзакциях БД.

### 1.8. Конвенции именования

- Пути — kebab-case: `/measurements/:id/attachments`.
- JSON-поля — camelCase: `takenAt`, `baseUnit`.
- IDs — `cuid()` из Prisma, строки длиной 24 символа.

---

## 2. Health checks

### GET /healthz

Проверка живости сервиса. Публичный, без авторизации.

**Ответ 200:**
```json
{ "status": "ok", "version": "0.1.0" }
```

### GET /readyz

Проверка готовности (миграции применены, БД доступна). Публичный.

**Ответ 200:**
```json
{ "status": "ready", "db": "ok" }
```

**Ответ 503:**
```json
{ "status": "not_ready", "db": "error", "reason": "migrations pending" }
```

---

## 3. Auth — `/auth`

### POST /auth/register

Регистрация нового пользователя.

**Запрос:**
```json
{
  "email": "anna@example.com",
  "password": "StrongP@ss1234",
  "name": "Анна",
  "sex": "female",
  "birthDate": "1990-05-15"
}
```

**Валидация:**
- `email`: RFC 5322, lowercase.
- `password`: ≥ 10 символов, ≥ 3 из 4 классов (lower, upper, digit, special).
- `name`: 1–100 символов, trim.
- `sex`: `"male"` | `"female"`.
- `birthDate`: ISO-дата в прошлом, не более 120 лет назад.

**Ответ 201:**
```json
{
  "user": {
    "id": "clx2k7q8a0000abc",
    "email": "anna@example.com",
    "profile": {
      "name": "Анна",
      "sex": "female",
      "birthDate": "1990-05-15"
    }
  }
}
```
Заголовки: `Set-Cookie: healthtracker_sid=...; HttpOnly; Secure; SameSite=Strict`.

**Ошибки:** `409 CONFLICT` (e-mail занят), `400 VALIDATION_ERROR`.

### POST /auth/login

Вход.

**Запрос:**
```json
{ "email": "anna@example.com", "password": "StrongP@ss1234" }
```

**Ответ 200:**
```json
{ "user": { "id": "clx2k7q8a0000abc", "email": "anna@example.com" } }
```
+ `Set-Cookie`.

**Ошибки:** `401 UNAUTHENTICATED` (неверные данные), `429 TOO_MANY_REQUESTS` (после 5 попыток за 15 минут).

### POST /auth/logout

Выход, инвалидация текущей сессии.

**Ответ 204** (без тела). `Set-Cookie` с `Max-Age=0`.

### GET /auth/me

Получить текущего пользователя.

**Ответ 200:**
```json
{
  "user": {
    "id": "clx2k7q8a0000abc",
    "email": "anna@example.com",
    "profile": {
      "name": "Анна",
      "sex": "female",
      "birthDate": "1990-05-15",
      "ageYears": 35
    }
  }
}
```

**Ошибки:** `401` если нет активной сессии.

### POST /auth/change-password

Смена пароля.

**Запрос:**
```json
{
  "currentPassword": "StrongP@ss1234",
  "newPassword": "NewStrongP@ss1234"
}
```

**Ответ 204.** Все сессии, кроме текущей, удалены.

**Ошибки:** `401` (неверный текущий пароль), `400` (невалидный новый).

### POST /auth/sessions/revoke-all

Инвалидация всех сессий, кроме текущей.

**Ответ 204.**

### GET /auth/sessions

Список активных сессий пользователя.

**Ответ 200:**
```json
{
  "data": [
    {
      "id": "clx2sess0001",
      "createdAt": "2026-04-20T10:00:00Z",
      "lastSeenAt": "2026-04-24T14:30:00Z",
      "expiresAt": "2026-05-20T10:00:00Z",
      "userAgent": "Mozilla/5.0 (iPhone...)",
      "current": true
    }
  ]
}
```

### DELETE /auth/sessions/:id

Удалить конкретную сессию (например, с чужого устройства).

**Ответ 204** или `404`, если сессия не принадлежит пользователю.

---

## 4. Profile — `/profile`

### GET /profile

Получить профиль текущего пользователя.

**Ответ 200:**
```json
{
  "id": "clx2prof0001",
  "name": "Анна",
  "sex": "female",
  "birthDate": "1990-05-15",
  "ageYears": 35,
  "createdAt": "2026-04-20T10:00:00Z",
  "updatedAt": "2026-04-20T10:00:00Z"
}
```

### PATCH /profile

Обновить профиль.

**Запрос:**
```json
{
  "name": "Анна Иванова",
  "sex": "female",
  "birthDate": "1990-05-15"
}
```

Все поля опциональны. Обновляется только переданное.

**Ответ 200** — обновлённый профиль.

**Примечание:** Изменение `sex` или `birthDate` пересчитывает референсы для всех будущих отображений. Сами значения в `MetricValue` не меняются. UI должен показать предупреждение до отправки запроса.

---

## 5. Metrics (справочник) — `/metrics`

### GET /metrics

Список показателей с фильтрацией и поиском.

**Параметры:**
- `?q=гем` — полнотекстовый поиск по name и synonyms.
- `?category=hematology` — фильтр по категории.
- `?scope=system` | `?scope=custom` | `?scope=all` (по умолчанию — `all`).

**Ответ 200:**
```json
{
  "data": [
    {
      "id": "clxmetric0001",
      "key": "hemoglobin",
      "name": "Гемоглобин",
      "synonyms": ["HGB", "Hb"],
      "category": "hematology",
      "baseUnit": "г/л",
      "allowedUnits": [
        { "unit": "г/л", "factor": 1, "offset": 0 },
        { "unit": "г/дл", "factor": 10, "offset": 0 }
      ],
      "isSystem": true,
      "reference": {
        "source": "system",
        "valueMin": 117,
        "valueMax": 155,
        "comment": null
      }
    }
  ]
}
```

Поле `reference` рассчитывается на бэке для профиля текущего пользователя (с учётом user override).

### GET /metrics/:id

Получить один показатель.

**Ответ 200:** как элемент массива выше + поле `usageCount` (сколько замеров с этим показателем у пользователя).

### POST /metrics

Создать пользовательский показатель.

**Запрос:**
```json
{
  "name": "Специфический маркер Х",
  "category": "biochemistry",
  "baseUnit": "нг/мл",
  "allowedUnits": [{ "unit": "нг/мл", "factor": 1, "offset": 0 }],
  "synonyms": ["Marker X"],
  "description": "Тест от конкретной лаборатории",
  "reference": { "valueMin": 0, "valueMax": 10 }
}
```

**Ответ 201** — созданный показатель. `isSystem = false`, `ownerUserId = currentUser`.

**Валидация:**
- `name` уникален в рамках пользователя + системных имён.
- `baseUnit` обязателен.
- `allowedUnits` должен содержать запись для `baseUnit`.
- `reference.valueMin < reference.valueMax`.

### PATCH /metrics/:id

Обновить пользовательский показатель. Системные — `403 FORBIDDEN`.

**Запрос:** любые поля кроме `key`.

**Ответ 200** — обновлённый показатель.

### DELETE /metrics/:id

Удалить пользовательский показатель. Возможно только если `usageCount = 0`.

**Ответ 204** или `409 CONFLICT` с сообщением «показатель используется в N замерах, удалите их сначала».

### PUT /metrics/:id/reference

Установить пользовательский референс (override) для показателя. Работает и для системных, и для пользовательских.

**Запрос:**
```json
{ "valueMin": 100, "valueMax": 150, "comment": "По рекомендации эндокринолога" }
```

**Ответ 200** — показатель с обновлённым `reference.source = "user"`.

### DELETE /metrics/:id/reference

Сбросить пользовательский референс — вернуться к системному.

**Ответ 204**. Для пользовательских показателей (без системного fallback) — оставляет референс нетронутым, если есть, или `409` если сбрасывать нечего.

---

## 6. Measurements — `/measurements`

### GET /measurements

Список замеров пользователя с превью.

**Параметры:**
- `?page=0&pageSize=50` — пагинация.
- `?from=2026-01-01&to=2026-04-24` — фильтр по диапазону дат.
- `?metricId=clxmetric0001` — оставить замеры, где есть этот показатель.

**Ответ 200:**
```json
{
  "data": [
    {
      "id": "clxmeas0001",
      "takenAt": "2026-04-20",
      "noteExcerpt": "Сдавала утром натощак. Последние 2 недели...",
      "valuesCount": 8,
      "attachmentsCount": 1,
      "previewValues": [
        { "metricName": "Гемоглобин", "value": 125, "unit": "г/л", "status": "normal" },
        { "metricName": "ТТГ", "value": 4.8, "unit": "мкМЕ/мл", "status": "above" }
      ]
    }
  ],
  "pagination": { "page": 0, "pageSize": 50, "totalItems": 12, "totalPages": 1 }
}
```

`status`: `"normal"` | `"above"` | `"below"` | `"unknown"` (если нет референса).

### GET /measurements/:id

Получить один замер со всеми данными.

**Ответ 200:**
```json
{
  "id": "clxmeas0001",
  "takenAt": "2026-04-20",
  "note": "Сдавала утром натощак...",
  "values": [
    {
      "id": "clxvalue0001",
      "metricId": "clxmetric0001",
      "metricName": "Гемоглобин",
      "value": 125,
      "unit": "г/л",
      "status": "normal",
      "reference": { "valueMin": 117, "valueMax": 155, "source": "system" }
    }
  ],
  "attachments": [
    {
      "id": "clxattach0001",
      "filename": "analysis.pdf",
      "mimeType": "application/pdf",
      "sizeBytes": 245678,
      "createdAt": "2026-04-20T10:30:00Z"
    }
  ],
  "createdAt": "2026-04-20T10:30:00Z",
  "updatedAt": "2026-04-20T10:30:00Z"
}
```

**Ошибки:** `404 NOT_FOUND` если замер не принадлежит пользователю.

### POST /measurements

Создать замер.

**Запрос:**
```json
{
  "takenAt": "2026-04-20",
  "note": "Сдавала утром натощак",
  "values": [
    { "metricId": "clxmetric0001", "value": 125, "unit": "г/л" },
    { "metricId": "clxmetric0042", "value": 4.8, "unit": "мкМЕ/мл" }
  ]
}
```

**Валидация:**
- `takenAt`: ISO-дата, не в будущем.
- `note`: ≤ 5000 символов.
- `values`: массив, уникальность по `metricId`, все `metricId` должны существовать и быть доступны пользователю.
- Каждая `unit` должна быть в `allowedUnits` показателя.
- `value` — число; конвертируется в baseUnit перед сохранением.

**Ответ 201:** полный объект замера.

**Примечание:** вложения добавляются отдельно через `POST /measurements/:id/attachments`.

### PUT /measurements/:id

Полное обновление замера. Значения заменяются целиком: что не передано — удаляется.

**Запрос:** как в POST.

**Ответ 200** — обновлённый замер.

### PATCH /measurements/:id

Частичное обновление: меняет только переданные поля. Для значений — другие эндпоинты (`POST /measurements/:id/values`, `DELETE /values/:id`).

**Запрос:**
```json
{ "takenAt": "2026-04-21", "note": "Исправленная заметка" }
```

**Ответ 200** — обновлённый замер.

### DELETE /measurements/:id

Удалить замер. Каскадно удаляются значения и вложения (включая файлы на диске).

**Ответ 204.**

### POST /measurements/:id/values

Добавить одно значение к существующему замеру.

**Запрос:**
```json
{ "metricId": "clxmetric0015", "value": 5.2, "unit": "ммоль/л" }
```

**Ответ 201:** созданное значение.

**Ошибки:** `409 CONFLICT` если для этого метрика уже есть значение в этом замере.

### PATCH /measurements/:mid/values/:vid

Изменить одно значение.

**Запрос:**
```json
{ "value": 5.1, "unit": "ммоль/л" }
```

**Ответ 200:** обновлённое значение.

### DELETE /measurements/:mid/values/:vid

Удалить значение.

**Ответ 204.**

---

## 7. Attachments — `/attachments`

### POST /measurements/:id/attachments

Загрузить файл к замеру. `multipart/form-data`.

**Запрос:** поле `file` — файл.

**Валидация:**
- Content-Type файла в whitelist: `application/pdf`, `image/jpeg`, `image/png`, `image/heic`, `image/heif`.
- Magic bytes совпадают с Content-Type.
- Размер ≤ `STORAGE_MAX_FILE_MB` (по умолчанию 10 МБ).
- Общий размер storage пользователя + размер файла ≤ `STORAGE_MAX_USER_GB`.
- К одному замеру не более 10 вложений.

**Ответ 201:**
```json
{
  "id": "clxattach0001",
  "filename": "analysis.pdf",
  "mimeType": "application/pdf",
  "sizeBytes": 245678,
  "sha256": "abc123...",
  "createdAt": "2026-04-20T10:30:00Z"
}
```

**Ошибки:** `413 PAYLOAD_TOO_LARGE`, `415 UNSUPPORTED_MEDIA_TYPE`, `409 CONFLICT` (лимит вложений на замер или на пользователя).

### GET /attachments/:id

Скачать файл.

**Ответ 200:** бинарный поток с заголовками:
```
Content-Type: application/pdf
Content-Disposition: inline; filename="analysis.pdf"
Content-Length: 245678
Cache-Control: private, max-age=3600
```

**Ошибки:** `404` если не принадлежит пользователю.

### GET /attachments/:id/thumbnail

Для изображений — уменьшенная версия (150×150). Для PDF — первая страница как изображение (v1.0, в MVP — иконка).

### DELETE /attachments/:id

Удалить вложение. Файл удаляется с диска, запись — из БД.

**Ответ 204.**

---

## 8. Chart data — `/chart`

Специализированные эндпоинты для графиков, оптимизированные под объём данных.

### GET /chart/single

Точки для одного показателя.

**Параметры:**
- `?metricId=clxmetric0001` (обязателен)
- `?from=2025-01-01&to=2026-04-24` (опционально; по умолчанию — за всё время)

**Ответ 200:**
```json
{
  "metric": {
    "id": "clxmetric0001",
    "name": "Гемоглобин",
    "baseUnit": "г/л"
  },
  "reference": { "valueMin": 117, "valueMax": 155, "source": "system" },
  "points": [
    {
      "measurementId": "clxmeas0001",
      "date": "2026-04-20",
      "value": 125,
      "status": "normal"
    }
  ]
}
```

Точки отсортированы по дате по возрастанию. Если референс отсутствует — `reference: null`, `status` не рассчитывается.

### GET /chart/multi

Точки для нескольких показателей, с нормализацией.

**Параметры:**
- `?metricIds=clx1,clx2,clx3` (обязателен, 2–8 id через запятую)
- `?from=...&to=...` (опционально)
- `?normalize=true` (опционально; по умолчанию true)

**Ответ 200:**
```json
{
  "series": [
    {
      "metric": { "id": "clx1", "name": "Гемоглобин", "color": "#E74C3C" },
      "reference": { "valueMin": 117, "valueMax": 155 },
      "points": [
        {
          "measurementId": "clxmeas0001",
          "date": "2026-04-20",
          "value": 125,
          "normalizedValue": 91.9,
          "status": "normal"
        }
      ]
    }
  ],
  "normalizedRange": { "min": 80, "max": 120 }
}
```

`normalizedValue = value / midReference * 100`, где `midReference = (min + max) / 2`.
`normalizedRange` — общая полоса для всех серий (самая узкая из нормализованных референсов).

---

## 9. Export — `/export`

### POST /export/backup

Создать полный бэкап пользователя. Возвращает task для отслеживания (т.к. может занять время).

**Запрос:** тело не требуется.

**Ответ 202 Accepted:**
```json
{
  "taskId": "clxtask0001",
  "statusUrl": "/api/v1/export/tasks/clxtask0001"
}
```

### GET /export/tasks/:taskId

Проверить статус задачи экспорта.

**Ответ 200:**
```json
{
  "id": "clxtask0001",
  "status": "in_progress",
  "progress": 0.65,
  "downloadUrl": null
}
```

Когда `status: "completed"`, в `downloadUrl` — URL для скачивания сгенерированного ZIP.

### GET /export/tasks/:taskId/download

Скачать готовый бэкап.

**Ответ 200:** `application/zip` с заголовком `Content-Disposition: attachment; filename="backup-2026-04-24.zip"`.

**Ошибки:** `404` если задача не завершена или истёк TTL (24 часа после готовности).

### POST /export/csv

Экспорт в CSV за период.

**Запрос:**
```json
{
  "from": "2026-01-01",
  "to": "2026-04-24",
  "metricIds": ["clx1", "clx2"]
}
```

`metricIds` опционально — если пусто, все показатели.

**Ответ 200:** `text/csv; charset=utf-8`:

```csv
date,metric_key,metric_name,value,unit,status,reference_min,reference_max
2026-04-20,hemoglobin,"Гемоглобин",125,"г/л",normal,117,155
2026-04-20,tsh,"ТТГ",4.8,"мкМЕ/мл",normal,0.4,4
```

### POST /export/report

PDF-отчёт для врача. Тоже асинхронная задача.

**Запрос:**
```json
{
  "from": "2025-04-24",
  "to": "2026-04-24",
  "metricIds": ["clx1", "clx2"],
  "includeNotes": true,
  "includeAttachmentsList": true
}
```

**Ответ 202:**
```json
{ "taskId": "clxtask0002", "statusUrl": "/api/v1/export/tasks/clxtask0002" }
```

Дальше — как `/export/backup`.

---

## 10. OpenAPI документация

- `GET /docs` — интерактивный Swagger UI.
- `GET /docs/json` — OpenAPI 3.1 JSON.
- `GET /docs/yaml` — OpenAPI 3.1 YAML.

OpenAPI генерируется автоматически из Fastify-роутов с Zod-схемами через `fastify-type-provider-zod`. Схемы находятся в `packages/shared/src/schemas/`, что позволяет фронту использовать те же типы.

## 11. Версионирование API

- Текущая версия — `v1`.
- Breaking changes → новая версия `v2`; обе поддерживаются переходный период.
- Добавление полей в ответ — не breaking.
- Удаление поля / ужесточение валидации — breaking.
- Deprecation помечается заголовком `Sunset: Sat, 31 Dec 2026 23:59:59 GMT` и в OpenAPI (`deprecated: true`).

## 12. Итоговая таблица эндпоинтов

| Method | Path                                          | Auth | Описание                              |
| ------ | --------------------------------------------- | ---- | ------------------------------------- |
| GET    | `/healthz`                                    | no   | Healthcheck                           |
| GET    | `/readyz`                                     | no   | Readiness                             |
| POST   | `/auth/register`                              | no   | Регистрация                           |
| POST   | `/auth/login`                                 | no   | Вход                                  |
| POST   | `/auth/logout`                                | yes  | Выход                                 |
| GET    | `/auth/me`                                    | yes  | Текущий пользователь                  |
| POST   | `/auth/change-password`                       | yes  | Смена пароля                          |
| POST   | `/auth/sessions/revoke-all`                   | yes  | Инвалидация всех сессий               |
| GET    | `/auth/sessions`                              | yes  | Список сессий                         |
| DELETE | `/auth/sessions/:id`                          | yes  | Удалить сессию                        |
| GET    | `/profile`                                    | yes  | Профиль                               |
| PATCH  | `/profile`                                    | yes  | Обновить профиль                      |
| GET    | `/metrics`                                    | yes  | Список показателей                    |
| GET    | `/metrics/:id`                                | yes  | Один показатель                       |
| POST   | `/metrics`                                    | yes  | Создать пользовательский              |
| PATCH  | `/metrics/:id`                                | yes  | Обновить пользовательский             |
| DELETE | `/metrics/:id`                                | yes  | Удалить пользовательский              |
| PUT    | `/metrics/:id/reference`                      | yes  | Установить user-override референса    |
| DELETE | `/metrics/:id/reference`                      | yes  | Сбросить override                     |
| GET    | `/measurements`                               | yes  | Список замеров                        |
| GET    | `/measurements/:id`                           | yes  | Один замер                            |
| POST   | `/measurements`                               | yes  | Создать замер                         |
| PUT    | `/measurements/:id`                           | yes  | Полное обновление                     |
| PATCH  | `/measurements/:id`                           | yes  | Частичное обновление                  |
| DELETE | `/measurements/:id`                           | yes  | Удалить замер                         |
| POST   | `/measurements/:id/values`                    | yes  | Добавить значение                     |
| PATCH  | `/measurements/:mid/values/:vid`              | yes  | Изменить значение                     |
| DELETE | `/measurements/:mid/values/:vid`              | yes  | Удалить значение                      |
| POST   | `/measurements/:id/attachments`               | yes  | Загрузить файл                        |
| GET    | `/attachments/:id`                            | yes  | Скачать файл                          |
| GET    | `/attachments/:id/thumbnail`                  | yes  | Миниатюра                             |
| DELETE | `/attachments/:id`                            | yes  | Удалить вложение                      |
| GET    | `/chart/single`                               | yes  | Данные графика одного показателя      |
| GET    | `/chart/multi`                                | yes  | Данные графика нескольких             |
| POST   | `/export/backup`                              | yes  | Запустить бэкап                       |
| GET    | `/export/tasks/:id`                           | yes  | Статус задачи экспорта                |
| GET    | `/export/tasks/:id/download`                  | yes  | Скачать результат                     |
| POST   | `/export/csv`                                 | yes  | CSV-экспорт (синхронный)              |
| POST   | `/export/report`                              | yes  | PDF-отчёт                             |