# 08. Эксплуатация

Документ описывает операционные процедуры HealthTracker: развёртывание, обновление, бэкапы, восстановление, мониторинг, решение типовых проблем.

Аудитория — администратор (оператор), который развернул инсталляцию на своей машине или VPS.

## 1. Системные требования

### 1.1. Минимальные

- CPU: 1 vCPU.
- RAM: 1 ГБ.
- Disk: 10 ГБ (БД + файлы для семьи из 4 человек на 5 лет).
- OS: любой Linux с поддержкой Docker 24+ (Ubuntu 22.04, Debian 12, Fedora 38+).
- Docker ≥ 24, Docker Compose ≥ 2.20.

### 1.2. Рекомендованные

- CPU: 2 vCPU.
- RAM: 2 ГБ.
- Disk: 20 ГБ SSD.
- Внешний домен с A/AAAA-записью на сервер (для HTTPS).
- Регулярные бэкапы диска на уровне провайдера.

## 2. Первичная установка

### 2.1. Клонирование репозитория

```bash
git clone https://github.com/yourname/healthtracker.git
cd healthtracker
```

### 2.2. Настройка .env

Скопировать шаблон и отредактировать:

```bash
cp .env.example .env
$EDITOR .env
```

Ключевые переменные:

```env
# Домен. Для production — ваш реальный домен.
# Для локальной разработки — localhost.
DOMAIN=health.example.com

# Postgres
POSTGRES_USER=healthtracker
POSTGRES_PASSWORD=<сгенерируйте случайный, 32+ символа>
POSTGRES_DB=healthtracker

# Сессии — случайная строка минимум 32 символа
SESSION_SECRET=<openssl rand -hex 32>

# Лимиты
STORAGE_MAX_FILE_MB=10
STORAGE_MAX_USER_GB=1

# Функциональные флаги
FEATURE_REGISTRATION_OPEN=true
FEATURE_BACKUP_CRON=true
BACKUP_RETENTION_DAYS=14

# Наблюдаемость
LOG_LEVEL=info
```

Генерация секретов:

```bash
echo "SESSION_SECRET=$(openssl rand -hex 32)" >> .env
echo "POSTGRES_PASSWORD=$(openssl rand -base64 32)" >> .env
```

### 2.3. Запуск

```bash
docker compose up -d
```

При первом запуске:
1. Собираются образы (~2–3 минуты).
2. PostgreSQL создаёт БД.
3. api применяет миграции и заливает seed-каталог.
4. Caddy запрашивает сертификат Let's Encrypt (если DOMAIN резолвится в сервер).

Проверка готовности:

```bash
# Статус контейнеров
docker compose ps

# Логи api
docker compose logs -f api

# Healthcheck
curl https://$DOMAIN/api/v1/healthz
# {"status":"ok","version":"0.1.0"}
```

### 2.4. Первая регистрация

Открыть `https://$DOMAIN` в браузере, зарегистрироваться. Готово.

### 2.5. Закрытие регистрации

Если сервер только для вас и семьи — закройте публичную регистрацию после того, как все зарегистрировались:

```env
FEATURE_REGISTRATION_OPEN=false
```

```bash
docker compose up -d  # применяет новый env
```

Теперь `/register` возвращает 403.

## 3. Локальная разработка без Docker

Альтернатива, если вы разработчик и Docker не нужен:

```bash
# Установить зависимости
pnpm install

# Создать dev .env
cp .env.example .env.development
# В .env.development:
# DATABASE_PROVIDER=sqlite
# DATABASE_URL=file:./prisma/dev.db

# Миграции + seed
pnpm --filter api prisma migrate dev

# Запуск api и web параллельно
pnpm dev
```

- api на `http://localhost:3000`
- web на `http://localhost:5173`

## 4. Обновление версии

### 4.1. Обычное обновление (minor)

```bash
cd healthtracker
git pull
docker compose pull
docker compose up -d --build
```

Миграции применяются автоматически при старте api. В логах будет:

```
[api] Prisma schema loaded
[api] Running migrations…
[api] Applied X migrations
[api] Seed check: up-to-date
[api] Ready on :3000
```

### 4.2. Обновление с breaking changes

Если в `CHANGELOG.md` указано «breaking changes» — перед обновлением обязательно:

```bash
# 1. Сделать бэкап
docker compose exec api pnpm backup:create

# 2. Прочитать раздел миграции в CHANGELOG

# 3. Обновиться
git pull
docker compose up -d --build

# 4. Проверить логи на ошибки миграций
docker compose logs api --tail 100
```

