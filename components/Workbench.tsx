'use client';

import {
  Activity,
  ArrowRight,
  Bot,
  Check,
  ChevronDown,
  ChevronUp,
  CircleDot,
  Clock3,
  CreditCard,
  DatabaseZap,
  Lock,
  LockOpen,
  MapPin,
  MessageSquareText,
  Navigation,
  Pencil,
  RefreshCcw,
  Route,
  Send,
  ShieldCheck,
  Sparkles,
  Utensils,
  WalletCards,
  Wrench,
  XCircle,
  Zap,
} from 'lucide-react';
import { FormEvent, useEffect, useMemo, useState } from 'react';
import { useLifeTask } from '@/frontend/useLifeTask';
import type {
  ActionKind,
  FulfillmentEvent,
  GoalEditPayload,
  GoalContract,
  PlanEditPayload,
  PlanNode,
  PreferenceFact,
  TaskPhase,
  ToolTrace,
} from '@/frontend/types';

const heroGoal = '今晚下班后想和朋友好好放松，预算 500，不想排队，23:00 前到家';

const phaseCopy: Record<TaskPhase, { label: string; detail: string }> = {
  understanding: { label: '理解目标', detail: '正在提取结果、约束与上下文' },
  clarifying: { label: '确认关键选择', detail: '只追问会改变方案的问题' },
  retrieving: { label: '核验真实供给', detail: '正在并行确认相关供给是否可用' },
  composing: { label: '组合可行方案', detail: '正在协调时间、预算、路线与取舍' },
  awaiting_mandate: { label: '等待代办授权', detail: '确认范围后可开始占位与预约' },
  awaiting_transaction: { label: '等待付款确认', detail: '逐项确认即将发生的交易' },
  executing: { label: '正在履约', detail: '预约、购券、出票与叫车有序执行' },
  needs_replan: { label: '正在修复方案', detail: '外部供给变化，正在生成最小改动' },
  unsupported: { label: '超出代办边界', detail: '已说明原因与下一步建议' },
  completed: { label: '履约完成', detail: '现实结果已记录' },
  failed: { label: '需要人工处理', detail: '自动恢复未能完成，请查看异常' },
  cancelled: { label: '任务已结束', detail: '未发生的预约、订单或票券已取消' },
};

const actionCopy: Record<ActionKind, string> = {
  reserve_table: '预约餐位',
  buy_coupon: '购买餐券',
  buy_ticket: '购买门票',
  request_ride: '呼叫车辆',
  book_service: '预约到店服务',
  place_order: '提交配送订单',
  start_navigation: '开始导航',
  change_reservation: '修改预约',
  change_ticket: '修改票务',
  change_ride: '调整叫车',
  cancel_reservation: '取消预约',
  refund_coupon: '退餐券',
  refund_ticket: '退门票',
  cancel_ride: '取消叫车',
  cancel_service: '取消服务预约',
  cancel_order: '取消配送订单',
};

const eventCopy: Record<FulfillmentEvent['status'], string> = {
  started: '执行中',
  succeeded: '已完成',
  failed: '发生异常',
  compensated: '已撤销',
};

const time = (value: string) => {
  const parsed = new Date(value);
  if (!Number.isNaN(parsed.getTime())) {
    return new Intl.DateTimeFormat('zh-CN', {
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
      timeZone: 'Asia/Shanghai',
    }).format(parsed);
  }
  return value.slice(0, 5);
};

const verticalMeta = {
  food: { label: '餐饮', Icon: Utensils },
  activity: { label: '活动', Icon: Activity },
  service: { label: '到店服务', Icon: Sparkles },
  delivery: { label: '即时配送', Icon: Zap },
  mobility: { label: '交通', Icon: Navigation },
};

