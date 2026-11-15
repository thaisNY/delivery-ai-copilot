-- Dados REAIS: restaurantes de Caruaru-PE no iFood (dataset público do Kaggle, fev/2021).
-- Usados só como referência de mercado (benchmarks por categoria).
CREATE TABLE IF NOT EXISTS market_restaurants (
    id              SERIAL PRIMARY KEY,
    name            TEXT,
    category        TEXT,
    delivery_fee    NUMERIC,
    delivery_time   INT,
    minimum_order   NUMERIC,
    price_range     TEXT,
    rating          NUMERIC
);

-- Dados SINTÉTICOS: restaurantes fictícios que usam o copiloto.
-- Campos inspirados no formato da API de parceiros do iFood (merchant / order / review).
CREATE TABLE IF NOT EXISTS merchants (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    category    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS menu_items (
    id          TEXT PRIMARY KEY,
    merchant_id TEXT REFERENCES merchants(id),
    name        TEXT NOT NULL,
    price       NUMERIC NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    id                TEXT PRIMARY KEY,
    merchant_id       TEXT REFERENCES merchants(id),
    created_at        TIMESTAMP NOT NULL,
    total             NUMERIC NOT NULL,
    items             JSONB NOT NULL,
    promised_minutes  INT NOT NULL,
    delivery_minutes  INT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_orders_merchant_date ON orders(merchant_id, created_at);

CREATE TABLE IF NOT EXISTS reviews (
    id            TEXT PRIMARY KEY,
    order_id      TEXT REFERENCES orders(id),
    merchant_id   TEXT REFERENCES merchants(id),
    created_at    TIMESTAMP NOT NULL,
    rating        INT NOT NULL,
    comment       TEXT,
    -- preenchidos pelo pipeline de classificação (LLM ou regras)
    sentiment     TEXT,
    topics        TEXT[],
    classified_by TEXT
);
CREATE INDEX IF NOT EXISTS idx_reviews_merchant_date ON reviews(merchant_id, created_at);
