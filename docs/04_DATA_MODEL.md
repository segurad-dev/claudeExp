# 04. Модель данных

Документ описывает реляционную модель HealthTracker: ER-диаграмму, полную Prisma-схему с комментариями, индексы, инварианты и seed-каталог показателей.

## 1. ER-диаграмма

```
┌──────────────────┐        ┌──────────────────┐
│      User        │ 1    1 │     Profile      │
│──────────────────│────────│──────────────────│
│ id (PK)          │        │ id (PK)          │
│ email (unique)   │        │ userId (FK,uniq) │
│ passwordHash     │        │ name             │
│ createdAt        │        │ sex              │
│ updatedAt        │        │ birthDate        │
└────────┬─────────┘        │ createdAt        │
         │                  │ updatedAt        │
         │                  └──────────────────┘
         │ 1
         │
         │ * ┌──────────────────┐
         ├───│     Session      │
         │   │──────────────────│
         │   │ id (PK) = sid    │
         │   │ userId (FK)      │
         │   │ createdAt        │
         │   │ lastSeenAt       │
         │   │ expiresAt        │
         │   │ userAgent        │
         │   │ ipHash           │
         │   └──────────────────┘
         │
         │ *
         │
┌────────▼──────────┐   1    * ┌──────────────────┐
│   Measurement     │──────────│   MetricValue    │
│───────────────────│          │──────────────────│
│ id (PK)           │          │ id (PK)          │
│ userId (FK)       │          │ measurementId(FK)│
│ takenAt (date)    │          │ metricId (FK)    │
│ note              │          │ value (numeric)  │
│ createdAt         │          │ unit             │
│ updatedAt         │          │ createdAt        │
└────────┬──────────┘          │ updatedAt        │
         │ 1                   └────────┬─────────┘
         │                              │ *
         │ *                            │
┌────────▼──────────┐                   │ 1
│   Attachment      │         ┌─────────▼────────┐       ┌──────────────────┐
│───────────────────│         │     Metric       │ 1   * │ ReferenceRange   │
│ id (PK)           │         │──────────────────│───────│──────────────────│
│ measurementId(FK) │         │ id (PK)          │       │ id (PK)          │
│ userId (FK)       │         │ key (unique)     │       │ metricId (FK)    │
│ filename          │         │ name             │       │ userId (FK, null)│
│ mimeType          │         │ synonyms[]       │       │ sex              │
│ sizeBytes         │         │ category         │       │ ageMin           │
│ sha256            │         │ baseUnit         │       │ ageMax           │
│ path              │         │ allowedUnits[]   │       │ valueMin         │
│ createdAt         │         │ isSystem         │       │ valueMax         │
└───────────────────┘         │ ownerUserId(FK,null)     │ comment          │
                              │ createdAt        │       │ createdAt        │
                              │ updatedAt        │       │ updatedAt        │
                              └──────────────────┘       └──────────────────┘
```

### 1.1. Основные связи

- **User 1:1 Profile** — профиль создаётся автоматически при регистрации.
- **User 1:N Session** — одновременно может быть несколько активных сессий (разные устройства).
- **User 1:N Measurement** — пациент ведёт свои замеры.
- **Measurement 1:N MetricValue** — в одном замере может быть много показателей.
- **Measurement 1:N Attachment** — в одном замере может быть до 10 вложений.
- **Metric 1:N MetricValue** — один показатель встречается во многих замерах.
- **Metric 1:N ReferenceRange** — для одного показателя может быть несколько референсов (разные пол/возраст), плюс пользовательский override.
- **Metric N:1 User (ownerUserId)** — пользовательский показатель принадлежит создавшему его; системный — имеет `ownerUserId = null` и `isSystem = true`.
- **ReferenceRange N:1 User (userId)** — пользовательский override референса. Для дефолтных — `userId = null`.

## 2. Prisma-схема

Полная схема `prisma/schema.prisma`. Диалект переключается между SQLite и PostgreSQL через переменную окружения.