### 4.3. Откат

Если что-то пошло не так:

```bash
# Вернуться к предыдущему тегу
git checkout v0.1.0
docker compose up -d --build

# Если была не-обратно-совместимая миграция — восстановить БД из бэкапа
docker compose exec api pnpm backup:restore ./backups/backup-YYYY-MM-DD-HHMM.tar.gz --yes
```

## 5. Бэкапы

### 5.1. Автоматические

Если `FEATURE_BACKUP_CRON=true`, внутри контейнера api работает cron, делающий ежедневный бэкап в 03:00 по UTC. Файлы сохраняются в volume `backups`.

Формат имени: `backup-YYYY-MM-DD-0300.tar.gz`.

Содержимое:
- `db.sql` — `pg_dump` БД.
- `storage/` — копия всех пользовательских файлов.
- `meta.json` — версия приложения, дата, размеры.

Ротация: `BACKUP_RETENTION_DAYS` (по умолчанию 14). Старые файлы удаляются автоматически.

### 5.2. Ручной бэкап

```bash
docker compose exec api pnpm backup:create
```

Файл появляется в `backups/`. Время — UTC текущего момента.

### 5.3. Выгрузка бэкапа наружу

Volume `backups` находится в Docker. Скопировать файл на хост:

```bash
# Список
docker compose exec api ls /backups/

# Копирование
docker cp healthtracker-api-1:/backups/backup-2026-04-24-0300.tar.gz ./local/
```

Ещё надёжнее — монтировать `./backups` как bind-mount в `docker-compose.yml`:

```yaml
volumes:
  - ./backups:/backups
```

Тогда файлы сразу на хосте, можно забирать через rsync/scp куда нужно.

### 5.4. Off-site бэкапы

**Обязательно** делайте копии бэкапов вне основного сервера. Пример с rclone:

```bash
# Настроить rclone remote (Backblaze B2, S3, etc.) — один раз
rclone config

# Cron на хосте: ежедневно в 04:00 синхронизировать
0 4 * * * rclone sync /path/to/backups healthtracker-backups:backups --max-age 30d
```

### 5.5. Шифрование бэкапов

Чувствительные медицинские данные — бэкапы должны храниться зашифрованными. Вариант с age:

```bash
# Генерация ключа (один раз)
age-keygen -o key.txt

# Шифрование при создании
tar czf - db.sql storage/ | age -r <public_key> > backup-encrypted.age

# Дешифрование при восстановлении
age -d -i key.txt backup-encrypted.age | tar xzf -
```

Ключ храните отдельно от бэкапов (например, в менеджере паролей).

## 6. Восстановление

### 6.1. Из автоматического бэкапа

```bash
# Выбрать нужный файл
docker compose exec api ls /backups/

# Восстановить (скрипт интерактивно просит подтверждение)
docker compose exec api pnpm backup:restore /backups/backup-2026-04-24-0300.tar.gz

# Для автоматизации (без подтверждения)
docker compose exec api pnpm backup:restore /backups/backup-2026-04-24-0300.tar.gz --yes
```

Скрипт:
1. Останавливает обработку новых запросов (api отвечает 503 readyz).
2. Дропает текущую БД, применяет `db.sql`.
3. Удаляет текущий `storage/`, копирует из бэкапа.
4. Применяет миграции поверх (если бэкап старой версии — структура приведётся к текущей).
5. Возвращается в рабочий режим.

### 6.2. Из ручного ZIP (экспорта пользователя)

Если пользователь сделал `/export/backup` и хочет восстановить данные в пустой аккаунт на другой инсталляции:

```bash
docker compose exec api pnpm export:import <user-backup.zip>
# скрипт запросит email нового пользователя
```

Эта функциональность — в v1.1+, не в MVP.

### 6.3. Сценарий DR (Disaster Recovery)

Если сервер полностью утрачен:

1. Поднять новый сервер (чистый Linux).
2. Установить Docker + Compose.
3. `git clone` того же репозитория на ту же версию (`git checkout v1.0.0`).
4. Скопировать `.env` с сохранённого бэкапа конфига (или восстановить).
5. `docker compose up -d` — поднимется пустой кластер.
6. Остановить api: `docker compose stop api`.
7. Скопировать последний бэкап в `./backups/`.
8. Запустить restore: `docker compose exec api pnpm backup:restore /backups/... --yes`.
9. Убедиться, что DNS нового сервера совпадает с DOMAIN (или обновить DNS).
10. `docker compose start api`, дождаться сертификата.

Ожидаемый RTO (recovery time objective): 30–60 минут.
RPO (recovery point objective): до 24 часов (интервал автобэкапа).

