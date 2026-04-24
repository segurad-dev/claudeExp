# 09. План коммитов

Документ описывает **план атомарных коммитов** для реализации MVP (v0.1) и последующих версий. Коммиты сгруппированы по спринтам из `07_ROADMAP.md`.

---

## Принципы

1. **Conventional Commits**: `<type>(<scope>): <subject>`
   * `type`: `feat`, `fix`, `chore`, `refactor`, `test`, `docs`, `ci`, `perf`, `a11y`, `style`, `build`, `release`
   * `scope`: `web`, `api`, `db`, `shared`, `infra`, `ops` (или опущен для кросс-репо изменений)
   * `subject`: короткая формулировка в повелительном наклонении, строчными буквами

2. **Маленькие коммиты**:
   * один логический шаг = один коммит;
   * целевой размер: **30–200 строк diff**;
   * каждый коммит оставляет репозиторий в компилируемом состоянии;
   * **не смешивать** миграции БД + логику + UI в один коммит.

3. **Порядок**: сначала `db` (схема/миграция) → `shared` (типы/zod) → `api` (эндпоинт) → `web` (клиент + UI) → `test` → `docs`.

4. **Ветки**: Git Flow lite — `main` (stable) + фича-ветки `feat/<short>`, `fix/<short>`, PR в `main` через squash или rebase (на ваше усмотрение; при rebase план коммитов ниже сохраняется 1-в-1).

5. **Релизы**: помечаются тегами `v0.1.0`, `v0.1.1`, `v1.0.0` и отдельным коммитом `release: v0.1.0` с апдейтом `CHANGELOG.md`.

6. **Проверки работоспособности** (см. `11_VERIFICATION.md`) встроены в план:
   * husky pre-commit / pre-push + GitHub Actions CI настраиваются пачкой коммитов в Milestone 0 — до первой продуктовой работы;
   * каждая веха завершается коммитом `docs(checklist): milestone-N …` с ручным smoke-листом;
   * на Milestone 7 добавляются «тяжёлые» CI-джобы (Playwright e2e, bundle size, security audit).

---

## Milestone 0 — Setup (≈ 1 день)

Задача: монорепо и инструменты до старта продуктовой работы.

```
chore: init git repo with .gitignore and .gitattributes
chore: add LICENSE (MIT) and top-level README placeholder
chore: add .editorconfig and .nvmrc
chore: init pnpm workspace (pnpm-workspace.yaml, package.json)
chore: add prettier config at root
chore: add eslint base config and shared ruleset
chore: add tsconfig.base.json
chore: setup husky and lint-staged
chore: add pre-commit hook — prettier + eslint on staged files
chore: add pre-commit hook — typecheck changed workspaces
chore: add pre-push hook — full typecheck and unit tests
chore: add commit-msg hook with commitlint (conventional commits)
ci: github actions — skeleton workflow (on push + pr, with pnpm setup)
ci: github actions — lint job
ci: github actions — typecheck job
ci: github actions — test:api job with sqlite fixture
ci: github actions — test:web job (vitest + jsdom)
ci: github actions — build job (web + api production builds)
ci: github actions — migrate:check job (fresh db + all migrations)
ci: github actions — docker-build job (verifies Dockerfiles)
ci: cache pnpm store between runs
docs: add CI status badge to README
docs: copy design docs (00–11) into /docs
chore(web): scaffold vite + react + ts app in apps/web
chore(web): add tailwind + postcss config
chore(web): init shadcn/ui and add base components
chore(web): setup react-router v6 with empty routes
chore(web): add path aliases (@/*)
chore(api): scaffold fastify + ts app in apps/api
chore(api): add fastify plugins — sensible, helmet, cookie, cors
chore(api): add zod and fastify-type-provider-zod
chore(api): add dotenv-safe and .env.example
chore(api): init prisma with sqlite provider
chore(shared): create packages/shared for DTOs and zod schemas
chore(shared): export common error types and result helpers
chore(infra): add docker-compose.dev.yml (api + web)
chore(infra): add Dockerfile for api (multi-stage)
chore(infra): add Dockerfile for web (nginx-based)
docs: add CONTRIBUTING.md with commit conventions
docs(checklist): milestone-0 setup verification
```