```prisma
generator client {
  provider = "prisma-client-js"
}

datasource db {
  provider = env("DATABASE_PROVIDER")  // "sqlite" | "postgresql"
  url      = env("DATABASE_URL")
}

/// Пользователь — учётная запись с аутентификацией.
model User {
  id            String   @id @default(cuid())
  email         String   @unique
  passwordHash  String
  createdAt     DateTime @default(now())
  updatedAt     DateTime @updatedAt

  profile       Profile?
  sessions      Session[]
  measurements  Measurement[]
  attachments   Attachment[]
  ownedMetrics  Metric[]          @relation("UserOwnedMetrics")
  customRanges  ReferenceRange[]  @relation("UserCustomRanges")

  @@index([email])
}

/// Профиль пациента — данные для расчёта референсов.
/// В MVP — один профиль на пользователя (unique userId).
model Profile {
  id         String   @id @default(cuid())
  userId     String   @unique
  name       String
  sex        Sex
  birthDate  DateTime  // только дата, время игнорируется
  createdAt  DateTime @default(now())
  updatedAt  DateTime @updatedAt

  user       User     @relation(fields: [userId], references: [id], onDelete: Cascade)
}

enum Sex {
  male
  female
  // В MVP не поддерживаем промежуточные/другие значения —
  // референсы для небинарных пациентов требуют отдельной проработки
  // и выносятся в v2. Пока — мужские/женские как проксимация.
}

/// Активная сессия. sid хранится в cookie.
model Session {
  id          String   @id  // = sid, base64url(32 bytes)
  userId      String
  createdAt   DateTime @default(now())
  lastSeenAt  DateTime @default(now())
  expiresAt   DateTime
  userAgent   String?
  ipHash      String?  // SHA-256 от IP + SESSION_SECRET, для аудита без хранения сырого IP

  user        User     @relation(fields: [userId], references: [id], onDelete: Cascade)

  @@index([userId])
  @@index([expiresAt])
}

/// Справочник показателей. Системные + пользовательские.
model Metric {
  id            String   @id @default(cuid())
  key           String   @unique  // машинный ключ, например "hemoglobin"
  name          String            // человекочитаемое имя на русском
  synonyms      String[]          // ["HGB", "Hb", "Гемоглобин"] — для поиска
  category      String            // "hematology" | "biochemistry" | "hormones" | "vitamins" | ...
  baseUnit      String            // "г/л" — единица, в которой храним value
  allowedUnits  String[]          // ["г/л", "г/дл"] — разрешённые единицы с конвертерами
  description   String?           // что измеряет, зачем нужно
  isSystem      Boolean  @default(false)
  ownerUserId   String?           // для пользовательских показателей
  createdAt     DateTime @default(now())
  updatedAt     DateTime @updatedAt

  owner         User?            @relation("UserOwnedMetrics", fields: [ownerUserId], references: [id], onDelete: Cascade)
  values        MetricValue[]
  references    ReferenceRange[]

  @@index([category])
  @@index([ownerUserId])
  @@index([key])
}

/// Референсный диапазон для показателя.
/// Системный: userId = null, isSystem неявно.
/// Пользовательский override: userId = конкретный пользователь.
/// Выбор диапазона при отображении: сначала ищем user-specific для профиля,
/// затем системный по полу+возрасту.
model ReferenceRange {
  id         String   @id @default(cuid())
  metricId   String
  userId     String?           // null = системный
  sex        Sex?              // null = для обоих полов
  ageMin     Int?              // в годах; null = без нижней границы
  ageMax     Int?              // в годах; null = без верхней границы
  valueMin   Decimal  @db.Decimal(20, 6)
  valueMax   Decimal  @db.Decimal(20, 6)
  comment    String?
  createdAt  DateTime @default(now())
  updatedAt  DateTime @updatedAt

  metric     Metric   @relation(fields: [metricId], references: [id], onDelete: Cascade)
  user       User?    @relation("UserCustomRanges", fields: [userId], references: [id], onDelete: Cascade)

  @@index([metricId, userId])
  @@index([metricId, sex, ageMin, ageMax])
}

/// Замер — акт сдачи анализа в конкретную дату.
model Measurement {
  id         String   @id @default(cuid())
  userId     String
  takenAt    DateTime            // дата сдачи
  note       String?             // свободный текст до 5000 символов
  createdAt  DateTime @default(now())
  updatedAt  DateTime @updatedAt

  user        User          @relation(fields: [userId], references: [id], onDelete: Cascade)
  values      MetricValue[]
  attachments Attachment[]

  @@index([userId, takenAt])
}

/// Конкретное значение показателя в замере.
/// Value хранится в baseUnit показателя (при вводе в другой единице — конвертируем).
model MetricValue {
  id             String   @id @default(cuid())
  measurementId  String
  metricId       String
  value          Decimal  @db.Decimal(20, 6)
  unit           String             // единица, в которой введено (= baseUnit после конверсии)
  createdAt      DateTime @default(now())
  updatedAt      DateTime @updatedAt

  measurement    Measurement @relation(fields: [measurementId], references: [id], onDelete: Cascade)
  metric         Metric      @relation(fields: [metricId], references: [id], onDelete: Restrict)

  @@unique([measurementId, metricId])  // одно значение показателя на замер
  @@index([metricId])
}

/// Вложение — файл, прикреплённый к замеру.
model Attachment {
  id             String   @id @default(cuid())
  measurementId  String
  userId         String              // денормализация для быстрой проверки доступа
  filename       String              // оригинальное имя
  mimeType       String
  sizeBytes      Int
  sha256         String              // для дедупликации и целостности
  path           String              // относительный путь от STORAGE_ROOT
  createdAt      DateTime @default(now())

  measurement    Measurement @relation(fields: [measurementId], references: [id], onDelete: Cascade)
  user           User        @relation(fields: [userId], references: [id], onDelete: Cascade)

  @@index([measurementId])
  @@index([userId, sha256])  // для дедупликации на уровне пользователя
}
```

