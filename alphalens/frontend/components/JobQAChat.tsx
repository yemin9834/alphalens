import { useEffect, useRef, useState } from "react";
import { askJobStream } from "../lib/qa-stream";
import { resolveToken } from "../lib/api";
import { HAS_CLERK } from "../lib/config";
import type { GetTokenFn } from "./WithAuthToken";
import MarkdownContent from "./MarkdownContent";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  streaming?: boolean;
}

interface JobQAChatProps {
  jobId: string;
  getToken: GetTokenFn;
}

const SUGGESTIONS = [
  "What actions do you recommend?",
  "Summarize the portfolio risk.",
  "Which candidates look most attractive?",
];

export default function JobQAChat({ jobId, getToken }: JobQAChatProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState(SUGGESTIONS[0]);
  const [asking, setAsking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages]);

  const submit = async (text?: string) => {
    const question = (text ?? input).trim();
    if (!question || asking) return;

    setError(null);
    setAsking(true);
    const userId = `user-${Date.now()}`;
    const assistantId = `assistant-${Date.now()}`;

    const finalizeAssistant = () => {
      setMessages((prev) =>
        prev.map((m) => {
          if (m.id !== assistantId) return m;
          const content = m.content.replace(/^Thinking…\s*/, "").trim();
          return { ...m, content, streaming: false };
        })
      );
    };

    setMessages((prev) => [
      ...prev,
      { id: userId, role: "user", content: question },
      { id: assistantId, role: "assistant", content: "", streaming: true },
    ]);
    if (!text) setInput("");

    try {
      const token = await resolveToken(HAS_CLERK ? getToken : undefined);
      await askJobStream(jobId, question, token, {
        onToken: (tokenChunk) => {
          if (tokenChunk === "Thinking… ") return;
          setMessages((prev) =>
            prev.map((m) => {
              if (m.id !== assistantId) return m;
              const next = (m.content + tokenChunk).replace(/^Thinking…\s*/, "");
              return { ...m, content: next };
            })
          );
        },
        onDone: finalizeAssistant,
        onError: (message) => setError(message),
      });
      finalizeAssistant();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Q&A failed";
      setError(message);
      setMessages((prev) => prev.filter((m) => m.id !== assistantId));
    } finally {
      setAsking(false);
    }
  };

  return (
    <section className="card job-qa-card">
      <div className="report-header">
        <div className="report-title-block">
          <span className="report-icon" aria-hidden>
            ?
          </span>
          <div>
            <h2>Ask about this analysis</h2>
            <p className="muted report-subtitle">
              Follow-up questions grounded in this job&apos;s results.
            </p>
          </div>
        </div>
      </div>

      {error && (
        <div className="banner banner-error" style={{ marginBottom: "1rem" }}>
          {error}
        </div>
      )}

      <div className="job-qa-messages" ref={scrollRef}>
        {messages.length === 0 ? (
          <p className="muted job-qa-empty">
            Ask about risk, recommended actions, or top opportunities.
          </p>
        ) : (
          messages.map((msg) => (
            <div
              key={msg.id}
              className={`job-qa-bubble job-qa-bubble-${msg.role}`}
            >
              <span className="job-qa-bubble-label">
                {msg.role === "user" ? "You" : "AlphaLens"}
              </span>
              {msg.role === "assistant" ? (
                msg.streaming ? (
                  <p className="job-qa-stream-text">
                    {msg.content || "Thinking…"}
                    <span className="job-qa-cursor" aria-hidden>
                      ▍
                    </span>
                  </p>
                ) : msg.content ? (
                  <MarkdownContent content={msg.content} />
                ) : (
                  <p className="muted job-qa-stream-text">No answer returned.</p>
                )
              ) : (
                <p className="job-qa-user-text">{msg.content}</p>
              )}
            </div>
          ))
        )}
      </div>

      <div className="job-qa-suggestions">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            type="button"
            className="btn btn-ghost job-qa-suggestion"
            disabled={asking}
            onClick={() => submit(s)}
          >
            {s}
          </button>
        ))}
      </div>

      <div className="job-qa-composer">
        <label className="job-qa-input-label">
          <span>Your question</span>
          <textarea
            value={input}
            rows={3}
            disabled={asking}
            placeholder="What should I do with my NVDA position?"
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                submit();
              }
            }}
          />
        </label>
        <button
          type="button"
          className="btn btn-primary job-qa-send"
          disabled={asking || !input.trim()}
          onClick={() => submit()}
        >
          {asking ? "Thinking…" : "Ask"}
        </button>
      </div>
    </section>
  );
}
