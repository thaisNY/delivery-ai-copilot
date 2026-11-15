# Copiloto do Restaurante 🍽️🤖

[![CI/CD](https://github.com/thaisNY/delivery-ai-copilot/actions/workflows/ci.yml/badge.svg)](https://github.com/thaisNY/delivery-ai-copilot/actions/workflows/ci.yml)

Agente de IA generativa que ajuda donos de restaurantes parceiros de delivery a entender **por que as vendas mudaram** e **o que fazer a respeito**, cruzando pedidos, tempos de entrega e avaliações de clientes.

> "Por que minhas vendas caíram nas últimas duas semanas?"
>
> **Copiloto:** Seus pedidos caíram 28%. Nas sextas e sábados à noite, 70% das entregas atrasam (em média +20 min), e "atraso" e "embalagem" são os temas que mais aparecem nas avaliações negativas, com o *Combo Família* citado em boa parte delas. Sugestões: aumentar o tempo de preparo informado no pico de sexta/sábado, reforçar a equipe nesse turno e trocar a embalagem do combo por uma com lacre.

*(exemplo ilustrativo; a resposta real é gerada pelo modelo a partir dos dados)*

## Por que esse problema

Com a chegada de novos concorrentes ao delivery no Brasil, **reter restaurantes parceiros** virou estratégico: restaurante que vende mais e entende o próprio negócio não troca de plataforma. Hoje o dono de um restaurante pequeno tem dados (pedidos, avaliações), mas não tem tempo nem ferramenta para transformar isso em decisão. O copiloto faz essa ponte em linguagem natural.

## Arquitetura

```
 CSV público (restaurantes reais     Gerador sintético
 de Caruaru no iFood, fev/2021)      (pedidos + avaliações com padrões)
            │                                 │
            ▼                                 ▼
      ┌──────────────────── Pipeline (Python) ─────────────────────┐
      │ carga do mercado → avaliações → classificação com LLM       │
      │ (sentimento + temas, em lotes, saída JSON; fallback regras) │
      └──────────────────────────────┬──────────────────────────────┘
                                     ▼
                              PostgreSQL 16
                                     ▲
                 ferramentas SQL     │
   ┌──────────── FastAPI ────────────┴───────────────┐
   │ /api/chat → Agente (Gemini + function calling)  │
   │   resumo_vendas · vendas_por_item · atrasos ·   │
   │   reclamacoes · comparar_mercado                │
   │ /api/merchants/{id}/dashboard                   │
   └───────────────────────┬─────────────────────────┘
                           ▼
              React (Vite) · painel + chat
```

**Decisões de engenharia**
- **O LLM não inventa números.** Toda métrica vem de uma ferramenta SQL; o modelo só decide *o que consultar* e *interpreta* o resultado. O `merchant_id` é injetado pelo servidor, então o agente não consegue consultar outro restaurante mesmo se o usuário pedir. (A demo não tem login; em produção, o `merchant_id` viria do token de autenticação.)
- **Classificação como etapa de pipeline**, não em tempo de conversa: as avaliações são classificadas uma vez, em lote, e ficam no banco (mais barato, mais rápido e auditável, com a coluna `classified_by`).
- **Degradação graciosa:** sem chave de API, o classificador cai para regras e o chat responde num modo offline, então a demo nunca quebra.
- **Pronto para dados reais:** `app/connector.py` separa a fonte de dados. Os campos espelham o formato de uma API de parceiros (merchant / order / review). Para produção, basta implementar `MerchantApiSource` com o token do restaurante autorizado.
- **Defesa contra prompt injection:** comentários de clientes são tratados como dados no prompt do sistema, e o histórico do chat é validado (papéis, tamanho).
- **Classificador medido contra gabarito:** o gerador guarda o tema verdadeiro de cada avaliação, e o pipeline imprime a acurácia do LLM e das regras (`docker compose logs api`).
- **Avaliação do agente:** `evals/` tem casos com a ferramenta esperada e a causa plantada nos dados, medindo acerto de ferramenta e de conteúdo.

## Dados

| Fonte | Tipo | Uso |
|---|---|---|
| `data/restaurantes_caruaru_fev2021.csv` | **Real**: 1.015 restaurantes de Caruaru-PE no iFood (dataset público do Kaggle, fev/2021) | Benchmarks de mercado por categoria (tempo de entrega, taxa, nota) |
| `pipeline/generate.py` | **Sintético**: 3 restaurantes fictícios, 60 dias, ~3.800 pedidos e ~1.100 avaliações | Vendas, entregas e avaliações com padrões para o agente descobrir |

Padrões plantados: o *Sabor do Agreste* atrasa nas sextas e sábados à noite, tem embalagem vazando no Combo Família e queda de vendas recente; a *Pizzaria Alto do Moura* aumentou preços há ~15 dias; o *Açaí da Feira* é o grupo de controle.

## Como rodar

Pré-requisito: [Docker Desktop](https://www.docker.com/products/docker-desktop/).

1. Copie `.env.example` para `.env` e coloque sua chave gratuita do Gemini ([aistudio.google.com/apikey](https://aistudio.google.com/apikey)). Sem chave também funciona, em modo offline.
2. Suba tudo:
   ```bash
   docker compose up -d --build
   ```
   No Windows, é só dar dois cliques em `iniciar.cmd`.
3. Acesse:
   - Painel: http://localhost:5173
   - API (Swagger): http://localhost:8000/docs
   - Postgres: `localhost:5433` (usuário/senha/banco: `copiloto`)

Na primeira subida, a API cria o schema e roda o pipeline (com a chave, a classificação por LLM leva cerca de 1 minuto). Para recriar os dados: `docker compose down -v`.

**Rodar os testes** (unitários; os de integração rodam se houver `DATABASE_URL`):
```bash
cd backend && pip install -r requirements-dev.txt && pytest
```

**CI/CD:** a cada push, o GitHub Actions roda lint e testes contra um PostgreSQL real, compila o front, monta as imagens Docker e, na branch `main`, publica no GitHub Container Registry.

**Rodar a avaliação do agente:**
```bash
docker compose exec api python -m evals.run_evals
```

## Stack

Python 3.12 · FastAPI · pytest · GitHub Actions · PostgreSQL 16 · psycopg 3 · Gemini API (function calling, saída JSON) · React 18 · Vite · Recharts · Docker Compose

## Próximos passos

- Conector real com a API de parceiros (OAuth por loja) e sincronização incremental
- Alertas proativos ("seus atrasos de sexta subiram 40%"), enviados por WhatsApp
- Busca semântica (RAG) sobre os comentários, com pgvector
- Mais casos de avaliação e um LLM-as-judge para a qualidade das recomendações

---
Feito por **Thais Rodrigues** · [LinkedIn](https://www.linkedin.com/in/thais-rodrigues-queiroz/) · [GitHub](https://github.com/thaisNY)

*Projeto de portfólio, sem afiliação com o iFood.*
