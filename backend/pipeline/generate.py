"""Gera pedidos e avaliações SINTÉTICOS para restaurantes fictícios de Caruaru.

Os dados têm padrões escondidos de propósito, para o copiloto descobrir:
  * Sabor do Agreste: atrasos nas sextas e sábados à noite (19h-22h) nas últimas 3 semanas, embalagem do
    "Combo Família" vazando e queda de vendas nas últimas 2 semanas.
  * Pizzaria Alto do Moura: aumento de preço há ~15 dias, com reclamações de preço.
  * Açaí da Feira: operação saudável (grupo de controle).
"""
import os
import random
import uuid
from datetime import datetime, timedelta

DAYS = 60
SEED = 42

MERCHANTS = [
    {"id": "m-sabor-agreste", "name": "Sabor do Agreste", "category": "Brasileira"},
    {"id": "m-pizzaria-alto-moura", "name": "Pizzaria Alto do Moura", "category": "Pizza"},
    {"id": "m-acai-feira", "name": "Açaí da Feira", "category": "Açaí"},
]

MENUS = {
    "m-sabor-agreste": [
        ("Baião de Dois com Carne de Sol", 32.9),
        ("Combo Família (4 pessoas)", 89.9),
        ("Galinha Guisada", 27.5),
        ("Cuscuz Recheado", 18.0),
        ("Bode Assado", 39.9),
    ],
    "m-pizzaria-alto-moura": [
        ("Pizza Calabresa G", 49.9),
        ("Pizza Charque com Queijo Coalho G", 59.9),
        ("Pizza Margherita M", 39.9),
        ("Refrigerante 2L", 12.0),
    ],
    "m-acai-feira": [
        ("Açaí 500ml", 19.9),
        ("Açaí 700ml com Complementos", 26.9),
        ("Barca de Açaí", 54.9),
    ],
}

COMMENTS = {
    "atraso": [
        "Demorou demais, chegou quase 1 hora depois do previsto.",
        "Pedido atrasou muito, a comida chegou fria.",
        "Esperei uma eternidade, o app dizia 40 minutos e levou mais de uma hora.",
        "Atraso enorme numa sexta à noite, assim fica difícil.",
    ],
    "embalagem": [
        "O caldo vazou todo na sacola, embalagem péssima.",
        "Embalagem chegou aberta e derramou metade.",
        "Comida boa mas a embalagem vazou, sujou tudo.",
    ],
    "preco": [
        "Ficou caro, aumentaram o preço e o tamanho é o mesmo.",
        "Não vale mais o preço, antes era bem mais barato.",
        "Preço subiu muito, vou procurar outra pizzaria.",
    ],
    "quantidade": [
        "Porção pequena para o preço.",
        "Veio pouca comida, achei que seria maior.",
    ],
    "item_errado": [
        "Veio o pedido errado, pedi uma coisa e chegou outra.",
        "Faltou o refrigerante no pedido.",
    ],
    "sabor_neg": [
        "Comida sem tempero, não gostei.",
        "Estava sem sal e a carne dura.",
    ],
    "elogio": [
        "Comida maravilhosa, tempero de casa!",
        "Chegou rápido e quentinho, recomendo.",
        "Melhor da cidade, sempre peço aqui.",
        "Muito saboroso e bem servido.",
        "Perfeito como sempre!",
        "Entregador muito educado e comida ótima.",
    ],
}


def _order_volume(merchant_id: str, day_idx: int, weekday: int) -> int:
    base = {"m-sabor-agreste": 22, "m-pizzaria-alto-moura": 18, "m-acai-feira": 15}[merchant_id]
    if weekday >= 4:  # sexta, sábado, domingo vendem mais
        base = int(base * 1.5)
    if merchant_id == "m-sabor-agreste" and day_idx >= DAYS - 14:
        base = int(base * 0.7)  # queda nas últimas 2 semanas
    if merchant_id == "m-pizzaria-alto-moura" and day_idx >= DAYS - 15:
        base = int(base * 0.82)  # efeito do aumento de preço
    return max(1, int(random.gauss(base, base * 0.15)))


