"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { inventory, recommendations, Inventory, Recommendation } from "@/lib/api";
import Navbar from "@/components/Navbar";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export default function RecommendationsPage() {
  const router = useRouter();
  const [inventories, setInventories] = useState<Inventory[]>([]);
  const [results, setResults] = useState<Record<number, Recommendation>>({});
  const [loading, setLoading] = useState(true);
  const [auditing, setAuditing] = useState<number | null>(null);

  useEffect(() => {
    if (!localStorage.getItem("access_token")) {
      router.push("/login");
      return;
    }
    inventory.list()
      .then(setInventories)
      .catch(() => router.push("/login"))
      .finally(() => setLoading(false));
  }, []);

  async function handleAudit(inv: Inventory) {
    setAuditing(inv.id);
    try {
      const result = await recommendations.audit(inv.id);
      setResults((prev) => ({ ...prev, [inv.id]: result }));
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "AI 분석 실패");
    } finally {
      setAuditing(null);
    }
  }

  if (loading) {
    return (
      <>
        <Navbar />
        <div className="flex items-center justify-center h-64 text-gray-500">불러오는 중...</div>
      </>
    );
  }

  return (
    <>
      <Navbar />
      <main className="max-w-6xl mx-auto px-4 py-8 space-y-6">
        <h1 className="text-xl font-semibold">AI 절감 추천</h1>

        {inventories.length === 0 ? (
          <Card>
            <CardContent className="py-12 text-center text-gray-500">
              <p>인스턴스가 없습니다. 대시보드에서 먼저 수집해주세요.</p>
            </CardContent>
          </Card>
        ) : (
          inventories.map((inv) => {
            const result = results[inv.id];
            return (
              <Card key={inv.id}>
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle className="text-base">{inv.instance_type}</CardTitle>
                      <p className="text-sm text-gray-500">{inv.resource_id} · {inv.region_normalized}</p>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-sm font-medium">${parseFloat(inv.current_monthly_cost).toFixed(2)}/월</span>
                      <Button size="sm" onClick={() => handleAudit(inv)} disabled={auditing === inv.id}>
                        {auditing === inv.id ? "분석 중..." : "AI 분석"}
                      </Button>
                    </div>
                  </div>
                </CardHeader>

                {result && (
                  <CardContent className="space-y-4 border-t pt-4">
                    {/* 진단 */}
                    {result.diagnosis && (
                      <p className="text-sm text-gray-700 bg-gray-50 rounded p-3">{result.diagnosis}</p>
                    )}

                    {/* 현재 vs 추천 */}
                    <div className="grid grid-cols-2 gap-4">
                      <div className="border rounded-lg p-3 space-y-1">
                        <p className="text-xs text-gray-500">현재</p>
                        <div className="flex items-center gap-2">
                          <Badge variant="outline">{result.current.provider}</Badge>
                          <span className="font-medium text-sm">{result.current.instance_type}</span>
                        </div>
                        <p className="text-sm font-semibold">${result.current.monthly_cost.toFixed(2)}/월</p>
                      </div>
                      <div className="border rounded-lg p-3 space-y-1 border-green-200 bg-green-50">
                        <p className="text-xs text-gray-500">추천</p>
                        <div className="flex items-center gap-2">
                          <Badge variant="outline">{result.recommended.provider}</Badge>
                          <span className="font-medium text-sm">{result.recommended.instance_type}</span>
                        </div>
                        <p className="text-sm font-semibold text-green-700">
                          ${result.recommended.monthly_cost.toFixed(2)}/월
                          <span className="text-xs ml-1">(${result.monthly_savings.toFixed(2)} 절감)</span>
                        </p>
                      </div>
                    </div>

                    {/* 이유 */}
                    {result.reason && (
                      <p className="text-sm text-gray-600">{result.reason}</p>
                    )}

                    {/* 3사 비교 */}
                    {result.compare_result && result.compare_result.length > 0 && (
                      <div className="space-y-2">
                        <p className="text-xs font-medium text-gray-500">3사 가격 비교</p>
                        {result.compare_result.map((c, i) => (
                          <div key={i} className="flex items-center justify-between text-sm border rounded px-3 py-2">
                            <div className="flex items-center gap-2">
                              <Badge variant="outline">{c.provider}</Badge>
                              <span>{c.instance_type}</span>
                            </div>
                            <span className="font-medium">${c.monthly_cost?.toFixed(2)}/월</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </CardContent>
                )}
              </Card>
            );
          })
        )}
      </main>
    </>
  );
}
