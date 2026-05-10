'use client';

import React, { useMemo, useState } from 'react';
import { Filter, MapPin, ReceiptText, Search, Ticket } from 'lucide-react';
import { recentActivity } from '@/features/planner/mockAgent';

export function ActivityView() {
  const [filterOpen, setFilterOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [selectedReceipt, setSelectedReceipt] = useState(null);

  const visibleActivity = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) {
      return recentActivity;
    }
    return recentActivity.filter((item) => JSON.stringify(item).toLowerCase().includes(normalized));
  }, [query]);

  return (
    <section className="activity-view">
      <div className="content-pane">
        <header className="activity-header">
          <h1>最近执行</h1>
          <div className="activity-tools">
            <button
              type="button"
              aria-label="筛选"
              data-testid="activity-filter-toggle"
              aria-pressed={filterOpen}
              onClick={() => setFilterOpen((open) => !open)}
            >
              <Filter size={20} />
            </button>
            <button
              type="button"
              aria-label="搜索"
              data-testid="activity-search-toggle"
              aria-pressed={searchOpen}
              onClick={() => setSearchOpen((open) => !open)}
            >
              <Search size={20} />
            </button>
          </div>
        </header>

        {filterOpen ? (
          <div className="activity-filter-panel" data-testid="activity-filter-panel">
            <button type="button" className="active">全部</button>
            <button type="button">已完成</button>
            <button type="button">含回执</button>
          </div>
        ) : null}

        {searchOpen ? (
          <div className="activity-search-panel">
            <Search size={17} />
            <input
              data-testid="activity-search-input"
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="搜索执行记录、地点或回执"
            />
          </div>
        ) : null}

        <div className="activity-timeline">
          {visibleActivity.map((item, index) => (
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
                    <button
                      key={link}
                      type="button"
                      data-testid={linkIndex === 0 ? `activity-receipt-${index}` : undefined}
                      onClick={() => setSelectedReceipt({ item, link })}
                    >
                      {linkIndex === 0 ? <ReceiptText size={16} /> : <Ticket size={16} />}
                      {link}
                    </button>
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
        {selectedReceipt ? (
          <section className="activity-receipt-panel" data-testid="activity-receipt-panel">
            <h3>查看回执</h3>
            <strong>{selectedReceipt.item.title}</strong>
            <p>{selectedReceipt.link}</p>
            <button type="button" onClick={() => setSelectedReceipt(null)}>关闭</button>
          </section>
        ) : null}
      </aside>
    </section>
  );
}
