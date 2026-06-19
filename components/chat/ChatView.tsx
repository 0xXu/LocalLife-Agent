'use client';

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Activity, Brain, ChevronDown, ListChecks, ShieldCheck } from 'lucide-react';
import { ChatBubble } from './ChatBubble';
import { QuickActions } from './QuickActions';
import { GoalInput } from './GoalInput';
import { ClarificationCard } from '../clarification/ClarificationCard';
import type { ClarificationQuestion, RunEventEnvelope } from '../../features/runs/schemas';

type ChatViewProps = {
  onSubmitGoal: (goal: string) => void;
  isPlanning: boolean;
  error: string | null;
  goal?: string;
  planningMessage?: string;
  planningEvents?: RunEventEnvelope[];
  clarificationQuestion?: ClarificationQuestion | null;
  clarificationSubmitting?: boolean;
  onAnswerClarification?: (questionId: string, answer: unknown) => void | Promise<void>;
};

export function ChatView({
  onSubmitGoal,
  isPlanning,
  error,
  goal,
  planningMessage,
  planningEvents = [],
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
  }, [isPlanning, error, clarificationQuestion, planningEvents.length, planningMessage]);

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
            <AgentPlanningBubble
              message={planningMessage}
              events={planningEvents}
            />
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

function AgentPlanningBubble({
  message,
  events,
}: {
  message?: string;
  events: RunEventEnvelope[];
}) {
  const [detailsOpen, setDetailsOpen] = useState(false);
  const statusMessage = message ?? friendlyPlanningMessage(events);
  const stages = useMemo(() => planningStages(events), [events]);
  const details = useMemo(() => events.slice(-8).map(formatRunDetail), [events]);

  return (
    <div className="chat-agent-status">
      <div className="chat-agent-status-head">
        <div className="chat-typing chat-typing--blue" aria-hidden>
          <span /><span /><span />
        </div>
        <p>{statusMessage}</p>
      </div>

      <div className="chat-agent-stages" aria-label="规划进度">
        {stages.map((stage) => (
          <span
            key={stage.label}
            className={`chat-agent-stage chat-agent-stage--${stage.status}`}
          >
            {stage.label}
          </span>
        ))}
      </div>

      {details.length > 0 && (
        <div className={`chat-run-details${detailsOpen ? ' open' : ''}`}>
          <button
            type="button"
            className="chat-run-details-toggle"
            data-testid="chat-run-details-toggle"
            aria-expanded={detailsOpen}
            onClick={() => setDetailsOpen((open) => !open)}
          >
            <Activity size={14} />
            <span>运行细节</span>
            <ChevronDown size={14} />
          </button>
          {detailsOpen && (
            <div className="chat-run-details-list" data-testid="chat-run-details-list">
              {details.map((detail) => (
                <div key={detail.key} className="chat-run-detail-row">
                  <span>{detail.label}</span>
                  <code>{detail.raw}</code>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function friendlyPlanningMessage(events: RunEventEnvelope[]) {
  const latest = events.at(-1);
  if (!latest) return '我正在理解你的需求，先检查时间、人数和出发点。';
  const copy: Partial<Record<RunEventEnvelope['type'], string>> = {
    'run.started': '我正在理解你的需求，先检查时间、人数和出发点。',
    'run.running': '我正在把你的描述拆成可检索的条件。',
    'agent.started': '我正在提取已给出的时间、地点、人数和偏好。',
    'agent.completed': '我已经整理出关键约束，继续检查是否还缺信息。',
    'tool.called': '我正在查找符合条件的本地候选。',
    'tool.completed': '候选已经回来，我正在比较距离、时间和匹配度。',
    'plan.draft.created': '初版方案已经生成，我正在整理路线和备选项。',
    'plan.validation.completed': '我正在校验营业时间、路线和约束。',
    'clarification.required': '我已经理解了主要意图，还差一个关键信息。',
    'approval.required': '方案已经准备好，马上给你确认。',
  };
  return copy[latest.type] ?? '我正在把需求转成可执行的本地生活方案。';
}

function planningStages(events: RunEventEnvelope[]) {
  const latest = events.at(-1)?.type;
  const stageLabels = ['理解需求', '检查缺口', '搜索候选', '生成方案'];
  let activeIndex = 0;

  if (latest === 'clarification.required') activeIndex = 1;
  else if (latest === 'tool.called' || latest === 'tool.completed') activeIndex = 2;
  else if (latest === 'plan.draft.created' || latest === 'plan.validation.completed' || latest === 'approval.required') activeIndex = 3;
  else if (latest === 'run.completed') activeIndex = stageLabels.length;

  return stageLabels.map((label, index) => ({
    label,
    status: index < activeIndex ? 'done' : index === activeIndex ? 'active' : 'pending',
  }));
}

function formatRunDetail(event: RunEventEnvelope) {
  return {
    key: `${event.seq}-${event.type}`,
    label: `#${event.seq} ${event.type}`,
    raw: compactPayload(event.payload),
  };
}

function compactPayload(payload: Record<string, unknown>) {
  const entries = Object.entries(payload).filter(([, value]) => value !== undefined && value !== null);
  if (!entries.length) return '{}';
  return entries
    .slice(0, 3)
    .map(([key, value]) => `${key}: ${String(value)}`)
    .join(', ');
}
