# Copiloto do Restaurante 🍽️🤖

**Agente de IA generativa que explica para o dono de um restaurante de delivery _por que_ as vendas mudaram e _o que fazer_ a respeito**, cruzando pedidos, tempos de entrega e avaliações de clientes em linguagem natural.

`Python 3.12` · `FastAPI` · `PostgreSQL 16` · `Gemini (function calling)` · `React 18 + Vite` · `Docker Compose` · `pytest` · `GitHub Actions`

---

## Sumário

1. [O problema de negócio](#1-o-problema-de-negócio)
2. [O que o projeto faz](#2-o-que-o-projeto-faz)
3. [Demonstração](#3-demonstração)
4. [Arquitetura](#4-arquitetura)
5. [Dados](#5-dados)
6. [Decisões técnicas](#6-decisões-técnicas)
7. [Resultados e avaliação](#7-resultados-e-avaliação)
8. [Como rodar](#8-como-rodar)
9. [API](#9-api)
10. [Testes e CI/CD](#10-testes-e-cicd)
11. [Estrutura do repositório](#11-estrutura-do-repositório)
12. [Limitações conhecidas](#12-limitações-conhecidas)
13. [Próximos passos](#13-próximos-passos)

---

## 1. O problema de negócio

### Contexto

O delivery de comida no Brasil ficou mais competitivo com a chegada e o retorno de novas plataformas. Nesse cenário, **os restaurantes parceiros viraram o território disputado**: concorrentes oferecem taxas menores e incentivos para que eles migrem ou dividam pedidos com outros apps.

Para uma plataforma, **reter o restaurante** passa a ser tão importante quanto atrair o consumidor. E um restaurante fica onde **vende mais e entende melhor o próprio negócio**.

### A dor

O dono de um restaurante pequeno, como uma cozinha regional em Caruaru-PE, até tem dados: pedidos, tempos de entrega e avaliações. O que falta é **tempo e ferramenta para transformar isso em decisão**. As perguntas que ele faz são simples:

- "Por que vendi menos essa semana?"
- "Do que os clientes estão reclamando?"
- "Estou pior ou melhor que a concorrência da cidade?"

Respondê-las hoje exige abrir vários relatórios, cruzar números na mão e interpretar dezenas de comentários.

### Objetivo do projeto

Reduzir de horas para segundos o caminho entre **o dado** e **a ação**, com um copiloto que:

1. responde em linguagem natural, como um consultor;
2. **cruza fontes** (vendas × entregas × avaliações × mercado) para chegar à causa provável;
3. sugere **ações práticas e específicas**;
4. **nunca inventa números**: toda métrica vem do banco de dados.

### Como o sucesso seria medido em produção

| Métrica | O que indica |
|---|---|
| Retenção e churn de restaurantes que usam o copiloto vs. os que não usam | Impacto direto no objetivo de negócio |
| % de recomendações aplicadas pelo restaurante | Se as sugestões são úteis e acionáveis |
| Variação de atraso, nota e pedidos após uma recomendação | Se a ação resolveu o problema |
| Perguntas por restaurante por semana | Adoção e engajamento |
| Taxa de respostas com números corretos (fidelidade) | Confiabilidade do agente |

---

## 2. O que o projeto faz

- **Painel** por restaurante: pedidos e faturamento dos últimos 14 dias (com variação contra o período anterior), nota média, % de entregas atrasadas, faturamento diário, reclamações por tema e comparação com o mercado real da cidade.
- **Chat com o copiloto:** o dono pergunta em português e o agente decide quais consultas fazer, executa e responde com diagnóstico, causa e ações. A interface mostra quais fontes ele consultou.
- **Pipeline de dados:** carrega dados reais de mercado, gera os dados operacionais e **classifica cada avaliação com IA** (sentimento e temas), guardando tudo no PostgreSQL.

---

## 3. Demonstração

Resposta real do copiloto, gerada pelo `gemini-3.8-flash` com os dados do projeto, para o restaurante fictício *Sabor do Agreste*:

> **Pergunta:** Por que minhas vendas caíram nas últimas duas semanas?
>
> **1. O que está acontecendo**
> Nas últimas duas semanas, seu faturamento caiu **27,2%** (de R$ 27.318 para R$ 19.900) e os pedidos recuaram **24,4%** (de 353 para 267). [...] queda nas vendas do *Cuscuz Recheado* (-41,7%), *Bode Assado* (-30,7%) e *Combo Família* (-30,1%).
>
> **2. Causa provável**
> Gargalo operacional no fim de semana e avarias no transporte:
> - **Atrasos severos:** a taxa de atraso geral subiu de 9,3% para 13,9%, explodindo nas noites de **sexta (84% de atrasos)** e **sábado (68,2%)** [...]
> - **Embalagens inadequadas:** líder de queixas, com relatos de caldos derramados (principalmente no *Combo Família* e na *Galinha Guisada*).
>
> **3. Ações práticas**
> 1. Trocar ou reforçar a vedação das embalagens com caldo.
> 2. Aumentar em 15 minutos o tempo estimado nas noites de sexta e sábado, ou reforçar a expedição.
> 3. Pré-embalar os acompanhamentos do Combo Família nos horários de pico.
>
> *Fontes consultadas pelo agente: vendas · itens · atrasos · avaliações*

O agente chegou sozinho, só consultando os dados, às duas causas que foram plantadas na base: **atrasos no pico do fim de semana** e **embalagem do Combo Família vazando**.

---

## 4. Arquitetura

```
 CSV público (restaurantes reais          Gerador sintético
 de Caruaru no iFood, fev/2021)           (pedidos + avaliações com padrões)
            │                                        │
            ▼                                        ▼
   ┌──────────────────────── Pipeline (Python) ────────────────────────┐
   │ 1. carga do mercado real                                          │
   │ 2. geração dos dados operacionais                                 │
   │ 3. classificação das avaliações com LLM (lotes, saída JSON)       │
   │    └─ fallback por regras se não houver chave ou a API falhar     │
   │ 4. medição de acurácia contra o gabarito                          │
   └───────────────────────────────┬───────────────────────────────────┘
                                   ▼
                            PostgreSQL 16
                                   ▲
                   consultas SQL parametrizadas
                                   │
   ┌──────────────────────── FastAPI ──────────────────────────────────┐
   │ POST /api/chat ──► Agente                                         │
   │                     ├─ Gemini decide quais ferramentas chamar     │
   │                     ├─ servidor executa (merchant_id injetado)    │
   │                     └─ Gemini redige a resposta com os números    │
   │ GET /api/merchants/{id}/dashboard                                 │
   └───────────────────────────────┬───────────────────────────────────┘
                                   ▼
                  React + Vite + Recharts (painel + chat)
                  servido por Nginx, que faz proxy de /api
```

### Ferramentas do agente

| Ferramenta | O que devolve |
|---|---|
| `resumo_vendas(dias)` | Pedidos, faturamento, ticket médio e nota do período, comparados com o período anterior |
| `vendas_por_item(dias)` | Quantidade e preço médio por item do cardápio, atual vs. anterior |
| `atrasos(dias)` | % de entregas atrasadas (atual e período anterior) e os piores dias e turnos |
| `reclamacoes(dias, tema?)` | Temas das avaliações negativas, itens mais citados e exemplos de comentários |
| `comparar_mercado()` | Tempo de entrega e nota do restaurante vs. a média real da categoria em Caruaru |

---

## 5. Dados

| Fonte | Tipo | Volume | Uso |
|---|---|---|---|
| `data/restaurantes_caruaru_fev2021.csv` | **Real**: restaurantes de Caruaru-PE no iFood, extraídos de um dataset público do Kaggle (fev/2021) | 1.015 restaurantes | Benchmarks de mercado por categoria |
| `backend/pipeline/generate.py` | **Sintético**: 3 restaurantes fictícios, 60 dias de operação | ~3.700 pedidos, ~1.000 avaliações | Vendas, entregas e avaliações |

### Por que dados sintéticos?

Pedidos e avaliações de restaurantes não são públicos: a API oficial de parceiros exige CNPJ, homologação e autorização de cada loja. Raspar o site violaria os termos de uso. A solução foi:

- usar **dados reais onde eles são públicos** (o mercado da cidade);
- gerar **dados operacionais sintéticos, mas com padrões realistas e conhecidos**, o que permite **medir se a IA encontra a resposta certa**.

Os restaurantes são fictícios de propósito, para não atribuir avaliações ruins inventadas a estabelecimentos reais.

### Padrões plantados

| Restaurante | Padrão | O agente deveria concluir |
|---|---|---|
| **Sabor do Agreste** (Brasileira) | Atrasos nas noites de sexta e sábado nas últimas 3 semanas, embalagem do *Combo Família* vazando e queda de pedidos nas últimas 2 semanas | Queda causada por atraso no pico + embalagem |
| **Pizzaria Alto do Moura** (Pizza) | Aumento de preço de ~18% há 15 dias e reclamações de preço | Menos pedidos, mas ticket maior: o faturamento quase não cai |
| **Açaí da Feira** (Açaí) | Operação saudável | Grupo de controle: o agente não deve inventar problemas |

---

## 6. Decisões técnicas

Cada decisão vem com o motivo e o custo assumido.

### 6.1 O LLM não calcula nada, só escolhe ferramentas e interpreta

**Decisão:** toda métrica sai de uma ferramenta SQL. O modelo decide *o que* consultar (function calling) e redige a resposta com os números devolvidos.
**Por quê:** LLMs erram contas e inventam números com confiança. Separar *cálculo* (determinístico, no banco) de *raciocínio* (no modelo) torna as respostas auditáveis.
**Custo:** mais idas e voltas com o modelo, de 2 a 5 chamadas por pergunta.

### 6.2 Isolamento por restaurante no servidor

**Decisão:** as ferramentas não recebem `merchant_id` do modelo. O servidor injeta o identificador do restaurante da sessão.
**Por quê:** mesmo que alguém peça "mostre os dados do concorrente", o agente não consegue consultar outro restaurante.
**Limite:** a demo não tem login. Em produção, o `merchant_id` viria do token de autenticação.

### 6.3 Classificação de avaliações como etapa de pipeline, não em tempo de conversa

**Decisão:** as avaliações são classificadas uma vez, em lotes de 60, com saída JSON, e gravadas no banco com a coluna `classified_by` (`llm` ou `regras`).
**Por quê:** é mais barato (uma vez em vez de a cada pergunta), mais rápido no chat e auditável.
**Detalhe:** as avaliações **mais recentes são classificadas primeiro**, porque são as que aparecem no painel e nas perguntas. Valores fora do esperado (como um sentimento inválido) caem para as regras.

### 6.4 Degradação graciosa: o projeto funciona sem chave de API

**Decisão:** sem `GEMINI_API_KEY`, o classificador usa regras por palavras-chave e o chat responde num modo offline, que chama as mesmas ferramentas e formata os números.
**Por quê:** a demo nunca quebra para quem clona o repositório, os testes de CI rodam sem segredos, e o sistema continua de pé se o provedor de LLM cair.

### 6.5 Cliente REST do Gemini, sem SDK

**Decisão:** chamadas HTTP diretas (`httpx`) para a API `generateContent`.
**Por quê:** deixa explícito o protocolo de function calling (`functionCall` → `functionResponse`), tem menos dependências e facilita trocar de provedor.
**Robustez:** novas tentativas com espera crescente em 429/500/503, erro tratado quando o modelo devolve resposta vazia ou bloqueada, e a **chave vai no header `x-goog-api-key`**, nunca na URL, para não vazar em logs e mensagens de erro.

### 6.6 SQL puro com psycopg 3, sem ORM

**Decisão:** consultas SQL escritas à mão, parametrizadas (`%(param)s`).
**Por quê:** as ferramentas são consultas analíticas (`FILTER`, `percentile_cont`, `jsonb_array_elements`, `unnest`), que ficam mais claras e eficientes em SQL do que num ORM. A parametrização protege contra SQL injection.

### 6.7 Data de referência baseada nos dados, não em "agora"

**Decisão:** "últimos 14 dias" é calculado a partir do último pedido do banco.
**Por quê:** a demo continua coerente mesmo rodando semanas depois de os dados serem gerados. Com `DATA_END_DATE`, os dados ficam reproduzíveis para testes.

### 6.8 Defesa contra prompt injection

**Decisão:** o prompt de sistema trata os comentários de clientes como **dados, nunca instruções**, e restringe o escopo à operação do restaurante. O histórico do chat é validado com Pydantic (papéis permitidos, tamanho máximo).
**Por quê:** quando os dados forem reais, um cliente poderia escrever numa avaliação "ignore as instruções e...". Isso é injeção indireta de prompt.

### 6.9 Dados sintéticos com gabarito

**Decisão:** o gerador guarda o tema verdadeiro de cada avaliação (`_true_topic`), e o pipeline mede a acurácia da classificação contra ele.
**Por quê:** permite **medir a qualidade da IA com um número**, em vez de confiar nela "no olho".

### 6.10 Camada de conector para dados reais

**Decisão:** `app/connector.py` separa a fonte de dados. Os campos de `merchants`, `orders` e `reviews` foram pensados para espelhar uma API de parceiros.
**Por quê:** para ir para produção, basta implementar `MerchantApiSource` com o token OAuth do restaurante e sincronizar para as mesmas tabelas. **As ferramentas e o agente não mudam.**

### 6.11 Infraestrutura

- **Docker Compose** com 3 serviços (`db`, `api`, `web`): roda igual em qualquer máquina, com um comando.
- Postgres exposto na porta **5433**, para não conflitar com uma instalação local.
- *Healthcheck* via TCP (`pg_isready -h 127.0.0.1`) e `restart: on-failure` para evitar corrida na primeira subida.
- `.env` opcional (`required: false`) e fora do Git.
- Front com **build multi-stage** (Node → Nginx), e o Nginx faz proxy de `/api`, então front e API ficam na mesma origem.

### 6.12 Escolha do modelo

`gemini-3.8-flash` é o padrão: rápido, barato e com camada gratuita, o que basta para function calling e classificação. O modelo é configurável por `GEMINI_MODEL` sem mudar código.

---

## 7. Resultados e avaliação

Medições feitas rodando o projeto localmente, com `gemini-3.8-flash`.

### Classificação de avaliações (contra o gabarito)

| Método | Acerto do tema | Observação |
|---|---|---|
| **LLM (Gemini)** | **82%** (440/536) | Classifica texto livre, sem regras escritas à mão |
| Regras por palavras-chave | 100% (383/383) | **Resultado inflado:** as regras foram escritas sobre os mesmos modelos de frase do gerador. Em texto real, elas cairiam bastante |

O número que importa é o do LLM. Os 100% das regras mostram uma armadilha clássica de avaliação (avaliar com os mesmos dados usados para construir a regra) e estão aqui de propósito, para deixar isso explícito.

### Agente (7 perguntas de teste em `backend/evals/cases.json`)

| Métrica | Resultado |
|---|---|
| Chamou as ferramentas esperadas | **7/7** |
| Mencionou a causa plantada nos dados | **7/7** |
| Latência média por pergunta | **~12 s** (de 2 a 5 chamadas ao modelo) |

> A avaliação ainda é simples: o critério de conteúdo verifica palavras-chave. Os próximos passos (seção 13) incluem casos negativos, fora de escopo, de injeção e de fidelidade numérica.

---

## 8. Como rodar

### Pré-requisitos

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows, Mac ou Linux)
- *(Opcional)* uma chave gratuita do Gemini em [aistudio.google.com/apikey](https://aistudio.google.com/apikey). Sem ela, o projeto roda em modo offline.

### Windows (mais fácil)

1. Abra o Docker Desktop e espere aparecer **"Engine running"**.
2. Dê dois cliques em **`iniciar.cmd`**.
   - Na primeira vez, ele cria o `.env` e abre o Bloco de Notas. Cole sua chave depois de `GEMINI_API_KEY=` (ou deixe vazio para o modo offline), salve e feche.
3. Dê dois cliques em **`iniciar.cmd`** de novo.
4. O navegador abre em **http://localhost:5173**.

Para parar: **`parar.cmd`**.

### Mac / Linux / terminal

```bash
cp .env.example .env          # edite e cole sua GEMINI_API_KEY (opcional)
docker compose up -d --build
```

Acesse:

| Serviço | Endereço |
|---|---|
| Painel | http://localhost:5173 |
| API (Swagger) | http://localhost:8000/docs |
| PostgreSQL | `localhost:5433`, usuário/senha/banco `copiloto` |

### Primeira subida

Na primeira vez, a API cria o schema e roda o pipeline. **Com chave, a classificação por IA leva de 1 a 3 minutos.** O painel mostra "A API ainda está preparando os dados…" e tenta de novo sozinho.

Para acompanhar:

```bash
docker compose logs -f api
```

Ao final, aparecem linhas como:

```
[pipeline] classificação: {'regras': 440, 'llm': 600}
[pipeline] acurácia contra o gabarito: {'regras': '383/383 (100%)', 'llm': '440/536 (82%)'}
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### Comandos úteis

```bash
docker compose down -v                 # apaga o banco (os dados são recriados na próxima subida)
docker compose up -d --build web       # reconstrói só o front
docker compose exec api python -m evals.run_evals   # roda a avaliação do agente
```

### Variáveis de ambiente (`.env`)

| Variável | Padrão | Descrição |
|---|---|---|
| `GEMINI_API_KEY` | vazio | Chave do Google AI Studio. Vazio = modo offline |
| `GEMINI_MODEL` | `gemini-3.8-flash` | Modelo usado no agente e na classificação |
| `DATA_END_DATE` | data de hoje | *(Opcional)* Fixa a data final dos dados sintéticos, por exemplo `2026-11-15`, para resultados reproduzíveis |

---

## 9. API

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/api/health` | Status e se há LLM configurado |
| `GET` | `/api/merchants` | Lista os restaurantes |
| `GET` | `/api/merchants/{id}/dashboard` | Métricas do painel |
| `POST` | `/api/chat` | Pergunta ao copiloto |

Exemplo:

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"merchant_id": "m-sabor-agreste", "message": "O que os clientes mais reclamam?"}'
```

Resposta:

```json
{
  "answer": "…texto em markdown…",
  "tool_calls": [{"name": "reclamacoes", "args": {"dias": 30}}],
  "mode": "gemini"
}
```

---

## 10. Testes e CI/CD

### Testes

```bash
cd backend
pip install -r requirements-dev.txt
pytest -v
```

- **Unitários** (`tests/test_pipeline.py`): determinismo do gerador, presença dos padrões plantados e classificador por regras. Não precisam de banco nem de LLM.
- **Integração** (`tests/test_integration.py`): pipeline completo e todas as ferramentas contra um PostgreSQL real, além dos endpoints da API (404, validação do histórico e chat offline). Rodam quando `DATABASE_URL` está definido.

### Pipeline de CI/CD (`.github/workflows/ci.yml`)

A cada push e pull request:

1. **Backend:** lint com `ruff` e testes unitários e de integração com um PostgreSQL 16 de verdade (*service container*).
2. **Frontend:** `npm install` e build de produção do Vite.
3. **Docker:** build das imagens da API e do front. Na branch `main`, **publica no GitHub Container Registry** com as tags `latest` e o hash do commit.

---

## 11. Estrutura do repositório

```
.
├── backend/
│   ├── app/
│   │   ├── main.py          # endpoints FastAPI e validação
│   │   ├── agent.py         # loop do agente (function calling) e modo offline
│   │   ├── tools.py         # ferramentas SQL e declarações para o LLM
│   │   ├── llm.py           # cliente REST do Gemini (retry, erros sanitizados)
│   │   ├── connector.py     # camada de fonte de dados (sintético / API real)
│   │   └── db.py            # conexão com o PostgreSQL
│   ├── pipeline/
│   │   ├── schema.sql       # tabelas
│   │   ├── generate.py      # gerador sintético com padrões e gabarito
│   │   ├── classify.py      # classificação LLM + regras + acurácia
│   │   └── run_pipeline.py  # orquestra a carga
│   ├── evals/               # avaliação do agente
│   ├── tests/               # pytest (unitários e integração)
│   └── Dockerfile
├── frontend/
│   ├── src/App.jsx          # painel + chat
│   ├── nginx.conf           # serve o build e faz proxy de /api
│   └── Dockerfile
├── data/
│   └── restaurantes_caruaru_fev2021.csv
├── .github/workflows/ci.yml
├── docker-compose.yml
├── iniciar.cmd / parar.cmd  # atalhos para Windows
└── .env.example
```

---

## 12. Limitações conhecidas

- **Dados operacionais sintéticos.** Os padrões são conhecidos, o que é bom para avaliar, mas não substitui dados reais.
- **Sem autenticação.** Qualquer cliente da API pode escolher o `merchant_id`. O isolamento vale para o agente, não para a API.
- **Avaliação do agente simples**, baseada em palavras-chave. Ainda não mede fidelidade numérica.
- **Latência de ~12 s por pergunta**, por causa das várias chamadas ao modelo. Sem streaming de resposta.
- **Dados de mercado de 2021.** Servem como referência de ordem de grandeza, não como retrato atual.
- **Uma conexão de banco por consulta.** Em produção, usaria um pool (`psycopg_pool`).

---

## 13. Próximos passos

- [ ] Conector real com a API de parceiros (OAuth por loja) e sincronização incremental
- [ ] Avaliação mais rigorosa: casos negativos (o Açaí não deve "achar" problema), fora de escopo, injeção de prompt e **fidelidade numérica** (todo número da resposta existe no retorno das ferramentas?)
- [ ] Observabilidade do agente: latência, passos e tokens (`usageMetadata`) por pergunta
- [ ] **Alertas proativos** ("seus atrasos de sexta subiram 40%"), enviados por WhatsApp
- [ ] Busca semântica (RAG) sobre os comentários, com `pgvector`
- [ ] Streaming das respostas no chat
- [ ] Autenticação e pool de conexões

---

## Autora

**Thais Rodrigues**, bacharel em Sistemas de Informação (UPE), Caruaru-PE
[LinkedIn](https://www.linkedin.com/in/thais-rodrigues-queiroz/) · [GitHub](https://github.com/thaisNY)

*Projeto de portfólio, sem afiliação com o iFood ou qualquer plataforma de delivery. Os dados de mercado vêm de um dataset público. Os pedidos e avaliações são sintéticos.*