function HaobanMark({ size = 22 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none" aria-hidden="true">
      <circle cx="7.25" cy="8.5" r="2.35" fill="currentColor" />
      <path
        d="M11 8.5h5.2c2.45 0 4.3 1.55 4.3 3.75S18.65 16 16.2 16h-3.4c-2.4 0-4.3 1.55-4.3 3.75s1.9 3.75 4.3 3.75h1.45"
        stroke="currentColor"
        strokeWidth="2.6"
        strokeLinecap="round"
      />
      <path d="m13.5 21.25 3.4 3.35 7.9-9.3" stroke="currentColor" strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function GoalComposer({ busy, onCreate }: { busy: boolean; onCreate: (goal: string) => void }) {
  const [goal, setGoal] = useState(heroGoal);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (goal.trim()) onCreate(goal.trim());
  };

  return (
    <main className="demo-stage launch-stage">
      <aside className="demo-story demo-story-left" aria-hidden="true">
        <span>好办 · LIFE AGENT</span>
        <h2>把一句想法，<br />变成今晚的安排。</h2>
        <p>这是移动端产品的 Web 演示。所有关键动作都按拇指触达、单手浏览和逐步确认来设计。</p>
      </aside>

      <section className="mobile-device launch-shell">
        <header className="brand-bar">
          <div className="brand-mark"><HaobanMark size={22} /></div>
          <div>
            <strong>好办</strong>
            <span>你说想要，剩下好办</span>
          </div>
          <div className="system-online"><i /> 可代办</div>
        </header>

        <section className="launch-grid">
          <div className="launch-copy">
            <div className="eyebrow"><Sparkles size={14} /> 今天想怎么过？</div>
            <h1>说出目标，<br /><em>我来把它办成。</em></h1>
            <p>吃什么、去哪里、怎么衔接，我会核验供给并组合成一条可执行的生活路线。</p>
          </div>

          <form className="goal-composer" onSubmit={submit}>
            <div className="composer-topline">
              <span><MessageSquareText size={17} /> 直接像聊天一样说</span>
              <small>不用写指令</small>
            </div>
            <textarea
              aria-label="生活目标"
              value={goal}
              onChange={(event) => setGoal(event.target.value)}
              placeholder="例如：今晚想和朋友放松一下……"
              rows={5}
            />
            <div className="context-hints" aria-label="可以描述的内容">
              <span>和谁</span><span>想做什么</span><span>预算</span><span>最晚几点</span>
            </div>
            <button className="primary-button" type="submit" disabled={busy || !goal.trim()}>
              {busy ? <RefreshCcw className="spin" size={18} /> : <ArrowRight size={19} />}
              开始安排
            </button>
            <p className="composer-note"><ShieldCheck size={14} /> 预约和付款前，我都会先问你</p>
          </form>

          <div className="capability-line" aria-label="工作过程">
            <span><i>1</i> 理解目标</span><b />
            <span><i>2</i> 核验供给</span><b />
            <span><i>3</i> 确认后执行</span>
          </div>
        </section>
      </section>

      <aside className="demo-story demo-story-right" aria-hidden="true">
        <span>不是搜索框</span>
        <div><strong>01</strong><p>只追问会改变结果的关键问题</p></div>
        <div><strong>02</strong><p>同时协调时间、距离、预算与库存</p></div>
        <div><strong>03</strong><p>现实变化时，只修复受影响的部分</p></div>
      </aside>
    </main>
  );
}

function GoalEditor({ goal, busy, onCancel, onSave }: {
  goal: GoalContract;
  busy: boolean;
  onCancel: () => void;
  onSave: (edit: GoalEditPayload) => void;
}) {
  const [values, setValues] = useState({
    budget_yuan: goal.budget_yuan,
    deadline: goal.deadline,
    origin: goal.origin,
    party_size: goal.party_size,
  });
  const [deadlineLabel, setDeadlineLabel] = useState(goal.deadline_label || '最晚完成');
  const [locked, setLocked] = useState(() => new Set(goal.locked_fields));
  const [hardness, setHardness] = useState(() => Object.fromEntries(
    goal.constraints.map((item) => [item.id, item.hard]),
  ));
  const [assumptions, setAssumptions] = useState(() => Object.fromEntries(
    goal.assumptions.map((item) => [item.id, item.value]),
  ));
  const [removedAssumptions, setRemovedAssumptions] = useState(() => new Set<string>());

  const toggleLock = (field: string) => setLocked((current) => {
    const next = new Set(current);
    if (next.has(field)) next.delete(field); else next.add(field);
    return next;
  });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const originalLocks = new Set(goal.locked_fields);
    const edit: GoalEditPayload = {
      lock_fields: [...locked].filter((item) => !originalLocks.has(item)),
      unlock_fields: [...originalLocks].filter((item) => !locked.has(item)),
      constraint_edits: goal.constraints
        .filter((item) => hardness[item.id] !== item.hard)
        .map((item) => ({ id: item.id, hard: hardness[item.id] })),
      assumption_edits: goal.assumptions
        .filter((item) => removedAssumptions.has(item.id) || assumptions[item.id] !== item.value)
        .map((item) => removedAssumptions.has(item.id)
          ? { id: item.id, delete: true }
          : { id: item.id, value: assumptions[item.id] }),
    };
    if (values.budget_yuan !== goal.budget_yuan) edit.budget_yuan = values.budget_yuan;
    if (values.deadline !== goal.deadline) edit.deadline = values.deadline;
    if (deadlineLabel !== goal.deadline_label) edit.deadline_label = deadlineLabel;
    if (values.origin !== goal.origin) edit.origin = values.origin;
    if (values.party_size !== goal.party_size) edit.party_size = values.party_size;
    const hasChanges = Object.entries(edit).some(([, value]) => (
      Array.isArray(value) ? value.length > 0 : value !== undefined
    ));
    if (!hasChanges) {
      onCancel();
      return;
    }
    onSave(edit);
    onCancel();
  };

  const fact = (field: keyof typeof values, label: string, type: string) => (
    <label className="goal-edit-field">
      <span>{label}</span>
      <div>
        <input
          aria-label={label}
          type={type}
          min={field === 'party_size' ? 1 : undefined}
          value={values[field]}
          onChange={(event) => setValues((current) => ({
            ...current,
            [field]: type === 'number' ? Number(event.target.value) : event.target.value,
          }))}
        />
        <button type="button" className={locked.has(field) ? 'locked' : ''} onClick={() => toggleLock(field)} aria-label={`${locked.has(field) ? '取消锁定' : '锁定'}${label}`}>
          {locked.has(field) ? <Lock size={13} /> : <LockOpen size={13} />}
        </button>
      </div>
    </label>
  );

  return (
    <form className="goal-editor" onSubmit={submit}>
      <div className="goal-edit-grid">
        {fact('budget_yuan', '预算上限', 'number')}
        {fact('deadline', deadlineLabel || '最晚完成', 'time')}
        {fact('origin', '出发位置', 'text')}
        {fact('party_size', '同行人数', 'number')}
        <label className="goal-edit-field">
          <span>截止时间含义</span>
          <div><input aria-label="截止时间含义" value={deadlineLabel} onChange={(event) => setDeadlineLabel(event.target.value)} placeholder="如：最晚结束、最晚到家" /></div>
        </label>
      </div>
      <section className="compact-section">
        <h3>约束强度</h3>
        {goal.constraints.map((constraint) => (
          <button type="button" className="editable-constraint" key={constraint.id} onClick={() => setHardness((current) => ({ ...current, [constraint.id]: !current[constraint.id] }))}>
            <span>{constraint.label}</span><b>{constraint.value}</b><small>{hardness[constraint.id] ? '必须' : '尽量'}</small>
          </button>
        ))}
      </section>
      {goal.assumptions.length > 0 && <section className="compact-section">
        <h3>可编辑假设</h3>
        {goal.assumptions.map((assumption) => !removedAssumptions.has(assumption.id) && (
          <div className="editable-assumption" key={assumption.id}>
            <span>{assumption.label}</span>
            <input value={assumptions[assumption.id]} onChange={(event) => setAssumptions((current) => ({ ...current, [assumption.id]: event.target.value }))} />
            <button type="button" onClick={() => setRemovedAssumptions((current) => new Set(current).add(assumption.id))}>删除</button>
          </div>
        ))}
      </section>}
      <div className="goal-edit-actions">
        <button type="button" onClick={onCancel}>取消</button>
        <button type="submit" disabled={busy}>保存并重新规划</button>
      </div>
    </form>
  );
}

