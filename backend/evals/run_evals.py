"""Avaliação simples do agente.

Cada caso tem uma pergunta, as ferramentas que o agente DEVERIA chamar e palavras que a
resposta deveria conter (os padrões plantados nos dados sintéticos). Mede:
  * acerto de ferramenta: chamou todas as ferramentas esperadas?
  * acerto de conteúdo: a resposta menciona a causa plantada?

Uso (com a API rodando):  docker compose exec api python -m evals.run_evals
"""
import json
import sys
import time
from pathlib import Path

import httpx

API = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
CASES = json.loads((Path(__file__).parent / "cases.json").read_text(encoding="utf-8"))


def main():
    tool_ok = content_ok = 0
    for c in CASES:
        r = httpx.post(f"{API}/api/chat", json={"merchant_id": c["merchant_id"], "message": c["question"]}, timeout=120).json()
        called = {t["name"] for t in r.get("tool_calls", [])}
        answer = r.get("answer", "").lower()
        t_pass = set(c["expected_tools"]) <= called
        c_pass = any(k in answer for k in c["expected_keywords"])
        tool_ok += t_pass
        content_ok += c_pass
        time.sleep(5)  # respeita o limite da camada gratuita
        print(f"[{'OK ' if t_pass and c_pass else 'FALHOU'}] {c['question']}")
        print(f"      ferramentas: {sorted(called)} (esperado {c['expected_tools']}) | conteúdo: {'ok' if c_pass else 'faltou ' + str(c['expected_keywords'])}")
    n = len(CASES)
    print(f"\nModo: {r.get('mode')} | Ferramentas: {tool_ok}/{n} | Conteúdo: {content_ok}/{n}")


if __name__ == "__main__":
    main()
