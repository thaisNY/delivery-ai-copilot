"""Ferramentas que o agente pode chamar. Cada uma é uma consulta SQL que devolve números prontos,
para o LLM não inventar dados: ele só interpreta o que as ferramentas retornam.

A data de referência é o último pedido no banco (não "agora"), para os períodos fazerem
sentido mesmo se a demo rodar semanas depois de gerada.
"""
from app.db import query

WEEKDAYS = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]
REF = "(SELECT date_trunc('day', max(created_at)) + interval '1 day' FROM orders)"


def _pct(new, old):
    if not old:
        return None
    return round((float(new) - float(old)) / float(old) * 100, 1)


def resumo_vendas(merchant_id: str, dias: int = 14) -> dict:
    rows = query(f"""
        WITH ref AS (SELECT {REF} AS d)
        SELECT CASE WHEN created_at >= (SELECT d FROM ref) - make_interval(days => %(dias)s::int)
                    THEN 'atual' ELSE 'anterior' END AS periodo,
               count(*) AS pedidos, round(sum(total), 2) AS faturamento, round(avg(total), 2) AS ticket_medio
        FROM orders
        WHERE merchant_id = %(m)s
          AND created_at >= (SELECT d FROM ref) - make_interval(days => %(dias)s::int * 2)
        GROUP BY 1""", {"m": merchant_id, "dias": dias})
    p = {r["periodo"]: r for r in rows}
    atual, ant = p.get("atual", {}), p.get("anterior", {})
    nota = query(f"""
        SELECT round(avg(rating)::numeric, 2) AS nota_media, count(*) AS avaliacoes
        FROM reviews WHERE merchant_id = %(m)s
          AND created_at >= {REF} - make_interval(days => %(dias)s::int)""", {"m": merchant_id, "dias": dias})[0]
    return {
        "periodo_dias": dias,
        "atual": {k: float(v) for k, v in atual.items() if k != "periodo"},
        "anterior": {k: float(v) for k, v in ant.items() if k != "periodo"},
        "variacao_pedidos_pct": _pct(atual.get("pedidos", 0), ant.get("pedidos")),
        "variacao_faturamento_pct": _pct(atual.get("faturamento", 0), ant.get("faturamento")),
        "nota_media_periodo": float(nota["nota_media"]) if nota["nota_media"] else None,
        "avaliacoes_periodo": nota["avaliacoes"],
    }


def vendas_por_item(merchant_id: str, dias: int = 14) -> dict:
    rows = query(f"""
        WITH ref AS (SELECT {REF} AS d), it AS (
            SELECT o.created_at, i->>'name' AS item, (i->>'price')::numeric AS preco
            FROM orders o, jsonb_array_elements(o.items) i
            WHERE o.merchant_id = %(m)s
              AND o.created_at >= (SELECT d FROM ref) - make_interval(days => %(dias)s::int * 2))
        SELECT item,
               count(*) FILTER (WHERE created_at >= (SELECT d FROM ref) - make_interval(days => %(dias)s::int)) AS qtd_atual,
               count(*) FILTER (WHERE created_at <  (SELECT d FROM ref) - make_interval(days => %(dias)s::int)) AS qtd_anterior,
               round(avg(preco) FILTER (WHERE created_at >= (SELECT d FROM ref) - make_interval(days => %(dias)s::int)), 2) AS preco_atual,
               round(avg(preco) FILTER (WHERE created_at <  (SELECT d FROM ref) - make_interval(days => %(dias)s::int)), 2) AS preco_anterior
        FROM it GROUP BY item ORDER BY qtd_atual DESC""", {"m": merchant_id, "dias": dias})
    return {"periodo_dias": dias, "itens": [
        {**{k: (float(v) if v is not None and k != "item" else v) for k, v in r.items()},
         "variacao_qtd_pct": _pct(r["qtd_atual"], r["qtd_anterior"])} for r in rows]}


