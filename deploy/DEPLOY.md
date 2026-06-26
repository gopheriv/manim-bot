# 🚀 Manim Bot — Oracle Cloud Deployment Guide

Полная инструкция по развёртыванию Manim Bot на Oracle Cloud Free Tier.

## Содержание

1. [Создать Oracle Cloud аккаунт](#1-создать-oracle-cloud-аккаунт)
2. [Создать VM инстанс](#2-создать-vm-инстанс)
3. [Настроить сеть и firewall](#3-настроить-сеть-и-firewall)
4. [Подключиться по SSH](#4-подключиться-по-ssh)
5. [Деплой бота](#5-деплой-бота)
6. [Миграция данных](#6-миграция-данных)
7. [Проверка и мониторинг](#7-проверка-и-мониторинг)
8. [Docker альтернатива](#8-docker-альтернатива)

---

## 1. Создать Oracle Cloud аккаунт

1. Зайти на [cloud.oracle.com](https://cloud.oracle.com) → **Sign Up**
2. Заполнить: email, имя, пароль
3. Привязать карту (для верификации, спишут ~$1 и вернут)
4. Выбрать регион: **Frankfurt (eu-frankfurt-1)** — ближе к тебе = меньше пинг

## 2. Создать VM инстанс

В консоли: **Compute → Instances → Create Instance**

### Конфигурация:

| Параметр | Значение |
|----------|----------|
| **Name** | `manim-bot` |
| **Placement** | default (любая AD) |
| **Image** | Ubuntu 24.04 (minimal) |
| **Shape** | `VM.Standard.A1.Flex` (ARM Ampere) |
| **OCPUs** | 2 |
| **RAM** | 12 GB |
| **Boot volume** | 50 GB |
| **SSH key** | Сгенерировать, скачать `ssh-key-example.pem` |

> **Важно:** Сохрани `.pem` файл в безопасном месте! Без него не подключиться.

На Windows конвертируй `.pem` в `.ppk` для PuTTY:
```
PuTTYgen → Load → ssh-key-example.pem → Save private key
```

Или используй OpenSSH (встроен в Windows 10/11):
```bash
ssh -i ssh-key-example.pem ubuntu@<public-ip>
```

## 3. Настроить сеть и firewall

### 3.1. Oracle Cloud Security List

В консоли: **Networking → Virtual Cloud Networks → <твоя VCN> → Security Lists → Default**

Добавить Ingress Rules:
| Port | Protocol | Source | Purpose |
|------|----------|--------|---------|
| 22 | TCP | 0.0.0.0/0 | SSH |
| 443 | TCP | 0.0.0.0/0 | HTTPS (опционально) |

### 3.2. Ubuntu firewall (на сервере)

```bash
sudo ufw allow 22/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

## 4. Подключиться по SSH

### Записать IP инстанса

В консоли: **Compute → Instances → manim-bot** → скопировать **Public IP**

### Подключение

```bash
# Windows (OpenSSH):
ssh -i C:\path\to\ssh-key-example.pem ubuntu@<PUBLIC_IP>

# Если .pem в другой директории — указать полный путь
```

### Защитить ключ (опционально, но рекомендуется)

```bash
# На сервере — отключить парольную аутентификацию
sudo sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo systemctl restart sshd
```

## 5. Деплой бота

### 5.1. Скопировать код на сервер

С **ноутбука** (открой новое окно терминала, НЕ закрывая SSH):

```bash
# Windows PowerShell — из папки manim-bot:
scp -i C:\path\to\ssh-key-example.pem -r .\* ubuntu@<PUBLIC_IP>:/tmp/manim-upload/
scp -i C:\path\to\ssh-key-example.pem -r .\.env ubuntu@<PUBLIC_IP>:/tmp/manim-upload/
scp -i C:\path\to\ssh-key-example.pem -r .\deploy\* ubuntu@<PUBLIC_IP>:/tmp/manim-upload/deploy/
```

### 5.2. Запустить setup на сервере

В SSH-сессии:

```bash
# Переместить код в /opt
sudo cp -r /tmp/manim-upload/* /opt/manim-bot/
sudo cp -r /tmp/manim-upload/deploy/* /opt/manim-bot/deploy/ 2>/dev/null || true
sudo chown -R ubuntu:ubuntu /opt/manim-bot

# Запустить setup
sudo bash /opt/manim-bot/deploy/setup_server.sh
```

Скрипт автоматически:
- Установит Python 3.14, ffmpeg, Manim зависимости
- Создаст virtual environment
- Установит systemd сервис с авто-рестартом
- Настроит log rotation

### 5.3. Проверить .env

```bash
cat /opt/manim-bot/.env
```

Убедись что `TELEGRAM_BOT_TOKEN` и API ключи на месте.

Если `.env` не скопировался — создай вручную:

```bash
nano /opt/manim-bot/.env
# Вставить содержимое deploy/.env.production с реальными ключами
```

### 5.4. Запустить бота

```bash
sudo systemctl start manim-bot
sudo systemctl enable manim-bot  # автозапуск при boot

# Проверить статус:
sudo systemctl status manim-bot

# Смотреть логи:
sudo journalctl -u manim-bot -f --no-pager
```

Должно быть:
```
manim-bot[12345]: 2026-06-21 ... [bot] INFO  Starting Manim Animation Bot + AI Assistant
manim-bot[12345]: 2026-06-21 ... [aiogram.dispatcher] INFO  Start polling
manim-bot[12345]: 2026-06-21 ... [aiogram.dispatcher] INFO  Run polling for bot @Manim_is_so_useful_bot
```

### 5.5. Отправить тестовое сообщение

Напиши боту в Telegram: `/start`

Если ответил — всё работает! ✅

## 6. Миграция данных

### 6.1. Настройки пользователей

```bash
# С ноутбука:
scp -i C:\path\to\ssh-key-example.pem user_settings.json ubuntu@<PUBLIC_IP>:/opt/manim-bot/
```

### 6.2. Аналитика

```bash
# С ноутбука:
scp -i C:\path\to\ssh-key-example.pem data\analytics.json ubuntu@<PUBLIC_IP>:/opt/manim-bot/data/
```

### 6.3. Локальный кэш рендеров (опционально)

```bash
# С ноутбука — если есть .local_cache.db:
scp -i C:\path\to\ssh-key-example.pem .local_cache.db ubuntu@<PUBLIC_IP>:/opt/manim-bot/
```

### 6.4. Автоматическая миграция

Или используй готовый скрипт:

```bash
# На сервере:
bash /opt/manim-bot/deploy/migrate_to_cloud.sh <laptop-public-ip>
```

Скрипт запросит SSH ключ и скопирует все данные.

## 7. Проверка и мониторинг

### 7.1. Базовые проверки

```bash
# Бот работает?
sudo systemctl is-active manim-bot

# RAM usage:
free -h

# CPU load:
top -bn1 | head -5

# Manim работает?
manim --version

# ffmpeg работает?
ffmpeg -version | head -1
```

### 7.2. Журналы

```bash
# Последние 50 строк логов:
sudo journalctl -u manim-bot -n 50 --no-pager

# Следить в реальном времени:
sudo journalctl -u manim-bot -f

# Логи бота (файл):
tail -f /opt/manim-bot/logs/manim-bot.log

# Ошибки за последний час:
sudo journalctl -u manim-bot --since "1 hour ago" -p err
```

### 7.3. Тест рендера

Отправь боту простое сообщение:
```
/animation rotating square
```

Должен ответить видео через 1-3 минуты (сервер быстрее ноутбука!).

### 7.4. Настроить уведомления о рестарте

В `.env` добавь:
```
WATCHDOG_NOTIFY_CHAT=6042733716
```

systemd будет рестарить бота при краше, и бот пришлёт уведомление в Telegram.

### 7.5. Logrotate

Логи ротируются автоматически:
- `/opt/manim-bot/logs/*.log` — ежедневно, хранится 7 дней, макс 10 MB

Проверить:
```bash
sudo logrotate -d /etc/logrotate.d/manim-bot
```

## 8. Docker альтернатива

Если предпочитаешь контейнеры вместо systemd:

### 8.1. Установить Docker

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker ubuntu
# Перелогиниться: exit && ssh снова
```

### 8.2. Запустить через Docker Compose

```bash
cd /opt/manim-bot/deploy
cp .env.production .env
# Отредактировать .env с реальными ключами
docker compose up -d
docker compose logs -f
```

### 8.3. Управление

```bash
docker compose down          # остановить
docker compose up -d         # запустить
docker compose logs -f       # логи
docker compose pull && docker compose up -d  # обновить
```

## Команды управления

| Команда | Что делает |
|---------|------------|
| `sudo systemctl start manim-bot` | Запустить бота |
| `sudo systemctl stop manim-bot` | Остановить |
| `sudo systemctl restart manim-bot` | Перезапустить |
| `sudo systemctl status manim-bot` | Статус |
| `sudo journalctl -u manim-bot -f` | Логи в реальном времени |
| `sudo systemctl enable manim-bot` | Автозапуск при boot |
| `sudo systemctl disable manim-bot` | Отключить автозапуск |

## Troubleshooting

### Бот не запускается

```bash
# Проверить логи:
sudo journalctl -u manim-bot -n 100

# Проверить .env:
cat /opt/manim-bot/.env

# Проверить Python:
/opt/manim-bot/venv/bin/python3 --version

# Проверить зависимости:
/opt/manim-bot/venv/bin/pip list
```

### Manim не устанавливается

```bash
# Проверить системные зависимости:
dpkg -l | grep -E 'pango|cairo|glew|egl|gl1'

# Установить недостающее:
sudo apt install libpango1.0-dev pkg-config libcairo2-dev libglew-dev libegl1 libgl1
```

### Рендер зависает

```bash
# Проверить RAM:
free -h

# Убить зависший процесс:
sudo pkill -f "manim.*GenScene"

# Уменьшить concurrency в .env:
# MAX_CONCURRENT_RENDERS=1
```

### Telegram не отвечает

```bash
# Проверить интернет:
curl -s https://api.telegram.org/bot<your-token>/getMe

# Проверить токен:
grep TELEGRAM_BOT_TOKEN /opt/manim-bot/.env
```

## Цена

Oracle Cloud Free Tier:
- **2 VM.Standard.A1.Flex** инстанса бесплатно
- До **4 OCPU** и **24 GB RAM** суммарно
- 200 GB boot volume
- **$0/мес навсегда**

Рекомендуемая конфигурация для Manim Bot:
- 2 OCPU, 12 GB RAM — отлично рендерит 720p за 1-3 минуты
- Можно запустить второй инстанс для других задач (10 GB RAM, 2 OCPU)
