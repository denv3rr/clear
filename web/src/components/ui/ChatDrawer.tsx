import { X } from "lucide-react";
import { ReactNode, useState } from "react";
import { apiPost } from "../../lib/api";

type Message = {
  text: string;
  sender: "user" | "bot";
};

type ChatDrawerProps = {
  onClose: () => void;
};

export function ChatDrawer({ onClose }: ChatDrawerProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");

  const sendMessage = async () => {
    if (!input.trim()) return;

    const newMessages: Message[] = [...messages, { text: input, sender: "user" }];
    setMessages(newMessages);
    setInput("");

    try {
      const response = await apiPost<{ answer: string }>("/api/assistant/query", {
        question: input
      });
      setMessages([...newMessages, { text: response.answer, sender: "bot" }]);
    } catch (error) {
      setMessages([
        ...newMessages,
        { text: "Error: Could not connect to the AI assistant.", sender: "bot" }
      ]);
    }
  };

  return (
    <div className="fixed inset-y-0 right-0 z-50 w-full max-w-md bg-ink-900 border-l border-slate-800/60 shadow-lg flex flex-col">
      <div className="flex items-center justify-between p-4 border-b border-slate-800/60">
        <h2 className="text-lg font-medium text-slate-100">AI Assistant</h2>
        <button
          onClick={onClose}
          className="rounded-full p-1 text-slate-400 hover:bg-slate-800/60"
        >
          <X size={20} />
        </button>
      </div>
      <div className="flex-1 p-4 overflow-y-auto">
        <div className="space-y-4">
          {messages.map((message, index) => (
            <div
              key={index}
              className={`flex ${
                message.sender === "user" ? "justify-end" : "justify-start"
              }`}
            >
              <div
                className={`rounded-lg px-4 py-2 ${
                  message.sender === "user"
                    ? "bg-emerald-600 text-white"
                    : "bg-slate-700 text-slate-100"
                }`}
              >
                {message.text}
              </div>
            </div>
          ))}
        </div>
      </div>
      <div className="p-4 border-t border-slate-800/60">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            sendMessage();
          }}
        >
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask a question..."
            className="w-full rounded-xl bg-ink-950/60 border border-slate-800 px-4 py-2 text-sm text-slate-200"
          />
        </form>
      </div>
    </div>
  );
}