### 2.1. Отличия для SQLite vs PostgreSQL

Prisma в целом прозрачна, но:

- `String[]` (массивы) — не поддерживаются в SQLite. Для SQLite-dev используем `String` с JSON-кодировкой (через приложение) **или** отдельные join-таблицы. Рекомендация: **отдельные join-таблицы** для `Metric.synonyms` и `Metric.allowedUnits`. Это усложняет схему, но даёт полную совместимость.
- `Decimal(20, 6)` в SQLite реализован как REAL — теряется точность. Для медицинских значений с 2–3 знаками после запятой это приемлемо, но в prod (Postgres) точность сохраняется.
- `onDelete: Restrict` в SQLite требует включённых foreign keys (`PRAGMA foreign_keys = ON;`).

### 2.2. Join-таблицы для совместимости с SQLite

Вместо `synonyms String[]`:

```prisma
model MetricSynonym {
  id        String @id @default(cuid())
  metricId  String
  value     String

  metric    Metric @relation(fields: [metricId], references: [id], onDelete: Cascade)

  @@unique([metricId, value])
  @@index([value])
}

model MetricAllowedUnit {
  id        String @id @default(cuid())
  metricId  String
  unit      String
  // Коэффициент для конвертации в baseUnit: valueInBase = value * factor + offset
  factor    Decimal @db.Decimal(20, 10) @default(1)
  offset    Decimal @db.Decimal(20, 6)  @default(0)

  metric    Metric  @relation(fields: [metricId], references: [id], onDelete: Cascade)

  @@unique([metricId, unit])
}
```

Тогда в `Metric` убираем `synonyms` и `allowedUnits`:

```prisma
model Metric {
  // ... как выше, но без synonyms и allowedUnits
  metricSynonyms     MetricSynonym[]
  metricAllowedUnits MetricAllowedUnit[]
}
```

Это предпочтительный вариант — он также даёт возможность хранить коэффициенты конвертации единиц явно.

## 3. Инварианты и правила целостности

