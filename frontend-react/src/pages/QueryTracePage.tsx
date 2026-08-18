import { useChat } from "../context/ChatContext";
import { t } from "../i18n/translations";

export function QueryTracePage() {
  const { lastChunks, lastQuestion } = useChat();

  if (lastChunks.length === 0) {
    return <div className="alert alert-info">{t("code_tab_hint")}</div>;
  }

  return (
    <div>
      <p className="text-soft">{t("context_retrieved", { q: lastQuestion })}</p>
      {lastChunks.map((c, i) => (
        <div key={i} className="card">
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.5rem" }}>
            <span>
              📄&nbsp;<b>{c.source}</b>
            </span>
            <span className="text-soft">{t("chunk_label", { n: c.chunk })}</span>
          </div>
          <pre style={{ whiteSpace: "pre-wrap", fontFamily: "Consolas, monospace", fontSize: "0.85rem", margin: 0 }}>
            {c.text}
          </pre>
        </div>
      ))}
    </div>
  );
}
