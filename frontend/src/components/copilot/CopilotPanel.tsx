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
import { copilotApi, type ConversationSummary } from "@/services/api";
import { format } from "date-fns";

export default function CopilotPanel() {
  const {
    copilotMessages,
    addCopilotMessage,
    updateCopilotMessage,
    clearCopilotMessages,
    setCopilotOpen,
    byokKey,
    setByokKey,
    applyMapAction,
    viewState,
    dateRange,
    selectedCell,
    user,
    currentConversationId,
    setCurrentConversationId,
  } = useEchelonStore();

  const [input, setInput] = useState("");
  const [isThinking, setIsThinking] = useState(false);
  const [showKeyPrompt, setShowKeyPrompt] = useState(!byokKey);
  const [keyInput, setKeyInput] = useState("");
  const [provider, setProvider] = useState<"anthropic" | "openai" | "google" | "ollama">("ollama");
  const [showConversations, setShowConversations] = useState(false);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
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

    const assistantId = crypto.randomUUID();
    const assistantMessage: CopilotMessage = {
      id: assistantId,
      role: "assistant",
      content: "",
      toolCalls: [],
      timestamp: new Date(),
    };
    addCopilotMessage(assistantMessage);

    try {
      const requestPayload = {
        messages: [...copilotMessages, userMessage].map((m) => ({
          role: m.role,
          content: m.content,
        })),
        provider,
        mapContext: {
          viewport: {
            center: [viewState.longitude ?? 0, viewState.latitude ?? 20] as [number, number],
            zoom: viewState.zoom ?? 2,
          },
          dateRange: {
            from: dateRange.from.toISOString().split("T")[0],
            to: dateRange.to.toISOString().split("T")[0],
          },
          selectedCell: selectedCell?.h3Index,
        },
      };

      let accumulated = "";
      const toolCalls: Array<{ toolName: string; status: "pending" | "complete" | "error" }> = [];

      for await (const event of copilotApi.chatStream(requestPayload, byokKey || "")) {
        if (event.type === "text" && event.content) {
          accumulated += event.content;
          updateCopilotMessage(assistantId, { content: accumulated });
        } else if (event.type === "tool_start" && event.name) {
          toolCalls.push({ toolName: event.name, status: "pending" });
          updateCopilotMessage(assistantId, { toolCalls: [...toolCalls] });
        } else if (event.type === "tool_end" && event.name) {
          const tc = toolCalls.find((t) => t.toolName === event.name && t.status === "pending");
          if (tc) tc.status = "complete";
          updateCopilotMessage(assistantId, { toolCalls: [...toolCalls] });
        } else if (event.type === "map_action" && event.action) {
          const mapAction = event.action as CopilotMessage["mapAction"];
          updateCopilotMessage(assistantId, { mapAction });
          if (mapAction) applyMapAction(mapAction);
        } else if (event.type === "error") {
          updateCopilotMessage(assistantId, {
            content: accumulated || event.detail || "Copilot request failed",
          });
        }
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
        else if (msg) {
          try { errorMsg = JSON.parse(msg).detail || errorMsg; } catch { errorMsg = msg.length < 200 ? msg : errorMsg; }
        }
      }
      updateCopilotMessage(assistantId, { content: errorMsg });
    } finally {
      setIsThinking(false);
    }
  }, [input, byokKey, isThinking, copilotMessages, addCopilotMessage, updateCopilotMessage, applyMapAction, viewState, dateRange, selectedCell, provider]);

  const handleLoadConversations = useCallback(async () => {
    if (!user) return;
    try {
      const list = await copilotApi.listConversations();
      setConversations(list);
      setShowConversations(true);
    } catch { /* non-critical */ }
  }, [user]);

  const handleSaveConversation = useCallback(async () => {
    if (!user || copilotMessages.length === 0) return;
    const firstUserMsg = copilotMessages.find((m) => m.role === "user");
    const title = firstUserMsg?.content.slice(0, 60) || "Untitled conversation";
    try {
      if (currentConversationId) {
        await copilotApi.updateConversation(currentConversationId, {
          messages: copilotMessages.map((m) => ({ role: m.role, content: m.content })),
        });
      } else {
        const result = await copilotApi.saveConversation({
          title,
          provider,
          messages: copilotMessages.map((m) => ({ role: m.role, content: m.content })),
        });
        setCurrentConversationId(result.id);
      }
    } catch { /* non-critical */ }
  }, [user, copilotMessages, currentConversationId, setCurrentConversationId, provider]);

  const handleLoadConversation = useCallback(async (id: string) => {
    try {
      const conv = await copilotApi.loadConversation(id);
      clearCopilotMessages();
      setCurrentConversationId(conv.id);
      for (const msg of conv.messages) {
        addCopilotMessage({
          id: crypto.randomUUID(),
          role: msg.role as "user" | "assistant",
          content: msg.content,
          timestamp: msg.timestamp ? new Date(msg.timestamp) : new Date(),
        });
      }
      setShowConversations(false);
    } catch { /* non-critical */ }
  }, [clearCopilotMessages, setCurrentConversationId, addCopilotMessage]);

  const handleNewConversation = useCallback(() => {
    clearCopilotMessages();
    setShowConversations(false);
  }, [clearCopilotMessages]);

  const handleExportMarkdown = useCallback(() => {
    if (copilotMessages.length === 0) return;
    const lines = [
      `# Echelon Copilot — Analysis Export`,
      `_Exported ${new Date().toISOString()}_\n`,
      `**Viewport:** ${(viewState.longitude ?? 0).toFixed(4)}, ${(viewState.latitude ?? 20).toFixed(4)} | Zoom ${(viewState.zoom ?? 2).toFixed(1)}`,
      `**Date range:** ${dateRange.from.toISOString().split("T")[0]} to ${dateRange.to.toISOString().split("T")[0]}`,
      `**Provider:** ${provider}\n`,
      `---\n`,
    ];
    for (const msg of copilotMessages) {
      lines.push(`### ${msg.role === "user" ? "Analyst" : "Copilot"} — ${format(msg.timestamp, "HH:mm")}\n`);
      if (msg.toolCalls?.length) {
        lines.push(`> Tools used: ${msg.toolCalls.map((t) => t.toolName).join(", ")}\n`);
      }
      lines.push(msg.content + "\n");
    }
    lines.push(`\n---\n_Generated by Echelon GEOINT Dashboard_`);
    const blob = new Blob([lines.join("\n")], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `echelon-analysis-${format(new Date(), "yyyy-MM-dd-HHmm")}.md`;
    a.click();
    URL.revokeObjectURL(url);
  }, [copilotMessages, viewState, dateRange, provider]);

  const handleSharePermalink = useCallback(() => {
    const params = new URLSearchParams();
    params.set("lng", (viewState.longitude ?? 0).toFixed(4));
    params.set("lat", (viewState.latitude ?? 20).toFixed(4));
    params.set("z", (viewState.zoom ?? 2).toFixed(1));
    params.set("from", dateRange.from.toISOString().split("T")[0]);
    params.set("to", dateRange.to.toISOString().split("T")[0]);
    if (selectedCell) params.set("cell", selectedCell.h3Index);
    const url = `${window.location.origin}${window.location.pathname}?${params.toString()}`;
    navigator.clipboard.writeText(url).catch(() => {});
    setShareCopied(true);
    setTimeout(() => setShareCopied(false), 2000);
  }, [viewState, dateRange, selectedCell]);

  const [shareCopied, setShareCopied] = useState(false);

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
        <div style={{ display: "flex", gap: 4, alignItems: "center" }}>
          {user && (
            <>
              <button
                onClick={handleLoadConversations}
                aria-label="Browse saved conversations"
                title="Saved conversations"
                style={{ background: "none", border: "1px solid var(--color-border)", borderRadius: 4, color: "var(--color-text-secondary)", cursor: "pointer", fontSize: 10, padding: "2px 6px" }}
              >
                History
              </button>
              {copilotMessages.length > 0 && (
                <button
                  onClick={handleSaveConversation}
                  aria-label="Save conversation"
                  title={currentConversationId ? "Update saved conversation" : "Save conversation"}
                  style={{ background: "none", border: "1px solid var(--color-border)", borderRadius: 4, color: "var(--color-text-secondary)", cursor: "pointer", fontSize: 10, padding: "2px 6px" }}
                >
                  Save
                </button>
              )}
            </>
          )}
          {copilotMessages.length > 0 && (
            <>
              <button
                onClick={handleExportMarkdown}
                aria-label="Export conversation as markdown"
                title="Export as Markdown"
                style={{ background: "none", border: "1px solid var(--color-border)", borderRadius: 4, color: "var(--color-text-secondary)", cursor: "pointer", fontSize: 10, padding: "2px 6px" }}
              >
                Export
              </button>
              <button
                onClick={handleSharePermalink}
                aria-label="Copy share link"
                title="Copy permalink to clipboard"
                style={{ background: "none", border: "1px solid var(--color-border)", borderRadius: 4, color: shareCopied ? "var(--color-accent)" : "var(--color-text-secondary)", cursor: "pointer", fontSize: 10, padding: "2px 6px" }}
              >
                {shareCopied ? "Copied" : "Share"}
              </button>
            </>
          )}
          <button
            onClick={() => setCopilotOpen(false)}
            aria-label="Close copilot"
            style={{ background: "none", border: "none", color: "var(--color-text-secondary)", cursor: "pointer", fontSize: 18, padding: 4 }}
          >
            ×
          </button>
        </div>
      </div>

      {/* Conversation history list */}
      {showConversations && (
        <div style={{ padding: 12, borderBottom: "1px solid var(--color-border)", background: "var(--color-surface-raised)", maxHeight: 240, overflow: "auto" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: "var(--color-text-primary)" }}>Saved Conversations</div>
            <div style={{ display: "flex", gap: 4 }}>
              <button
                onClick={handleNewConversation}
                style={{ background: "none", border: "1px solid var(--color-border)", borderRadius: 4, color: "var(--color-accent)", cursor: "pointer", fontSize: 10, padding: "2px 8px" }}
              >
                + New
              </button>
              <button
                onClick={() => setShowConversations(false)}
                style={{ background: "none", border: "none", color: "var(--color-text-muted)", cursor: "pointer", fontSize: 14, padding: "0 4px" }}
              >
                x
              </button>
            </div>
          </div>
          {conversations.length === 0 ? (
            <div style={{ fontSize: 11, color: "var(--color-text-muted)", textAlign: "center", padding: 12 }}>
              No saved conversations yet.
            </div>
          ) : (
            conversations.map((conv) => (
              <div
                key={conv.id}
                onClick={() => handleLoadConversation(conv.id)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => e.key === "Enter" && handleLoadConversation(conv.id)}
                style={{
                  padding: "8px 10px", marginBottom: 4, borderRadius: 6, cursor: "pointer",
                  background: conv.id === currentConversationId ? "var(--color-accent-muted)" : "transparent",
                  border: "1px solid var(--color-border)",
                }}
              >
                <div style={{ fontSize: 11, fontWeight: 500, color: "var(--color-text-primary)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {conv.title}
                </div>
                <div style={{ fontSize: 9, color: "var(--color-text-muted)", marginTop: 2 }}>
                  {conv.messageCount} messages | {conv.provider} | {format(new Date(conv.updatedAt), "MMM d HH:mm")}
                </div>
              </div>
            ))
          )}
        </div>
      )}

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
