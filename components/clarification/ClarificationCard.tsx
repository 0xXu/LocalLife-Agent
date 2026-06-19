'use client';

import React, { useMemo, useState } from 'react';
import { ArrowRight, Check, MessageCircleQuestion } from 'lucide-react';

import type { ClarificationQuestion } from '../../features/runs/schemas';

type ClarificationCardProps = {
  question: ClarificationQuestion;
  submitting?: boolean;
  error?: string | null;
  onSubmit: (questionId: string, answer: unknown) => void | Promise<void>;
};

type OptionValue = string | number | boolean;

export function ClarificationCard({ question, submitting = false, error, onSubmit }: ClarificationCardProps) {
  const [selected, setSelected] = useState<OptionValue | OptionValue[] | null>(null);
  const [customValue, setCustomValue] = useState('');
  const answer = useMemo(() => {
    if (customValue.trim()) {
      return normalizeCustomValue(question, customValue);
    }
    return selected;
  }, [customValue, question, selected]);
  const validationError = validateAnswer(question, answer);
  const canSubmit = !submitting && !validationError;

  function chooseOption(value: OptionValue) {
    setCustomValue('');
    if (question.kind !== 'multi_select') {
      setSelected(value);
      return;
    }
    setSelected((current) => {
      const values = Array.isArray(current) ? current : [];
      return values.includes(value) ? values.filter((item) => item !== value) : [...values, value];
    });
  }

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!canSubmit) return;
    void onSubmit(question.id, answer);
  }

  function handleCustomInput(event: React.FormEvent<HTMLInputElement>) {
    setSelected(null);
    setCustomValue(event.currentTarget.value);
  }

  return (
    <section className="clarification-card" aria-label="补充信息">
      <div className="clarification-card-head">
        <div className="clarification-card-icon" aria-hidden="true">
          <MessageCircleQuestion size={24} />
        </div>
        <div>
          <span>我还需要确认一下</span>
          <h1>{question.label}</h1>
          {question.description && <p>{question.description}</p>}
        </div>
      </div>

      <form className="clarification-card-form" onSubmit={handleSubmit}>
        {!!question.options?.length && (
          <div className="clarification-card-options">
            {question.options.map((option) => {
              const active = isSelected(selected, option.value);
              return (
                <button
                  key={`${option.label}_${String(option.value)}`}
                  type="button"
                  className={active ? 'active' : ''}
                  data-testid={`clarification-option-${String(option.value)}`}
                  aria-pressed={active}
                  onClick={() => chooseOption(option.value)}
                >
                  {active && <Check size={15} />}
                  {option.label}
                </button>
              );
            })}
          </div>
        )}

        {question.allow_custom && (
          <label className="clarification-custom-field">
            <span>{customLabel(question.kind)}</span>
            <input
              data-testid="clarification-custom-input"
              type={question.kind === 'number' ? 'number' : question.kind === 'time' ? 'text' : 'text'}
              inputMode={question.kind === 'number' ? 'numeric' : undefined}
              min={question.validation?.min}
              max={question.validation?.max}
              value={customValue}
              onChange={handleCustomInput}
              onInput={handleCustomInput}
              placeholder={customPlaceholder(question.kind)}
            />
          </label>
        )}

        {(validationError || error) && (
          <p className="clarification-card-error" role="alert">
            {error ?? validationError}
          </p>
        )}

        <button
          className="primary-button clarification-card-submit"
          data-testid="clarification-submit"
          type="submit"
          disabled={!canSubmit}
        >
          {submitting ? '提交中...' : '继续生成'}
          <ArrowRight size={17} />
        </button>
      </form>
    </section>
  );
}

function normalizeCustomValue(question: ClarificationQuestion, value: string): unknown {
  if (question.kind !== 'number') {
    return value.trim();
  }
  const numberValue = Number(value);
  return Number.isFinite(numberValue) ? numberValue : value;
}

function validateAnswer(question: ClarificationQuestion, answer: unknown): string | null {
  if (question.required) {
    if (answer === null || answer === undefined || answer === '') {
      return '请先补充这个信息';
    }
    if (Array.isArray(answer) && answer.length === 0) {
      return '请先补充这个信息';
    }
  }
  if (question.kind === 'number' && typeof answer === 'number') {
    if (question.validation?.min !== undefined && answer < question.validation.min) {
      return `不能小于 ${question.validation.min}`;
    }
    if (question.validation?.max !== undefined && answer > question.validation.max) {
      return `不能大于 ${question.validation.max}`;
    }
  }
  return null;
}

function isSelected(selected: OptionValue | OptionValue[] | null, value: OptionValue) {
  return Array.isArray(selected) ? selected.includes(value) : selected === value;
}

function customLabel(kind: ClarificationQuestion['kind']) {
  if (kind === 'location') return '手动输入地点';
  if (kind === 'time') return '手动输入时间';
  if (kind === 'number') return '手动输入数量';
  return '手动输入';
}

function customPlaceholder(kind: ClarificationQuestion['kind']) {
  if (kind === 'location') return '例如：仙台站、家附近、青叶区';
  if (kind === 'time') return '例如：今天下午 2 点开始，玩 3 小时';
  if (kind === 'number') return '输入数字';
  return '输入你的答案';
}
