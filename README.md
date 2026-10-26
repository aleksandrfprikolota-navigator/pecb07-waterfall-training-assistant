# ИИ-ассистент: обучение водопадной модели

Telegram-бот обучает сотрудника классической водопадной модели управления проектами и затем проверяет знания. Результат теста сохраняется в PostgreSQL.

Бот:

- просит имя сотрудника;
- объясняет материал четырьмя короткими блоками;
- отвечает на вопросы только по этому материалу;
- проводит тест из пяти вопросов, по одному за раз;
- оценивает ответ и даёт короткую обратную связь;
- записывает итог в таблицу `training_results`.

## Учебные блоки

1. Порядок фаз: требования, проектирование, реализация, проверка, внедрение, сопровождение. Следующая фаза начинается после формальной приёмки предыдущей.
2. Документы фаз и ворота фазы.
3. Запрос на изменение и роли заказчика, руководителя, аналитика, проектировщика, разработчиков и тестировщиков.
4. Когда водопад уместен и почему ошибка в требованиях обнаруживается поздно.

Текст материала лежит в `material/waterfall.txt`.

## Структура проекта

```text
├── bot/
│   ├── handlers/
│   │   └── onboarding.py       # /start, /cancel и ход обучения
│   ├── keyboards/
│   ├── main.py                 # логирование, база, polling
│   └── middlewares/
├── config/
│   └── settings.py             # переменные окружения и текст материала
├── database/
│   ├── db.py
│   ├── models.py               # таблица training_results
│   └── repository.py
├── material/
│   └── waterfall.txt
├── schemas/
│   └── training.py             # черновик сессии и ответ модели
├── services/
│   ├── ai_training_prompts.py  # роль, блоки, JSON-схема
│   ├── ai_training_service.py  # запрос к модели
│   └── training_service.py     # имя, фазы, подсчёт, запись результата
├── .env.example
├── docker-compose.yml
├── Dockerfile
├── main.py
└── requirements.txt
```

## Как проходит сессия

1. Сотрудник отправляет `/start`. Бот включает состояние `TrainingStates.active` и создаёт черновик сессии.
2. Первое текстовое сообщение — имя. Короче двух символов бот не принимает.
3. Дальше модель ведёт фазу `learning` и сдаёт блоки по одному. Номер уже сданного блока хранится в черновике, потому что в запрос не уходит вся переписка.
4. Прямая просьба перейти к тесту после первых двух блоков, либо подтверждение после четвёртого блока, переводит сессию в `testing`.
5. На каждый ответ модель возвращает JSON: текст сотруднику, фазу, оценку и следующий вопрос. Верный ответ увеличивает счётчик.
6. Когда проверены все вопросы, фаза становится `completed`. Бот пишет строку в PostgreSQL и присылает итог `верные/всего` и процент.
7. `/cancel` сбрасывает незавершённую сессию. Голос, фото и файлы бот не разбирает.

Состояние диалога лежит в памяти процесса. После перезапуска контейнера незаконченный тест нужно начать заново. Сохранённые результаты в базе остаются.

## Переменные окружения

```env
BOT_TOKEN=your_telegram_bot_token
DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/onboarding
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-6-sol
OPENAI_BASE_URL=https://api.openai.com/v1
TRAINING_TOPIC=Классическая водопадная модель управления проектами
TRAINING_MATERIAL_FILE=material/waterfall.txt
QUIZ_QUESTION_COUNT=5
LOG_LEVEL=INFO
```

`BOT_TOKEN` выдаёт BotFather. `DATABASE_URL` внутри Docker Compose указывает на сервис `db`, а не на `localhost`. Если задан `TRAINING_MATERIAL_FILE`, бот читает его. Иначе используется короткий текст из `TRAINING_MATERIAL`.

Модель должна принимать Chat Completions и ответ `json_schema`. Запрос уходит с `temperature=0.2`. Если модель принимает только температуру по умолчанию, следующий запрос уходит без этого поля.

Файл `.env` не коммитится и не копируется в образ: он указан в `.dockerignore` и в `.gitignore`.

## Локальный запуск

Нужен запущенный Docker Desktop. В `requirements.txt` указан `greenlet`: без него актуальный SQLAlchemy не поднимает async-движок. В Dockerfile репозиторий Debian переведён на HTTPS и включены повторы загрузки: по обычному HTTP сборка компилятора с этой машины обрывается.

```powershell
cd D:\PythonProject_PI\Career_in_business\PEcb07_AI_AssistantStaffTraining\onboard-main
Copy-Item .env.example .env
docker compose up --build
```

В другом окне журналы смотрят так:

```powershell
docker compose logs -f bot
```

О готовности говорят строки `database system is ready to accept connections` и `Starting AI training bot`. Остановка из того же каталога: `Ctrl+C`, затем `docker compose down`. База на томе при этом сохраняется. `docker compose down -v` удаляет том вместе с результатами.

## Сервер

На чистой Ubuntu ставят Docker и Docker Compose, клонируют репозиторий, создают `.env` по образцу и запускают контейнеры в фоне:

```bash
apt update
apt install docker.io docker-compose -y
git clone https://github.com/aleksandrfprikolota-navigator/pecb07-waterfall-training-assistant.git
cd pecb07-waterfall-training-assistant
nano .env
docker-compose up --build -d
```

Флаг `-d` оставляет контейнеры работать после закрытия SSH. Проверка: `docker ps` и `docker-compose logs -f bot`.

## База

Локально DBeaver подключается к PostgreSQL так: хост `localhost`, порт `5432`, база `onboarding`, пользователь `postgres`, пароль `postgres`. На сервере в поле хоста указывают IP машины. Таблица `training_results` появляется после первого запуска бота.

В строке результата лежат имя, идентификаторы Telegram, тема, число вопросов, число верных ответов, процент, итоговый текст и время записи.

Пароль `postgres` и открытый порт `5432` оставлены как в учебном примере, чтобы подключение из DBeaver совпадало с заданием. Для постоянного доступа вне учебной проверки порт лучше закрыть и вынести пароль в переменные.
