import { useEffect, useRef, useState } from "react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

const SUGESTOES = [
  "Por que minhas vendas caíram nas últimas duas semanas?",
  "O que os clientes mais reclamam?",
  "Em quais horários eu mais atraso?",
  "Como estou comparado com o mercado em Caruaru?",
];

const TOOL_LABEL = {
  resumo_vendas: "vendas",
  vendas_por_item: "itens",
  atrasos: "atrasos",
  reclamacoes: "avaliações",
  comparar_mercado: "mercado real",
};

const brl = (v) => (v ?? 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

function Variation({ pct }) {
  if (pct === null || pct === undefined) return null;
  return <span className={pct < 0 ? "neg" : "pos"}>{pct > 0 ? "+" : ""}{pct}%</span>;
}

// Renderização mínima de markdown: **negrito**, _itálico_, listas com "-" ou "*"
function Markdown({ text }) {
  const inline = (s) =>
    s.split(/(\*\*[^*]+\*\*|_[^_]+_)/g).map((p, i) =>
      p.startsWith("**") ? <strong key={i}>{p.slice(2, -2)}</strong>
        : p.startsWith("_") && p.endsWith("_") && p.length > 2 ? <em key={i}>{p.slice(1, -1)}</em>
        : p);
  const blocks = [];
  let list = [];
  text.split("\n").forEach((line, i) => {
    const m = line.match(/^\s*(?:[-*]|\d+\.)\s+(.*)/);
    if (m) { list.push(<li key={i}>{inline(m[1])}</li>); return; }
    if (list.length) { blocks.push(<ul key={`u${i}`}>{list}</ul>); list = []; }
    if (line.trim()) blocks.push(<p key={i}>{inline(line.replace(/^#+\s*/, ""))}</p>);
  });
  if (list.length) blocks.push(<ul key="ulast">{list}</ul>);
  return <>{blocks}</>;
}

export default function App() {
  const [merchants, setMerchants] = useState([]);
  const [mid, setMid] = useState("");
  const [dash, setDash] = useState(null);
  const [health, setHealth] = useState(null);
  const [msgs, setMsgs] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const endRef = useRef(null);

  useEffect(() => {
    fetch("/api/health").then((r) => r.json()).then(setHealth).catch(() => {});
    // A API pode demorar na primeira subida (pipeline de dados): tenta de novo por até ~2 min
    let tries = 0;
    const load = () => fetch("/api/merchants")
      .then((r) => { if (!r.ok) throw new Error(); return r.json(); })
      .then((ms) => { setError(""); setMerchants(ms); setMid(ms[0]?.id ?? ""); })
      .catch(() => {
        setError("A API ainda está preparando os dados… tentando de novo.");
        if (++tries < 24) setTimeout(load, 5000);
        else setError("Não consegui falar com a API. Veja os logs: docker compose logs api");
      });
    load();
  }, []);

  useEffect(() => {
    if (!mid) return;
    setDash(null); setMsgs([]);
    fetch(`/api/merchants/${mid}/dashboard`)
      .then((r) => { if (!r.ok) throw new Error(); return r.json(); })
      .then(setDash)
      .catch(() => setError("Erro ao carregar o painel. Veja os logs: docker compose logs api"));
  }, [mid]);

  useEffect(() => endRef.current?.scrollIntoView({ behavior: "smooth" }), [msgs, loading]);

  async function send(text) {
    const q = (text ?? input).trim();
    if (!q || loading) return;
    setInput("");
    const history = msgs.map((m) => ({ role: m.role, text: m.text }));
    setMsgs((m) => [...m, { role: "user", text: q }]);
    setLoading(true);
    try {
      const r = await fetch("/api/chat", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ merchant_id: mid, message: q, history }),
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data.detail || "erro");
      setMsgs((m) => [...m, { role: "model", text: data.answer, tools: data.tool_calls }]);
    } catch (e) {
      setMsgs((m) => [...m, { role: "model", text: `Ops, deu erro: ${e.message}` }]);
    } finally {
      setLoading(false);
    }
  }

  const merchant = merchants.find((m) => m.id === mid);
  const r = dash?.resumo, a = dash?.atrasos, rec = dash?.reclamacoes, mk = dash?.mercado;

  return (
    <div className="app">
      <header>
        <div className="brand">
          <div className="logo">C</div>
          <div>
            <h1>Copiloto do Restaurante</h1>
            <span className="sub">IA para parceiros de delivery em Caruaru-PE</span>
          </div>
        </div>
        <div className="right">
          {health && <span className={`badge ${health.llm ? "on" : "off"}`}>{health.llm ? `Gemini · ${health.model}` : "modo offline"}</span>}
          <select value={mid} onChange={(e) => setMid(e.target.value)}>
            {merchants.map((m) => <option key={m.id} value={m.id}>{m.name} · {m.category}</option>)}
          </select>
        </div>
      </header>

      {error && <div className="error">{error}</div>}

      <main>
        <section className="panel">
          {!dash ? <div className="loading">Carregando painel…</div> : (
            <>
              <div className="kpis">
                <div className="kpi"><span>Pedidos (14 dias)</span><strong>{r.atual.pedidos ?? 0}</strong><Variation pct={r.variacao_pedidos_pct} /></div>
                <div className="kpi"><span>Faturamento (14 dias)</span><strong>{brl(r.atual.faturamento)}</strong><Variation pct={r.variacao_faturamento_pct} /></div>
                <div className="kpi"><span>Nota média</span><strong>{r.nota_media_periodo ?? "–"}</strong><small>{r.avaliacoes_periodo} avaliações</small></div>
                <div className="kpi"><span>Pedidos atrasados</span><strong>{a.geral.pct_atrasados}%</strong><small>últimos 30 dias</small></div>
              </div>

              <div className="card">
                <h3>Faturamento diário</h3>
                <ResponsiveContainer width="100%" height={200}>
                  <AreaChart data={dash.serie_diaria} margin={{ left: 0, right: 8, top: 8 }}>
                    <defs>
                      <linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#ea1d2c" stopOpacity={0.25} />
                        <stop offset="100%" stopColor="#ea1d2c" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid stroke="#eee" vertical={false} />
                    <XAxis dataKey="dia" tick={{ fontSize: 11 }} interval={6} />
                    <YAxis tick={{ fontSize: 11 }} width={48} />
                    <Tooltip formatter={(v) => brl(v)} />
                    <Area type="monotone" dataKey="faturamento" stroke="#ea1d2c" strokeWidth={2} fill="url(#g)" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>

              <div className="grid2">
                <div className="card">
                  <h3>Reclamações por tema <small>({health?.llm ? "classificadas por IA" : "classificadas por regras"})</small></h3>
                  {rec.temas.slice(0, 5).map((t) => {
                    const max = rec.temas[0]?.qtd || 1;
                    return (
                      <div className="bar" key={t.tema}>
                        <span>{t.tema.replace("_", " ")}</span>
                        <div><i style={{ width: `${(t.qtd / max) * 100}%` }} /></div>
                        <b>{t.qtd}</b>
                      </div>
                    );
                  })}
                </div>
                <div className="card">
                  <h3>Piores horários de entrega</h3>
                  {a.piores_horarios.slice(0, 4).map((s, i) => (
                    <div className="row" key={i}><span>{s.dia} · {s.turno}</span><b className={s.pct_atrasados > 30 ? "neg" : ""}>{s.pct_atrasados}%</b></div>
                  ))}
                </div>
              </div>

              <div className="card market">
                <h3>Você vs mercado real <small>({mk.categoria} em Caruaru · {mk.mercado_caruaru.restaurantes} restaurantes · dados iFood fev/2021)</small></h3>
                <div className="row"><span>Tempo médio de entrega</span><b>{mk.seu_restaurante_ultimos_30d.tempo_entrega_medio_min} min <small>vs {mk.mercado_caruaru.tempo_entrega_medio_min} min</small></b></div>
                <div className="row"><span>Nota média</span><b>{mk.seu_restaurante_ultimos_30d.nota_media ?? "–"} <small>vs {mk.mercado_caruaru.nota_media ?? "–"}</small></b></div>
              </div>
            </>
          )}
        </section>

        <section className="chat">
          <div className="chat-head">Pergunte ao copiloto{merchant ? ` · ${merchant.name}` : ""}</div>
          <div className="msgs">
            {msgs.length === 0 && (
              <div className="empty">
                <p>Eu cruzo vendas, entregas e avaliações para explicar o que está acontecendo e sugerir ações.</p>
                {SUGESTOES.map((s) => <button key={s} className="sug" onClick={() => send(s)}>{s}</button>)}
              </div>
            )}
            {msgs.map((m, i) => (
              <div key={i} className={`msg ${m.role}`}>
                {m.role === "model" ? <Markdown text={m.text} /> : m.text}
                {m.tools?.length > 0 && (
                  <div className="tools">consultou: {[...new Set(m.tools.map((t) => TOOL_LABEL[t.name] || t.name))].join(" · ")}</div>
                )}
              </div>
            ))}
            {loading && <div className="msg model typing">Analisando os dados…</div>}
            <div ref={endRef} />
          </div>
          <form onSubmit={(e) => { e.preventDefault(); send(); }}>
            <input value={input} onChange={(e) => setInput(e.target.value)} placeholder="Ex.: o que fazer para vender mais na sexta?" />
            <button disabled={loading || !input.trim()}>Enviar</button>
          </form>
        </section>
      </main>
      <footer>Demo de portfólio · pedidos e avaliações são sintéticos; benchmarks de mercado usam dados públicos reais.</footer>
    </div>
  );
}
