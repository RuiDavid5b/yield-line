import { useState } from "react";
import { api } from "../api/client";

import { type Company } from "../api/types";

interface Message {
  role: "user" | "agent";
  text: string;
}

interface AgentChatProps {
  selectedCompany: Company | null;
}

const threadId = crypto.randomUUID();

export default function AgentChat({ selectedCompany }: AgentChatProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  async function send() {
    if (!input.trim()) return;

    const question = input;

    setMessages((messages) => [...messages, { role: "user", text: question }]);
    setInput("");
    setLoading(true);

    try {
      const { answer } = await api.askAgent(question, threadId, selectedCompany);
      setMessages((messages) => [...messages, { role: "agent", text: answer }]);
    } catch {
      setMessages((messages) => [
        ...messages,
        { role: "agent", text: "Something went wrong reaching the agent." },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <div className="section-heading">Ask questions related to a company listed on the left</div>
      <div className="panel">
        <div className="chat-messages">
          {messages.map((message, index) => (
            <div key={index} className={`chat-msg ${message.role}`}>
              {message.text}
            </div>
          ))}

          {loading && <div className="chat-msg agent">Thinking…</div>}
        </div>

        <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
          <input
            style={{ flex: 1 }}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") send();
            }}
            placeholder={selectedCompany ? `Ask about ${selectedCompany.name}...` : "Ask anything..."}
          />

          <button onClick={send} disabled={loading}>
            Send
          </button>
        </div>
      </div>
    </div>
  );
}
