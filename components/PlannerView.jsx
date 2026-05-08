'use client';

import {
  CalendarCheck,
  Car,
  Check,
  FlaskConical,
  LocateFixed,
  MoreVertical,
  ReceiptText,
  SlidersHorizontal,
  Sparkles,
  Ticket,
  Users,
  Utensils
} from 'lucide-react';
import { RoutePreview } from './RoutePreview';

const toolLabels = {
  parse_user_goal: '正在解析人群、时间和出行意图。',
  search_places: '正在搜索 5 公里内适合亲子的活动地点。',
  search_restaurants: '正在交叉匹配附近低脂友好餐厅。',
  rank_candidates: '正在按匹配度、等待时间和路线效率排序。',
  optimize_route: '正在生成顺路的空间路线...',
  check_availability: '正在检查餐厅可订时间和活动名额。'
};

const actionIcons = {
  activity_reservation: Ticket,
  restaurant_reservation: Utensils,
  message: CalendarCheck
};

export function PlannerView({ goal, result, receipts, recoveredPlan, onExecute, onRecover }) {
  const plan = recoveredPlan ?? result.plan;

  return (
    <section className="planner-view">
      <div className="conversation-pane">
        <header className="planner-topbar">
          <label className="search-strip">
            <LocateFixed size={18} />
            <span>搜索目的地...</span>
          </label>
          <button className="primary-button compact" type="button" onClick={onExecute}>
            执行
          </button>
          <button className="icon-button" type="button" aria-label="更多">
            <MoreVertical size={19} />
          </button>
        </header>

        <div className="conversation-scroll">
          <div className="user-message">
            <p>{goal}</p>
            <time>12:42</time>
          </div>

          <div className="agent-line">
            <Sparkles size={20} />
            <span>正在为你规划下午...</span>
          </div>

          <section className="constraint-card">
            <div className="card-heading">
              <span>已理解你的需求</span>
              <Check size={18} />
            </div>
            <div className="constraint-grid">
              <Metric icon={Users} label="人群" value={result.constraints.party} />
              <Metric icon={CalendarCheck} label="时长" value={result.constraints.duration} />
              <Metric icon={Utensils} label="饮食" value={result.constraints.dietary} />
              <Metric icon={LocateFixed} label="半径" value={`< ${result.constraints.radiusKm} 公里`} />
            </div>
          </section>

          <ol className="agent-steps">
            {result.trace.slice(0, 5).map((step, index) => (
              <li key={step.tool} className={index < 3 ? 'done' : 'running'}>
                <span>{index < 3 ? <Check size={15} /> : null}</span>
                {toolLabels[step.tool] ?? step.message}
              </li>
            ))}
          </ol>

          <section className="itinerary-section">
            <h2>草案行程：亲子互动 + 健康轻食</h2>
            <div className="timeline-list">
              {plan.itinerary.map((step, index) => (
                <article key={step.placeId} className={`itinerary-card ${index === 0 ? 'featured' : ''}`}>
                  <div className="timeline-dot">
                    {step.category === 'family_activity' ? <FlaskConical size={17} /> : <Utensils size={17} />}
                  </div>
                  <div className="itinerary-content">
                    <div className="itinerary-topline">
                      <h3>{step.title}</h3>
                      <span>{formatTime(step.start)} - {formatTime(step.end)}</span>
                    </div>
                    <p>{step.reason}</p>
                    <footer>
                      <span><ReceiptText size={15} /> {step.cost}</span>
                      <span><Car size={15} /> {step.travel}</span>
                    </footer>
                  </div>
                </article>
              ))}
            </div>
          </section>
        </div>
      </div>

      <aside className="plan-side-panel">
        <RoutePreview />
        <PlanOverview overview={plan.overview} />
        <ActionPanel actions={plan.actions} receipts={receipts} onExecute={onExecute} onRecover={onRecover} />
        {plan.diff ? <RecoveryPanel plan={plan} /> : null}
      </aside>
    </section>
  );
}

function Metric({ icon: Icon, label, value }) {
  return (
    <div className="constraint-metric">
      <span><Icon size={16} /> {label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function PlanOverview({ overview }) {
  return (
    <section className="overview-card">
      <p>计划概览</p>
      <h2>{overview.theme}</h2>
      <dl>
        <div><dt>总时长</dt><dd>{overview.totalDuration}</dd></div>
        <div><dt>预计车程</dt><dd>{overview.driveTime}</dd></div>
        <div><dt>步行距离</dt><dd>{overview.walkingDistance}</dd></div>
        <div><dt>预计花费</dt><dd>{overview.estimatedCost}</dd></div>
      </dl>
    </section>
  );
}

function ActionPanel({ actions, receipts, onExecute, onRecover }) {
  return (
    <section className="action-card">
      <div className="card-heading">
        <span>确认后我会执行</span>
        <small>需要你确认</small>
      </div>
      <div className="action-list">
        {actions.map((action) => {
          const Icon = actionIcons[action.type] ?? CalendarCheck;
          return (
            <div className="action-row" key={action.label}>
              <Icon size={19} />
              <div>
                <strong>{action.label}</strong>
                <span>{action.target} · {action.detail}</span>
              </div>
            </div>
          );
        })}
      </div>
      <button className="primary-button full" type="button" onClick={onExecute}>确认执行</button>
      <button className="secondary-button full" type="button" onClick={onRecover}>
        <SlidersHorizontal size={17} />
        换一家餐厅
      </button>
      {receipts.length ? (
        <div className="receipt-stack">
          {receipts.map((receipt) => (
            <div className="receipt" key={receipt.id}>
              <strong>{receipt.id}</strong>
              <span>{receipt.detail}</span>
            </div>
          ))}
        </div>
      ) : null}
    </section>
  );
}

function RecoveryPanel({ plan }) {
  return (
    <section className="recovery-card">
      <h2>{plan.adjustment.headline}</h2>
      <p>{plan.adjustment.message}</p>
      <div className="diff-grid">
        <div><span>原方案</span><strong>{plan.diff.from}</strong></div>
        <div><span>新方案</span><strong>{plan.diff.to}</strong></div>
        <div><span>预算变化</span><strong>{plan.diff.costDelta}</strong></div>
        <div><span>路线变化</span><strong>{plan.diff.travelDelta}</strong></div>
      </div>
    </section>
  );
}

function formatTime(time) {
  const [hour, minute] = time.split(':').map(Number);
  return `${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}`;
}
