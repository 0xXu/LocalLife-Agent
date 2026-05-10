'use client';

import React, { useState, useRef, useEffect } from 'react';
import { X } from 'lucide-react';
import type { PlanSummary } from '../../types/api';
import styles from './PlanEditModal.module.css';

export interface PlanEditModalProps {
  plan: PlanSummary;
  onSave: (updates: Partial<PlanSummary>) => Promise<void>;
  onClose: () => void;
}

export function PlanEditModal({ plan, onSave, onClose }: PlanEditModalProps) {
  const [title, setTitle] = useState(plan.title);
  const [tags, setTags] = useState<string[]>(plan.tags);
  const [tagInput, setTagInput] = useState('');
  const [saved, setSaved] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => { inputRef.current?.focus(); }, []);

  function addTag() {
    const tag = tagInput.trim();
    if (tag && !tags.includes(tag)) setTags([...tags, tag]);
    setTagInput('');
  }

  function removeTag(tag: string) {
    setTags(tags.filter((t) => t !== tag));
  }

  async function handleSave() {
    await onSave({ title, tags });
    setSaved(true);
    setTimeout(() => onClose(), 600);
  }

  return (
    <div className={styles.backdrop} onClick={onClose} data-testid="plan-edit-modal">
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div className={styles.header}>
          <h2>编辑计划</h2>
          <button type="button" className={styles.closeBtn} onClick={onClose} aria-label="关闭"><X size={18} /></button>
        </div>
        <div className={styles.field}>
          <label htmlFor="plan-title">标题</label>
          <input ref={inputRef} id="plan-title" value={title} onChange={(e) => setTitle(e.target.value)} />
        </div>
        <div className={styles.field}>
          <label>标签</label>
          <div className={styles.tagInput}>
            {tags.map((tag) => (
              <span key={tag} className={styles.tag}>
                {tag}
                <button type="button" onClick={() => removeTag(tag)} aria-label={`移除 ${tag}`}><X size={10} /></button>
              </span>
            ))}
            <input value={tagInput} onChange={(e) => setTagInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') { e.preventDefault(); addTag(); }
                if (e.key === 'Backspace' && !tagInput && tags.length) removeTag(tags[tags.length - 1]);
              }}
              placeholder={tags.length ? '' : '输入标签后回车'} />
          </div>
        </div>
        <div className={styles.actions}>
          <button type="button" className={styles.cancelBtn} onClick={onClose}>取消</button>
          <button type="button" className={`${styles.saveBtn} ${saved ? styles.saved : ''}`}
            onClick={handleSave} disabled={!title.trim()}>
            {saved ? '已保存' : '保存'}
          </button>
        </div>
      </div>
    </div>
  );
}
