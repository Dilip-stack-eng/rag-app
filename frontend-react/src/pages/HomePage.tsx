import { useEffect, useState, type FormEvent } from "react";
import { apiGet, apiPost, ApiError } from "../api/client";
import type { QueryResponse, TokenUsageStatus } from "../api/types";
import { useChat } from "../context/ChatContext";
import { t } from "../i18n/translations";

const SUGGESTIONS = [t("suggestion_1"), t("suggestion_2"), t("suggestion_3")];

function TokenUsageCard() {
  const [usage, setUsage] = useState<TokenUsageStatus | null>(null);

  useEffect(() => {
    apiGet<TokenUsageStatus>("/token-usage")
      .then(setUsage)
      .catch(() => setUsage(null));
  }, []);

  if (!usage) return null;
  const pct = usage.limit ? Math.min(1, usage.used / usage.limit) : 0;
  const over = usage.used >= usage.limit;

  return (
    <div className={`token-usage-card${over ? " over-limit" : ""}`}>
      <div className="tuc-header">
        <span>🔢 DAILY TOKEN USAGE</span>
        <span>{over ? "Limit reached" : `${Math.round(pct * 100)}%`}</span>
      </div>
      <div className="tuc-value">
        {usage.used.toLocaleString()}
        <span className="sep">/</span>
        {usage.limit.toLocaleString()}
        <span className="tuc-unit">tokens today</span>
      </div>
      <div className="token-usage-track">
        <div className="token-usage-fill" style={{ width: `${pct * 100}%` }} />
      </div>
    </div>
  );
}

export function HomePage() {
  const { history, addTurn, setLastQuery, promptVersion } = useChat();
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);

  const ask = async (q: string) => {
    if (!q.trim() || busy) return;
    addTurn({ role: "user", text: q });
    setQuestion("");
    setBusy(true);
    try {
      const resp = await apiPost<QueryResponse>("/query", { question: q, prompt_version: promptVersion });
      let answer = resp.answer;
      if (resp.sources.length) {
        answer += `\n\n**${t("sources_label")}** ${resp.sources.join(", ")}`;
      }
      addTurn({ role: "assistant", text: answer });
      setLastQuery(q, resp.chunks);
    } catch (err) {
      const apiErr = err as ApiError;
      addTurn({ role: "assistant", text: `⚠️ ${apiErr.message || t("backend_unreachable")}` });
    } finally {
      setBusy(false);
    }
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    void ask(question);
  };

  return (
    <div>
      <TokenUsageCard />

      {history.length === 0 ? (
        <div className="text-center" style={{ minHeight: "40vh", display: "flex", flexDirection: "column", justifyContent: "center" }}>
          <h1 style={{ fontSize: "2.15rem" }}>{t("greeting")}</h1>
          <p className="text-soft" style={{ marginBottom: "1.7rem" }}>
            {t("subgreeting")}
          </p>
          <div className="suggestion-chips">
            {SUGGESTIONS.map((s) => (
              <button key={s} className="chip" onClick={() => void ask(s)}>
                {s}
              </button>
            ))}
          </div>
        </div>
      ) : (
        <div className="chat-history">
          {history.map((turn, i) => (
            <div key={i} className={`chat-message ${turn.role}`}>
              {turn.text}
            </div>
          ))}
          {busy && <div className="chat-message assistant text-soft">Thinking…</div>}
        </div>
      )}

      <form onSubmit={handleSubmit} className="chat-input-row">
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask a question about your documents…"
          disabled={busy}
        />
        <button type="submit" className="btn" disabled={busy || !question.trim()}>
          Send
        </button>
      </form>
    </div>
  );
}
