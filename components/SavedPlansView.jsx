'use client';

import React, { useMemo, useState } from 'react';
import { Calendar, Copy, Edit3, Grid2X2, List, Map, MapPin, Play, Share2, Trash2 } from 'lucide-react';
import { savedPlans } from '@/features/planner/mockAgent';

export function SavedPlansView({ onPlan }) {
  const [plans, setPlans] = useState(savedPlans);
  const [viewMode, setViewMode] = useState('grid');
  const [selectedId, setSelectedId] = useState(savedPlans[0]?.id);
  const [menuPlanId, setMenuPlanId] = useState(null);
  const [editingPlanId, setEditingPlanId] = useState(null);
  const [detailsOpen, setDetailsOpen] = useState(true);
  const [notice, setNotice] = useState('');

  const selected = useMemo(
    () => plans.find((plan) => plan.id === selectedId) ?? plans[0] ?? null,
    [plans, selectedId],
  );

  function selectPlan(planId) {
    setSelectedId(planId);
    setDetailsOpen(true);
  }

  function deleteSelectedPlan() {
    if (!selected) {
      return;
    }
    const nextPlans = plans.filter((plan) => plan.id !== selected.id);
    setPlans(nextPlans);
    setSelectedId(nextPlans[0]?.id ?? null);
    setMenuPlanId(null);
    setEditingPlanId(null);
    setNotice('已删除计划');
  }

  return (
    <section className="saved-view">
      <div className="content-pane">
        <header className="page-heading">
          <div>
            <h1>保存计划</h1>
            <p>管理并执行你收藏的周末行程。</p>
          </div>
          <div className="view-toggle">
            <button
              className={viewMode === 'grid' ? 'active' : ''}
              type="button"
              data-testid="saved-view-grid"
              onClick={() => setViewMode('grid')}
            >
              <Grid2X2 size={17} /> 网格
            </button>
            <button
              className={viewMode === 'list' ? 'active' : ''}
              type="button"
              data-testid="saved-view-list"
              onClick={() => setViewMode('list')}
            >
              <List size={17} /> 列表
            </button>
          </div>
        </header>

        {notice ? <div className="inline-notice" role="status">{notice}</div> : null}

        <div className={`saved-grid ${viewMode === 'list' ? 'list' : ''}`} data-testid="saved-plans-list">
          {plans.map((plan) => (
            <article
              className={`saved-card ${plan.accent}${selected?.id === plan.id ? ' selected' : ''}`}
              key={plan.id}
              onClick={() => selectPlan(plan.id)}
            >
              <div className={`saved-image ${plan.imageClass}`}>
                {plan.imageClass === 'map' ? <Map size={52} /> : null}
                {plan.status === '即将开始' ? <span className="status-badge">即将开始</span> : null}
              </div>
              <div className="saved-body">
                <div className="saved-title">
                  <h2>{plan.title}</h2>
                  <button
                    type="button"
                    aria-label="计划菜单"
                    data-testid={`saved-menu-${plan.id}`}
                    onClick={(event) => {
                      event.stopPropagation();
                      selectPlan(plan.id);
                      setMenuPlanId((current) => current === plan.id ? null : plan.id);
                    }}
                  >
                    •••
                  </button>
                </div>
                {menuPlanId === plan.id ? (
                  <div className="saved-menu-panel" data-testid="saved-menu-panel">
                    <button type="button" onClick={() => { setNotice('已复制计划摘要'); setMenuPlanId(null); }}>复制计划</button>
                    <button type="button" onClick={() => { setNotice('已准备分享文案'); setMenuPlanId(null); }}>分享行程</button>
                  </div>
                ) : null}
                <div className="saved-meta">
                  <span><Calendar size={15} /> {plan.date}</span>
                  <span><MapPin size={15} /> {plan.location}</span>
                </div>
                <div className="tag-row">
                  {plan.tags.map((tag) => <span key={tag}>{tag}</span>)}
                </div>
              </div>
              <footer>
                <button
                  type="button"
                  data-testid={`saved-edit-${plan.id}`}
                  onClick={(event) => {
                    event.stopPropagation();
                    selectPlan(plan.id);
                    setEditingPlanId(plan.id);
                    setNotice('');
                  }}
                >
                  <Edit3 size={16} /> 编辑
                </button>
                <button
                  type="button"
                  data-testid={`saved-execute-${plan.id}`}
                  onClick={(event) => {
                    event.stopPropagation();
                    selectPlan(plan.id);
                    onPlan();
                  }}
                >
                  <Play size={16} /> 执行
                </button>
              </footer>
            </article>
          ))}
        </div>
      </div>

      {detailsOpen && selected ? (
      <aside className="details-panel" data-testid="saved-details-panel">
        <header>
          <h2>计划详情</h2>
          <button type="button" aria-label="关闭" data-testid="details-close" onClick={() => setDetailsOpen(false)}>×</button>
        </header>
        <div className="details-map">
          <div className="coastline" />
        </div>
        <div className="detail-block">
          <span>已选计划</span>
          <strong>{selected.title}</strong>
        </div>
        <div className="detail-block">
          <span>状态</span>
          <strong className="blue-dot">即将开始（3 天后）</strong>
        </div>
        {editingPlanId ? (
          <div className="edit-panel" data-testid="saved-edit-panel">
            <h3>编辑计划</h3>
            <label>
              <span>标题</span>
              <input value={selected.title} readOnly />
            </label>
          </div>
        ) : null}
        <div className="quick-actions">
          <button type="button" data-testid="saved-share" onClick={() => setNotice('已准备分享文案')}><Share2 size={18} /> 分享行程</button>
          <button type="button" data-testid="saved-copy" onClick={() => setNotice('已复制计划摘要')}><Copy size={18} /> 复制计划</button>
          <button className="danger" type="button" data-testid="saved-delete" onClick={deleteSelectedPlan}><Trash2 size={18} /> 删除计划</button>
        </div>
      </aside>
      ) : null}
    </section>
  );
}