function ConstraintPanel({ task, busy, onEditGoal, onEditingChange }: {
  task: NonNullable<ReturnType<typeof useLifeTask>['task']>;
  busy: boolean;
  onEditGoal: (edit: GoalEditPayload) => void;
  onEditingChange: (editing: boolean) => void;
}) {
  const goal = task.goal;
  const [editing, setEditing] = useState(false);
  return (
    <aside className="side-panel goal-panel">
      <div className="panel-heading">
        <span className="panel-index">01</span>
        <div><h2>目标上下文</h2><p>系统当前如何理解你</p></div>
        {goal && !editing && <button className="panel-edit-button" onClick={() => { setEditing(true); onEditingChange(true); }}><Pencil size={13} /> 编辑</button>}
      </div>
      <blockquote>{task.goal_text}</blockquote>

      {goal && editing ? <GoalEditor goal={goal} busy={busy} onCancel={() => { setEditing(false); onEditingChange(false); }} onSave={onEditGoal} /> : goal ? (
        <>
          <div className="goal-facts">
            <div><WalletCards size={15} /><span>预算上限</span><strong>¥{goal.budget_yuan}</strong></div>
            <div><Clock3 size={15} /><span>{goal.deadline_label || '最晚完成'}</span><strong>{goal.deadline}</strong></div>
            <div><MapPin size={15} /><span>出发位置</span><strong>{goal.origin}</strong></div>
            <div><CircleDot size={15} /><span>同行人数</span><strong>{goal.party_size} 人</strong></div>
          </div>
          {!!goal.context_facts?.filter((item) => !['city', 'origin', 'party_size', 'deadline_meaning'].includes(item.key)).length && (
            <section className="compact-section">
              <h3>场景事实</h3>
              <div className="constraint-stack">
                {goal.context_facts
                  .filter((item) => !['city', 'origin', 'party_size', 'deadline_meaning'].includes(item.key))
                  .map((item) => (
                    <div className="constraint-row" key={item.id}>
                      <i />
                      <span>{item.label}</span>
                      <b>{item.value}</b>
                      {item.source !== 'explicit' && <small>{item.source === 'default' ? '默认' : '推断'}</small>}
                    </div>
                  ))}
              </div>
            </section>
          )}
          <section className="compact-section">
            <h3>必须满足 <span>{goal.constraints.filter((item) => item.hard).length}</span></h3>
            <div className="constraint-stack">
              {goal.constraints.map((constraint) => (
                <div className="constraint-row" key={constraint.id}>
                  <i className={constraint.hard ? 'hard' : ''} />
                  <span>{constraint.label}</span>
                  <b>{constraint.value}</b>
                  {constraint.source !== 'explicit' && <small>{constraint.source === 'default' ? '默认' : '推断'}</small>}
                </div>
              ))}
            </div>
          </section>
          {goal.assumptions.length > 0 && (
            <section className="compact-section assumptions">
              <h3>当前假设 <span>{goal.assumptions.length}</span></h3>
              {goal.assumptions.map((assumption) => (
                <div className="assumption" key={assumption.id}>
                  <div><span>{assumption.label}</span><strong>{assumption.value}</strong></div>
                  <p>{assumption.reason}</p>
                </div>
              ))}
            </section>
          )}
        </>
      ) : (
        <div className="thinking-block">
          <span /><span /><span />
          <p>正在形成结构化目标…</p>
        </div>
      )}
    </aside>
  );
}

function PlanNodeCard({ node, isLast, locked, removable, busy, candidates, onEdit }: {
  node: PlanNode;
  isLast: boolean;
  locked: boolean;
  removable: boolean;
  busy: boolean;
  candidates: PlanNode[];
  onEdit: (edit: PlanEditPayload) => void;
}) {
  const { label, Icon } = verticalMeta[node.vertical];
  const [editingTime, setEditingTime] = useState(false);
  const [startsAt, setStartsAt] = useState(node.starts_at);
  return (
    <article className={`plan-node node-${node.status}`}>
      <div className="route-rail" aria-hidden="true">
        <div className="node-dot"><Icon size={16} /></div>
        {!isLast && <div className="route-line"><i /></div>}
      </div>
      <div className="node-card">
        <div className="node-topline">
          <span className={`vertical-tag ${node.vertical}`}>{label}</span>
          <time>{time(node.starts_at)}—{time(node.ends_at)}</time>
          <strong>¥{node.price_yuan}</strong>
        </div>
        <h3>{node.title}</h3>
        <p className="venue"><MapPin size={14} /> {node.venue}</p>
        <p className="node-reason">{node.reason}</p>
        <div className="node-meta">
          <span className="evidence-pill"><DatabaseZap size={13} /> 已核验 v{node.evidence.inventory_version}</span>
          {node.actions.map((action) => <span key={action}>{actionCopy[action]}</span>)}
          {node.status !== 'proposed' && <span className={`status-${node.status}`}>{node.status === 'completed' ? '已完成' : node.status === 'failed' ? '异常' : node.status === 'approved' ? '已授权' : node.status}</span>}
        </div>
        {node.status === 'proposed' && <div className="node-edit-actions">
          <button disabled={busy} onClick={() => onEdit({
            instruction: `${locked ? '取消锁定' : '锁定'}“${node.title}”，其他节点保持不变。`,
            operation: locked ? 'unlock_node' : 'lock_node',
            node_id: node.id,
          })}>
            {locked ? <Lock size={12} /> : <LockOpen size={12} />}{locked ? '已锁定' : '锁定节点'}
          </button>
          <button disabled={busy || locked || !removable} title={removable ? '删除非必要节点' : '这是达成当前目标的必要节点'} onClick={() => onEdit({
            instruction: `替换“${node.title}”，优先保持其他节点、总预算和最晚完成时间不变。`,
            operation: 'replace_node',
            node_id: node.id,
          })}>
            <RefreshCcw size={12} /> 换一个
          </button>
          <button disabled={busy || locked} onClick={() => setEditingTime((value) => !value)}>
            <Clock3 size={12} /> 调时间
          </button>
          <button disabled={busy || locked} onClick={() => onEdit({
            instruction: `删除非必要节点“${node.title}”，其他部分保持不变。`,
            operation: 'remove_node',
            node_id: node.id,
          })}>
            <XCircle size={12} /> 删除
          </button>
        </div>}
        {editingTime && node.status === 'proposed' && (
          <form className="node-time-editor" onSubmit={(event) => {
            event.preventDefault();
            onEdit({
              instruction: `把“${node.title}”调整到 ${startsAt} 开始，其他部分保持不变。`,
              operation: 'adjust_node',
              node_id: node.id,
              starts_at: startsAt,
            });
            setEditingTime(false);
          }}>
            <input aria-label={`调整${node.title}开始时间`} type="time" value={startsAt} onChange={(event) => setStartsAt(event.target.value)} />
            <input
              aria-label={`拖动${node.title}开始时间`}
              type="range"
              min={0}
              max={1435}
              step={5}
              value={Number(startsAt.slice(0, 2)) * 60 + Number(startsAt.slice(3, 5))}
              onChange={(event) => {
                const minutes = Number(event.target.value);
                setStartsAt(`${String(Math.floor(minutes / 60)).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}`);
              }}
            />
            <button disabled={busy || startsAt === node.starts_at}>应用并修复后续</button>
          </form>
        )}
        {!!candidates.length && node.status === 'proposed' && (
          <div className="node-candidates">
            <small>已核验候选</small>
            {candidates.map((candidate) => (
              <button key={candidate.option_id} disabled={busy || locked} onClick={() => onEdit({
                instruction: `将“${node.title}”替换为已核验候选“${candidate.title}”，其他部分保持不变。`,
                operation: 'replace_node',
                node_id: node.id,
                option_id: candidate.option_id,
              })}>{candidate.title} · ¥{candidate.price_yuan}</button>
            ))}
          </div>
        )}
      </div>
    </article>
  );
}

