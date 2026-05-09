# NMT Daily

Telegram-бот, що щогодини надсилає питання зі шкільного курсу для підготовки до НМТ/ЗНО.

Підтримувані предмети: математика, українська мова, історія України, біологія.

Працює повністю на **GitHub Actions** — сервер не потрібен.

---

## Як це працює

Кожної години `send_daily.yml` запускає `send_telegram.py`:
1. Обирає по одному випадковому питанню з кожного предмету.
2. Надсилає питання у вигляді повідомлення (або фото) + опитування-вікторини.
3. Зберігає надіслані ID у `data/sent.json` (вікно 200 питань — без повторів).

Банк питань (`bank/*.json`) поповнюється щопонеділка через `build_db.yml`.

---

## Налаштування

### 1. Клонуй репозиторій та додай секрети

У налаштуваннях GitHub-репозиторію (`Settings → Secrets and variables → Actions`) додай:

| Secret | Опис |
|--------|------|
| `BOT_TOKEN` | Токен бота від [@BotFather](https://t.me/BotFather) |
| `CHAT_IDS` | Список ID чатів через кому, наприклад `-100123456789,-100987654321` |

### 2. Увімкни GitHub Actions

Переконайся, що Actions увімкнено: `Settings → Actions → General → Allow all actions`.

Workflows запустяться автоматично за розкладом. Для ручного запуску обери workflow та натисни `Run workflow`.

---

## Локальний запуск

```bash
pip install -r requirements.txt

# Створи .env з твоїми даними
echo "BOT_TOKEN=<токен>" >> .env
echo "CHAT_IDS=<id_чату>" >> .env

python send_telegram.py
```

Для запуску тестів:
```bash
pip install pytest pyyaml
pytest
```

---

## Структура

```
send_telegram.py     — головний скрипт
subjects.py          — реєстр предметів і тем
bank/{subject}.json  — банки питань
data/sent.json       — журнал надісланих питань
scripts/backfill.py  — поповнення банку (zno.osvita.ua)
parse_pdf.py         — імпорт питань з PDF-файлів НМТ
.github/workflows/   — GitHub Actions
```

---

## Workflows

| Workflow | Розклад | Призначення |
|---|---|---|
| `send_daily.yml` | Щогодини | Надсилає питання |
| `build_db.yml` | Щопонеділка 03:00 UTC | Поповнює банк питань |
| `check_bank.yml` | Щосуботи 06:00 UTC | Перевіряє стан банку |
| `backfill_images.yml` | Вручну | Заповнює відсутні URL зображень |
| `parse_pdf.yml` | Вручну | Імпортує PDF-варіант НМТ |

---

## Ліцензія

MIT
