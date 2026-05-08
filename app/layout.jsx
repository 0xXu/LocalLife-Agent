import './globals.css';

export const metadata = {
  title: 'WeekendPilot',
  description: '本地生活规划助手前端原型'
};

export default function RootLayout({ children }) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
