import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CostCutter — 클라우드 비용 최적화",
  description: "AWS/GCP/Azure 인프라 비용 분석 및 절감 솔루션",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ko">
      <body className="antialiased bg-gray-50 text-gray-900">
        {children}
      </body>
    </html>
  );
}