1. **E-mail уникален глобально**: `User.email` unique.
2. **Один профиль на пользователя**: `Profile.userId` unique.
3. **Одно значение показателя на замер**: `MetricValue @@unique([measurementId, metricId])`. Если пользователь сдал ОАК дважды за день — это два отдельных замера.
4. **Каскадное удаление**: при удалении пользователя удаляются профиль, сессии, замеры (и все их зависимости), пользовательские показатели и референсы.
5. **Restrict на Metric → MetricValue**: нельзя удалить показатель, если у него есть значения. Пользователь сначала должен удалить все значения.
6. **Системные показатели не редактируются пользователями**: `isSystem = true` → запрет на PUT/DELETE через API.
7. **Single owner rule для пользовательских показателей**: значения показателя с `ownerUserId = X` могут существовать только в замерах пользователя X.
8. **Значение хранится в baseUnit**: при вводе в другой единице API делает конверсию через `MetricAllowedUnit.factor/offset` перед сохранением.
9. **Референс для профиля выбирается по приоритету**:
   - 1-й приоритет: `ReferenceRange WHERE metricId = X AND userId = currentUser` (override).
   - 2-й приоритет: лучший подходящий системный (`userId = null AND sex matches AND ageMin ≤ age ≤ ageMax`).
   - Если ничего не найдено — показатель отображается без референсной полосы.
10. **Вложение принадлежит тому же пользователю, что и замер**: `Attachment.userId` должен совпадать с `Measurement.userId`. Проверяется в сервисе при создании.

## 4. Индексы

Критичные индексы (объявлены в схеме):

- `User.email` — для логина.
- `Session.userId`, `Session.expiresAt` — для middleware валидации и очистки просроченных.
- `Measurement[userId, takenAt]` — композитный, для списка замеров и запросов графика по периоду.
- `MetricValue.metricId` — для запроса всех значений одного показателя.
- `MetricValue @@unique([measurementId, metricId])` — уникальность + быстрый lookup.
- `Metric.key`, `Metric.category`, `Metric.ownerUserId` — поиск и фильтрация.
- `ReferenceRange[metricId, userId]` — поиск user-override.
- `ReferenceRange[metricId, sex, ageMin, ageMax]` — поиск системного референса.
- `Attachment.measurementId` — превью вложений в карточке замера.
- `Attachment[userId, sha256]` — дедупликация при загрузке.

## 5. Seed-каталог показателей

При первом старте api применяет `prisma/seed/metrics.ts`, который идемпотентно заливает системные показатели и их референсы. Ниже — каталог на ~45 показателей по 5 категориям.

Формат — TypeScript-литерал, но концептуально это CSV. Все референсы указаны по общепринятым клиническим рекомендациям РФ; пользователь может переопределить.

### 5.1. Категория: ОАК (общий анализ крови) — hematology

| key                   | name                           | baseUnit | ref female 18-60 | ref male 18-60 |
| --------------------- | ------------------------------ | -------- | ---------------- | -------------- |
| `hemoglobin`          | Гемоглобин (Hb)                | г/л      | 117–155          | 130–165        |
| `erythrocytes`        | Эритроциты                     | 10¹²/л   | 3.8–5.1          | 4.0–5.5        |
| `hematocrit`          | Гематокрит                     | %        | 35–45            | 39–49          |
| `mcv`                 | Средний объём эритроцита       | фл       | 80–100           | 80–100         |
| `mch`                 | Среднее содержание Hb в эр.    | пг       | 27–34            | 27–34          |
| `mchc`                | Средняя концентрация Hb        | г/л      | 320–360          | 320–360        |
| `rdw`                 | Распределение эритроцитов      | %        | 11.5–14.5        | 11.5–14.5      |
| `leukocytes`          | Лейкоциты                      | 10⁹/л    | 4.0–9.0          | 4.0–9.0        |
| `neutrophils_percent` | Нейтрофилы %                   | %        | 47–72            | 47–72          |
| `lymphocytes_percent` | Лимфоциты %                    | %        | 19–37            | 19–37          |
| `monocytes_percent`   | Моноциты %                     | %        | 3–11             | 3–11           |
| `eosinophils_percent` | Эозинофилы %                   | %        | 0.5–5            | 0.5–5          |
| `basophils_percent`   | Базофилы %                     | %        | 0–1              | 0–1            |
| `platelets`           | Тромбоциты                     | 10⁹/л    | 150–400          | 150–400        |
| `esr`                 | СОЭ                            | мм/ч     | 2–20             | 2–15           |

