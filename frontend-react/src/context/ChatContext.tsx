import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import type { RetrievedChunk } from "../api/types";

export interface ChatTurn {
  role: "user" | "assistant";
  text: string;
}

interface ChatContextValue {
  history: ChatTurn[];
  addTurn: (turn: ChatTurn) => void;
  clearHistory: () => void;
  lastChunks: RetrievedChunk[];
  lastQuestion: string;
  setLastQuery: (question: string, chunks: RetrievedChunk[]) => void;
  promptVersion: string;
  setPromptVersion: (v: string) => void;
}

const ChatContext = createContext<ChatContextValue | undefined>(undefined);

export function ChatProvider({ children }: { children: ReactNode }) {
  const [history, setHistory] = useState<ChatTurn[]>([]);
  const [lastChunks, setLastChunks] = useState<RetrievedChunk[]>([]);
  const [lastQuestion, setLastQuestion] = useState("");
  const [promptVersion, setPromptVersion] = useState("v4");

  const value = useMemo<ChatContextValue>(
    () => ({
      history,
      addTurn: (turn) => setHistory((h) => [...h, turn]),
      clearHistory: () => setHistory([]),
      lastChunks,
      lastQuestion,
      setLastQuery: (question, chunks) => {
        setLastQuestion(question);
        setLastChunks(chunks);
      },
      promptVersion,
      setPromptVersion,
    }),
    [history, lastChunks, lastQuestion, promptVersion]
  );

  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>;
}

export function useChat(): ChatContextValue {
  const ctx = useContext(ChatContext);
  if (!ctx) throw new Error("useChat must be used within ChatProvider");
  return ctx;
}