def atrasos(merchant_id: str, dias: int = 30) -> dict:
    geral = query(f"""
        SELECT count(*) AS pedidos,
               round(100.0 * avg((delivery_minutes > promised_minutes + 10)::int), 1) AS pct_atrasados,
               round(avg(delivery_minutes - promised_minutes)::numeric, 1) AS atraso_medio_min
        FROM orders WHERE merchant_id = %(m)s
          AND created_at >= {REF} - make_interval(days => %(dias)s::int)""", {"m": merchant_id, "dias": dias})[0]
    slots = query(f"""
        SELECT extract(isodow FROM created_at)::int AS dow,
               CASE WHEN extract(hour FROM created_at) < 15 THEN 'almoço (11h-15h)'
                    WHEN extract(hour FROM created_at) < 19 THEN 'tarde (15h-19h)'
                    ELSE 'noite (19h-23h)' END AS turno,
               count(*) AS pedidos,
               round(100.0 * avg((delivery_minutes > promised_minutes + 10)::int), 1) AS pct_atrasados,
               round(avg(delivery_minutes - promised_minutes)::numeric, 1) AS atraso_medio_min
        FROM orders WHERE merchant_id = %(m)s
          AND created_at >= {REF} - make_interval(days => %(dias)s::int)
        GROUP BY 1, 2 HAVING count(*) >= 10
        ORDER BY pct_atrasados DESC LIMIT 5""", {"m": merchant_id, "dias": dias})
    return {
        "periodo_dias": dias,
        "criterio": "atrasado = entregue mais de 10 min depois do prometido",
        "geral": {k: (float(v) if v is not None else None) for k, v in geral.items()},
        "pct_atrasados_periodo_anterior": _late_prev(merchant_id, dias),
        "piores_horarios": [{"dia": WEEKDAYS[s["dow"] - 1], "turno": s["turno"], "pedidos": s["pedidos"],
                             "pct_atrasados": float(s["pct_atrasados"]),
                             "atraso_medio_min": float(s["atraso_medio_min"])} for s in slots],
    }


def _late_prev(merchant_id: str, dias: int):
    r = query(f"""
        SELECT round(100.0 * avg((delivery_minutes > promised_minutes + 10)::int), 1) AS pct
        FROM orders WHERE merchant_id = %(m)s
          AND created_at >= {REF} - make_interval(days => %(dias)s::int * 2)
          AND created_at <  {REF} - make_interval(days => %(dias)s::int)""", {"m": merchant_id, "dias": dias})[0]
    return float(r["pct"]) if r["pct"] is not None else None


def reclamacoes(merchant_id: str, dias: int = 30, tema: str | None = None) -> dict:
    temas = query(f"""
        SELECT t AS tema, count(*) AS qtd
        FROM reviews r, unnest(r.topics) t
        WHERE r.merchant_id = %(m)s AND r.sentiment <> 'positivo'
          AND r.created_at >= {REF} - make_interval(days => %(dias)s::int)
          AND t <> 'sem_comentario'
        GROUP BY t ORDER BY qtd DESC""", {"m": merchant_id, "dias": dias})
    filtro = "AND %(tema)s = ANY(r.topics)" if tema else ""
    itens = query(f"""
        SELECT i->>'name' AS item, count(*) AS reclamacoes
        FROM reviews r JOIN orders o ON o.id = r.order_id, jsonb_array_elements(o.items) i
        WHERE r.merchant_id = %(m)s AND r.sentiment = 'negativo'
          AND r.created_at >= {REF} - make_interval(days => %(dias)s::int) {filtro}
        GROUP BY 1 ORDER BY 2 DESC LIMIT 5""", {"m": merchant_id, "dias": dias, "tema": tema})
    exemplos = query(f"""
        SELECT rating AS nota, comment AS comentario, topics AS temas
        FROM reviews r
        WHERE r.merchant_id = %(m)s AND r.sentiment <> 'positivo' AND comment <> ''
          AND r.created_at >= {REF} - make_interval(days => %(dias)s::int) {filtro}
        ORDER BY created_at DESC LIMIT 6""", {"m": merchant_id, "dias": dias, "tema": tema})
    total = query(f"""
        SELECT count(*) AS n, count(*) FILTER (WHERE sentiment = 'negativo') AS negativas
        FROM reviews WHERE merchant_id = %(m)s
          AND created_at >= {REF} - make_interval(days => %(dias)s::int)""", {"m": merchant_id, "dias": dias})[0]
    return {"periodo_dias": dias, "tema_filtrado": tema, "avaliacoes_total": total["n"],
            "avaliacoes_negativas": total["negativas"], "temas": temas,
            "itens_mais_citados_em_negativas": itens, "exemplos": exemplos}