function PlanCanvas({ task, busy, onEditPlan }: {
  task: NonNullable<ReturnType<typeof useLifeTask>['task']>;
  busy: boolean;
  onEditPlan: (edit: PlanEditPayload) => void;
}) {
  const plan = task.policy?.primary_plan ?? null;
  return (
    <section className="plan-canvas">
      <div className="canvas-heading">
        <div>
          <div className="panel-heading compact">
            <span className="panel-index">02</span>
            <div><h2>今晚这样安排</h2><p>价格、时间和可订状态都已经核对</p></div>
          </div>
        </div>
        {plan && <span className="version-chip">第 {plan.version} 版</span>}
        {plan && task.plan_undo && <button className="panel-edit-button" disabled={busy} onClick={() => onEditPlan({
          instruction: '撤销最近一次尚未履约的计划修改。',
          operation: 'undo_last_edit',
        })}><RefreshCcw size={13} /> 撤销修改</button>}
      </div>

      {task.last_patch && (
        <div className="patch-banner">
          <RefreshCcw size={16} />
          <div>
            <strong>只调整了 {task.last_patch.operations.length} 处</strong>
            <span>{task.last_patch.summary}</span>
            <small>
              其余 {Math.max(0, (plan?.nodes.length ?? 0) - task.last_patch.operations.length)} 项保持不变
              {task.last_patch.operations.map((operation) => ` · ${operation.reason}`).join('')}
            </small>
          </div>
          {task.last_patch.requires_confirmation && <b>需要确认</b>}
        </div>
      )}

      {plan ? (
        <>
          <div className="plan-thesis">
            <div><span>方案主张</span><h1>{plan.title}</h1></div>
            <p>{plan.thesis}</p>
          </div>
          {task.policy && (
            <div className="policy-strip" data-testid="plan-policy">
              <div>
                <span>已验证取舍</span>
                <strong>{task.policy.alternatives.length
                  ? `另有 ${task.policy.alternatives.length} 个可行方向`
                  : '目前没有更省钱且不更晚的替代方案'}</strong>
                {task.policy.alternatives.map((alternative) => (
                  <button className="policy-alternative" disabled={busy} key={alternative.candidate_id} onClick={() => onEditPlan({
                    instruction: `改用${alternative.summary}的可行方向，其他目标保持不变。`,
                    operation: 'select_alternative',
                    candidate_id: alternative.candidate_id,
                  })}>
                    {alternative.summary} · ¥{alternative.total_yuan} · {alternative.completion_time} 完成
                  </button>
                ))}
              </div>
              <div>
                <span>变化预案</span>
                <strong>{task.policy.decision_points.length} 个关键节点会持续观察</strong>
                <small>
                  {task.policy.decision_points.filter((item) => item.fallbacks.length).length} 个已有核验候补
                </small>
              </div>
            </div>
          )}
          <div className="plan-route">
            {plan.nodes.map((node, index) => (
              <PlanNodeCard
                node={node}
                isLast={index === plan.nodes.length - 1}
                locked={plan.locked_node_ids.includes(node.id)}
                removable={plan.nodes.filter((item) => item.capability_id === node.capability_id).length > 1}
                busy={busy}
                candidates={(task.policy?.decision_points.find((item) => item.node_id === node.id)?.fallbacks ?? []).map((item) => item.replacement)}
                onEdit={onEditPlan}
                key={node.id}
              />
            ))}
          </div>
          <div className="plan-bottom">
            <div><span>预计总计</span><strong>¥{plan.total_yuan}</strong><small>/ ¥{plan.goal.budget_yuan}</small></div>
            <div className="budget-bar"><i style={{ width: `${Math.min(100, plan.total_yuan / plan.goal.budget_yuan * 100)}%` }} /></div>
            {plan.tradeoffs.length > 0 && <p><CircleDot size={13} /> 取舍：{plan.tradeoffs.join('；')}</p>}
          </div>
        </>
      ) : (
        <div className="planning-state">
          <div className="radar"><i /><b><Route size={26} /></b></div>
          <h2>{phaseCopy[task.phase].label}</h2>
          <p>{phaseCopy[task.phase].detail}</p>
          <div className={`life-pulse pulse-${task.phase}`} aria-label="方案生成进度">
            <div><i /><span>理解目标</span><small>结果与边界</small></div>
            <b aria-hidden="true" />
            <div><i /><span>核验供给</span><small>可用性与价格</small></div>
            <b aria-hidden="true" />
            <div><i /><span>组合方案</span><small>时间与取舍</small></div>
          </div>
          {!!task.progress_events?.length && (
            <div className="semantic-progress" aria-live="polite">
              {task.progress_events.slice(-3).map((event) => (
                <div key={event.id}><Check size={12} /><span>{event.detail}</span></div>
              ))}
            </div>
          )}
        </div>
      )}
    </section>
  );
}

function ClarificationCard({ task, busy, onSelect, onReply }: {
  task: NonNullable<ReturnType<typeof useLifeTask>['task']>;
  busy: boolean;
  onSelect: (optionId: string) => void;
  onReply: (content: string) => void;
}) {
  const question = task.question;
  const [freeText, setFreeText] = useState('');
  if (!question) return null;
  return (
    <section className="interaction-card clarification-card">
      <div className="interaction-kicker"><MessageSquareText size={15} /> 一个关键选择</div>
      <h3>{question.prompt}</h3>
      <p>{question.why_now}</p>
      <div className="choice-stack">
        {question.options.map((option) => (
          <button disabled={busy} onClick={() => option.branch ? onSelect(option.id) : onReply(option.label)} key={option.id}>
            <span>{option.label}</span><small>{option.impact}</small>
            {option.branch?.feasibility_status === 'feasible' && <b>已验证可行</b>}
            {option.branch?.feasibility_status === 'infeasible' && <b className="not-feasible">当前仍不可行</b>}
            <ArrowRight size={15} />
          </button>
        ))}
      </div>
      {question.allow_free_text && (
        <form className="inline-reply" onSubmit={(event) => { event.preventDefault(); if (freeText.trim()) onReply(freeText.trim()); }}>
          <input aria-label="补充回答" value={freeText} onChange={(event) => setFreeText(event.target.value)} placeholder="或者直接告诉我…" />
          <button aria-label="发送回答" disabled={busy || !freeText.trim()}><Send size={16} /></button>
        </form>
      )}
    </section>
  );
}