### 5.2. Категория: Биохимия — biochemistry

| key                        | name                        | baseUnit | ref female | ref male  |
| -------------------------- | --------------------------- | -------- | ---------- | --------- |
| `glucose`                  | Глюкоза                     | ммоль/л  | 3.9–5.6    | 3.9–5.6   |
| `total_protein`            | Общий белок                 | г/л      | 64–83      | 64–83     |
| `albumin`                  | Альбумин                    | г/л      | 35–52      | 35–52     |
| `urea`                     | Мочевина                    | ммоль/л  | 2.5–6.7    | 3.2–7.1   |
| `creatinine`               | Креатинин                   | мкмоль/л | 44–80      | 62–115    |
| `uric_acid`                | Мочевая кислота             | мкмоль/л | 150–350    | 200–420   |
| `total_bilirubin`          | Билирубин общий             | мкмоль/л | 3.4–20.5   | 3.4–20.5  |
| `direct_bilirubin`         | Билирубин прямой            | мкмоль/л | 0–5.1      | 0–5.1     |
| `alt`                      | АЛТ                         | Ед/л     | 0–35       | 0–45      |
| `ast`                      | АСТ                         | Ед/л     | 0–35       | 0–45      |
| `ggt`                      | ГГТ                         | Ед/л     | 0–32       | 0–55      |
| `alkaline_phosphatase`     | Щелочная фосфатаза          | Ед/л     | 40–150     | 40–150    |
| `amylase`                  | Амилаза                     | Ед/л     | 25–125     | 25–125    |
| `ck`                       | Креатинкиназа общая         | Ед/л     | 0–145      | 0–170     |
| `ldh`                      | Лактатдегидрогеназа         | Ед/л     | 135–214    | 135–214   |
| `sodium`                   | Натрий                      | ммоль/л  | 136–145    | 136–145   |
| `potassium`                | Калий                       | ммоль/л  | 3.5–5.1    | 3.5–5.1   |
| `chloride`                 | Хлор                        | ммоль/л  | 98–107     | 98–107    |
| `calcium_total`            | Кальций общий               | ммоль/л  | 2.15–2.55  | 2.15–2.55 |
| `calcium_ionized`          | Кальций ионизированный      | ммоль/л  | 1.12–1.32  | 1.12–1.32 |
| `magnesium`                | Магний                      | ммоль/л  | 0.66–1.07  | 0.66–1.07 |
| `phosphorus`               | Фосфор                      | ммоль/л  | 0.81–1.45  | 0.81–1.45 |
| `iron`                     | Железо сывороточное         | мкмоль/л | 9.0–30.4   | 11.6–31.3 |
| `ferritin`                 | Ферритин                    | нг/мл    | 10–120     | 30–400    |
| `transferrin`              | Трансферрин                 | г/л      | 2.5–3.8    | 2.0–3.6   |
| `c_reactive_protein`       | СРБ                         | мг/л     | 0–5        | 0–5       |

### 5.3. Категория: Липидный профиль — lipids

| key                         | name                        | baseUnit | ref female | ref male |
| --------------------------- | --------------------------- | -------- | ---------- | -------- |
| `total_cholesterol`         | Холестерин общий            | ммоль/л  | 3.0–5.2    | 3.0–5.2  |
| `hdl`                       | ЛПВП (HDL)                  | ммоль/л  | >1.2       | >1.0     |
| `ldl`                       | ЛПНП (LDL)                  | ммоль/л  | 1.7–3.5    | 1.7–3.5  |
| `triglycerides`             | Триглицериды                | ммоль/л  | 0.5–1.7    | 0.5–1.7  |
| `atherogenic_coefficient`   | Индекс атерогенности        | —        | <3         | <3       |

### 5.4. Категория: Гормоны — hormones

