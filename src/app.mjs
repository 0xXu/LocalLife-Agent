import {
  buildPlan,
  executePlan,
  recoverUnavailableRestaurant,
  demoTools
} from './agent.mjs';

const state = {
  currentPlan: null
};

const toolLabels = {
  parse_user_goal: '解析目标',
  search_places: '搜索活动',
  search_restaurants: '搜索餐厅',
  rank_candidates: '候选排序',
  optimize_route: '规划路线',
  check_availability: '检查可订性',
  create_reservation: '创建预约',
  send_plan_message: '发送计划'
};

const receiptLabels = {
  activity_reservation: '活动预约',
  restaurant_reservation: '餐厅订座',
  message: '计划发送'
};

const nodes = {
  goalInput: document.querySelector('#goalInput'),
  planButton: document.querySelector('#planButton'),
  recoverButton: document.querySelector('#recoverButton'),
  executeButton: document.querySelector('#executeButton'),
  executeTopButton: document.querySelector('#executeTopButton'),
  newPlanButton: document.querySelector('#newPlanButton'),
  detailsButton: document.querySelector('#detailsButton'),
  constraints: document.querySelector('#constraints'),
  progressList: document.querySelector('#progressList'),
  trace: document.querySelector('#trace'),
  traceDetails: document.querySelector('#traceDetails'),
  timeline: document.querySelector('#timeline'),
  timelineStatus: document.querySelector('#timelineStatus'),
  overview: document.querySelector('#overview'),
  receipts: document.querySelector('#receipts'),
  recovery: document.querySelector('#recovery'),
  recoveryCard: document.querySelector('#recoveryCard'),
  actionList: document.querySelector('#actionList'),
  planTitle: document.querySelector('#planTitle'),
  toolList: document.querySelector('#toolList')
};

nodes.toolList.innerHTML = demoTools.map((tool) => `<span>${toolLabels[tool] ?? tool}</span>`).join('');

function renderPlan(result) {
  state.currentPlan = result.plan;
  nodes.planTitle.textContent = result.plan.title;
  nodes.constraints.innerHTML = [
    ['人群', result.constraints.party],
    ['时长', result.constraints.duration],
    ['饮食', result.constraints.dietary],
    ['半径', `${result.constraints.radiusKm} 公里`],
    ['交通', result.constraints.transport]
  ].map(([label, value]) => `<div><span>${label}</span><strong>${value}</strong></div>`).join('');

  nodes.progressList.innerHTML = result.progress.map((step) => `
    <li class="${step.status}">
      <span></span>
      <div>
        <strong>${step.label}</strong>
        <p>${step.detail}</p>
      </div>
    </li>
  `).join('');

  nodes.trace.innerHTML = result.trace.map((step) => `
    <li>
      <span class="status">${step.status}</span>
      <div>
        <strong>${toolLabels[step.tool] ?? step.tool}</strong>
        <p>${step.message}</p>
        <small>${step.durationMs} 毫秒</small>
      </div>
    </li>
  `).join('');

  renderTimeline(result.plan.itinerary);
  renderOverview(result.plan.overview);
  renderActions(result.plan.actions);
  nodes.timelineStatus.textContent = '等待确认执行';
  nodes.receipts.className = 'receipts empty';
  nodes.receipts.textContent = '确认后显示活动预约、餐厅订座和计划发送结果。';
  nodes.recoveryCard.hidden = true;
  nodes.recovery.innerHTML = '';
}

function renderTimeline(itinerary) {
  nodes.timeline.innerHTML = itinerary.map((step, index) => `
    <div class="timeline-item">
      <span class="step-index">${index + 1}</span>
      <div>
        <div class="timeline-topline">
          <h3>${step.title}</h3>
          <span class="time">${step.start} - ${step.end}</span>
        </div>
        <p>${step.reason}</p>
        <footer>
          <span>${step.cost}</span>
          <span>${step.travel}</span>
        </footer>
      </div>
    </div>
  `).join('');
}

function renderOverview(overview) {
  nodes.overview.innerHTML = `
    <p class="eyebrow">计划概览</p>
    <h2>${overview.theme}</h2>
    <dl>
      <div><dt>总时长</dt><dd>${overview.totalDuration}</dd></div>
      <div><dt>车程</dt><dd>${overview.driveTime}</dd></div>
      <div><dt>步行</dt><dd>${overview.walkingDistance}</dd></div>
      <div><dt>预算</dt><dd>${overview.estimatedCost}</dd></div>
    </dl>
  `;
}

function renderActions(actions) {
  nodes.actionList.innerHTML = actions.map((action) => `
    <div class="action-item">
      <span></span>
      <div>
        <strong>${action.label}</strong>
        <p>${action.target} · ${action.detail}</p>
      </div>
    </div>
  `).join('');
}

function renderReceipts(receipts) {
  nodes.receipts.className = 'receipts';
  nodes.receipts.innerHTML = receipts.map((receipt) => `
    <div class="receipt">
      <span>${receipt.id}</span>
      <strong>${receiptLabels[receipt.type] ?? receipt.type}</strong>
      <p>${receipt.detail}</p>
    </div>
  `).join('');
}

function renderRecovery(plan) {
  nodes.recoveryCard.hidden = false;
  nodes.recovery.className = 'recovery';
  nodes.recovery.innerHTML = `
    <h3>${plan.adjustment.headline}</h3>
    <p>${plan.adjustment.message}</p>
    <div class="diff-grid">
      <div><span>原餐厅</span><strong>${plan.diff.from}</strong></div>
      <div><span>新餐厅</span><strong>${plan.diff.to}</strong></div>
      <div><span>预算变化</span><strong>${plan.diff.costDelta}</strong></div>
      <div><span>路线变化</span><strong>${plan.diff.travelDelta}</strong></div>
    </div>
    <div class="preserved">保留：${plan.diff.preserved.join(' / ')}</div>
  `;
}

nodes.planButton.addEventListener('click', () => {
  renderPlan(buildPlan(nodes.goalInput.value));
});

nodes.executeButton.addEventListener('click', () => {
  if (!state.currentPlan) renderPlan(buildPlan(nodes.goalInput.value));
  renderReceipts(executePlan(state.currentPlan));
  nodes.timelineStatus.textContent = '已确认并生成回执';
});

nodes.executeTopButton.addEventListener('click', () => {
  nodes.executeButton.click();
});

nodes.recoverButton.addEventListener('click', () => {
  if (!state.currentPlan) renderPlan(buildPlan(nodes.goalInput.value));
  state.currentPlan = recoverUnavailableRestaurant(state.currentPlan);
  renderTimeline(state.currentPlan.itinerary);
  renderActions(state.currentPlan.actions);
  renderRecovery(state.currentPlan);
  nodes.timelineStatus.textContent = '餐厅已替换，等待重新确认';
});

nodes.newPlanButton.addEventListener('click', () => {
  renderPlan(buildPlan(nodes.goalInput.value));
});

nodes.detailsButton.addEventListener('click', () => {
  nodes.traceDetails.hidden = !nodes.traceDetails.hidden;
  nodes.detailsButton.textContent = nodes.traceDetails.hidden ? '查看规划过程' : '收起规划过程';
});

renderPlan(buildPlan(nodes.goalInput.value));