## 7. Мониторинг

### 7.1. Healthcheck

- `GET /api/v1/healthz` — жив ли api.
- `GET /api/v1/readyz` — готов ли (миграции, БД).

В Docker Compose прописаны HEALTHCHECK-инструкции; `docker compose ps` показывает статус.

### 7.2. Внешний мониторинг

Рекомендуется использовать бесплатный uptime-сервис (UptimeRobot, BetterUptime) с пингом на `/api/v1/healthz` каждые 5 минут. Алерт — в Telegram / e-mail.

### 7.3. Логи

Все контейнеры пишут в stdout. Просмотр:

```bash
# Последние 100 строк api
docker compose logs api --tail 100

# Реалтайм всех
docker compose logs -f

# Только ошибки api
docker compose logs api | grep -i error
```

Если инсталляция работает долго и логи разрастаются — настройте ротацию на уровне Docker:

```yaml
services:
  api:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "5"
```

### 7.4. Ключевые метрики для наблюдения

- **Размер БД**: `docker compose exec db psql -U healthtracker -d healthtracker -c "SELECT pg_size_pretty(pg_database_size('healthtracker'));"`.
- **Размер storage**: `du -sh /var/lib/docker/volumes/healthtracker_storage/_data`.
- **Число сессий**: `SELECT COUNT(*) FROM "Session";`.
- **Число просроченных сессий** (должно быть мало, они чистятся): `SELECT COUNT(*) FROM "Session" WHERE "expiresAt" < NOW();`.

## 8. Регулярное обслуживание

### 8.1. Еженедельно

- Проверить, что ежедневные бэкапы создаются (`ls -lt backups/`).
- Посмотреть логи на ERROR: `docker compose logs --since 7d | grep ERROR`.
- Проверить обновления: `git fetch && git log HEAD..origin/main --oneline`.

### 8.2. Ежемесячно

- Обновить образ: `docker compose pull && docker compose up -d`.
- Проверить заполнение диска: `df -h`.
- Выполнить восстановление из бэкапа в тестовое окружение — проверить, что процедура работает.
- `docker system prune` — очистить старые образы.

### 8.3. Ежеквартально

- Ротация SESSION_SECRET: поменять в .env, перезапустить api. Все сессии инвалидируются, пользователи перелогинятся.
- Ротация POSTGRES_PASSWORD: сложнее, требует синхронизированной смены в БД и в env. Процедура — в отдельной инструкции.
- Проверка уязвимостей: `pnpm audit`, `docker scout cves`.

## 9. Troubleshooting

### 9.1. api не стартует

Симптом: `docker compose ps` показывает api в `unhealthy` или `restarting`.

Диагностика:
```bash
docker compose logs api --tail 200
```

Частые причины:
- **«Cannot connect to database»** → проверить, что db-контейнер здоров: `docker compose logs db`. Возможно, БД не успела подняться — подождать 30 секунд.
- **«Prisma migration failed»** → посмотреть конкретную ошибку. Если схема расходится с состоянием БД — откатить на предыдущую версию и разбираться.
- **«SESSION_SECRET must be at least 32 chars»** → увеличить длину в `.env`.

### 9.2. Нет HTTPS (Caddy)

Симптом: по https://domain недоступно, по http:// работает (или нет).

Диагностика:
```bash
docker compose logs caddy
```

Частые причины:
- **DNS не настроен** → проверить: `dig $DOMAIN`. Должен резолвиться в IP сервера.
- **Firewall блокирует 443** → открыть: `ufw allow 443/tcp`.
- **Let's Encrypt rate limit** → если пробовали много раз — подождите час.
- **Staging-сертификат** → если в Caddyfile `acme_staging` — сертификат не доверяется; убрать для prod.

### 9.3. Медленные запросы

Симптом: страницы грузятся > 3 секунд.

Диагностика:
- Проверить ресурсы: `docker stats`.
- Проверить медленные запросы в Postgres: включить `log_min_duration_statement = 500` в postgresql.conf.
- Проверить индексы: использовать `EXPLAIN ANALYZE` на медленных запросах.

Типовые решения:
- Увеличить ресурсы контейнера api.
- Добавить недостающий индекс (в миграции).
- Уменьшить объём данных в списке (уменьшить pageSize).

### 9.4. Ошибки загрузки файлов

Симптом: 413, 415 или 500 при upload.

