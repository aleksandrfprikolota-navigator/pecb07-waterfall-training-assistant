import json

import httpx

from config import Settings
from schemas import TrainingAssistantTurn, TrainingSessionDraft
from services.ai_training_prompts import AI_TRAINING_RESPONSE_SCHEMA, build_training_system_prompt


class AITrainingService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._training_material = settings.get_training_material()
        self._omit_temperature = False
        self._client = httpx.AsyncClient(
            base_url=settings.openai_base_url,
            timeout=httpx.Timeout(120.0, connect=30.0),
            headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json",
            },
        )

    async def generate_turn(
        self,
        draft: TrainingSessionDraft,
        user_message: str,
        is_new_dialogue: bool,
    ) -> TrainingAssistantTurn:
        payload = {
            "model": self._settings.openai_model,
            "temperature": 0.2,
            "messages": [
                {
                    "role": "system",
                    "content": build_training_system_prompt(
                        topic=self._settings.training_topic,
                        material=self._training_material,
                        total_questions=draft.total_questions,
                    ),
                },
                {
                    "role": "user",
                    "content": self._build_prompt(
                        draft=draft,
                        user_message=user_message,
                        is_new_dialogue=is_new_dialogue,
                    ),
                },
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": AI_TRAINING_RESPONSE_SCHEMA,
            },
        }

        response = await self._post(payload)
        content = response.json()["choices"][0]["message"]["content"]
        return TrainingAssistantTurn.model_validate(self._load_json_object(content))

    async def close(self) -> None:
        await self._client.aclose()

    async def _post(self, payload: dict) -> httpx.Response:
        request_payload = dict(payload)
        if self._omit_temperature:
            request_payload.pop("temperature", None)
        response = await self._client.post("/chat/completions", json=request_payload)
        if (
            response.status_code == 400
            and not self._omit_temperature
            and "temperature" in response.text.lower()
        ):
            self._omit_temperature = True
            request_payload.pop("temperature", None)
            response = await self._client.post("/chat/completions", json=request_payload)
        response.raise_for_status()
        return response

    @staticmethod
    def _load_json_object(content: str) -> dict:
        text = content.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:]
            text = text.strip()
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            text = text[start : end + 1]
        return json.loads(text)

    @staticmethod
    def _build_prompt(
        draft: TrainingSessionDraft,
        user_message: str,
        is_new_dialogue: bool,
    ) -> str:
        serialized_draft = json.dumps(draft.model_dump(), ensure_ascii=False, indent=2)
        if draft.phase == "learning" and draft.learning_block < 4:
            stage = (
                f"Объяснено блоков: {draft.learning_block} из 4. "
                "В этом ходе дай только следующий один блок и оставь phase=learning. "
                "«Да», «дальше» и «понятно» означают следующий блок, а не тест. "
                "К тесту переходи только по прямой просьбе и только если блоков уже не меньше 2."
            )
        elif draft.phase == "learning":
            stage = (
                "Все 4 блока уже объяснены. Если сотрудник подтверждает готовность, "
                "поставь phase=testing, latest_answer_evaluated=false и сразу запиши "
                "первый вопрос в reply и в next_question."
            )
        elif draft.phase == "testing":
            stage = (
                "Идёт тест. Оцени ответ именно на current_question. "
                f"Уже проверено {draft.questions_answered} из {draft.total_questions}. "
                "Если оцениваешь этот ответ, проверенных станет на один больше. "
                "phase=completed ставь только когда это число сравняется с total_questions. "
                "Пока вопросы не кончились, следующий вопрос положи и в reply, и в next_question."
            )
        else:
            stage = "Сессия завершена. Кратко подтверди итог по материалу."
        return (
            f"Новая сессия: {str(is_new_dialogue).lower()}\n"
            f"Текущее состояние сессии:\n{serialized_draft}\n\n"
            f"Последнее сообщение сотрудника:\n{user_message}\n\n"
            f"Что сделать в этом ходе:\n{stage}"
        )