**≈ 40 коммитов**

Контрольный чек-лист Milestone 0 (файл `docs/checklists/milestone-0.md`) проверяет: `pnpm install && pnpm dev` поднимает оба приложения; `git commit` с нарушающим сообщением отклонён husky; пустой push попадает в CI и все джобы зелёные; CI status badge в README отображается.

---

## Milestone 1 — Auth (Sprint 1, ≈ 2–3 дня)

```
feat(db): add User and Session models to prisma schema
feat(db): create migration 0001_init with users and sessions
feat(shared): add auth dto — RegisterInput, LoginInput, UserPublic
feat(api): add password hashing utility (bcrypt wrapper)
feat(api): add session store backed by prisma
feat(api): add cookie plugin config and session cookie helper
feat(api): add auth middleware — resolve user from sessionId cookie
feat(api): POST /auth/register — validate, hash, create user
feat(api): POST /auth/login — verify password, create session, set cookie
feat(api): POST /auth/logout — invalidate session and clear cookie
feat(api): GET /auth/me — return current user or 401
feat(api): add CSRF token issuance on login
feat(api): add CSRF verify hook for mutating routes
feat(api): add rate limit on /auth/login (fastify-rate-limit)
test(api): auth endpoints — register flow
test(api): auth endpoints — login + me + logout flow
test(api): auth endpoints — csrf rejection
feat(shared): add openapi-fetch client factory
feat(web): add api client with credentials and csrf header
feat(web): add auth store (zustand) with current user
feat(web): add useAuth hook
feat(web): add RequireAuth route wrapper
feat(web): login page — form, validation, submit
feat(web): register page — form, validation, submit
feat(web): logout action in header menu
feat(web): redirect to login on 401
feat(web): remember last route and redirect after login
docs(api): document auth endpoints in openapi
ci: github actions — coverage report comment on pr
docs(checklist): milestone-1 auth manual checks
```

**≈ 30 коммитов**

Чек-лист (`docs/checklists/milestone-1.md`): регистрация → вход → F5 → всё ещё залогинен → logout → попытка открыть защищённый роут → редирект на /login → 6 неверных паролей подряд → rate-limit срабатывает → проверка флагов cookie в DevTools.

---

## Milestone 2 — Profile & Metrics Catalog (Sprint 2, ≈ 3 дня)

```
feat(db): add Profile model and Sex enum
feat(db): migration 0002_profile
feat(shared): add Profile dto and zod schema
feat(api): GET /profile — return current user profile
feat(api): PUT /profile — update name, dob, sex
test(api): profile endpoints — get/update
feat(web): profile page — read-only view
feat(web): profile page — edit form with validation
feat(web): onboarding redirect when profile incomplete

feat(db): add Metric, MetricSynonym, MetricAllowedUnit models
feat(db): add ReferenceRange model
feat(db): migration 0003_metrics
feat(shared): add Metric dto and filter schema
feat(api): seed utility — loader and idempotency check
feat(api): seed catalog — hematology block (CBC, WBC, RBC...)
feat(api): seed catalog — biochemistry block (ALT, AST, creatinine...)
feat(api): seed catalog — lipids block (TC, LDL, HDL, TG)
feat(api): seed catalog — hormones block (TSH, T4, T3, cortisol...)
feat(api): seed catalog — vitamins block (D, B12, folate, ferritin)
feat(api): add reference ranges — sex-stratified for hormones and CBC
feat(api): add reference ranges — age-stratified for children metrics
feat(api): GET /metrics — list with search and pagination
feat(api): GET /metrics/:id — single with ranges
feat(api): POST /metrics — user custom metric
feat(api): PUT /metrics/:id — override reference for user
feat(api): DELETE /metrics/:id — user-owned only
test(api): metrics endpoints — list/get
test(api): metrics endpoints — create/update custom
feat(web): metrics catalog page — list with search
feat(web): metric detail — ranges, synonyms, units
feat(web): create custom metric dialog
feat(web): override reference range dialog
docs(checklist): milestone-2 profile and catalog manual checks
```