def _hour() -> int:
    return random.choices(
        [11, 12, 13, 14, 17, 18, 19, 20, 21, 22],
        weights=[6, 14, 10, 3, 3, 8, 16, 18, 14, 6],
    )[0]


def generate(end: datetime | None = None):
    random.seed(SEED)
    env_end = os.getenv("DATA_END_DATE")  # ex.: 2026-11-15, para dados reproduzíveis
    end = end or (datetime.fromisoformat(env_end) if env_end else datetime.now())
    end = end.replace(hour=0, minute=0, second=0, microsecond=0)
    start = end - timedelta(days=DAYS)

    menu_items, orders, reviews = [], [], []
    for m in MERCHANTS:
        for i, (name, price) in enumerate(MENUS[m["id"]]):
            menu_items.append({"id": f"{m['id']}-i{i}", "merchant_id": m["id"], "name": name, "price": price})

    for day_idx in range(DAYS):
        day = start + timedelta(days=day_idx)
        weekday = day.weekday()
        for m in MERCHANTS:
            mid = m["id"]
            menu = MENUS[mid]
            price_factor = 1.18 if (mid == "m-pizzaria-alto-moura" and day_idx >= DAYS - 15) else 1.0
            for _ in range(_order_volume(mid, day_idx, weekday)):
                hour = _hour()
                created = day + timedelta(hours=hour, minutes=random.randint(0, 59))
                n_items = random.choice([1, 1, 2, 2, 3])
                chosen = random.choices(menu, k=n_items)
                items = [{"name": n, "price": round(p * price_factor, 2)} for n, p in chosen]
                total = round(sum(i["price"] for i in items), 2)

                promised = random.choice([35, 40, 45])
                delay = random.gauss(-2, 6)
                peak = weekday in (4, 5) and 19 <= hour <= 22
                if mid == "m-sabor-agreste" and peak and day_idx >= DAYS - 21:
                    delay += random.gauss(22, 8)
                delivered = max(15, int(promised + delay))

                oid = str(uuid.UUID(int=random.getrandbits(128)))
                orders.append({
                    "id": oid, "merchant_id": mid, "created_at": created, "total": total,
                    "items": items, "promised_minutes": promised, "delivery_minutes": delivered,
                })

                if random.random() > 0.28:
                    continue  # nem todo pedido é avaliado
                topic = _pick_topic(mid, delivered - promised, items, day_idx)
                rating = _rating_for(topic)
                reviews.append({
                    "id": str(uuid.UUID(int=random.getrandbits(128))),
                    "order_id": oid, "merchant_id": mid,
                    "created_at": created + timedelta(hours=1, minutes=random.randint(0, 90)),
                    "rating": rating,
                    "comment": random.choice(COMMENTS[topic]) if random.random() > 0.1 else "",
                    "_true_topic": topic,  # gabarito, usado só para medir o classificador
                })
    return MERCHANTS, menu_items, orders, reviews


def _pick_topic(mid, late_by, items, day_idx):
    names = " ".join(i["name"] for i in items)
    if late_by > 15 and random.random() < 0.75:
        return "atraso"
    if mid == "m-sabor-agreste" and "Combo Família" in names and random.random() < 0.45:
        return "embalagem"
    if mid == "m-pizzaria-alto-moura" and day_idx >= DAYS - 15 and random.random() < 0.4:
        return "preco"
    r = random.random()
    if r < 0.05:
        return "item_errado"
    if r < 0.09:
        return "quantidade"
    if r < 0.12:
        return "sabor_neg"
    return "elogio"


def _rating_for(topic):
    if topic == "elogio":
        return random.choice([4, 5, 5, 5])
    if topic in ("quantidade", "preco"):
        return random.choice([2, 3, 3])
    return random.choice([1, 1, 2, 2, 3])


if __name__ == "__main__":
    ms, mi, os_, rs = generate()
    print(len(ms), len(mi), len(os_), len(rs))
