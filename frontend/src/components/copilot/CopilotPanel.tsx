/**
 * CopilotPanel
 *
 * BYOK Anthropic copilot chat interface. Slides in from the right as an overlay.
 * The user's API key is stored in Zustand (browser only by default) and
 * passed as X-Anthropic-Key header — never logged or persisted server-side
 * without explicit opt-in.
 *
 * Tool calls are surfaced as collapsible status rows in the chat.
 * Map actions in responses are dispatched to the Zustand store.
 */
import { useState, useRef, useEffect, useCallback } from "react";
import { useEchelonStore, type CopilotMessage } from "@/store/echelonStore";
import { copilotApi } from "@/services/api";
import { format } from "date-fns";

export default function CopilotPanel() {
  const {
    copilotMessages,
    addCopilotMessage,
    setCopilotOpen,
    byokKey,
    setByokKey,
    applyMapAction,
    viewState,
    dateRange,
    selectedCell,
  } = useEchelonStore();

  const [input, setInput] = useState("");
  const [isThinking, setIsThinking] = useState(false);
  const [showKeyPrompt, setShowKeyPrompt] = useState(!byokKey);
  const [keyInput, setKeyInput] = useState("");
  const [provider, setProvider] = useState<"anthropic" | "openai" | "google" | "ollama">("ollama");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [copilotMessages, isThinking]);

  const handleSaveKey = useCallback(() => {
    const key = keyInput.trim();
    if (key.length > 10) {
      // Auto-detect provider from key format
      if (key.startsWith("sk-ant-")) setProvider("anthropic");
      else if (key.startsWith("sk-")) setProvider("openai");
      else if (key.startsWith("AI")) setProvider("google");
      setByokKey(key);
      setShowKeyPrompt(false);
      setKeyInput("");
    }
  }, [keyInput, setByokKey]);

  const handleSend = useCallback(async () => {
    const needsKey = provider !== "ollama";
    if (!input.trim() || (needsKey && !byokKey) || isThinking) return;

    const userMessage: CopilotMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: input.trim(),
      timestamp: new Date(),
    };

    addCopilotMessage(userMessage);
    setInput("");
    setIsThinking(true);

    try {
      const response = await copilotApi.chat(
        {
          messages: [...copilotMessages, userMessage].map((m) => ({
            role: m.role,
            content: m.content,
          })),
          provider,
          mapContext: {
            viewport: {
              center: [viewState.longitude ?? 0, viewState.latitude ?? 20],
              zoom: viewState.zoom ?? 2,
            },
            dateRange: {
              from: dateRange.from.toISOString().split("T")[0],
              to: dateRange.to.toISOString().split("T")[0],
            },
            selectedCell: selectedCell?.h3Index,
          },
        },
        byokKey || ""
      );

      const assistantMessage: CopilotMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: response.content,
        toolCalls: response.toolCallsSummary?.map((t) => ({
          toolName: t.toolName,
          status: "complete" as const,
        })),
        mapAction: response.mapAction as CopilotMessage["mapAction"],
        timestamp: new Date(),
      };

      addCopilotMessage(assistantMessage);

      if (response.mapAction) {
        applyMapAction(response.mapAction as Parameters<typeof applyMapAction>[0]);
      }
    } catch (err: unknown) {
      let errorMsg = "Something went wrong. Check that your API key is valid and try again.";
      if (err && typeof err === "object") {
        const status = "status" in err ? (err as { status: number }).status : 0;
        const msg = "message" in err ? String((err as { message: string }).message) : "";
        if (status === 401 || msg.includes("401")) errorMsg = "Invalid API key. Please check your key and try again.";
        else if (status === 429 || msg.includes("429")) errorMsg = "Rate limit exceeded. Wait a moment and try again.";
        else if (status === 503 || msg.includes("503")) errorMsg = provider === "ollama"
          ? "Ollama is not running on the server. Install and start it, or switch to another provider."
          : "Service temporarily unavailable. Try again in a moment.";
        else if (status === 502 || msg.includes("502")) errorMsg = "The copilot backend is restarting. Try again in a few seconds.";
        else if (msg) {
          // Surface the actual error detail from the API
          try { errorMsg = JSON.parse(msg).detail || errorMsg; } catch { errorMsg = msg.length < 200 ? msg : errorMsg; }
        }
      }
      addCopilotMessage({
        id: crypto.randomUUID(),
        role: "assistant",
        content: errorMsg,
        timestamp: new Date(),
      });
    } finally {
      setIsThinking(false);
    }
  }, [input, byokKey, isThinking, copilotMessages, addCopilotMessage, applyMapAction, viewState, dateRange, selectedCell, provider]);

  return (
    <div
      aria-label="Echelon BYOK Copilot"
      style={{
        position: "absolute",
        right: 0,
        top: 0,
        bottom: 0,
        width: 400,
        background: "var(--color-surface)",
        borderLeft: "1px solid var(--color-border)",
        display: "flex",
        flexDirection: "column",
        zIndex: 10,
      }}
    >
      {/* Header */}
      <div style={{ padding: "12px 16px", borderBottom: "1px solid var(--color-border)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <div style={{ fontWeight: 600, fontSize: 13 }}>Echelon Copilot</div>
          <div style={{ fontSize: 10, color: "var(--color-text-secondary)", textTransform: "capitalize" }}>{provider === "ollama" ? "Self-hosted" : "BYOK"} — {provider}</div>
        </div>
        <button
          onClick={() => setCopilotOpen(false)}
          aria-label="Close copilot"
          style={{ background: "none", border: "none", color: "var(--color-text-secondary)", cursor: "pointer", fontSize: 18, padding: 4 }}
        >
          ×
        </button>
      </div>

      {/* BYOK key prompt */}
      {showKeyPrompt && (
        <div style={{ padding: 16, borderBottom: "1px solid var(--color-border)", background: "var(--color-surface-raised)" }}>
          <div style={{ fontSize: 12, color: "var(--color-text-primary)", marginBottom: 6, fontWeight: 600 }}>Connect your AI provider</div>
          <div style={{ fontSize: 11, color: "var(--color-text-secondary)", marginBottom: 10 }}>
            Your key stays in your browser. It's sent as a header only when you chat.
          </div>
          <div style={{ display: "flex", gap: 4, marginBottom: 8 }}>
            {(["anthropic", "openai", "google", "ollama"] as const).map((p) => (
              <button key={p} onClick={() => setProvider(p)} style={{
                padding: "3px 8px", borderRadius: 4, fontSize: 10, fontWeight: 500, cursor: "pointer",
                border: "1px solid", textTransform: "capitalize",
                borderColor: provider === p ? "var(--color-accent)" : "var(--color-border)",
                background: provider === p ? "var(--color-accent-muted)" : "transparent",
                color: provider === p ? "var(--color-accent)" : "var(--color-text-muted)",
              }}>{p}</button>
            ))}
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <input
              type="password"
              placeholder={provider === "ollama" ? "No key needed — click Save" : `${provider} API key...`}
              value={keyInput}
              onChange={(e) => setKeyInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSaveKey()}
              aria-label="API key"
              style={{ flex: 1, background: "var(--color-bg)", border: "1px solid var(--color-border)", borderRadius: 6, padding: "6px 10px", color: "var(--color-text-primary)", fontSize: 12 }}
            />
            <button
              onClick={() => { if (provider === "ollama") { setByokKey("ollama"); setShowKeyPrompt(false); } else handleSaveKey(); }}
              disabled={provider !== "ollama" && keyInput.trim().length < 10}
              style={{ background: "var(--color-accent)", border: "none", borderRadius: 6, padding: "6px 12px", color: "#fff", cursor: "pointer", fontSize: 12, opacity: (provider !== "ollama" && keyInput.trim().length < 10) ? 0.5 : 1 }}
            >
              Save
            </button>
          </div>
        </div>
      )}

      {/* Messages */}
      <div style={{ flex: 1, overflow: "auto", padding: 16, display: "flex", flexDirection: "column", gap: 12 }}>
        {copilotMessages.length === 0 && (
          <div style={{ color: "var(--color-text-secondary)", fontSize: 12, textAlign: "center", marginTop: 24 }}>
            <div style={{ marginBottom: 8 }}>Ask anything about conflict activity and maritime signals.</div>
            <div style={{ fontSize: 11, color: "var(--color-border)" }}>
              Try: "Show unusual vessel activity near the Strait of Hormuz this week" or "What's driving the spike in eastern Ukraine?"
            </div>
          </div>
        )}
        {copilotMessages.map((msg) => (
          <ChatMessage key={msg.id} message={msg} />
        ))}
        {isThinking && (
          <div style={{ display: "flex", gap: 6, alignItems: "center", color: "var(--color-text-secondary)", fontSize: 12 }}>
            <span style={{ animation: "pulse 1.5s infinite" }}>Analyzing…</span>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div style={{ padding: 12, borderTop: "1px solid var(--color-border)" }}>
        <div style={{ display: "flex", gap: 8 }}>
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); }}}
            placeholder={(byokKey || provider === "ollama") ? "Ask about conflict and maritime activity…" : "Add API key above to enable copilot"}
            disabled={(!byokKey && provider !== "ollama") || isThinking}
            rows={2}
            aria-label="Copilot message input"
            style={{
              flex: 1,
              resize: "none",
              background: "var(--color-bg)",
              border: "1px solid var(--color-border)",
              borderRadius: 6,
              padding: "8px 10px",
              color: "var(--color-text-primary)",
              fontSize: 12,
              fontFamily: "inherit",
            }}
          />
          <button
            onClick={handleSend}
            disabled={(!byokKey && provider !== "ollama") || !input.trim() || isThinking}
            aria-label="Send message"
            style={{
              background: "var(--color-accent)",
              border: "none",
              borderRadius: 6,
              padding: "0 14px",
              color: "#fff",
              cursor: "pointer",
              fontSize: 12,
              opacity: ((!byokKey && provider !== "ollama") || !input.trim() || isThinking) ? 0.5 : 1,
            }}
          >
            Send
          </button>
        </div>
        <div style={{ marginTop: 6, fontSize: 10, color: "var(--color-text-secondary)" }}>
          Enter to send · Shift+Enter for newline
        </div>
      </div>
    </div>
  );
}

function ChatMessage({ message }: { message: CopilotMessage }) {
  const isUser = message.role === "user";
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: isUser ? "flex-end" : "flex-start" }}>
      {message.toolCalls?.map((tc, i) => (
        <details
          key={i}
          style={{
            marginBottom: 4,
            fontSize: 10,
            color: "var(--color-text-secondary)",
            background: "var(--color-surface-raised)",
            borderRadius: 4,
            padding: "3px 8px",
            width: "100%",
          }}
        >
          <summary style={{ cursor: "pointer" }}>Used tool: {tc.toolName}</summary>
        </details>
      ))}
      <div
        style={{
          maxWidth: "85%",
          background: isUser ? "var(--color-accent)" : "var(--color-surface-raised)",
          color: isUser ? "#fff" : "var(--color-text-primary)",
          borderRadius: isUser ? "12px 12px 2px 12px" : "12px 12px 12px 2px",
          padding: "8px 12px",
          fontSize: 12,
          lineHeight: 1.5,
          whiteSpace: "pre-wrap",
        }}
      >
        {message.content}
      </div>
      <div style={{ fontSize: 10, color: "var(--color-text-secondary)", marginTop: 2 }}>
        {format(message.timestamp, "HH:mm")}
      </div>
    </div>
  );
}
