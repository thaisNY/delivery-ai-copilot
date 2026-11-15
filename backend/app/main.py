from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Literal

from pydantic import BaseModel, Field

from app import agent, llm
from app.llm import LLMError
from app.db import query
from app.tools import atrasos, comparar_mercado, reclamacoes, resumo_vendas

app = FastAPI(title="Copiloto do Restaurante", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def _merchant(merchant_id: str) -> dict:
    rows = query("SELECT id, name, category FROM merchants WHERE id = %s", (merchant_id,))
    if not rows:
        raise HTTPException(404, "Restaurante não encontrado")
    return rows[0]


@app.get("/api/health")
def health():
    return {"ok": True, "llm": llm.available(), "model": llm.MODEL if llm.available() else None}


@app.get("/api/merchants")
def merchants():
    return query("SELECT id, name, category FROM merchants ORDER BY name")


@app.get("/api/merchants/{merchant_id}/dashboard")
def dashboard(merchant_id: str):
    _merchant(merchant_id)
    daily = query("""
        SELECT to_char(date_trunc('day', created_at), 'DD/MM') AS dia, count(*) AS pedidos,
               round(sum(total), 2)::float AS faturamento
        FROM orders WHERE merchant_id = %s GROUP BY date_trunc('day', created_at) ORDER BY date_trunc('day', created_at)
    """, (merchant_id,))
    return {
        "resumo": resumo_vendas(merchant_id, 14),
        "atrasos": atrasos(merchant_id, 30),
        "reclamacoes": reclamacoes(merchant_id, 30),
        "mercado": comparar_mercado(merchant_id),
        "serie_diaria": daily,
    }


class Turn(BaseModel):
    role: Literal["user", "model"]
    text: str = Field(max_length=4000)


class ChatIn(BaseModel):
    merchant_id: str
    message: str = Field(min_length=1, max_length=1000)
    history: list[Turn] = Field(default=[], max_length=20)


@app.post("/api/chat")
def chat(body: ChatIn):
    m = _merchant(body.merchant_id)
    try:
        return agent.ask(body.message, m, [t.model_dump() for t in body.history])
    except LLMError as e:
        raise HTTPException(502, f"Falha ao falar com o modelo: {e}") from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"Erro interno: {type(e).__name__}") from e
