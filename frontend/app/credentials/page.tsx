"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { credentials, Credential } from "@/lib/api";
import Navbar from "@/components/Navbar";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function CredentialsPage() {
  const router = useRouter();
  const [creds, setCreds] = useState<Credential[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [testResults, setTestResults] = useState<Record<number, Record<string, string>>>({});
  const [form, setForm] = useState({
    aws_access_key_id: "",
    aws_secret_access_key: "",
    aws_default_region: "ap-northeast-2",
  });
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    if (!localStorage.getItem("access_token")) {
      router.push("/login");
      return;
    }
    fetchCreds();
  }, []);

  async function fetchCreds() {
    try {
      const data = await credentials.list();
      setCreds(data);
    } catch {
      router.push("/login");
    } finally {
      setLoading(false);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSuccess("");
    setSubmitting(true);
    try {
      await credentials.create({ provider: "AWS", credential_type: "ACCESS_KEY", ...form });
      setSuccess("AWS 키가 등록되었습니다.");
      setForm({ aws_access_key_id: "", aws_secret_access_key: "", aws_default_region: "ap-northeast-2" });
      fetchCreds();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "등록에 실패했습니다.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleTest(id: number) {
    try {
      const result = await credentials.test(id);
      setTestResults((prev) => ({ ...prev, [id]: result as Record<string, string> }));
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "권한 테스트 실패");
    }
  }

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
      <main className="max-w-3xl mx-auto px-4 py-8 space-y-8">
        <h1 className="text-xl font-semibold">AWS 키 관리</h1>

        {/* 등록 폼 */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">AWS 키 등록</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label>Access Key ID</Label>
                <Input
                  placeholder="AKIA..."
                  value={form.aws_access_key_id}
                  onChange={(e) => setForm({ ...form, aws_access_key_id: e.target.value })}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label>Secret Access Key</Label>
                <Input
                  type="password"
                  placeholder="••••••••"
                  value={form.aws_secret_access_key}
                  onChange={(e) => setForm({ ...form, aws_secret_access_key: e.target.value })}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label>기본 리전</Label>
                <Input
                  placeholder="ap-northeast-2"
                  value={form.aws_default_region}
                  onChange={(e) => setForm({ ...form, aws_default_region: e.target.value })}
                />
              </div>
              {error && <p className="text-sm text-red-500">{error}</p>}
              {success && <p className="text-sm text-green-600">{success}</p>}
              <Button type="submit" disabled={submitting}>
                {submitting ? "등록 중..." : "등록"}
              </Button>
            </form>
          </CardContent>
        </Card>

        {/* 등록된 키 목록 */}
        <div className="space-y-3">
          <h2 className="font-medium text-gray-700">등록된 키</h2>
          {creds.length === 0 ? (
            <p className="text-sm text-gray-500">등록된 키가 없습니다.</p>
          ) : (
            creds.map((cred) => (
              <Card key={cred.id}>
                <CardContent className="pt-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <Badge>{cred.provider}</Badge>
                        <span className="text-sm text-gray-500">
                          {cred.aws_default_region ?? "-"}
                        </span>
                      </div>
                      <p className="text-xs text-gray-400">
                        등록: {new Date(cred.created_at).toLocaleDateString("ko-KR")}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge variant={cred.is_active ? "default" : "secondary"}>
                        {cred.is_active ? "활성" : "비활성"}
                      </Badge>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleTest(cred.id)}
                      >
                        권한 확인
                      </Button>
                    </div>
                  </div>

                  {testResults[cred.id] && (
                    <div className="bg-gray-50 rounded p-3 text-sm space-y-1">
                      {Object.entries(testResults[cred.id]).map(([key, val]) => (
                        <div key={key} className="flex justify-between">
                          <span className="text-gray-600">{key}</span>
                          <span className={val === "OK" ? "text-green-600 font-medium" : "text-red-500"}>
                            {val}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            ))
          )}
        </div>
      </main>
    </>
  );
}
