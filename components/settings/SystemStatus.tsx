'use client';

import React, { useEffect, useState } from 'react';
import { Activity, Cpu, Layers, Settings2, Wrench } from 'lucide-react';
import { getLlmStatus, getToolSchemas, type LlmStatus } from '../../features/system/api';
import styles from './SettingsView.module.css';

export function SystemStatus() {
  const [llm, setLlm] = useState<LlmStatus | null>(null);
  const [tools, setTools] = useState<Array<{ name?: string; description?: string }>>([]);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    getLlmStatus().then(setLlm).catch(() => {});
    getToolSchemas()
      .then((res) => setTools((res.tools ?? []) as Array<{ name?: string; description?: string }>))
      .catch(() => {});
  }, []);

  return (
    <div className={styles.section} style={{ animationDelay: '200ms' }}>
      <h3 className={styles.sectionTitle}><Cpu size={18} /> 系统状态</h3>
      <p className={styles.sectionLead}>后端 LLM 配置和可用工具一览。</p>

      {llm ? (
        <div className={styles.detailGrid ?? ''} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 16 }}>
          <StatusItem icon={<Settings2 size={13} />} label="Provider" value={llm.provider} />
          <StatusItem icon={<Cpu size={13} />} label="Model" value={llm.model} />
          <StatusItem icon={<Activity size={13} />} label="远程连接" value={llm.remote_enabled ? '已启用' : '未启用'} ok={llm.remote_enabled} />
          <StatusItem icon={<Layers size={13} />} label="Thinking" value={llm.disable_thinking ? '已关闭' : '已开启'} ok={llm.disable_thinking} />
          <StatusItem icon={<Layers size={13} />} label="Response Format" value={llm.response_format} />
          <StatusItem icon={<Activity size={13} />} label="API Key" value={llm.api_key} ok={llm.api_key === 'configured'} />
        </div>
      ) : (
        <p style={{ color: 'var(--muted)', fontSize: 13 }}>无法获取 LLM 状态</p>
      )}

      {tools.length > 0 && (
        <>
          <button
            type="button"
            onClick={() => setExpanded(!expanded)}
            style={{
              display: 'inline-flex', alignItems: 'center', gap: 6, padding: '8px 14px',
              border: '1px solid var(--line)', borderRadius: 12, background: '#fff',
              fontSize: 13, fontWeight: 600, color: 'var(--text)', cursor: 'pointer',
            }}
          >
            <Wrench size={14} /> 可用工具 ({tools.length}) {expanded ? '▲' : '▼'}
          </button>
          {expanded && (
            <ul style={{ margin: '10px 0 0', padding: 0, listStyle: 'none', display: 'grid', gap: 6 }}>
              {tools.map((tool, i) => (
                <li key={i} style={{
                  padding: '8px 12px', border: '1px solid var(--line)', borderRadius: 10,
                  background: 'rgba(255,255,255,0.7)', fontSize: 13,
                }}>
                  <strong style={{ color: 'var(--text)' }}>{tool.name ?? `tool_${i}`}</strong>
                  {tool.description && (
                    <span style={{ display: 'block', color: 'var(--muted)', fontSize: 12, marginTop: 2 }}>
                      {tool.description}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
}

function StatusItem({ icon, label, value, ok }: { icon: React.ReactNode; label: string; value: string; ok?: boolean }) {
  return (
    <div style={{
      padding: '8px 12px', border: '1px solid var(--line)', borderRadius: 10,
      background: 'rgba(255,255,255,0.7)', display: 'flex', alignItems: 'center', gap: 8,
    }}>
      <span style={{ color: ok === false ? 'var(--red, #e5484d)' : ok === true ? 'var(--green)' : 'var(--blue)' }}>{icon}</span>
      <div>
        <span style={{ display: 'block', fontSize: 11, color: 'var(--muted)', fontWeight: 600 }}>{label}</span>
        <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text)' }}>{value}</span>
      </div>
    </div>
  );
}
