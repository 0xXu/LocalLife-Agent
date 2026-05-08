'use client';

import { Calendar, Copy, Edit3, Grid2X2, List, Map, MapPin, Play, Share2, Trash2 } from 'lucide-react';
import { savedPlans } from '@/features/planner/mockAgent';

export function SavedPlansView({ onPlan }) {
  const selected = savedPlans[0];

  return (
    <section className="saved-view">
      <div className="content-pane">
        <header className="page-heading">
          <div>
            <h1>保存计划</h1>
            <p>管理并执行你收藏的周末行程。</p>
          </div>
          <div className="view-toggle">
            <button className="active" type="button"><Grid2X2 size={17} /> 网格</button>
            <button type="button"><List size={17} /> 列表</button>
          </div>
        </header>

        <div className="saved-grid">
          {savedPlans.map((plan) => (
            <article className={`saved-card ${plan.accent}`} key={plan.id}>
              <div className={`saved-image ${plan.imageClass}`}>
                {plan.imageClass === 'map' ? <Map size={52} /> : null}
                {plan.status === '即将开始' ? <span className="status-badge">即将开始</span> : null}
              </div>
              <div className="saved-body">
                <div className="saved-title">
                  <h2>{plan.title}</h2>
                <button type="button" aria-label="计划菜单">•••</button>
                </div>
                <div className="saved-meta">
                  <span><Calendar size={15} /> {plan.date}</span>
                  <span><MapPin size={15} /> {plan.location}</span>
                </div>
                <div className="tag-row">
                  {plan.tags.map((tag) => <span key={tag}>{tag}</span>)}
                </div>
              </div>
              <footer>
                <button type="button"><Edit3 size={16} /> 编辑</button>
                <button type="button" onClick={onPlan}><Play size={16} /> 执行</button>
              </footer>
            </article>
          ))}
        </div>
      </div>

      <aside className="details-panel">
        <header>
          <h2>计划详情</h2>
          <button type="button" aria-label="关闭">×</button>
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
        <div className="quick-actions">
          <button type="button"><Share2 size={18} /> 分享行程</button>
          <button type="button"><Copy size={18} /> 复制计划</button>
          <button className="danger" type="button"><Trash2 size={18} /> 删除计划</button>
        </div>
      </aside>
    </section>
  );
}
