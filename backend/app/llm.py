"""Cliente mínimo da API do Gemini (REST), sem SDK, para ficar claro o que acontece."""
import os
import time

import httpx

API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip()
URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class LLMError(Exception):
    """Erro já sanitizado (nunca contém a chave da API)."""


def available() -> bool:
    return bool(API_KEY)


def _post(body: dict, retries: int = 3) -> dict:
    # A chave vai no header, não na URL, para não vazar em mensagens de erro e logs.
    for attempt in range(retries):
        try:
            r = httpx.post(URL.format(model=MODEL), headers={"x-goog-api-key": API_KEY}, json=body, timeout=60)
        except httpx.HTTPError as e:
            if attempt == retries - 1:
                raise LLMError(f"falha de rede ({type(e).__name__})") from None
            time.sleep(2 ** attempt)
            continue
        if r.status_code in (429, 500, 503) and attempt < retries - 1:
            time.sleep(2 ** (attempt + 1))  # limite da camada gratuita / instabilidade
            continue
        if r.status_code >= 400:
            raise LLMError(f"HTTP {r.status_code} do Gemini (modelo {MODEL})")
        return r.json()
    raise LLMError("sem resposta do Gemini")


def _content(data: dict) -> dict:
    try:
        return data["candidates"][0]["content"]
    except (KeyError, IndexError):
        reason = (data.get("candidates") or [{}])[0].get("finishReason") or data.get("promptFeedback", {}).get("blockReason")
        raise LLMError(f"resposta vazia do modelo ({reason or 'motivo desconhecido'})") from None


def generate_text(prompt: str, json_mode: bool = False) -> str:
    body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
    if json_mode:
        body["generationConfig"] = {"responseMimeType": "application/json", "temperature": 0}
    return "".join(p.get("text", "") for p in _content(_post(body)).get("parts", []))


def generate_with_tools(system: str, contents: list[dict], tools: list[dict]) -> dict:
    """Uma rodada do modelo com function calling. Devolve o 'content' inteiro do candidato
    (inclui thoughtSignature, que precisa voltar na próxima rodada)."""
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": contents,
        "tools": [{"functionDeclarations": tools}],
        "generationConfig": {"temperature": 0.2},
    }
    return _content(_post(body))