**≈ 34 коммита**

Чек-лист: онбординг при пустом профиле → редактирование профиля → сид каталога содержит ≥ 45 метрик → поиск «гемоглобин» находит по RU/EN/синониму → детали метрики показывают референс с половой стратификацией → создание кастомной метрики → override reference range сохраняется и не затирается при повторном сиде.

---

## Milestone 3 — Measurements CRUD (Sprint 3, ≈ 3–4 дня)

```
feat(db): add Measurement and MetricValue models
feat(db): migration 0004_measurements
feat(shared): add Measurement dto with nested values
feat(shared): add zod schema with unit enum per metric
feat(api): unit conversion utility (mg/dL <-> mmol/L etc)
feat(api): POST /measurements — create with values and notes
feat(api): GET /measurements — list with date filter + pagination
feat(api): GET /measurements/:id — full detail
feat(api): PUT /measurements/:id — replace values
feat(api): DELETE /measurements/:id — cascade to values
test(api): measurements — create + list
test(api): measurements — update + delete
test(api): unit conversion — edge cases

feat(web): measurement form skeleton (date, notes)
feat(web): MetricSearchSelect component
feat(web): value input with unit dropdown
feat(web): add-row button and dynamic rows
feat(web): submit new measurement
feat(web): measurements list page
feat(web): date group headers in list
feat(web): measurement detail page
feat(web): edit measurement page (reuse form)
feat(web): delete measurement with confirm modal
feat(web): empty state for no measurements
feat(web): optimistic update on create
docs(checklist): milestone-3 measurements manual checks
```

**≈ 27 коммитов**

Чек-лист: создать → увидеть в списке → детали → редактировать → удалить; дата в будущем отклонена; отрицательное значение отклонено; форма удобна на мобильном; пустая единица — форма не отправляется; после create dashboard/список обновились.

---

## Milestone 4 — Attachments (Sprint 4, ≈ 2 дня)

```
feat(db): add Attachment model
feat(db): migration 0005_attachments
feat(api): StorageProvider interface in shared
feat(api): LocalFsStorage implementation
feat(api): mime whitelist and size limit config
feat(api): POST /measurements/:id/attachments — multipart upload
feat(api): GET /attachments/:id — stream file with access check
feat(api): DELETE /attachments/:id
test(api): attachments — upload + retrieve + delete
test(api): attachments — reject oversize and bad mime
feat(web): file picker component
feat(web): camera capture input for mobile
feat(web): upload progress indicator
feat(web): thumbnails gallery on measurement detail
feat(web): lightbox for image preview
feat(web): delete attachment action
docs(checklist): milestone-4 attachments manual checks
```

**≈ 17 коммитов**

Чек-лист: прикрепить фото (мобильная камера + file picker) → миниатюра появилась → lightbox открывается по клику → оверсайз файл отклонён с понятным сообщением → PDF отображается как вложение → удаление файла удаляет и его физический файл → попытка открыть чужой attachment → 403.

---

## Milestone 5 — Chart & Analytics (Sprint 5, ≈ 3–4 дня)

