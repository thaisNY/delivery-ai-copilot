"""Classificação de avaliações: sentimento + temas.

Etapa do pipeline: avaliação crua -> LLM (Gemini, em lotes, saída JSON) -> Postgres.
Se não houver chave ou a API falhar, usa um classificador por palavras-chave,
para o projeto continuar funcionando offline.
"""
import json
import re
import time

from app import llm

TOPICS = ["atraso", "embalagem", "preco", "quantidade", "item_errado", "sabor", "atendimento", "elogio"]

KEYWORDS = {
    "atraso": r"demor|atras|eternidade|frio|fria|hora depois",
    "embalagem": r"embalagem|vaz|derram|aberta",
    "preco": r"caro|pre[çc]o|barato|vale mais",
    "quantidade": r"pouca|pequen|porç",
    "item_errado": r"errad|faltou|outra coisa",
    "sabor": r"tempero|sal\b|dura|saboros|gostei",
    "atendimento": r"entregador|educad|atendimento",
    "elogio": r"maravilh|recomendo|melhor|perfeito|ótim|otim|saboros|bem servido|r[áa]pido",
}


def classify_rules(comment: str, rating: int) -> dict:
    text = (comment or "").lower()
    topics = [t for t, rx in KEYWORDS.items() if re.search(rx, text)]
    if rating >= 4:
        sentiment = "positivo"
        topics = [t for t in topics if t in ("elogio", "atendimento", "sabor")] or ["elogio"]
    elif rating == 3:
        sentiment = "neutro"
    else:
        sentiment = "negativo"
        topics = [t for t in topics if t != "elogio"]
    return {"sentiment": sentiment, "topics": topics or ["sem_comentario"]}


PROMPT = """Você classifica avaliações de clientes de restaurantes de delivery.
Para cada avaliação, devolva sentimento ("positivo", "neutro" ou "negativo") e uma lista de temas,
usando apenas: {topics}. Use ["sem_comentario"] se o texto estiver vazio.
Responda APENAS com um JSON no formato: [{{"id": "...", "sentiment": "...", "topics": ["..."]}}]

Avaliações:
{items}"""


def classify_llm_batch(batch: list[dict]) -> dict[str, dict]:
    items = "\n".join(json.dumps({"id": r["id"], "nota": r["rating"], "texto": r["comment"]}, ensure_ascii=False) for r in batch)
    text = llm.generate_text(PROMPT.format(topics=", ".join(TOPICS), items=items), json_mode=True)
    data = json.loads(text)
    out = {}
    for d in data:
        topics = [t for t in d.get("topics", []) if t in TOPICS or t == "sem_comentario"]
        sentiment = str(d.get("sentiment", "")).strip().lower()
        if sentiment not in ("positivo", "neutro", "negativo"):
            continue  # valor inválido: essa avaliação cai para as regras
        out[str(d.get("id"))] = {"sentiment": sentiment, "topics": topics or ["sem_comentario"]}
    return out


def classify_all(reviews: list[dict], batch_size: int = 60, max_llm_batches: int = 10) -> None:
    """Classifica in place. Manda até max_llm_batches lotes ao LLM (camada gratuita tem limite);
    o resto, e qualquer falha, vai para as regras."""
    use_llm = llm.available()
    llm_batches = 0
    # Mais recentes primeiro: são as que aparecem no painel e nas perguntas ao agente
    ordered = sorted(reviews, key=lambda r: r["created_at"], reverse=True)
    for i in range(0, len(ordered), batch_size):
        batch = ordered[i:i + batch_size]
        result = {}
        if use_llm and llm_batches < max_llm_batches:
            try:
                result = classify_llm_batch(batch)
                llm_batches += 1
                time.sleep(4)  # respeita o limite de requisições por minuto
            except Exception as e:  # noqa: BLE001
                print(f"[classify] LLM falhou ({e}); usando regras neste lote")
        for r in batch:
            if r["id"] in result:
                r.update(result[r["id"]], classified_by="llm")
            else:
                r.update(classify_rules(r["comment"], r["rating"]), classified_by="regras")


TRUE_TO_TOPIC = {"sabor_neg": "sabor"}


def classifier_accuracy(reviews: list[dict]) -> dict:
    """Compara o tema previsto com o gabarito do gerador (só avaliações com comentário).
    Acerto = o tema verdadeiro está entre os temas previstos."""
    stats = {}
    for r in reviews:
        if not r.get("comment") or "_true_topic" not in r:
            continue
        truth = TRUE_TO_TOPIC.get(r["_true_topic"], r["_true_topic"])
        s = stats.setdefault(r["classified_by"], [0, 0])
        s[0] += truth in r["topics"]
        s[1] += 1
    return {k: f"{ok}/{n} ({ok / n:.0%})" for k, (ok, n) in stats.items() if n}