Диагностика:
- 413 → файл больше `STORAGE_MAX_FILE_MB`. Увеличить лимит или уменьшить файл.
- 415 → тип файла не в whitelist. Проверить реальный MIME: `file --mime-type photo.jpg`.
- 500 → посмотреть логи. Часто это права на запись в `storage/`.

Права на storage:

```bash
docker compose exec api ls -la /app/storage
# Должно быть владельцем node:node
```

Если нет — исправить в Dockerfile или через init-скрипт.

### 9.5. Забыли пароль

В MVP нет восстановления пароля (это v1.1). Временное решение — ручная смена через БД:

```bash
docker compose exec api pnpm admin:reset-password <email>
# интерактивно спросит новый пароль, прохеширует bcrypt и обновит запись
```

Скрипт нужно реализовать как часть v0.1.

## 10. Безопасность — чек-лист оператора

При развёртывании на VPS пройдитесь по списку:

- [ ] OS обновлена: `apt update && apt upgrade`.
- [ ] SSH только по ключу, root-логин отключён.
- [ ] Firewall: открыты только 22, 80, 443.
- [ ] Docker daemon не запущен от root для продакшн-приложений (rootless или dedicated user).
- [ ] Диск зашифрован (LUKS или эквивалент).
- [ ] `.env` с правами 600, не в git.
- [ ] SESSION_SECRET ≥ 32 случайных символа.
- [ ] POSTGRES_PASSWORD ≥ 24 случайных символа.
- [ ] Бэкапы настроены и работают (проверено восстановлением в тест).
- [ ] Бэкапы синхронизируются off-site и зашифрованы.
- [ ] Внешний uptime-мониторинг настроен.
- [ ] Fail2ban на SSH.
- [ ] DNS CAA запись, ограничивающая выпуск сертификатов Let's Encrypt и вашим провайдером.
- [ ] Настроена ротация SESSION_SECRET (раз в квартал).

## 11. Конфигурация Docker Compose (справочник)

Пример `docker-compose.yml`:

```yaml
version: "3.9"

services:
  caddy:
    image: caddy:2-alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./docker/Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
      - caddy_config:/config
    environment:
      DOMAIN: ${DOMAIN}
    depends_on: [web, api]
    restart: unless-stopped

  web:
    build:
      context: .
      dockerfile: apps/web/Dockerfile
    restart: unless-stopped
    depends_on: [api]

  api:
    build:
      context: .
      dockerfile: apps/api/Dockerfile
    environment:
      NODE_ENV: production
      PORT: 3000
      DATABASE_PROVIDER: postgresql
      DATABASE_URL: postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}
      SESSION_SECRET: ${SESSION_SECRET}
      STORAGE_ROOT: /app/storage
      STORAGE_MAX_FILE_MB: ${STORAGE_MAX_FILE_MB:-10}
      STORAGE_MAX_USER_GB: ${STORAGE_MAX_USER_GB:-1}
      FEATURE_REGISTRATION_OPEN: ${FEATURE_REGISTRATION_OPEN:-true}
      FEATURE_BACKUP_CRON: ${FEATURE_BACKUP_CRON:-true}
      BACKUP_RETENTION_DAYS: ${BACKUP_RETENTION_DAYS:-14}
      LOG_LEVEL: ${LOG_LEVEL:-info}
    volumes:
      - storage:/app/storage
      - backups:/backups
    depends_on:
      db:
        condition: service_healthy
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "node", "-e", "fetch('http://localhost:3000/api/v1/healthz').then(r=>process.exit(r.ok?0:1))"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 20s

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    volumes:
      - db_data:/var/lib/postgresql/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  caddy_data:
  caddy_config:
  db_data:
  storage:
  backups:
```

Пример `Caddyfile`:

```caddyfile
{$DOMAIN} {
    encode gzip

    handle /api/* {
        reverse_proxy api:3000
    }

    handle {
        reverse_proxy web:80
    }

    log {
        output stdout
        format json
    }
}
```

## 12. Миграция между инсталляциями

Перенос всей инсталляции со старого сервера на новый:

1. На старом сервере: `docker compose exec api pnpm backup:create`, скопировать архив.
2. На новом сервере: пройти установку по разделу 2 до `docker compose up -d`.
3. Дождаться готовности (первый сертификат Let's Encrypt).
4. Остановить api: `docker compose stop api`.
5. Скопировать бэкап в `./backups/`.
6. Восстановить: `docker compose exec api pnpm backup:restore /backups/... --yes`.
7. Обновить DNS на новый IP.
8. Проверить, что всё работает.
9. На старом сервере остановить: `docker compose down`.

Downtime — ровно время переключения DNS (минуты–часы в зависимости от TTL).