import './globals.css';
import type { ReactNode } from 'react';

export const metadata = {
  title: 'WeekendPilot',
  description: '本地生活规划助手前端原型'
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