| key               | name                       | baseUnit | ref female | ref male  |
| ----------------- | -------------------------- | -------- | ---------- | --------- |
| `tsh`             | ТТГ                        | мкМЕ/мл  | 0.4–4.0    | 0.4–4.0   |
| `ft4`             | Тироксин свободный (fT4)   | пмоль/л  | 9.0–19.0   | 9.0–19.0  |
| `ft3`             | Трийодтиронин свободный    | пмоль/л  | 2.6–5.7    | 2.6–5.7   |
| `tpo_antibodies`  | АТ-ТПО                     | МЕ/мл    | 0–34       | 0–34      |
| `cortisol`        | Кортизол утренний          | нмоль/л  | 171–536    | 171–536   |
| `insulin`         | Инсулин                    | мкЕд/мл  | 2.6–24.9   | 2.6–24.9  |
| `prolactin`       | Пролактин                  | мЕд/л    | 102–496    | 86–324    |
| `testosterone`    | Тестостерон общий          | нмоль/л  | 0.3–2.5    | 8.6–29.0  |

### 5.5. Категория: Витамины и микроэлементы — vitamins

| key                  | name                  | baseUnit | ref (общий) |
| -------------------- | --------------------- | -------- | ----------- |
| `vitamin_d_25oh`     | Витамин D, 25(OH)     | нг/мл    | 30–100      |
| `vitamin_b12`        | Витамин B12           | пг/мл    | 191–663     |
| `folic_acid`         | Фолиевая кислота      | нг/мл    | 3.1–20.5    |
| `homocysteine`       | Гомоцистеин           | мкмоль/л | 4.4–13.6    |
| `hba1c`              | Гликированный Hb      | %        | 4.0–6.0     |

### 5.6. Пример записи seed-скрипта

```typescript
// prisma/seed/metrics.ts
import { PrismaClient } from '@prisma/client';
const prisma = new PrismaClient();

const metrics = [
  {
    key: 'hemoglobin',
    name: 'Гемоглобин',
    category: 'hematology',
    baseUnit: 'г/л',
    synonyms: ['HGB', 'Hb', 'Гемоглобин'],
    allowedUnits: [
      { unit: 'г/л', factor: 1, offset: 0 },
      { unit: 'г/дл', factor: 10, offset: 0 },
    ],
    references: [
      { sex: 'female', ageMin: 18, ageMax: 60, valueMin: 117, valueMax: 155 },
      { sex: 'male',   ageMin: 18, ageMax: 60, valueMin: 130, valueMax: 165 },
      // можно добавить диапазоны для других возрастных групп
    ],
  },
  // ... остальные
];

export async function seedMetrics() {
  for (const m of metrics) {
    await prisma.metric.upsert({
      where: { key: m.key },
      create: {
        key: m.key,
        name: m.name,
        category: m.category,
        baseUnit: m.baseUnit,
        isSystem: true,
        metricSynonyms: { create: m.synonyms.map(value => ({ value })) },
        metricAllowedUnits: { create: m.allowedUnits },
        references: { create: m.references },
      },
      update: {
        // обновляем только справочные поля, не трогая пользовательские данные
        name: m.name,
        category: m.category,
      },
    });
  }
}
```

## 6. Миграции

Prisma-миграции хранятся в `prisma/migrations/`. Правила:

1. Каждая миграция — отдельный коммит с описательным именем (`20260424_add_measurement_note_length`, а не `20260424_change`).
2. **Никогда не редактируем** применённые миграции; только новые.
3. Обратно-несовместимые изменения (drop column, rename) сопровождаются двухшаговой миграцией: сначала добавить новое, обновить код чтобы работал с обоими вариантами, после — удалить старое.
4. Seed применяется **после** миграций при каждом старте (идемпотентно через upsert).
5. В production миграции применяются через `prisma migrate deploy` (не `migrate dev`).

## 7. Работа с единицами

### 7.1. Конверсия при вводе

Пользователь вводит значение в некоторой единице. API:

1. Получает `{ metricId, value, unit }`.
2. Ищет в `MetricAllowedUnit` запись `[metricId, unit]`.
3. Если нет — 400 с сообщением «единица не поддерживается для этого показателя».
4. Конвертирует: `valueInBase = value * factor + offset`.
5. Сохраняет `MetricValue.value = valueInBase`, `unit = baseUnit`.

