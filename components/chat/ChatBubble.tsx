'use client';

import React from 'react';

type ChatBubbleProps = {
  role: 'user' | 'ai';
  children: React.ReactNode;
  animate?: boolean;
};

export function ChatBubble({ role, children, animate = false }: ChatBubbleProps) {
  return (
    <div
      className={`chat-bubble chat-bubble--${role}${animate ? ' chat-bubble--animate' : ''}`}
      role="article"
      aria-label={role === 'ai' ? 'AI助手' : '你的消息'}
    >
      {role === 'ai' && (
        <div className="chat-bubble-avatar" aria-hidden>
          <span>AI</span>
        </div>
      )}
      <div className="chat-bubble-content">
        {children}
      </div>
    </div>
  );
}
