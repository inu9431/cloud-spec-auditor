"use client";

import { useState, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import { recommendations, ConsultChatResult } from "@/lib/api";
import Navbar from "@/components/Navbar";
import { Button } from "@/components/ui/button";
import ReactMarkdown from "react-markdown";

interface Message {
  role: "user" | "assistant";
  content: string;
}

const EXAMPLES = [
  "쇼핑몰 만들건데 한국 유저 500명 동시접속이 목표야. 상품 이미지 많고 결제 기능 있어.",
  "실시간 채팅 앱 개발 중이야. 글로벌 서비스고 초기엔 유저 1000명 정도.",
  "스타트업 사내 관리 툴인데 직원 50명이 쓸 거야. 파일 업로드 기능 있어.",
];

export default function ConsultingPage() {
  const router = useRouter();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [showCta, setShowCta] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!localStorage.getItem("access_token")) router.push("/login");
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  function toHistory(msgs: Message[]) {
    return msgs.map((m) => ({
      role: m.role === "assistant" ? "model" : "user",
      parts: [m.content],
    }));
  }

  async function handleSend(text?: string) {
    const message = (text ?? input).trim();
    if (!message || loading) return;

    const newMessages: Message[] = [...messages, { role: "user", content: message }];
    setMessages(newMessages);
    setInput("");
    setLoading(true);

    try {
      const history = toHistory(messages);
      const data: ConsultChatResult = await recommendations.consultChat(message, history);

      setMessages([...newMessages, { role: "assistant", content: data.reply }]);
      setShowCta(data.show_register_cta);
    } catch (err: unknown) {
      setMessages([
        ...newMessages,
        {
          role: "assistant",
          content: err instanceof Error ? err.message : "응답에 실패했습니다.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <Navbar />
      <main className="max-w-2xl mx-auto px-4 flex flex-col" style={{ height: "calc(100vh - 64px)" }}>
        <h1 className="text-xl font-semibold py-4">AI 인프라 컨설팅</h1>

        {/* 메시지 영역 */}
        <div className="flex-1 overflow-y-auto space-y-4 pb-4">
          {messages.length === 0 && (
            <div className="space-y-3 pt-2">
              <p className="text-sm text-gray-500">
                서비스를 설명하면 적합한 클라우드 인프라를 추천해드립니다.
              </p>
              <div className="space-y-2">
                <p className="text-xs text-gray-400">예시 선택</p>
                {EXAMPLES.map((ex, i) => (
                  <button
                    key={i}
                    onClick={() => handleSend(ex)}
                    className="block text-left text-sm text-blue-600 hover:underline"
                  >
                    {ex}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((m, i) => (
            <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
              <div
                className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                  m.role === "user"
                    ? "bg-blue-500 text-white"
                    : "bg-gray-100 text-gray-800"
                }`}
              >
                {m.role === "user" ? (
                  m.content
                ) : (
                  <ReactMarkdown
                    components={{
                      p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
                      ul: ({ children }) => <ul className="list-disc pl-4 mb-2 space-y-1">{children}</ul>,
                      ol: ({ children }) => <ol className="list-decimal pl-4 mb-2 space-y-1">{children}</ol>,
                      li: ({ children }) => <li>{children}</li>,
                      strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
                      h3: ({ children }) => <p className="font-semibold mt-3 mb-1">{children}</p>,
                      hr: () => <hr className="my-2 border-gray-300" />,
                    }}
                  >
                    {m.content}
                  </ReactMarkdown>
                )}
              </div>
            </div>
          ))}

          {loading && (
            <div className="flex justify-start">
              <div className="bg-gray-100 rounded-2xl px-4 py-3 text-sm text-gray-400">
                분석 중...
              </div>
            </div>
          )}

          {/* AWS 키 등록 CTA */}
          {showCta && !loading && (
            <div className="flex justify-start">
              <div className="bg-blue-50 border border-blue-200 rounded-2xl px-4 py-3 text-sm space-y-2 max-w-[80%]">
                <p className="text-blue-800 font-medium">
                  AWS 키를 등록하면 실계정 기반 정밀 분석이 가능합니다.
                </p>
                <Button size="sm" onClick={() => router.push("/credentials")}>
                  AWS 키 등록하기
                </Button>
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        {/* 입력 영역 */}
        <div className="flex gap-2 py-4 border-t">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder="서비스를 설명해주세요..."
            className="flex-1 border rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            disabled={loading}
          />
          <Button onClick={() => handleSend()} disabled={loading || !input.trim()}>
            전송
          </Button>
        </div>
      </main>
    </>
  );
}
