# Налаштування cron-job.org для щогодинного тригера

## Загальна схема

```
cron-job.org  →  POST /repos/{owner}/{repo}/actions/workflows/send_daily.yml/dispatches
                  (GitHub API)  →  GitHub Actions  →  send_telegram.py
```

---

## 1. Отримати GitHub Token

1. Відкрийте **GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens** або **Tokens (classic)**.
2. Натисніть **Generate new token**.
3. Мінімальні права (достатньо лише одного):
   - **Tokens (classic):** увімкніть scope `workflow`.
   - **Fine-grained:** репозиторій → *Actions* → **Read and write**.
4. Скопіюйте токен — він показується лише один раз.

---

## 2. Реєстрація на cron-job.org

1. Перейдіть на [https://cron-job.org](https://cron-job.org) і створіть безкоштовний акаунт.
2. Після входу натисніть **+ Create cronjob**.

---

## 3. Параметри нового Cronjob

### Title
```
nmt-daily trigger
```

### URL
```
https://api.github.com/repos/YOUR_GITHUB_USERNAME/nmt-daily/actions/workflows/send_daily.yml/dispatches
```
Замініть `YOUR_GITHUB_USERNAME` на ваш нікнейм GitHub.

### Method
```
POST
```

### Schedule
- Оберіть **Custom** → `0 * * * *` (щогодини, на початку кожної години).

### Request headers

| Header | Value |
|---|---|
| `Authorization` | `Bearer ghp_ВАШ_ТОКЕН` |
| `Accept` | `application/vnd.github+json` |
| `Content-Type` | `application/json` |
| `X-GitHub-Api-Version` | `2022-11-28` |

### Request body
```json
{"ref": "main"}
```

---

## 4. Зберегти та перевірити

1. Натисніть **Create** / **Save**.
2. У списку cronjob-ів натисніть **Run now** — повинен з'явитись статус `204 No Content` у деталях відповіді.
3. У вашому репозиторії відкрийте **Actions → Send Daily Question** — повинен з'явитись новий запущений workflow.

---

## 5. Моніторинг

- **cron-job.org → Logs**: тут видно HTTP-статус кожного запиту. Норма — `204`.
- **GitHub → Actions**: тут видно час запуску та логи `send_telegram.py` з точним UTC-часом.

---

## Що означають помилки від GitHub API

| Статус | Причина |
|---|---|
| `204 No Content` | Успіх — workflow запущено |
| `401 Unauthorized` | Токен невалідний або закінчився термін дії |
| `404 Not Found` | Неправильний `owner/repo` або токен не має доступу до репозиторію |
| `422 Unprocessable Entity` | Файл workflow не знайдено або гілка `main` не існує |