```
feat(api): reference range resolver — pick by sex/age at date
feat(api): GET /analytics/chart/:metricId — time series + ranges
test(api): chart endpoint — range overlap and normalization
feat(shared): AnalyteSeries and AnalyteChartProps types

feat(web): AnalyteChart facade component — props interface
feat(web): Recharts implementation behind facade
feat(web): reference band overlay (rectangle between min/max)
feat(web): out-of-range point markers (color-coded)
feat(web): axis formatting — dates + values
feat(web): tooltip with value, unit, status
feat(web): single-metric chart page — route and loading states
feat(web): date timeline strip under chart
feat(web): point click — navigate to measurement detail
feat(web): value status indicator component

feat(api): GET /analytics/chart — multi-metric normalized response
feat(web): multi-metric overlay mode — percent-of-reference-mid
feat(web): unified 80–120% reference band
feat(web): legend with show/hide per series
feat(web): metric picker for overlay (multi-select)
test(web): AnalyteChart renders with stubbed data
docs(checklist): milestone-5 chart manual checks
```

**≈ 19 коммитов**

Чек-лист: single-metric chart рисуется для метрики с ≥ 2 значениями; референсная полоса отображается; точки outside нормы выделены; клик по точке → переход на измерение; overlay для 3 метрик с нормализацией; легенда скрывает/показывает серии; тултип содержит значение, единицу, дату, статус.

---

## Milestone 6 — Export, Import, Dashboard (Sprint 6, ≈ 2 дня)

```
feat(api): GET /export/json — full user dump
feat(api): GET /export/csv — flattened rows
feat(api): POST /import — round-trip from export
test(api): export/import — round-trip equality
feat(web): export page — format picker + download
feat(web): import page — upload + dry-run preview
feat(web): home/dashboard — latest value per pinned metric
feat(web): dashboard — quick-action buttons (new measurement, ...)
feat(web): dashboard — recent activity list
feat(web): pin/unpin metrics on dashboard
docs(checklist): milestone-6 export and dashboard manual checks
```

**≈ 11 коммитов**

Чек-лист: export JSON → import в пустой аккаунт → содержимое идентично оригиналу; CSV открывается в Excel/LibreOffice без поломанной кодировки; dashboard рендерится < 500 мс; pin/unpin метрики сохраняется между сессиями.

---

## Milestone 7 — Polish, PWA, Release (Sprint 7, ≈ 3 дня)

```
feat(web): PWA manifest and icons
feat(web): service worker with workbox — app-shell cache
feat(web): install prompt on supported browsers
feat(web): dark mode theme + toggle
feat(web): persist theme preference in profile
feat(web): empty states for all main screens
feat(web): global error boundary with retry
feat(web): toast notifications (success/error)
a11y: focus trap in dialogs
a11y: aria-labels and roles on form controls
a11y: color contrast audit fixes
perf(web): route-level code splitting
perf(web): image lazy-loading
test(web): measurement create flow e2e
test(web): chart rendering smoke test
ci: github actions — playwright e2e smoke job
ci: github actions — bundle size check vs main
ci: github actions — security audit (pnpm audit + trivy on docker image)

chore(infra): docker-compose.prod.yml with caddy
chore(infra): Caddyfile with auto https
chore(ops): backup.sh — sqlite + attachments tarball
chore(ops): restore.sh counterpart
docs(ops): deployment guide additions
docs: user manual (RU) in /docs/USER_GUIDE.md
docs(checklist): milestone-7 pre-release manual checks
release: bump versions to v0.1.0
release: CHANGELOG.md for v0.1.0
release: tag v0.1.0
```

**≈ 27 коммитов**

Чек-лист перед релизом: PWA устанавливается на iPhone и открывается offline; dark mode переключается и палитра графика читается; все empty states корректны; error boundary ловит ошибку и показывает retry; прогон всего регрессионного листа (M1–M6); `backup.sh` создаёт архив, `restore.sh` разворачивает в чистом контейнере.

---

## Итоги v0.1 (MVP)

| Milestone | Коммитов |
|---|---|
| 0 Setup | 40 |
| 1 Auth | 30 |
| 2 Profile & Metrics | 34 |
| 3 Measurements | 27 |
| 4 Attachments | 17 |
| 5 Chart & Analytics | 19 |
| 6 Export & Dashboard | 11 |
| 7 Polish & Release | 27 |
| **Всего** | **≈ 205** |

