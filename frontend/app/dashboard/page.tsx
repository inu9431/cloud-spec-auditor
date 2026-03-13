"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { inventory, Inventory } from "@/lib/api";
import Navbar from "@/components/Navbar";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

export default function DashboardPage() {
  const router = useRouter();
  const [inventories, setInventories] = useState<Inventory[]>([]);
  const [syncing, setSyncing] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!localStorage.getItem("access_token")) {
      router.push("/login");
      return;
    }
    fetchData();
  }, []);

  async function fetchData() {
    try {
      const inv = await inventory.list();
      setInventories(inv);
    } catch (err) {
      console.error("fetchData error:", err);
      setInventories([]);
    } finally {
      setLoading(false);
    }
  }

  async function handleSync() {
    setSyncing(true);
    try {
      await inventory.sync();
      alert("수집 요청이 등록되었습니다. 잠시 후 새로고침해주세요.");
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "오류가 발생했습니다.");
    } finally {
      setSyncing(false);
    }
  }

  const totalMonthlyCost = inventories.reduce(
    (sum, inv) => sum + parseFloat(inv.current_monthly_cost || "0"),
    0
  );
  if (loading) {
    return (
      <>
        <Navbar />
        <div className="flex items-center justify-center h-64 text-gray-500">
          불러오는 중...
        </div>
      </>
    );
  }

  return (
    <>
      <Navbar />
      <main className="max-w-6xl mx-auto px-4 py-8 space-y-8">
        {/* 요약 카드 */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-gray-500">총 인스턴스</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-3xl font-bold">{inventories.length}개</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-gray-500">월 예상 비용</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-3xl font-bold">${totalMonthlyCost.toFixed(2)}</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-gray-500">AI 추천</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-gray-500 pt-2">AI 추천 탭에서 확인하세요</p>
            </CardContent>
          </Card>
        </div>

        {/* 인스턴스 목록 */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">인스턴스 목록</h2>
            <Button size="sm" onClick={handleSync} disabled={syncing}>
              {syncing ? "요청 중..." : "수동 재수집"}
            </Button>
          </div>

          {inventories.length === 0 ? (
            <Card>
              <CardContent className="py-12 text-center text-gray-500">
                <p>등록된 인스턴스가 없습니다.</p>
                <p className="text-sm mt-1">
                  AWS 키를 등록하고 수동 재수집을 눌러주세요.
                </p>
              </CardContent>
            </Card>
          ) : (
            <Card>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>인스턴스 ID</TableHead>
                    <TableHead>타입</TableHead>
                    <TableHead>리전</TableHead>
                    <TableHead>vCPU</TableHead>
                    <TableHead>메모리</TableHead>
                    <TableHead>CPU 사용률</TableHead>
                    <TableHead>월 비용</TableHead>
                    <TableHead>상태</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {inventories.map((inv) => (
                    <TableRow key={inv.id}>
                      <TableCell className="font-mono text-xs">{inv.resource_id}</TableCell>
                      <TableCell>{inv.instance_type}</TableCell>
                      <TableCell>{inv.region_normalized}</TableCell>
                      <TableCell>{inv.vcpu}</TableCell>
                      <TableCell>{inv.memory_gb} GB</TableCell>
                      <TableCell>
                        {inv.cpu_usage_avg
                          ? `${parseFloat(inv.cpu_usage_avg).toFixed(1)}%`
                          : "-"}
                      </TableCell>
                      <TableCell>${parseFloat(inv.current_monthly_cost).toFixed(2)}</TableCell>
                      <TableCell>
                        <Badge variant={inv.is_active ? "default" : "secondary"}>
                          {inv.is_active ? "실행 중" : "중지"}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Card>
          )}
        </div>
      </main>
    </>
  );
}
