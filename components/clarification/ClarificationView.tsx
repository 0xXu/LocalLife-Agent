'use client';

import React, { useMemo, useState } from 'react';
import { ArrowRight, CalendarClock, MessageCircleQuestion, Sparkles } from 'lucide-react';
import type { ClarificationResponse } from '../../types/weekendpilot';

type ClarificationViewProps = {
  goal: string;
  clarification: ClarificationResponse;
  onSubmitGoal: (goal: string) => void;
};

const quickAnswers: Record<string, string[]> = {
  time_window: ['今天下午 2 小时', '周六半天', '周日晚上 3 小时'],
  activity_intent: ['安静散步和咖啡', '室内放松，不排队', '朋友聚会，先活动再吃饭'],
  people: ['我一个人', '两个人', '两个成人带孩子'],
};

export function ClarificationView({ goal, clarification, onSubmitGoal }: ClarificationViewProps) {
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const composedGoal = useMemo(() => {
    const additions = Object.values(answers).filter(Boolean).join('，');
    return additions ? `${goal}。补充：${additions}` : goal;
  }, [answers, goal]);

  function setAnswer(field: string, value: string) {
    setAnswers((current) => ({ ...current, [field]: value }));
  }

  return (
    <section className="clarification-view">
      <div className="clarification-hero">
        <div className="clarification-signal" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
        <div className="clarification-icon"><MessageCircleQuestion size={26} /></div>
        <h1>再补两点，我就能给你更准的计划</h1>
        <p>后端没有硬套模板生成低置信方案，而是把缺失信息交还给你确认。</p>
      </div>

      <div className="clarification-questions">
        {clarification.clarifying_questions.map((item, index) => (
          <article key={item.field} className="clarification-question" style={{ animationDelay: `${index * 90}ms` }}>
            <div className="clarification-question-head">
              <CalendarClock size={18} />
              <strong>{item.question}</strong>
            </div>
            <div className="clarification-options">
              {(quickAnswers[item.field] ?? []).map((option) => (
                <button
                  key={option}
                  type="button"
                  className={answers[item.field] === option ? 'active' : ''}
                  onClick={() => setAnswer(item.field, option)}
                >
                  {option}
                </button>
              ))}
            </div>
            <input
              value={answers[item.field] ?? ''}
              onChange={(event) => setAnswer(item.field, event.target.value)}
              placeholder="也可以直接输入你的答案"
              aria-label={item.question}
            />
          </article>
        ))}
      </div>

      <div className="clarification-compose">
        <div>
          <span><Sparkles size={15} /> 即将重新提交</span>
          <p>{composedGoal}</p>
        </div>
        <button className="primary-button" type="button" onClick={() => onSubmitGoal(composedGoal)}>
          继续生成
          <ArrowRight size={17} />
        </button>
      </div>
    </section>
  );
}
