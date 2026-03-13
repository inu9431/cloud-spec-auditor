"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { recommendations, ConsultResult } from "@/lib/api";
import Navbar from "@/components/Navbar";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

const EXAMPLES = [
  "쇼핑몰 만들건데 한국 유저 500명 동시접속이 목표야. 상품 이미지 많고 결제 기능 있어.",
  "실시간 채팅 앱 개발 중이야. 글로벌 서비스고 초기엔 유저 1000명 정도.",
  "스타트업 사내 관리 툴인데 직원 50명이 쓸 거야. 파일 업로드 기능 있어.",
];

export default function ConsultingPage() {
  const router = useRouter();
  const [description, setDescription] = useState("");
  const [result, setResult] = useState<ConsultResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!localStorage.getItem("access_token")) {
      router.push("/login");
    }
  }, []);

  async function handleConsult() {
    if (!description.trim()) return;
    setError("");
    setResult(null);
    setLoading(true);
    try {
      const data = await recommendations.consult(description);
      setResult(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "분석에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <Navbar />
      <main className="max-w-3xl mx-auto px-4 py-8 space-y-6">
        <div>
          <h1 className="text-xl font-semibold">AI 인프라 컨설팅</h1>
          <p className="text-sm text-gray-500 mt-1">
            서비스 기획을 설명하면 적합한 클라우드 인스턴스와 아키텍처를 추천해드립니다.
          </p>
        </div>

        {/* 입력 */}
        <Card>
          <CardContent className="pt-6 space-y-4">
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="예: 쇼핑몰 만들건데 한국 유저 500명 동시접속이 목표야. 이미지 많고 결제 기능 있어."
              className="w-full border rounded p-3 text-sm resize-none h-28 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />

            {/* 예시 버튼 */}
            <div className="space-y-1">
              <p className="text-xs text-gray-400">예시 선택</p>
              <div className="flex flex-col gap-2">
                {EXAMPLES.map((ex, i) => (
                  <button
                    key={i}
                    onClick={() => setDescription(ex)}
                    className="text-left text-xs text-blue-600 hover:underline truncate"
                  >
                    {ex}
                  </button>
                ))}
              </div>
            </div>

            {error && <p className="text-red-500 text-sm">{error}</p>}

            <Button
              onClick={handleConsult}
              disabled={loading || !description.trim()}
              className="w-full"
            >
              {loading ? "AI 분석 중..." : "인스턴스 추천받기"}
            </Button>
          </CardContent>
        </Card>

        {/* 결과 */}
        {result && (
          <div className="space-y-4">
            {/* 추정 스펙 */}
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm text-gray-500">추정된 서버 스펙</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-3 text-sm">
                  <span className="bg-gray-100 rounded px-2 py-1">vCPU {result.estimated_spec.vcpu}코어</span>
                  <span className="bg-gray-100 rounded px-2 py-1">메모리 {result.estimated_spec.memory_gb}GB</span>
                  <span className="bg-gray-100 rounded px-2 py-1">스토리지 {result.estimated_spec.storage_gb}GB</span>
                  <span className="bg-gray-100 rounded px-2 py-1">리전 {result.estimated_spec.region}</span>
                </div>
                <p className="text-xs text-gray-500 mt-2">{result.estimated_spec.reason}</p>
              </CardContent>
            </Card>

            {/* AI 요약 + 추천 */}
            <Card className="border-blue-200 bg-blue-50">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm text-gray-600">AI 분석 결과</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <p className="text-sm text-gray-700">{result.summary}</p>

                <div className="flex items-center gap-2">
                  <Badge>{result.recommended_provider}</Badge>
                  <span className="font-semibold text-sm">{result.recommended_instance}</span>
                  {result.compare_result?.results && (() => {
                    const rec = result.compare_result.results.find(
                      (r) => r.provider === result.recommended_provider && r.instance_type === result.recommended_instance
                    );
                    return rec ? (
                      <span className="text-sm text-green-700 font-medium">
                        ${rec.price_per_month.toFixed(2)}/월
                      </span>
                    ) : null;
                  })()}
                </div>

                <p className="text-sm text-gray-600">{result.reason}</p>

                {result.architecture_tips && (
                  <div className="bg-white rounded p-3 border border-blue-100">
                    <p className="text-xs font-medium text-gray-500 mb-1">아키텍처 제안</p>
                    <p className="text-sm text-gray-700">{result.architecture_tips}</p>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* 3사 가격 비교 */}
            {result.compare_result?.results?.length > 0 && (
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm text-gray-500">3사 가격 비교</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  {result.compare_result.results.map((r, i) => (
                    <div
                      key={i}
                      className={`flex items-center justify-between text-sm border rounded px-3 py-2 ${
                        r.provider === result.recommended_provider && r.instance_type === result.recommended_instance
                          ? "border-green-300 bg-green-50"
                          : ""
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <Badge variant="outline">{r.provider}</Badge>
                        <span>{r.instance_type}</span>
                        <span className="text-xs text-gray-400">{r.region_normalized}</span>
                      </div>
                      <span className="font-medium">${r.price_per_month.toFixed(2)}/월</span>
                    </div>
                  ))}
                </CardContent>
              </Card>
            )}
          </div>
        )}
      </main>
    </>
  );
}
