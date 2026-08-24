import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: '好办 · 美团生活意图履约 Agent',
  description: '你说想要，剩下好办。从一句生活目标，到可解释、可授权、可恢复的本地生活履约。',
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
