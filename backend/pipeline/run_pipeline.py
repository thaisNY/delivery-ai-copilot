"""Pipeline de dados: schema -> mercado real (CSV) -> dados sintéticos -> classificação -> Postgres.

Roda na subida do container. Se o banco já tiver dados, não faz nada
(para recriar tudo: docker compose down -v).
"""
import csv
import os
from pathlib import Path

from psycopg.types.json import Jsonb

from app.db import conn
from pipeline.classify import classifier_accuracy, classify_all
from pipeline.generate import generate

MARKET_CSV = os.getenv("MARKET_CSV", str(Path(__file__).resolve().parents[2] / "data" / "restaurantes_caruaru_fev2021.csv"))


def _num(v, default=None):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def load_market(c) -> int:
    rows = []
    with open(MARKET_CSV, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rating = _num(r["rating"], 0) or None  # 0.0 no dataset = sem nota
            rows.append((r["name"], r["category"], _num(r["delivery_fee"]), int(_num(r["delivery_time"], 0)),
                         _num(r["minimumOrderValue"]), r["price_range"], rating))
    with c.cursor() as cur:
        cur.executemany(
            "INSERT INTO market_restaurants (name, category, delivery_fee, delivery_time, minimum_order, price_range, rating)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s)", rows)
    return len(rows)


def main():
    schema = (Path(__file__).parent / "schema.sql").read_text(encoding="utf-8")
    with conn() as c:
        c.execute(schema)
        if c.execute("SELECT count(*) AS n FROM orders").fetchone()["n"] > 0:
            print("[pipeline] banco já populado, pulando")
            return

        if Path(MARKET_CSV).exists():
            print(f"[pipeline] mercado real: {load_market(c)} restaurantes de Caruaru")
        else:
            print(f"[pipeline] AVISO: {MARKET_CSV} não encontrado; benchmarks de mercado ficarão vazios")

        merchants, menu_items, orders, reviews = generate()
        print(f"[pipeline] sintéticos: {len(orders)} pedidos, {len(reviews)} avaliações")
        classify_all(reviews)
        by = {}
        for r in reviews:
            by[r["classified_by"]] = by.get(r["classified_by"], 0) + 1
        print(f"[pipeline] classificação: {by}")
        print(f"[pipeline] acurácia contra o gabarito: {classifier_accuracy(reviews)}")

        with c.cursor() as cur:
            cur.executemany("INSERT INTO merchants VALUES (%(id)s, %(name)s, %(category)s)", merchants)
            cur.executemany("INSERT INTO menu_items VALUES (%(id)s, %(merchant_id)s, %(name)s, %(price)s)", menu_items)
            cur.executemany(
                "INSERT INTO orders VALUES (%s,%s,%s,%s,%s,%s,%s)",
                [(o["id"], o["merchant_id"], o["created_at"], o["total"], Jsonb(o["items"]),
                  o["promised_minutes"], o["delivery_minutes"]) for o in orders])
            cur.executemany(
                "INSERT INTO reviews VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                [(r["id"], r["order_id"], r["merchant_id"], r["created_at"], r["rating"], r["comment"],
                  r["sentiment"], r["topics"], r["classified_by"]) for r in reviews])
        print("[pipeline] pronto")


if __name__ == "__main__":
    main()
