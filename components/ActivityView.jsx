'use client';

import { Filter, MapPin, ReceiptText, Search, Ticket } from 'lucide-react';
import { recentActivity } from '@/features/planner/mockAgent';

export function ActivityView() {
  return (
    <section className="activity-view">
      <div className="content-pane">
        <header className="activity-header">
          <h1>最近执行</h1>
          <div>
            <button type="button" aria-label="筛选"><Filter size={20} /></button>
            <button type="button" aria-label="搜索"><Search size={20} /></button>
          </div>
        </header>

        <div className="activity-timeline">
          {recentActivity.map((item, index) => (
            <article className="activity-card" key={item.title}>
              <span className={`timeline-node ${index === 0 ? 'active' : ''}`} />
              <div className="activity-card-body">
                <div className="activity-meta">
                  <span>{item.meta}</span>
                  <strong>{item.status}</strong>
                </div>
                <h2>{item.title}</h2>
                <p>{item.body}</p>
                <footer>
                  {item.links.map((link, linkIndex) => (
                    <span key={link}>
                      {linkIndex === 0 ? <ReceiptText size={16} /> : <Ticket size={16} />}
                      {link}
                    </span>
                  ))}
                </footer>
              </div>
            </article>
          ))}
          <div className="timeline-end">最近记录已全部显示</div>
        </div>
      </div>

      <aside className="summary-panel">
        <h2>执行概览</h2>
        <section className="summary-card">
          <span>过去 30 天</span>
          <div><p>已执行计划</p><strong>12</strong></div>
          <div><p>总支出</p><strong>约 3,480 元</strong></div>
          <div><p>高频类型</p><strong>餐饮</strong></div>
        </section>
        <section className="heatmap-card">
          <span>近期热力图</span>
          <div className="heatmap">
            <div className="heat-lines" />
            <strong><MapPin size={16} /> 城市核心区</strong>
          </div>
        </section>
      </aside>
    </section>
  );
}