При темпе 8–12 коммитов в рабочий день → **≈ 20–25 рабочих дней**. Небольшое увеличение относительно `07_ROADMAP.md` (18–22 дня) — за счёт тщательной настройки CI и husky-хуков в Milestone 0 и чек-листов в конце каждой вехи. Эти инвестиции возвращаются экономией на отладке.

---

## v1.0 — Stabilization (≈ 30–40 коммитов)

```
test(api): coverage for all crud paths to > 80%
test(web): critical user flows with playwright
perf(api): query plan review + missing indexes
perf(web): chart render optimization for > 100 points
fix: follow-up fixes from dogfooding (individual issue commits)
chore(ci): add playwright job
chore(ci): add codecov integration
chore(ops): healthcheck endpoint + docker healthcheck
chore(ops): log rotation config
docs(ops): runbook — incident scenarios
release: v1.0.0
```

(+ ≈ 20–30 индивидуальных fix-коммитов по результатам dogfooding, каждый со своим issue.)

---

## v1.1 — Quality of Life

```
feat(web): keyboard shortcuts on measurement form
feat(web): bulk delete measurements
feat(web): print-friendly measurement detail
feat(api): GET /analytics/summary — aggregates by period
feat(web): summary page with sparklines
feat(web): locale-aware date picker
feat(web): import lab PDF as attachment (no OCR yet)
refactor(web): extract chart into @/features/chart
release: v1.1.0
```

**≈ 10–15 коммитов**

---

## v2.0 — OCR, Symptoms, Medications, Tags, Multi-patient

Крупная фаза, выделите отдельный план. Ориентир:

```
feat(db): migration — add Tag, Symptom, Medication, Patient models
feat(api): tags crud
feat(web): tag picker on measurement
feat(api): symptoms crud
feat(web): symptoms diary screen
feat(api): medications crud + schedule
feat(web): medications screen
feat(api): ocr service integration (tesseract or external)
feat(api): pdf-to-measurement extraction pipeline
feat(web): OCR review/confirm screen
feat(db): migration — add Patient model and scope data by patient
feat(api): patient switcher
feat(web): patient switcher UI
feat(web): overlay chart — correlate metric vs symptom frequency
release: v2.0.0
```

**≈ 60–80 коммитов** (детализируется ближе к спринту).

---

## v3.0 — Sharing, Native, Lab API

```
feat(api): read-only share links with expiry
feat(web): share dialog + public view
feat(api): lab api integrations (provider adapter pattern)
chore(mobile): capacitor wrapper for ios/android
release: v3.0.0
```

**≈ 30–50 коммитов.**

---

## Шаблоны сообщений

**Feature:**
```
feat(web): add metric search select component

Combobox с поиском по name/synonym, возврат metricId.
Используется в форме нового измерения.

Closes #42
```

**Fix:**
```
fix(api): handle null dob when resolving age at measurement date

Раньше падал в зрелый блок. Теперь возвращаем adult-range как fallback.

Fixes #57
```

**Refactor:**
```
refactor(web): extract AnalyteChart facade from measurement-detail

Подготовка к multi-metric overlay (US-14).
Публичное API не меняется.
```

**Release:**
```
release: v0.1.0

- auth (session cookies)
- metrics catalog seed
- measurements crud + attachments
- single- and multi-metric chart
- export json/csv
- pwa + dark mode

See CHANGELOG.md for full list.
```

---

## Как пользоваться планом

1. Создайте issue на каждый коммит (или на группу 2–3 связанных) — трекайте прогресс в GitHub Projects/Linear.
2. Перед началом спринта **ревизируйте** список: что-то можно объединить, что-то разбить дальше.
3. Не бойтесь добавлять `chore: wip` коммиты при разработке — перед PR делайте `git rebase -i` и формируйте чистую историю по этому плану.
4. Если коммит получился > 300 строк — остановитесь, скорее всего его можно разрезать.