function LiveCanvas({ task, busy, onSupplyAction, onReality, onOutcome }: {
  task: NonNullable<ReturnType<typeof useLifeTask>['task']>;
  busy: boolean;
  onSupplyAction: (nodeId: string, action: ActionKind) => void;
  onReality: (event: { kind: 'user_late' | 'weather_change' | 'node_completed'; detail: string; magnitude?: number; node_id?: string }) => void;
  onOutcome: (response: 'achieved' | 'partly' | 'not_achieved') => void;
}) {
  const live = task.live;
  const plan = task.policy?.primary_plan;
  const [confirmingAction, setConfirmingAction] = useState<ActionKind | null>(null);
  const [clock, setClock] = useState(() => Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setClock(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);
  const countdown = useMemo(() => {
    if (!live?.next_step) return null;
    const [hour, minute] = live.next_step.due_at.split(':').map(Number);
    const target = new Date(clock);
    target.setHours(hour, minute, 0, 0);
    const seconds = Math.floor((target.getTime() - clock) / 1000);
    if (seconds <= 0) return '已到计划时间';
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const rest = seconds % 60;
    return `还有 ${hours ? `${hours} 小时 ` : ''}${minutes} 分 ${rest} 秒`;
  }, [clock, live?.next_step]);
  if (!live || !plan) return <PlanCanvas task={task} busy={false} onEditPlan={() => undefined} />;
  return (
    <section className="plan-canvas live-canvas" data-testid="live-mode">
      <div className="canvas-heading">
        <div className="panel-heading compact">
          <span className="panel-index">LIVE</span>
          <div><h2>现场陪伴</h2><p>只显示此刻该做什么和正在发生什么</p></div>
        </div>
        <span className="version-chip">供给状态 v{live.last_signal?.world_version ?? plan.nodes[0]?.evidence.inventory_version}</span>
      </div>
      <div className={`live-hero ${live.risk ? 'has-risk' : ''}`}>
        <small>{task.phase === 'completed' ? '目标已完成' : task.phase === 'cancelled' ? '任务已结束' : '下一步'}</small>
        <h1>{live.next_step?.title ?? (task.phase === 'cancelled' ? '未发生的安排已取消' : '所有现场步骤已完成')}</h1>
        <p>{live.next_step?.instruction ?? live.actual_outcome?.summary}</p>
        {live.next_step && <time><Clock3 size={17} /> {live.next_step.due_at} · {countdown} · {live.next_step.status === 'blocked' ? '等待修复' : '已就绪'}</time>}
      </div>
      <div className="live-status-grid">
        <article>
          <span><Bot size={15} /> 我正在处理</span>
          <strong>{live.agent_activity}</strong>
          {live.waiting_for && <small>等待：{live.waiting_for}</small>}
        </article>
        <article className={live.risk ? 'risk' : ''}>
          <span><DatabaseZap size={15} /> 现实状态</span>
          <strong>{live.risk ?? '当前没有影响计划的新变化'}</strong>
          {!!live.affected_node_ids.length && <small>仅影响 {live.affected_node_ids.join('、')}</small>}
        </article>
      </div>
      {live.actual_outcome && (
        <div className="actual-outcome">
          <div><Check size={19} /><span>{task.phase === 'cancelled' ? '实际结算' : '实际完成'}</span></div>
          <strong>¥{live.actual_outcome.total_yuan}</strong>
          <small>{task.phase === 'cancelled'
            ? `${live.actual_outcome.compensated_node_ids.length} 个承诺已取消或退款`
            : task.outcome_check_in?.response
              ? `${live.actual_outcome.completed_node_ids.length} 个现实步骤已完成 · 结果已归档`
              : `${live.actual_outcome.completed_node_ids.length} 个现实步骤已完成 · 等待你确认最终效果`}</small>
        </div>
      )}
      {task.phase === 'completed' && task.outcome_check_in && !task.outcome_check_in.response && (
        <section className="outcome-check-in">
          <span>最后确认一下结果</span>
          <strong>{task.outcome_check_in.prompt}</strong>
          <div>
            <button disabled={busy} onClick={() => onOutcome('achieved')}>达到了</button>
            <button disabled={busy} onClick={() => onOutcome('partly')}>只达到一部分</button>
            <button disabled={busy} onClick={() => onOutcome('not_achieved')}>没有达到</button>
          </div>
        </section>
      )}
      {!['completed', 'cancelled'].includes(task.phase) && !!live.available_actions.length && (
        <div className="live-actions">
          <span>可继续处理</span>
          {live.available_actions.map((action) => (
            <button
              key={action}
              disabled={busy}
              onClick={() => setConfirmingAction(action)}
            >{actionCopy[action]}</button>
          ))}
        </div>
      )}
      {confirmingAction && (
        <div className="live-action-confirm" role="alert">
          <span>确认{actionCopy[confirmingAction]}？执行后会同步更新任务状态。</span>
          <button disabled={busy} onClick={() => {
            onSupplyAction(
              live.next_step?.node_id ?? plan.nodes[plan.nodes.length - 1].id,
              confirmingAction,
            );
            setConfirmingAction(null);
          }}>确认</button>
          <button disabled={busy} onClick={() => setConfirmingAction(null)}>保留原安排</button>
        </div>
      )}
      {task.phase === 'executing' && live.next_step && (
        <div className="live-actions">
          <span>现场进度</span>
          {live.next_step.completion_available ? (
            <button disabled={busy} onClick={() => onReality({
              kind: 'node_completed',
              node_id: live.next_step!.node_id,
              detail: `用户确认已完成：${live.next_step!.title}`,
            })}>这一项已完成</button>
          ) : <small>{live.next_step.completion_hint}</small>}
        </div>
      )}
      {!['completed', 'cancelled'].includes(task.phase) && (
        <div className="live-actions">
          <span>现场有变化</span>
          <button disabled={busy} onClick={() => onReality({ kind: 'user_late', detail: '用户报告预计晚到 15 分钟', magnitude: 15 })}>我会晚到 15 分钟</button>
          <button disabled={busy} onClick={() => onReality({ kind: 'weather_change', detail: '现场开始下雨，原有步行与户外安排需要重新判断' })}>开始下雨了</button>
        </div>
      )}
      <div className="live-route">
        {plan.nodes.map((node) => (
          <div key={node.id} className={`live-route-node ${node.status}`}>
            <i />
            <span>{node.status === 'completed'
              ? time([...task.reality_events].reverse().find((event) => event.node_id === node.id && event.kind === 'node_completed')?.occurred_at ?? task.updated_at)
              : node.starts_at}</span>
            <strong>{node.title}</strong>
            <small>
              {node.status === 'completed' ? '已完成' : node.status === 'failed' ? '正在修复' : '待进行'}
              {node.supply_reference?.commitments && Object.keys(node.supply_reference.commitments).length > 0
                ? ` · ${Object.keys(node.supply_reference.commitments).map((action) => actionCopy[action as ActionKind]).join('、')}`
                : ''}
            </small>
          </div>
        ))}
      </div>
    </section>
  );
}

function ApprovalCard({ task, busy, approveMandate, confirmTransaction }: {
  task: NonNullable<ReturnType<typeof useLifeTask>['task']>;
  busy: boolean;
  approveMandate: () => void;
  confirmTransaction: () => void;
}) {
  const plan = task.policy?.primary_plan ?? null;
  if (!plan) return null;
  if (task.phase === 'awaiting_mandate') {
    return (
      <section className="interaction-card approval-card">
        <div className="approval-icon"><ShieldCheck size={21} /></div>
        <div className="interaction-kicker">第 1 步 · 代办授权</div>
        <h3>允许我按这个边界开始办</h3>
        <p>可预约和占位，但不会跳过付款确认。</p>
        <div className="mandate-grid">
          <span>预算上限<strong>¥{plan.mandate.max_total_yuan}</strong></span>
          <span>价格浮动<strong>≤ ¥{plan.mandate.max_price_increase_yuan}</strong></span>
          <span>自动替代<strong>{plan.mandate.allow_auto_substitution ? '允许同级' : '不允许'}</strong></span>
          <span>截止时间<strong>{plan.mandate.deadline}</strong></span>
        </div>
        <button className="wide-action" disabled={busy} onClick={approveMandate}>
          {busy ? <RefreshCcw className="spin" size={17} /> : <ShieldCheck size={17} />} 确认代办边界
        </button>
      </section>
    );
  }
  if (task.phase === 'awaiting_transaction' && task.transaction_confirmation) {
    const terms = [...new Set(plan.nodes.flatMap((node) => node.supply_reference?.terms ?? []))];
    return (
      <section className="interaction-card approval-card payment">
        <div className="approval-icon"><CreditCard size={21} /></div>
        <div className="interaction-kicker">第 2 步 · 交易确认</div>
        <h3>确认以下实际支出</h3>
        <div className="transaction-lines">
          {task.transaction_confirmation.lines.map((line) => (
            <div key={`${line.node_id}-${line.action}`}><span>{line.label}</span><strong>¥{line.amount_yuan}</strong></div>
          ))}
          <div className="transaction-total"><span>本次支付上限</span><strong>¥{task.transaction_confirmation.total_cap_yuan}</strong></div>
        </div>
        <div className="transaction-terms">
          <strong>取消与变更</strong>
          {terms.length
            ? terms.slice(0, 3).map((term) => <span key={term}>{term}</span>)
            : <span>如需取消、退款或改期，我会先展示供给规则并再次确认。</span>}
        </div>
        <button className="wide-action amber" disabled={busy} onClick={confirmTransaction}>
          {busy ? <RefreshCcw className="spin" size={17} /> : <CreditCard size={17} />} 确认并执行
        </button>
      </section>
    );
  }
  return null;
}

function FulfillmentLedger({ events, busy, onCompensate }: {
  events: FulfillmentEvent[];
  busy: boolean;
  onCompensate: (eventId: string, action: ActionKind) => void;
}) {
  const [confirming, setConfirming] = useState<string | null>(null);
  if (!events.length) return null;
  return (
    <section className="interaction-card ledger-card">
      <div className="interaction-kicker"><WalletCards size={15} /> 履约凭据</div>
      <div className="event-stack">
        {events.map((event) => (
          <div className={`event-row event-${event.status}`} key={event.id}>
            <span className="event-icon">{event.status === 'failed' ? <XCircle size={15} /> : <Check size={15} />}</span>
            <div><strong>{actionCopy[event.action]}</strong><small>{event.detail}</small></div>
            <time>{eventCopy[event.status]}</time>
            {event.status === 'succeeded' && event.compensation_action && (
              confirming === event.id ? (
                <div className="compensation-confirm">
                  <span>确认{actionCopy[event.compensation_action]}？此操作将单独提交。</span>
                  <button disabled={busy} onClick={() => onCompensate(event.id, event.compensation_action!)}>确认</button>
                  <button disabled={busy} onClick={() => setConfirming(null)}>保留</button>
                </div>
              ) : (
                <button className="compensation-link" onClick={() => setConfirming(event.id)}>
                  {actionCopy[event.compensation_action]}
                </button>
              )
            )}
          </div>
        ))}
      </div>
    </section>
  );
}

function TracePanel({ traces }: { traces: ToolTrace[] }) {
  const [open, setOpen] = useState(false);
  if (!traces.length) return null;
  return (
    <section className="trace-panel">
      <button className="trace-toggle" onClick={() => setOpen(!open)} aria-expanded={open}>
        <span><Wrench size={14} /> 开发者记录 <b>{traces.length}</b></span>
        {open ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
      </button>
      {open && <div className="trace-list">
        {traces.slice().reverse().map((trace) => (
          <div className="trace-row" key={trace.id}>
            <i className={trace.status} />
            <div><strong>{trace.tool}</strong><span>{trace.agent} · {trace.duration_ms}ms</span><p>{trace.result_summary}</p></div>
            {trace.world_version && <small>WORLD v{trace.world_version}</small>}
          </div>
        ))}
      </div>}
    </section>
  );
}

function PreferenceProfile({ facts, contextScope, onRevise }: {
  facts: PreferenceFact[];
  contextScope: string;
  onRevise: (id: string, edit: { preference?: string; context_scope?: string; delete?: boolean }) => Promise<void>;
}) {
  const [editing, setEditing] = useState<string | null>(null);
  const [value, setValue] = useState('');
  const visibleFacts = facts.filter((fact) => (
    fact.context_scope === contextScope || fact.context_scope === 'general'
  ));
  if (!visibleFacts.length) return null;
  return (
    <section className="preference-profile">
      <div className="interaction-kicker"><Sparkles size={14} /> 我逐渐了解的你</div>
      {visibleFacts.slice(-5).reverse().map((fact) => (
        <div className="preference-fact" key={fact.id}>
          {editing === fact.id ? (
            <form onSubmit={async (event) => {
              event.preventDefault();
              if (value.trim()) await onRevise(fact.id, { preference: value.trim() });
              setEditing(null);
            }}>
              <input autoFocus value={value} onChange={(event) => setValue(event.target.value)} />
              <button>保存</button>
            </form>
          ) : (
            <>
              <div><strong>{fact.preference}</strong><small>{fact.context_scope} · {Math.round(fact.confidence * 100)}%</small></div>
              <button onClick={() => { setValue(fact.preference); setEditing(fact.id); }}>修改</button>
              <button onClick={() => onRevise(fact.id, { delete: true })}>不再适用</button>
            </>
          )}
        </div>
      ))}
    </section>
  );
}

function InteractionPanel({ controller }: { controller: ReturnType<typeof useLifeTask> }) {
  const { task, busy, reply, selectDecision, approveMandate, confirmTransaction, compensate, preferences, revisePreference } = controller;
  const [message, setMessage] = useState('');
  if (!task) return null;
  const latestAgent = [...task.messages].reverse().find((item) => item.role === 'agent');
  return (
    <aside className="side-panel interaction-panel">
      <div className="panel-heading">
        <span className="panel-index">03</span>
        <div><h2>决策与履约</h2><p>你只处理真正需要判断的部分</p></div>
      </div>
      <div className="agent-brief">
        <span className="agent-avatar"><Bot size={17} /></span>
        <div><small>生活目标 Agent</small><p>{latestAgent?.content || phaseCopy[task.phase].detail}</p></div>
      </div>
      <ClarificationCard task={task} busy={busy} onSelect={selectDecision} onReply={reply} />
      <ApprovalCard task={task} busy={busy} approveMandate={approveMandate} confirmTransaction={confirmTransaction} />
      <FulfillmentLedger events={task.fulfillment_events} busy={busy} onCompensate={compensate} />
      <PreferenceProfile facts={preferences} contextScope={task.context_scope} onRevise={revisePreference} />
      {!task.question && !['awaiting_mandate', 'awaiting_transaction'].includes(task.phase) && (
        <form className="message-composer" onSubmit={(event) => {
          event.preventDefault();
          if (message.trim()) { reply(message.trim()); setMessage(''); }
        }}>
          <input aria-label="给 Agent 补充信息" value={message} onChange={(event) => setMessage(event.target.value)} placeholder="补充偏好或修改要求…" />
          <button aria-label="发送" disabled={busy || !message.trim()}><Send size={15} /></button>
        </form>
      )}
      <TracePanel traces={task.tool_traces} />
    </aside>
  );
}

function WorldControls({ inject, busy }: { inject: (scenario: string) => Promise<void>; busy: boolean }) {
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState('');
  const scenarios = [
    ['dinner_full', '餐厅满位'],
    ['show_sold_out', '演出售罄'],
    ['price_jump', '价格上涨'],
    ['ride_cancelled', '司机取消'],
    ['reset', '重置世界'],
  ];
  return (
    <div className={`world-controls ${open ? 'open' : ''}`}>
      <button className="world-trigger" onClick={() => setOpen(!open)} aria-expanded={open}>
        <DatabaseZap size={15} /> 世界控制 {open ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
      </button>
      {open && <div className="world-menu">
        <small>开发者场景注入 · Agent 不可见</small>
        {scenarios.map(([id, label]) => (
          <button disabled={busy} key={id} onClick={async () => { setActive(id); await inject(id); setActive(''); }}>
            {active === id ? <RefreshCcw className="spin" size={13} /> : <CircleDot size={13} />}{label}
          </button>
        ))}
      </div>}
    </div>
  );
}

type MobileView = 'goal' | 'plan' | 'assistant';

function MobileNavigation({ active, onChange, needsAttention }: {
  active: MobileView;
  onChange: (view: MobileView) => void;
  needsAttention: boolean;
}) {
  const items: Array<{ id: MobileView; label: string; Icon: typeof Route }> = [
    { id: 'goal', label: '目标', Icon: CircleDot },
    { id: 'plan', label: '方案', Icon: Route },
    { id: 'assistant', label: '助手', Icon: MessageSquareText },
  ];
  return (
    <nav className="mobile-navigation" aria-label="任务视图">
      {items.map(({ id, label, Icon }) => (
        <button
          key={id}
          className={active === id ? 'active' : ''}
          aria-current={active === id ? 'page' : undefined}
          onClick={() => onChange(id)}
        >
          <span><Icon size={20} />{id === 'assistant' && needsAttention && <i />}</span>
          {label}
        </button>
      ))}
    </nav>
  );
}

function MobileApprovalDock({ task, busy, approveMandate, confirmTransaction }: {
  task: NonNullable<ReturnType<typeof useLifeTask>['task']>;
  busy: boolean;
  approveMandate: () => void;
  confirmTransaction: () => void;
}) {
  const plan = task.policy?.primary_plan;
  const [open, setOpen] = useState(false);
  if (!plan) return null;
  const closeAndRun = (action: () => void) => {
    setOpen(false);
    action();
  };
  if (task.phase === 'awaiting_mandate') {
    return (
      <>
        <section className="mobile-action-dock">
          <button className="dock-summary" onClick={() => setOpen(true)}>
            <span>下一步</span><strong>查看代办边界</strong><small>付款前仍会再次确认</small>
          </button>
          <button className="dock-action" disabled={busy} onClick={() => setOpen(true)} aria-label="查看代办边界">
            <ShieldCheck size={18} />
          </button>
        </section>
        {open && (
          <div className="approval-sheet-backdrop" role="presentation" onClick={() => setOpen(false)}>
            <section className="approval-sheet" role="dialog" aria-modal="true" aria-label="代办边界" onClick={(event) => event.stopPropagation()}>
              <i />
              <span>第 1 步 · 代办授权</span>
              <h2>这些事情可以交给我</h2>
              <p>我可以核验、占位和预约；真实付款、取消与退款仍由你确认。</p>
              <div className="mandate-grid">
                <span>最多支出<strong>¥{plan.mandate.max_total_yuan}</strong></span>
                <span>价格变化<strong>不超过 ¥{plan.mandate.max_price_increase_yuan}</strong></span>
                <span>同等替换<strong>{plan.mandate.allow_auto_substitution ? '允许' : '不允许'}</strong></span>
                <span>最晚完成<strong>{plan.mandate.deadline}</strong></span>
              </div>
              <button className="wide-action" disabled={busy} onClick={() => closeAndRun(approveMandate)}>按这个边界开始办</button>
              <button className="sheet-cancel" onClick={() => setOpen(false)}>返回方案</button>
            </section>
          </div>
        )}
      </>
    );
  }
  if (task.phase === 'awaiting_transaction' && task.transaction_confirmation) {
    const terms = [...new Set(plan.nodes.flatMap((node) => node.supply_reference?.terms ?? []))];
    return (
      <>
        <section className="mobile-action-dock payment">
          <button className="dock-summary" onClick={() => setOpen(true)}>
            <span>待确认支付</span><strong>¥{task.transaction_confirmation.total_cap_yuan}</strong><small>查看交易明细</small>
          </button>
          <button className="dock-action" disabled={busy} onClick={() => setOpen(true)} aria-label="查看交易明细"><ArrowRight size={19} /></button>
        </section>
        {open && (
          <div className="approval-sheet-backdrop" role="presentation" onClick={() => setOpen(false)}>
            <section className="approval-sheet payment" role="dialog" aria-modal="true" aria-label="交易确认" onClick={(event) => event.stopPropagation()}>
              <i />
              <span>第 2 步 · 交易确认</span>
              <h2>确认这次真实支出</h2>
              <div className="transaction-lines">
                {task.transaction_confirmation.lines.map((line) => <div key={`${line.node_id}-${line.action}`}><span>{line.label}</span><strong>¥{line.amount_yuan}</strong></div>)}
                <div className="transaction-total"><span>本次支付上限</span><strong>¥{task.transaction_confirmation.total_cap_yuan}</strong></div>
              </div>
              <div className="transaction-terms"><strong>取消与变更</strong>{terms.length ? terms.slice(0, 3).map((term) => <span key={term}>{term}</span>) : <span>变更或取消时会再次向你确认。</span>}</div>
              <button className="wide-action amber" disabled={busy} onClick={() => closeAndRun(confirmTransaction)}>确认支付并执行</button>
              <button className="sheet-cancel" onClick={() => setOpen(false)}>返回方案</button>
            </section>
          </div>
        )}
      </>
    );
  }
  return null;
}

export function Workbench() {
  const controller = useLifeTask();
  const { task, busy, error, create, editGoal, editPlan, stop, injectScenario, supplyAction, reportReality, outcomeCheckIn } = controller;
  const [activeView, setActiveView] = useState<MobileView>('plan');
  const [goalEditing, setGoalEditing] = useState(false);
  const currentPhase = task ? phaseCopy[task.phase] : null;
  const progress = useMemo(() => {
    if (!task) return 0;
    const byPhase: Record<TaskPhase, number> = {
      understanding: 12,
      clarifying: 26,
      retrieving: 42,
      composing: 62,
      awaiting_mandate: 72,
      awaiting_transaction: 82,
      executing: 90,
      needs_replan: 68,
      unsupported: 100,
      completed: 100,
      failed: 100,
      cancelled: 100,
    };
    return byPhase[task.phase];
  }, [task]);

  useEffect(() => {
    if (!task) return;
    if (task.phase === 'clarifying' || task.question) setActiveView('assistant');
    else if (['understanding', 'retrieving', 'composing', 'awaiting_mandate', 'executing', 'needs_replan', 'completed', 'cancelled'].includes(task.phase)) setActiveView('plan');
  }, [task?.id, task?.phase, task?.question?.id]);

  useEffect(() => {
    if (activeView !== 'goal') setGoalEditing(false);
  }, [activeView]);

  if (!task) return (
    <>
      <GoalComposer busy={busy} onCreate={create} />
      {error && <div className="error-toast"><XCircle size={16} />{error}</div>}
    </>
  );

  return (
    <main className="demo-stage workbench-stage">
      <aside className="demo-story demo-story-left task-demo-copy" aria-hidden="true">
        <span>当前生活任务</span>
        <h2>{task.goal?.outcome || task.goal_text}</h2>
        <p>目标、方案与助手是同一个任务的三个视角，不是三个彼此割裂的页面。</p>
      </aside>

      <section className="mobile-device workbench-shell">
        <header className="workbench-header">
          <div className="brand-compact"><span><HaobanMark size={20} /></span><div><strong>好办</strong><small>任务 {task.id.slice(-4).toUpperCase()}</small></div></div>
          <div className="task-status">
            <span className={`phase-dot phase-${task.phase}`} />
            <div><strong>{currentPhase?.label}</strong><small>{currentPhase?.detail}</small></div>
          </div>
          {['understanding', 'retrieving', 'composing'].includes(task.phase) && (
            <button className="stop-planning" onClick={stop}>停止</button>
          )}
        </header>
        <div className="phase-progress"><i style={{ width: `${progress}%` }} /></div>

        <div className={`mobile-screen view-${activeView}`}>
          {activeView === 'goal' && <ConstraintPanel task={task} busy={busy} onEditGoal={editGoal} onEditingChange={setGoalEditing} />}
          {activeView === 'plan' && (
            task.live && ['executing', 'needs_replan', 'completed', 'cancelled'].includes(task.phase)
              ? <LiveCanvas task={task} busy={busy} onSupplyAction={supplyAction} onReality={reportReality} onOutcome={outcomeCheckIn} />
              : <PlanCanvas task={task} busy={busy} onEditPlan={editPlan} />
          )}
          {activeView === 'assistant' && <InteractionPanel controller={controller} />}
        </div>

        {activeView === 'plan' && !goalEditing && (
          <MobileApprovalDock
            task={task}
            busy={busy}
            approveMandate={controller.approveMandate}
            confirmTransaction={controller.confirmTransaction}
          />
        )}
        <MobileNavigation
          active={activeView}
          onChange={setActiveView}
          needsAttention={Boolean(task.question) || ['awaiting_mandate', 'awaiting_transaction'].includes(task.phase)}
        />
        <WorldControls inject={injectScenario} busy={busy} />
        {error && <div className="error-toast"><XCircle size={16} />{error}</div>}
      </section>

      <aside className="demo-story demo-story-right task-demo-meta" aria-hidden="true">
        <span>实时任务状态</span>
        <div><strong>{task.policy?.primary_plan?.nodes.length ?? 0}</strong><p>个已组合步骤</p></div>
        <div><strong>¥{task.policy?.primary_plan?.total_yuan ?? '—'}</strong><p>当前预计总支出</p></div>
        <div><strong>v{task.revision}</strong><p>可追溯任务版本</p></div>
      </aside>
    </main>
  );
}
