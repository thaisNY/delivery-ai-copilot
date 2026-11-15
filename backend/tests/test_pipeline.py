"""Testes unitários do pipeline (sem banco e sem LLM)."""
from datetime import datetime, timedelta

from pipeline.classify import classifier_accuracy, classify_all, classify_rules
from pipeline.generate import DAYS, generate

END = datetime(2026, 11, 15)


def _data():
    return generate(end=END)


def test_generate_is_deterministic():
    _, _, o1, r1 = generate(end=END)
    _, _, o2, r2 = generate(end=END)
    assert [o["id"] for o in o1] == [o["id"] for o in o2]
    assert len(r1) == len(r2)


def test_volumes_and_date_range():
    merchants, menu, orders, reviews = _data()
    assert len(merchants) == 3
    assert len(orders) > 3000
    assert 0.2 < len(reviews) / len(orders) < 0.35
    assert min(o["created_at"] for o in orders) >= END - timedelta(days=DAYS)
    assert max(o["created_at"] for o in orders) < END


def test_planted_pattern_late_deliveries_get_worse():
    _, _, orders, _ = _data()
    sabor = [o for o in orders if o["merchant_id"] == "m-sabor-agreste"]

    def late_pct(a, b):
        sel = [o for o in sabor if END - timedelta(days=a) <= o["created_at"] < END - timedelta(days=b)]
        return sum(o["delivery_minutes"] > o["promised_minutes"] + 10 for o in sel) / len(sel)

    assert late_pct(14, 0) > late_pct(56, 42) + 0.03


def test_planted_pattern_sales_drop():
    _, _, orders, _ = _data()
    sabor = [o for o in orders if o["merchant_id"] == "m-sabor-agreste"]
    recent = sum(o["created_at"] >= END - timedelta(days=14) for o in sabor)
    previous = sum(END - timedelta(days=28) <= o["created_at"] < END - timedelta(days=14) for o in sabor)
    assert recent < previous * 0.85


def test_rules_classifier():
    assert classify_rules("Demorou demais, chegou fria", 1) == {"sentiment": "negativo", "topics": ["atraso"]}
    assert "embalagem" in classify_rules("A embalagem vazou toda", 2)["topics"]
    assert classify_rules("Perfeito como sempre!", 5)["sentiment"] == "positivo"
    assert classify_rules("", 1)["topics"] == ["sem_comentario"]


def test_classify_all_offline_accuracy():
    _, _, _, reviews = _data()
    classify_all(reviews)  # sem GEMINI_API_KEY -> regras
    assert all(r["classified_by"] == "regras" for r in reviews)
    acc = classifier_accuracy(reviews)["regras"]
    ok, n = map(int, acc.split()[0].split("/"))
    assert ok / n > 0.9
