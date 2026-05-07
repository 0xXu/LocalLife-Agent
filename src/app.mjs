import {
  buildPlan,
  executePlan,
  recoverUnavailableRestaurant,
  demoTools
} from './agent.mjs';

const state = {
  currentPlan: null
};

const nodes = {
  goalInput: document.querySelector('#goalInput'),
  planButton: document.querySelector('#planButton'),
  recoverButton: document.querySelector('#recoverButton'),
  executeButton: document.querySelector('#executeButton'),
  newPlanButton: document.querySelector('#newPlanButton'),
  constraints: document.querySelector('#constraints'),
  trace: document.querySelector('#trace'),
  timeline: document.querySelector('#timeline'),
  overview: document.querySelector('#overview'),
  receipts: document.querySelector('#receipts'),
  recovery: document.querySelector('#recovery'),
  toolList: document.querySelector('#toolList')
};

nodes.toolList.innerHTML = demoTools.map((tool) => `<span>${tool}</span>`).join('');

function renderPlan(result) {
  state.currentPlan = result.plan;
  nodes.constraints.innerHTML = [
    ['人群', result.constraints.party],
    ['时长', result.constraints.duration],
    ['饮食', result.constraints.dietary],
    ['半径', `${result.constraints.radiusKm}km`],
    ['交通', result.constraints.transport]
  ].map(([label, value]) => `<div><span>${label}</span><strong>${value}</strong></div>`).join('');

  nodes.trace.innerHTML = result.trace.map((step) => `
    <li>
      <span class="status">${step.status}</span>
      <div>
        <strong>${step.tool}</strong>
        <p>${step.message}</p>
        <small>${step.durationMs}ms</small>
      </div>
    </li>
  `).join('');

  renderTimeline(result.plan.itinerary);
  renderOverview(result.plan.overview);
  nodes.receipts.className = 'receipts empty';
  nodes.receipts.textContent = '等待用户确认后执行订座、预约和发送计划。';
  nodes.recovery.className = 'recovery empty';
  nodes.recovery.textContent = '触发“餐厅无位”后，系统只替换冲突节点并保留其余行程。';
}

function renderTimeline(itinerary) {
  nodes.timeline.innerHTML = itinerary.map((step, index) => `
    <div class="timeline-item">
      <span class="step-index">${index + 1}</span>
      <div>
        <div class="time">${step.start} - ${step.end}</div>
        <h3>${step.title}</h3>
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
    <h2>路线概览</h2>
    <dl>
      <div><dt>总时长</dt><dd>${overview.totalDuration}</dd></div>
      <div><dt>车程</dt><dd>${overview.driveTime}</dd></div>
      <div><dt>步行</dt><dd>${overview.walkingDistance}</dd></div>
      <div><dt>预算</dt><dd>${overview.estimatedCost}</dd></div>
    </dl>
  `;
}

function renderReceipts(receipts) {
  nodes.receipts.className = 'receipts';
  nodes.receipts.innerHTML = receipts.map((receipt) => `
    <div class="receipt">
      <span>${receipt.id}</span>
      <strong>${receipt.type}</strong>
      <p>${receipt.detail}</p>
    </div>
  `).join('');
}

function renderRecovery(plan) {
  nodes.recovery.className = 'recovery';
  nodes.recovery.innerHTML = `
    <div class="diff-row"><span>失败原因</span><strong>${plan.diff.reason}</strong></div>
    <div class="diff-row"><span>替换前</span><strong>${plan.diff.from}</strong></div>
    <div class="diff-row"><span>替换后</span><strong>${plan.diff.to}</strong></div>
    <div class="diff-row"><span>影响</span><strong>${plan.diff.costDelta}, ${plan.diff.travelDelta}</strong></div>
    <div class="preserved">保留节点：${plan.diff.preserved.join(' / ')}</div>
  `;
}

nodes.planButton.addEventListener('click', () => {
  renderPlan(buildPlan(nodes.goalInput.value));
});

nodes.executeButton.addEventListener('click', () => {
  if (!state.currentPlan) renderPlan(buildPlan(nodes.goalInput.value));
  renderReceipts(executePlan(state.currentPlan));
});

nodes.recoverButton.addEventListener('click', () => {
  if (!state.currentPlan) renderPlan(buildPlan(nodes.goalInput.value));
  state.currentPlan = recoverUnavailableRestaurant(state.currentPlan);
  renderTimeline(state.currentPlan.itinerary);
  renderRecovery(state.currentPlan);
});

nodes.newPlanButton.addEventListener('click', () => {
  renderPlan(buildPlan(nodes.goalInput.value));
});

renderPlan(buildPlan(nodes.goalInput.value));
