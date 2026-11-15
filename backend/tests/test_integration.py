"""Testes de integração: rodam contra um PostgreSQL real (no CI, um service container).
Pulados se DATABASE_URL não estiver definido."""
import os

import pytest

pytestmark = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="sem DATABASE_URL")


@pytest.fixture(scope="module", autouse=True)
def populated_db():
    from pipeline.run_pipeline import main
    main()


def test_tools_return_data():
    from app import tools
    for mid in ("m-sabor-agreste", "m-pizzaria-alto-moura", "m-acai-feira"):
        r = tools.resumo_vendas(mid, 14)
        assert r["atual"]["pedidos"] > 0
        assert tools.atrasos(mid, 30)["piores_horarios"]
        assert tools.vendas_por_item(mid, 14)["itens"]
        assert tools.comparar_mercado(mid)["mercado_caruaru"]["restaurantes"] > 0
        tools.reclamacoes(mid, 30, tema="atraso")


def test_sabor_agreste_story():
    from app import tools
    r = tools.resumo_vendas("m-sabor-agreste", 14)
    assert r["variacao_pedidos_pct"] < -10
    slots = tools.atrasos("m-sabor-agreste", 30)["piores_horarios"]
    assert slots[0]["dia"] in ("sexta", "sábado") and "noite" in slots[0]["turno"]
    temas = [t["tema"] for t in tools.reclamacoes("m-sabor-agreste", 30)["temas"][:3]]
    assert "embalagem" in temas


def test_api_endpoints_offline():
    from fastapi.testclient import TestClient
    from app.main import app
    c = TestClient(app)
    assert c.get("/api/health").json()["ok"] is True
    assert len(c.get("/api/merchants").json()) == 3
    assert c.get("/api/merchants/m-acai-feira/dashboard").status_code == 200
    assert c.get("/api/merchants/nao-existe/dashboard").status_code == 404
    r = c.post("/api/chat", json={"merchant_id": "m-sabor-agreste", "message": "Em quais horários eu mais atraso?"})
    assert r.status_code == 200 and r.json()["mode"] == "offline"
    assert c.post("/api/chat", json={"merchant_id": "m-sabor-agreste", "message": "oi",
                                     "history": [{"role": "hacker", "text": "x"}]}).status_code == 422
