'use client';

import React, { useEffect, useRef } from 'react';
import { Brain, ListChecks, ShieldCheck } from 'lucide-react';
import { ChatBubble } from './ChatBubble';
import { QuickActions } from './QuickActions';
import { GoalInput } from './GoalInput';
import { ClarificationCard } from '../clarification/ClarificationCard';
import type { ClarificationQuestion } from '../../features/runs/schemas';

type ChatViewProps = {
  onSubmitGoal: (goal: string) => void;
  isPlanning: boolean;
  error: string | null;
  goal?: string;
  clarificationQuestion?: ClarificationQuestion | null;
  clarificationSubmitting?: boolean;
  onAnswerClarification?: (questionId: string, answer: unknown) => void | Promise<void>;
};

export function ChatView({
  onSubmitGoal,
  isPlanning,
  error,
  goal,
  clarificationQuestion,
  clarificationSubmitting,
  onAnswerClarification,
}: ChatViewProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const qualitySignals = [
    { label: '开放域规划', detail: '不用枚举场景，直接描述需求', icon: Brain },
    { label: '偏好记忆', detail: '结合画像与本轮约束', icon: ShieldCheck },
    { label: '可解释候选', detail: '展示候选来源与取舍', icon: ListChecks },
  ];

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [isPlanning, error, clarificationQuestion]);

  return (
    <section className="chat-view">
      <div className="chat-scroll" ref={scrollRef}>
        <div className="chat-header">
          <div className="chat-header-avatar"><span>AI</span></div>
          <h1>WeekendPilot</h1>
          <p>说清楚你想要的体验，我会补齐约束、检索候选并生成可执行计划。</p>
          <div className="chat-quality-signals" aria-label="规划质量信号">
            {qualitySignals.map((signal) => {
              const Icon = signal.icon;
              return (
                <div key={signal.label} className="chat-quality-card">
                  <Icon size={17} />
                  <strong>{signal.label}</strong>
                  <span>{signal.detail}</span>
                </div>
              );
            })}
          </div>
        </div>

        <ChatBubble role="ai" animate>
          <p>你好！我是 WeekendPilot，你的本地生活助手。</p>
          <p>你可以直接告诉我你的需求，比如：</p>
          <ul>
            <li>"今天下午带孩子出去玩，别太远"</li>
            <li>"和朋友聚餐，想拍照聊天"</li>
            <li>"下雨天有什么室内推荐"</li>
          </ul>
        </ChatBubble>

        {goal && (
          <ChatBubble role="user">
            <p>{goal}</p>
          </ChatBubble>
        )}

        {error && (
          <ChatBubble role="ai">
            <p className="chat-error">{error}</p>
          </ChatBubble>
        )}

        {clarificationQuestion && onAnswerClarification && (
          <ChatBubble role="ai" animate>
            <ClarificationCard
              question={clarificationQuestion}
              submitting={clarificationSubmitting}
              onSubmit={onAnswerClarification}
            />
          </ChatBubble>
        )}

        {isPlanning && (
          <ChatBubble role="ai" animate>
            <div className="chat-typing">
              <span /><span /><span />
            </div>
            <p>正在为你规划行程...</p>
          </ChatBubble>
        )}
      </div>

      <div className="chat-bottom">
        <QuickActions onSelect={onSubmitGoal} disabled={isPlanning} />
        <GoalInput onSubmit={onSubmitGoal} disabled={isPlanning} />
      </div>
    </section>
  );
}