### 7.2. Конверсия при отображении

UI может показывать значения в baseUnit (по умолчанию) или в другой разрешённой единице (опция пользователя, будущее). В MVP всегда показываем baseUnit.

### 7.3. Примеры конверсий

| Показатель | From | To   | factor | offset |
| ---------- | ---- | ---- | ------ | ------ |
| Гемоглобин | г/дл | г/л  | 10     | 0      |
| Глюкоза    | мг/дл | ммоль/л | 0.0555 | 0  |
| Холестерин | мг/дл | ммоль/л | 0.0259 | 0  |

## 8. Запросы для типовых сценариев

### 8.1. Получить референс для показателя и профиля

```typescript
async function resolveReference(metricId: string, profile: { sex: Sex; age: number }, userId: string) {
  // 1. Пользовательский override
  const userOverride = await prisma.referenceRange.findFirst({
    where: { metricId, userId },
  });
  if (userOverride) return userOverride;

  // 2. Системный, подходящий по полу и возрасту
  return prisma.referenceRange.findFirst({
    where: {
      metricId,
      userId: null,
      OR: [{ sex: profile.sex }, { sex: null }],
      AND: [
        { OR: [{ ageMin: null }, { ageMin: { lte: profile.age } }] },
        { OR: [{ ageMax: null }, { ageMax: { gte: profile.age } }] },
      ],
    },
    orderBy: [
      { sex: 'desc' },     // с указанным полом приоритетнее null
      { ageMin: 'desc' },  // узкий диапазон приоритетнее широкого
    ],
  });
}
```

### 8.2. Получить точки для графика

```typescript
async function getChartPoints(userId: string, metricId: string, from: Date, to: Date) {
  return prisma.metricValue.findMany({
    where: {
      metricId,
      measurement: {
        userId,
        takenAt: { gte: from, lte: to },
      },
    },
    select: {
      id: true,
      value: true,
      unit: true,
      measurementId: true,
      measurement: { select: { takenAt: true } },
    },
    orderBy: { measurement: { takenAt: 'asc' } },
  });
}
```

### 8.3. Список замеров с превью значений

```typescript
async function listMeasurements(userId: string, page: number) {
  return prisma.measurement.findMany({
    where: { userId },
    include: {
      values: {
        take: 5,
        include: { metric: { select: { name: true } } },
      },
      _count: { select: { values: true, attachments: true } },
    },
    orderBy: { takenAt: 'desc' },
    skip: page * 50,
    take: 50,
  });
}
```

## 9. Объёмы и производительность

Оценка для типового пользователя после 5 лет использования:

- Замеров: ~50 (10 в год).
- Значений: ~500 (10 значений в среднем на замер).
- Вложений: ~100 (2 на замер).
- Размер БД: ~2–3 МБ без файлов.
- Размер `storage/`: ~200–500 МБ (в зависимости от размера PDF).

Для семьи из 4 человек: ~10 МБ БД, ~2 ГБ storage. Postgres и локальная ФС справляются без проблем.

## 10. Будущие изменения модели (v2+)

- **Tag** — теги и категории событий (US-эпик v2): `Tag { id, userId, name, color }` + `TagOnMeasurement`.
- **SymptomEntry** — журнал симптомов: `SymptomEntry { id, userId, takenAt, type, severity, note }`.
- **MedicationCourse** — курс лекарства: `MedicationCourse { id, userId, name, dosage, startedAt, endedAt, note }`.
- **SharedLink** — read-only ссылки для врача: `SharedLink { id, userId, token, expiresAt, scope }`.
- **AuditLog** — журнал изменений замеров (для «истории» редактирования).
- **Patient** — отдельный профиль подопечного (ребёнок, родственник): `Patient { id, ownerUserId, name, sex, birthDate }`. Тогда `Measurement.userId` заменится на `patientId`.

Эти изменения потребуют миграций, но не ломают MVP-модель — добавляются рядом.