def comparar_mercado(merchant_id: str) -> dict:
    m = query("SELECT name, category FROM merchants WHERE id = %s", (merchant_id,))[0]
    mercado = query("""
        SELECT count(*) AS restaurantes,
               round(avg(delivery_time)::numeric, 1) AS tempo_entrega_medio_min,
               round(avg(delivery_fee)::numeric, 2) AS taxa_entrega_media,
               round(avg(rating)::numeric, 2) AS nota_media,
               round(percentile_cont(0.75) WITHIN GROUP (ORDER BY rating)::numeric, 2) AS nota_top25
        FROM market_restaurants WHERE category = %s""", (m["category"],))[0]
    meu = query(f"""
        SELECT round(avg(o.delivery_minutes)::numeric, 1) AS tempo_entrega_medio_min,
               (SELECT round(avg(rating)::numeric, 2) FROM reviews
                 WHERE merchant_id = %(m)s AND created_at >= {REF} - interval '30 days') AS nota_media
        FROM orders o WHERE o.merchant_id = %(m)s AND o.created_at >= {REF} - interval '30 days'""",
                {"m": merchant_id})[0]
    conv = lambda d: {k: (float(v) if v is not None and not isinstance(v, int) else v) for k, v in d.items()}  # noqa: E731
    return {"restaurante": m["name"], "categoria": m["category"],
            "fonte_mercado": "Restaurantes reais de Caruaru no iFood (dataset público do Kaggle, fev/2021)",
            "mercado_caruaru": conv(mercado), "seu_restaurante_ultimos_30d": conv(meu)}


TOOLS = {f.__name__: f for f in [resumo_vendas, vendas_por_item, atrasos, reclamacoes, comparar_mercado]}

# Declarações no formato de function calling do Gemini (merchant_id é injetado pelo servidor)
DECLARATIONS = [
    {"name": "resumo_vendas", "description": "Pedidos, faturamento, ticket médio e nota no período, comparando com o período anterior de mesmo tamanho.",
     "parameters": {"type": "object", "properties": {"dias": {"type": "integer", "description": "Tamanho do período em dias (padrão 14)"}}}},
    {"name": "vendas_por_item", "description": "Quantidade vendida e preço médio de cada item do cardápio, período atual vs anterior. Use para achar itens que caíram ou mudança de preço.",
     "parameters": {"type": "object", "properties": {"dias": {"type": "integer"}}}},
    {"name": "atrasos", "description": "Taxa de pedidos atrasados (e a do período anterior, para ver tendência) e os dias/turnos com mais atraso.",
     "parameters": {"type": "object", "properties": {"dias": {"type": "integer", "description": "Padrão 30"}}}},
    {"name": "reclamacoes", "description": "Temas das avaliações negativas/neutras (classificadas por IA), itens mais citados e exemplos de comentários. Temas: atraso, embalagem, preco, quantidade, item_errado, sabor, atendimento.",
     "parameters": {"type": "object", "properties": {"dias": {"type": "integer"}, "tema": {"type": "string", "description": "Opcional: filtrar por um tema"}}}},
    {"name": "comparar_mercado", "description": "Compara tempo de entrega e nota do restaurante com a média real da mesma categoria em Caruaru.",
     },
]
