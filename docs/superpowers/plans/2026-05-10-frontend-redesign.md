# WeekendPilot Frontend Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the WeekendPilot frontend as a mobile-first, chat-centric AI planning assistant that integrates all 10 backend APIs with polished animations and a complete user journey from goal input to execution receipts.

**Architecture:** Single-page app using React useState for state management, organized around a 5-phase plan lifecycle (input → progress → results → confirm → execute). The chat/home view serves as the primary entry point. Planning state is managed through a reducer pattern with clear phase transitions. All views are responsive with a mobile-first approach using CSS custom properties and `@media` breakpoints.

**Tech Stack:** Next.js 15 (App Router, client components), React 19, TypeScript, Zod, lucide-react, CSS custom properties (no Tailwind), existing `lib/api/client.ts` for API calls.

---

## File Structure

```
app/
  page.tsx                          # Root component - state machine + view routing
  layout.tsx                        # Keep existing (lang="zh-CN", globals.css)
  globals.css                       # Rewrite: mobile-first, animations, all new component styles

components/
  layout/
    AppShell.tsx                    # New: responsive shell with mobile bottom nav + desktop sidebar
    BottomNav.tsx                   # New: mobile bottom navigation (5 tabs)
    DesktopSidebar.tsx              # New: desktop sidebar navigation

  chat/
    ChatView.tsx                    # New: AI assistant home - chat bubbles + quick actions
    ChatBubble.tsx                  # New: single message bubble (user/AI)
    QuickActions.tsx                # New: scenario quick-action chips
    GoalInput.tsx                   # New: text input + voice + send button

  planning/
    PlanningProgress.tsx            # New: animated multi-step progress indicator
    ProgressStep.tsx                # New: single step with status icon + animation

  plan/
    PlanResultsView.tsx             # New: main plan results container
    ItineraryTimeline.tsx           # New: vertical timeline with staggered reveal animations
    ItineraryCard.tsx               # New: single timeline card (time, title, reason, cost, travel)
    ConstraintChips.tsx             # New: compact constraint display with inline edit
    OverviewCard.tsx                # New: plan summary card (theme, duration, cost, score)
    VariantSelector.tsx             # New: horizontal scroll variant tabs (calls buildAlternatives)
    RouteMapCard.tsx                # New: compact route map for mobile

  confirm/
    ConfirmView.tsx                 # New: action confirmation list with toggles
    ActionToggle.tsx                # New: single action with on/off switch + details
    ExecuteButton.tsx               # New: animated execute button with progress

  receipts/
    ReceiptsView.tsx                # New: execution results with receipt cards
    ReceiptCard.tsx                 # New: single receipt with status animation

  recovery/
    RecoveryBanner.tsx              # New: inline recovery notification + diff display

  trace/
    TracePanel.tsx                  # Keep existing, adapt props
    ToolCallDetails.tsx             # Keep existing

  map/
    RouteMap.tsx                    # Keep existing

features/
  planner/
    apiClient.ts                    # Keep existing (all 10 functions already defined)
    usePlanMachine.ts               # New: custom hook - plan lifecycle state machine
    useAnimations.ts                # New: shared animation utilities (stagger, spring)
    uiFixtures.js                   # Keep existing for scenarioPrompts

lib/
  api/client.ts                     # Keep existing
  contracts/schemas.ts              # Keep existing
  routing/routeProvider.ts          # Keep existing
  observability/tracing.ts          # Keep existing

types/
  weekendpilot.ts                   # Keep existing
  views.ts                          # New: view/tab type definitions
```

---

## Task 1: Create the Plan State Machine Hook

**Files:**
- Create: `features/planner/usePlanMachine.ts`
- Create: `types/views.ts`

- [ ] **Step 1: Define view types**

Create `types/views.ts`:
```typescript
export type ActiveTab = 'home' | 'plans' | 'activity' | 'settings';

export type PlanPhase =
  | 'idle'           // no plan, on home screen
  | 'planning'       // buildPlan in progress
  | 'results'        // plan generated, viewing itinerary
  | 'confirming'     // reviewing pending actions
  | 'executing'      // executePlan in progress
  | 'completed'      // execution done, viewing receipts
  | 'recovering';    // recoverPlan in progress

export type PlanState = {
  phase: PlanPhase;
  goal: string;
  planId: string | null;
  result: import('./weekendpilot').PlanResponse | null;
  recoveredPlan: import('./weekendpilot').Plan['plan'] | null;
  receipts: import('./weekendpilot').PlanResponse['receipts'];
  error: string | null;
  selectedActions: Set<string>;  // action keys user has toggled on
};
```

- [ ] **Step 2: Create the plan state machine hook**

Create `features/planner/usePlanMachine.ts`:
```typescript
import { useCallback, useReducer } from 'react';
import type { PlanPhase, PlanState } from '../../types/views';
import type { PlanResponse } from '../../types/weekendpilot';
import {
  buildPlan,
  buildAlternatives,
  confirmPlan,
  executePlan,
  recoverPlan,
} from './apiClient';

type Action =
  | { type: 'START_PLAN'; goal: string }
  | { type: 'PLAN_LOADED'; result: PlanResponse }
  | { type: 'PLAN_FAILED'; error: string }
  | { type: 'GO_TO_CONFIRM' }
  | { type: 'START_EXECUTE' }
  | { type: 'EXECUTE_LOADED'; result: PlanResponse }
  | { type: 'EXECUTE_FAILED'; error: string }
  | { type: 'START_RECOVER' }
  | { type: 'RECOVER_LOADED'; result: PlanResponse }
  | { type: 'RECOVER_FAILED'; error: string }
  | { type: 'TOGGLE_ACTION'; key: string }
  | { type: 'SELECT_ALL_ACTIONS' }
  | { type: 'DESELECT_ALL_ACTIONS' }
  | { type: 'RESET' }
  | { type: 'SET_PHASE'; phase: PlanPhase };

const initialState: PlanState = {
  phase: 'idle',
  goal: '',
  planId: null,
  result: null,
  recoveredPlan: null,
  receipts: [],
  error: null,
  selectedActions: new Set(),
};

function getActionKey(action: Record<string, unknown>): string {
  return `${action.tool ?? action.type}_${action.label ?? action.place_id ?? 'default'}`;
}

function reducer(state: PlanState, action: Action): PlanState {
  switch (action.type) {
    case 'START_PLAN':
      return {
        ...initialState,
        phase: 'planning',
        goal: action.goal,
      };
    case 'PLAN_LOADED': {
      const plan = action.result.plan;
      const allKeys = new Set(
        (plan.actions ?? []).map((a) => getActionKey(a))
      );
      return {
        ...state,
        phase: 'results',
        planId: plan.id,
        result: action.result,
        recoveredPlan: null,
        receipts: [],
        error: null,
        selectedActions: allKeys,
      };
    }
    case 'PLAN_FAILED':
      return {
        ...state,
        phase: 'idle',
        error: action.error,
      };
    case 'GO_TO_CONFIRM':
      return {
        ...state,
        phase: 'confirming',
        error: null,
      };
    case 'START_EXECUTE':
      return {
        ...state,
        phase: 'executing',
        error: null,
      };
    case 'EXECUTE_LOADED':
      return {
        ...state,
        phase: 'completed',
        result: action.result,
        recoveredPlan: null,
        receipts: action.result.receipts,
        error: null,
      };
    case 'EXECUTE_FAILED':
      return {
        ...state,
        phase: 'results',
        error: action.error,
      };
    case 'START_RECOVER':
      return {
        ...state,
        phase: 'recovering',
        error: null,
      };
    case 'RECOVER_LOADED':
      return {
        ...state,
        phase: 'results',
        result: action.result,
        recoveredPlan: action.result.plan,
        receipts: [],
        error: null,
      };
    case 'RECOVER_FAILED':
      return {
        ...state,
        phase: 'results',
        error: action.error,
      };
    case 'TOGGLE_ACTION': {
      const next = new Set(state.selectedActions);
      if (next.has(action.key)) {
        next.delete(action.key);
      } else {
        next.add(action.key);
      }
      return { ...state, selectedActions: next };
    }
    case 'SELECT_ALL_ACTIONS': {
      const plan = state.recoveredPlan ?? state.result?.plan;
      const allKeys = new Set(
        (plan?.actions ?? []).map((a) => getActionKey(a))
      );
      return { ...state, selectedActions: allKeys };
    }
    case 'DESELECT_ALL_ACTIONS':
      return { ...state, selectedActions: new Set() };
    case 'RESET':
      return initialState;
    case 'SET_PHASE':
      return { ...state, phase: action.phase };
    default:
      return state;
  }
}

export function usePlanMachine() {
  const [state, dispatch] = useReducer(reducer, initialState);

  const startPlan = useCallback(async (goal: string) => {
    dispatch({ type: 'START_PLAN', goal });
    try {
      const result = await buildPlan(goal);
      dispatch({ type: 'PLAN_LOADED', result });
    } catch (err) {
      dispatch({
        type: 'PLAN_FAILED',
        error: err instanceof Error ? err.message : '计划生成失败',
      });
    }
  }, []);

  const goToConfirm = useCallback(() => {
    dispatch({ type: 'GO_TO_CONFIRM' });
  }, []);

  const executeCurrentPlan = useCallback(async () => {
    const planId = (state.recoveredPlan ?? state.result?.plan)?.id;
    if (!planId) return;
    dispatch({ type: 'START_EXECUTE' });
    try {
      const result = await executePlan(planId);
      dispatch({ type: 'EXECUTE_LOADED', result });
    } catch (err) {
      dispatch({
        type: 'EXECUTE_FAILED',
        error: err instanceof Error ? err.message : '执行失败',
      });
    }
  }, [state.recoveredPlan, state.result]);

  const confirmAndExecute = useCallback(async () => {
    const planId = (state.recoveredPlan ?? state.result?.plan)?.id;
    if (!planId) return;
    dispatch({ type: 'START_EXECUTE' });
    try {
      await confirmPlan(planId);
      const result = await executePlan(planId);
      dispatch({ type: 'EXECUTE_LOADED', result });
    } catch (err) {
      dispatch({
        type: 'EXECUTE_FAILED',
        error: err instanceof Error ? err.message : '执行失败',
      });
    }
  }, [state.recoveredPlan, state.result]);

  const recoverCurrentPlan = useCallback(async (reason: string) => {
    const planId = (state.recoveredPlan ?? state.result?.plan)?.id;
    if (!planId) return;
    dispatch({ type: 'START_RECOVER' });
    try {
      const result = await recoverPlan(planId, reason);
      dispatch({ type: 'RECOVER_LOADED', result });
    } catch (err) {
      dispatch({
        type: 'RECOVER_FAILED',
        error: err instanceof Error ? err.message : '恢复失败',
      });
    }
  }, [state.recoveredPlan, state.result]);

  const loadAlternatives = useCallback(async () => {
    if (!state.planId) return;
    try {
      const result = await buildAlternatives(state.planId);
      dispatch({ type: 'PLAN_LOADED', result });
    } catch {
      // alternatives are optional, fail silently
    }
  }, [state.planId]);

  const toggleAction = useCallback((key: string) => {
    dispatch({ type: 'TOGGLE_ACTION', key });
  }, []);

  const selectAllActions = useCallback(() => {
    dispatch({ type: 'SELECT_ALL_ACTIONS' });
  }, []);

  const deselectAllActions = useCallback(() => {
    dispatch({ type: 'DESELECT_ALL_ACTIONS' });
  }, []);

  const reset = useCallback(() => {
    dispatch({ type: 'RESET' });
  }, []);

  const setPhase = useCallback((phase: PlanPhase) => {
    dispatch({ type: 'SET_PHASE', phase });
  }, []);

  return {
    state,
    startPlan,
    goToConfirm,
    executeCurrentPlan,
    confirmAndExecute,
    recoverCurrentPlan,
    loadAlternatives,
    toggleAction,
    selectAllActions,
    deselectAllActions,
    reset,
    setPhase,
    getActionKey,
  };
}
```

- [ ] **Step 3: Verify TypeScript compiles**

Run: `npx tsc --noEmit --pretty 2>&1 | head -20`
Expected: No errors from the new files (existing errors from other files are OK).

- [ ] **Step 4: Commit**

```bash
git add types/views.ts features/planner/usePlanMachine.ts
git commit -m "feat: add plan state machine hook with full lifecycle management"
```

---

## Task 2: Create the Responsive Shell Layout

**Files:**
- Create: `components/layout/AppShell.tsx`
- Create: `components/layout/BottomNav.tsx`
- Create: `components/layout/DesktopSidebar.tsx`
- Modify: `app/globals.css` (add new layout styles)

- [ ] **Step 1: Create BottomNav component**

Create `components/layout/BottomNav.tsx`:
```tsx
'use client';

import React from 'react';
import { Bot, Clock, Compass, Settings, User } from 'lucide-react';
import type { ActiveTab } from '../../types/views';

type BottomNavProps = {
  active: ActiveTab;
  onNavigate: (tab: ActiveTab) => void;
};

const tabs: Array<{ id: ActiveTab; label: string; icon: typeof Bot }> = [
  { id: 'home', label: 'AI助手', icon: Bot },
  { id: 'plans', label: '计划', icon: Compass },
  { id: 'activity', label: '记录', icon: Clock },
  { id: 'settings', label: '设置', icon: Settings },
];

export function BottomNav({ active, onNavigate }: BottomNavProps) {
  return (
    <nav className="bottom-nav" role="navigation" aria-label="主导航">
      {tabs.map((tab) => {
        const Icon = tab.icon;
        const isActive = active === tab.id;
        return (
          <button
            key={tab.id}
            className={`bottom-nav-item${isActive ? ' active' : ''}`}
            type="button"
            onClick={() => onNavigate(tab.id)}
            aria-current={isActive ? 'page' : undefined}
          >
            <span className="bottom-nav-icon">
              <Icon size={22} strokeWidth={isActive ? 2.4 : 1.8} />
              {isActive && <span className="bottom-nav-dot" />}
            </span>
            <span className="bottom-nav-label">{tab.label}</span>
          </button>
        );
      })}
    </nav>
  );
}
```

- [ ] **Step 2: Create DesktopSidebar component**

Create `components/layout/DesktopSidebar.tsx`:
```tsx
'use client';

import React from 'react';
import { Bot, Clock, Compass, Plus, Settings } from 'lucide-react';
import type { ActiveTab } from '../../types/views';

type DesktopSidebarProps = {
  active: ActiveTab;
  onNavigate: (tab: ActiveTab) => void;
  onNewPlan: () => void;
};

const navItems: Array<{ id: ActiveTab; label: string; icon: typeof Bot }> = [
  { id: 'home', label: 'AI助手', icon: Bot },
  { id: 'plans', label: '我的计划', icon: Compass },
  { id: 'activity', label: '执行记录', icon: Clock },
  { id: 'settings', label: '偏好设置', icon: Settings },
];

export function DesktopSidebar({ active, onNavigate, onNewPlan }: DesktopSidebarProps) {
  return (
    <aside className="desktop-sidebar" aria-label="主导航">
      <div className="sidebar-brand">
        <div className="sidebar-brand-avatar">WP</div>
        <div>
          <strong>WeekendPilot</strong>
          <span>本地生活助手</span>
        </div>
      </div>

      <button className="sidebar-new-plan" type="button" onClick={onNewPlan}>
        <Plus size={18} />
        新计划
      </button>

      <nav className="sidebar-nav">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = active === item.id;
          return (
            <button
              key={item.id}
              className={`sidebar-nav-item${isActive ? ' active' : ''}`}
              type="button"
              onClick={() => onNavigate(item.id)}
              aria-current={isActive ? 'page' : undefined}
            >
              <Icon size={20} strokeWidth={isActive ? 2.4 : 1.8} />
              {item.label}
            </button>
          );
        })}
      </nav>
    </aside>
  );
}
```

- [ ] **Step 3: Create AppShell component**

Create `components/layout/AppShell.tsx`:
```tsx
'use client';

import React from 'react';
import type { ActiveTab } from '../../types/views';
import { BottomNav } from './BottomNav';
import { DesktopSidebar } from './DesktopSidebar';

type AppShellProps = {
  activeTab: ActiveTab;
  onNavigate: (tab: ActiveTab) => void;
  onNewPlan: () => void;
  children: React.ReactNode;
};

export function AppShell({ activeTab, onNavigate, onNewPlan, children }: AppShellProps) {
  return (
    <div className="app-shell">
      <DesktopSidebar active={activeTab} onNavigate={onNavigate} onNewPlan={onNewPlan} />
      <main className="app-main">
        <div className="app-content">
          {children}
        </div>
        <BottomNav active={activeTab} onNavigate={onNavigate} />
      </main>
    </div>
  );
}
```

- [ ] **Step 4: Add layout styles to globals.css**

Add the following CSS to `app/globals.css` (append at the end, after existing styles):

```css
/* ==========================================
   LAYOUT: Responsive Shell
   ========================================== */

.app-shell {
  min-height: 100vh;
  min-height: 100dvh;
  display: grid;
  grid-template-columns: 1fr;
  background: var(--bg);
}

@media (min-width: 820px) {
  .app-shell {
    grid-template-columns: 260px 1fr;
  }
}

.app-main {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  min-height: 100dvh;
  position: relative;
}

.app-content {
  flex: 1;
  overflow-y: auto;
  padding-bottom: 80px; /* space for bottom nav */
}

@media (min-width: 820px) {
  .app-content {
    padding-bottom: 0;
  }
}

/* ==========================================
   BOTTOM NAV (mobile)
   ========================================== */

.bottom-nav {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 100;
  display: flex;
  justify-content: space-around;
  align-items: flex-end;
  padding: 6px 0 max(6px, env(safe-area-inset-bottom));
  background: var(--panel);
  border-top: 1px solid var(--line);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}

@media (min-width: 820px) {
  .bottom-nav {
    display: none;
  }
}

.bottom-nav-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 6px 16px;
  background: none;
  color: var(--muted);
  transition: color 0.2s ease;
  -webkit-tap-highlight-color: transparent;
}

.bottom-nav-item.active {
  color: var(--blue);
}

.bottom-nav-icon {
  position: relative;
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
}

.bottom-nav-dot {
  position: absolute;
  bottom: -4px;
  left: 50%;
  transform: translateX(-50%);
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: var(--blue);
  animation: nav-dot-in 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}

@keyframes nav-dot-in {
  from { scale: 0; opacity: 0; }
  to { scale: 1; opacity: 1; }
}

.bottom-nav-label {
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.01em;
}

/* ==========================================
   DESKTOP SIDEBAR
   ========================================== */

.desktop-sidebar {
  display: none;
}

@media (min-width: 820px) {
  .desktop-sidebar {
    display: flex;
    flex-direction: column;
    gap: 24px;
    padding: 20px 16px;
    background: var(--sidebar);
    border-right: 1px solid var(--line);
    min-height: 100vh;
    position: sticky;
    top: 0;
  }
}

.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 4px;
}

.sidebar-brand-avatar {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  display: grid;
  place-items: center;
  background: linear-gradient(135deg, #0b77ff, #0056b8);
  color: white;
  font-weight: 800;
  font-size: 15px;
  box-shadow: var(--shadow-sm);
}

.sidebar-brand strong {
  display: block;
  font-size: 18px;
  line-height: 1.2;
}

.sidebar-brand span {
  display: block;
  font-size: 12px;
  color: var(--muted);
}

.sidebar-new-plan {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 10px 16px;
  border-radius: 12px;
  background: var(--blue);
  color: white;
  font-weight: 600;
  font-size: 14px;
  transition: background 0.15s ease, transform 0.15s ease;
}

.sidebar-new-plan:hover {
  background: #0056b8;
}

.sidebar-new-plan:active {
  transform: scale(0.97);
}

.sidebar-nav {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.sidebar-nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 10px;
  background: none;
  color: var(--muted);
  font-size: 14px;
  font-weight: 500;
  transition: background 0.15s ease, color 0.15s ease;
}

.sidebar-nav-item:hover {
  background: var(--surface-2);
  color: var(--text);
}

.sidebar-nav-item.active {
  background: var(--blue-soft);
  color: var(--blue);
  font-weight: 600;
}
```

- [ ] **Step 5: Verify CSS has no syntax errors**

Run: `npx next build 2>&1 | tail -5`
Expected: Build succeeds (or only pre-existing errors).

- [ ] **Step 6: Commit**

```bash
git add components/layout/ app/globals.css
git commit -m "feat: add responsive shell layout with mobile bottom nav and desktop sidebar"
```

---

## Task 3: Create the Chat Home View

**Files:**
- Create: `components/chat/ChatView.tsx`
- Create: `components/chat/ChatBubble.tsx`
- Create: `components/chat/QuickActions.tsx`
- Create: `components/chat/GoalInput.tsx`

- [ ] **Step 1: Create ChatBubble component**

Create `components/chat/ChatBubble.tsx`:
```tsx
'use client';

import React from 'react';

type ChatBubbleProps = {
  role: 'user' | 'ai';
  children: React.ReactNode;
  animate?: boolean;
};

export function ChatBubble({ role, children, animate = false }: ChatBubbleProps) {
  return (
    <div
      className={`chat-bubble chat-bubble--${role}${animate ? ' chat-bubble--animate' : ''}`}
      role="article"
      aria-label={role === 'ai' ? 'AI助手' : '你的消息'}
    >
      {role === 'ai' && (
        <div className="chat-bubble-avatar" aria-hidden>
          <span>AI</span>
        </div>
      )}
      <div className="chat-bubble-content">
        {children}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create QuickActions component**

Create `components/chat/QuickActions.tsx`:
```tsx
'use client';

import React from 'react';
import { CloudRain, Heart, Sparkles, Users, Utensils } from 'lucide-react';
import { scenarioPrompts } from '../../features/planner/uiFixtures';

type QuickActionsProps = {
  onSelect: (goal: string) => void;
  disabled?: boolean;
};

const actions = [
  { id: 'family', label: '带娃出行', icon: Users, prompt: scenarioPrompts.family, color: 'blue' },
  { id: 'friends', label: '朋友聚会', icon: Utensils, prompt: scenarioPrompts.friends, color: 'violet' },
  { id: 'date', label: '浪漫约会', icon: Heart, prompt: scenarioPrompts.date, color: 'green' },
  { id: 'rainy', label: '雨天方案', icon: CloudRain, prompt: scenarioPrompts.rainy, color: 'coral' },
];

export function QuickActions({ onSelect, disabled }: QuickActionsProps) {
  return (
    <div className="quick-actions" role="group" aria-label="快捷场景">
      {actions.map((action, index) => {
        const Icon = action.icon;
        return (
          <button
            key={action.id}
            className={`quick-action quick-action--${action.color}`}
            type="button"
            disabled={disabled}
            onClick={() => onSelect(action.prompt)}
            style={{ animationDelay: `${index * 80}ms` }}
          >
            <Icon size={18} />
            <span>{action.label}</span>
          </button>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 3: Create GoalInput component**

Create `components/chat/GoalInput.tsx`:
```tsx
'use client';

import React, { useRef, useState } from 'react';
import { Mic, SendHorizontal, Square } from 'lucide-react';

type GoalInputProps = {
  onSubmit: (goal: string) => void;
  disabled?: boolean;
};

export function GoalInput({ onSubmit, disabled }: GoalInputProps) {
  const [value, setValue] = useState('');
  const [isListening, setIsListening] = useState(false);
  const [voiceStatus, setVoiceStatus] = useState('');
  const recognitionRef = useRef<any>(null);

  function handleSubmit() {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSubmit(trimmed);
    setValue('');
  }

  function handleKeyDown(event: React.KeyboardEvent) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      handleSubmit();
    }
  }

  function toggleVoice() {
    if (isListening) {
      recognitionRef.current?.stop();
      return;
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setVoiceStatus('浏览器不支持语音输入');
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.lang = 'zh-CN';
    recognition.interimResults = false;
    recognition.onstart = () => {
      setIsListening(true);
      setVoiceStatus('');
    };
    recognition.onresult = (event: any) => {
      const transcript = Array.from(event.results)
        .map((r: any) => r[0]?.transcript ?? '')
        .join('')
        .trim();
      if (transcript) setValue(transcript);
    };
    recognition.onerror = () => {
      setVoiceStatus('语音识别失败');
    };
    recognition.onend = () => {
      setIsListening(false);
    };
    recognition.start();
    recognitionRef.current = recognition;
  }

  return (
    <div className="goal-input-wrapper">
      <div className="goal-input-container">
        <textarea
          className="goal-input"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="描述你的周末安排..."
          disabled={disabled}
          rows={1}
          aria-label="输入出行需求"
        />
        <div className="goal-input-actions">
          <button
            className={`goal-input-voice${isListening ? ' listening' : ''}`}
            type="button"
            onClick={toggleVoice}
            disabled={disabled}
            aria-label={isListening ? '停止录音' : '语音输入'}
          >
            {isListening ? <Square size={18} /> : <Mic size={18} />}
          </button>
          <button
            className="goal-input-send"
            type="button"
            onClick={handleSubmit}
            disabled={disabled || !value.trim()}
            aria-label="发送"
          >
            <SendHorizontal size={18} />
          </button>
        </div>
      </div>
      {voiceStatus && <div className="goal-input-status" role="status">{voiceStatus}</div>}
    </div>
  );
}
```

- [ ] **Step 4: Create ChatView component**

Create `components/chat/ChatView.tsx`:
```tsx
'use client';

import React, { useEffect, useRef } from 'react';
import { ChatBubble } from './ChatBubble';
import { QuickActions } from './QuickActions';
import { GoalInput } from './GoalInput';

type ChatViewProps = {
  onSubmitGoal: (goal: string) => void;
  isPlanning: boolean;
  error: string | null;
};

export function ChatView({ onSubmitGoal, isPlanning, error }: ChatViewProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [isPlanning, error]);

  return (
    <section className="chat-view">
      <div className="chat-scroll" ref={scrollRef}>
        <div className="chat-header">
          <div className="chat-header-avatar">
            <span>AI</span>
          </div>
          <h1>WeekendPilot</h1>
          <p>告诉我你的周末计划，我来帮你安排。</p>
        </div>

        <ChatBubble role="ai" animate>
          <p>你好！我是 WeekendPilot，你的本地生活助手。</p>
          <p>你可以直接告诉我你的需求，比如：</p>
          <ul>
            <li>"今天下午带孩子出去玩，别太远"</li>
            <li>"和朋友聚餐，想拍照聊天"</li>
            <li>"下雨天有什么室内推荐"</li>
          </ul>
        </ChatBubble>

        {error && (
          <ChatBubble role="ai">
            <p className="chat-error">{error}</p>
          </ChatBubble>
        )}

        {isPlanning && (
          <ChatBubble role="ai" animate>
            <div className="chat-typing">
              <span />
              <span />
              <span />
            </div>
            <p>正在为你规划行程...</p>
          </ChatBubble>
        )}
      </div>

      <div className="chat-bottom">
        <QuickActions onSelect={onSubmitGoal} disabled={isPlanning} />
        <GoalInput onSubmit={onSubmitGoal} disabled={isPlanning} />
      </div>
    </section>
  );
}
```

- [ ] **Step 5: Add chat styles to globals.css**

Append to `app/globals.css`:

```css
/* ==========================================
   CHAT VIEW
   ========================================== */

.chat-view {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 80px);
  height: calc(100dvh - 80px);
}

@media (min-width: 820px) {
  .chat-view {
    height: 100vh;
    height: 100dvh;
  }
}

.chat-scroll {
  flex: 1;
  overflow-y: auto;
  padding: 24px 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

@media (min-width: 820px) {
  .chat-scroll {
    padding: 32px 24px;
    max-width: 720px;
    margin: 0 auto;
    width: 100%;
  }
}

.chat-header {
  text-align: center;
  padding: 20px 0 8px;
  animation: fade-up 0.5s ease both;
}

.chat-header-avatar {
  width: 56px;
  height: 56px;
  margin: 0 auto 12px;
  border-radius: 16px;
  display: grid;
  place-items: center;
  background: linear-gradient(135deg, #0b77ff, #7568e8);
  color: white;
  font-weight: 800;
  font-size: 18px;
  box-shadow: 0 4px 16px rgba(11, 119, 255, 0.3);
}

.chat-header h1 {
  font-size: 24px;
  font-weight: 700;
  margin: 0;
  color: var(--text);
}

.chat-header p {
  font-size: 14px;
  color: var(--muted);
  margin: 4px 0 0;
}

/* Chat bubbles */
.chat-bubble {
  display: flex;
  gap: 10px;
  max-width: 85%;
  animation: fade-up 0.4s ease both;
}

.chat-bubble--ai {
  align-self: flex-start;
}

.chat-bubble--user {
  align-self: flex-end;
  flex-direction: row-reverse;
}

.chat-bubble--animate {
  animation: fade-up 0.4s cubic-bezier(0.34, 1.56, 0.64, 1) both;
}

.chat-bubble-avatar {
  width: 32px;
  height: 32px;
  border-radius: 10px;
  display: grid;
  place-items: center;
  background: linear-gradient(135deg, #0b77ff, #7568e8);
  color: white;
  font-size: 11px;
  font-weight: 700;
  flex-shrink: 0;
}

.chat-bubble-content {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 16px;
  padding: 12px 16px;
  font-size: 14px;
  line-height: 1.6;
  box-shadow: var(--shadow-sm);
}

.chat-bubble--user .chat-bubble-content {
  background: var(--blue);
  border-color: var(--blue);
  color: white;
}

.chat-bubble-content p {
  margin: 0 0 8px;
}

.chat-bubble-content p:last-child {
  margin-bottom: 0;
}

.chat-bubble-content ul {
  margin: 4px 0;
  padding-left: 16px;
}

.chat-bubble-content li {
  margin: 4px 0;
  color: var(--muted);
  font-size: 13px;
}

.chat-bubble--user .chat-bubble-content li {
  color: rgba(255, 255, 255, 0.8);
}

.chat-error {
  color: var(--danger) !important;
  font-weight: 500;
}

/* Typing indicator */
.chat-typing {
  display: flex;
  gap: 4px;
  padding: 4px 0;
}

.chat-typing span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--muted);
  animation: typing-bounce 1.2s ease-in-out infinite;
}

.chat-typing span:nth-child(2) { animation-delay: 0.2s; }
.chat-typing span:nth-child(3) { animation-delay: 0.4s; }

@keyframes typing-bounce {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
  30% { transform: translateY(-6px); opacity: 1; }
}

/* Chat bottom area */
.chat-bottom {
  padding: 12px 16px;
  padding-bottom: max(12px, env(safe-area-inset-bottom));
  background: var(--panel);
  border-top: 1px solid var(--line);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

@media (min-width: 820px) {
  .chat-bottom {
    max-width: 720px;
    margin: 0 auto;
    width: 100%;
    border-radius: 18px 18px 0 0;
    box-shadow: var(--shadow-md);
  }
}

/* Quick actions */
.quick-actions {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding: 2px 0;
  scrollbar-width: none;
  -ms-overflow-style: none;
}

.quick-actions::-webkit-scrollbar {
  display: none;
}

.quick-action {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border-radius: 20px;
  background: var(--surface-2);
  color: var(--text);
  font-size: 13px;
  font-weight: 500;
  white-space: nowrap;
  transition: background 0.15s ease, transform 0.15s ease, box-shadow 0.15s ease;
  animation: chip-in 0.4s cubic-bezier(0.34, 1.56, 0.64, 1) both;
}

.quick-action:hover {
  box-shadow: var(--shadow-sm);
  transform: translateY(-1px);
}

.quick-action:active {
  transform: scale(0.96);
}

.quick-action--blue { color: var(--blue); }
.quick-action--violet { color: var(--violet); }
.quick-action--green { color: var(--green); }
.quick-action--coral { color: var(--coral); }

.quick-action--blue:hover { background: var(--blue-soft); }
.quick-action--violet:hover { background: var(--violet-soft); }
.quick-action--green:hover { background: var(--green-soft); }
.quick-action--coral:hover { background: var(--coral-soft); }

@keyframes chip-in {
  from { opacity: 0; transform: translateY(8px) scale(0.9); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

/* Goal input */
.goal-input-wrapper {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.goal-input-container {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  padding: 8px 8px 8px 16px;
  background: var(--surface);
  border: 1.5px solid var(--line);
  border-radius: 24px;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.goal-input-container:focus-within {
  border-color: var(--blue);
  box-shadow: 0 0 0 3px rgba(11, 119, 255, 0.1);
}

.goal-input {
  flex: 1;
  border: 0;
  background: none;
  resize: none;
  font-size: 15px;
  line-height: 1.5;
  color: var(--text);
  outline: none;
  min-height: 24px;
  max-height: 120px;
}

.goal-input::placeholder {
  color: var(--subtle);
}

.goal-input-actions {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
}

.goal-input-voice,
.goal-input-send {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  transition: background 0.15s ease, transform 0.15s ease, color 0.15s ease;
}

.goal-input-voice {
  background: var(--surface-2);
  color: var(--muted);
}

.goal-input-voice:hover {
  background: var(--line);
  color: var(--text);
}

.goal-input-voice.listening {
  background: var(--danger);
  color: white;
  animation: pulse-ring 1.5s ease infinite;
}

@keyframes pulse-ring {
  0% { box-shadow: 0 0 0 0 rgba(221, 75, 75, 0.4); }
  70% { box-shadow: 0 0 0 8px rgba(221, 75, 75, 0); }
  100% { box-shadow: 0 0 0 0 rgba(221, 75, 75, 0); }
}

.goal-input-send {
  background: var(--blue);
  color: white;
}

.goal-input-send:hover:not(:disabled) {
  background: #0056b8;
}

.goal-input-send:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.goal-input-send:active:not(:disabled) {
  transform: scale(0.92);
}

.goal-input-status {
  font-size: 12px;
  color: var(--muted);
  text-align: center;
  animation: fade-up 0.3s ease;
}

@keyframes fade-up {
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: translateY(0); }
}
```

- [ ] **Step 6: Commit**

```bash
git add components/chat/
git commit -m "feat: add chat home view with AI bubbles, quick actions, and goal input"
```

---

## Task 4: Create the Planning Progress View

**Files:**
- Create: `components/planning/PlanningProgress.tsx`
- Create: `components/planning/ProgressStep.tsx`

- [ ] **Step 1: Create ProgressStep component**

Create `components/planning/ProgressStep.tsx`:
```tsx
'use client';

import React from 'react';
import { Check, Loader2, AlertCircle, Circle } from 'lucide-react';

type StepStatus = 'pending' | 'running' | 'done' | 'error';

type ProgressStepProps = {
  label: string;
  detail?: string;
  status: StepStatus;
  index: number;
};

const statusIcons: Record<StepStatus, typeof Circle> = {
  pending: Circle,
  running: Loader2,
  done: Check,
  error: AlertCircle,
};

const statusClasses: Record<StepStatus, string> = {
  pending: 'progress-step--pending',
  running: 'progress-step--running',
  done: 'progress-step--done',
  error: 'progress-step--error',
};

export function ProgressStep({ label, detail, status, index }: ProgressStepProps) {
  const Icon = statusIcons[status];

  return (
    <div
      className={`progress-step ${statusClasses[status]}`}
      style={{ animationDelay: `${index * 100}ms` }}
    >
      <div className="progress-step-icon">
        <Icon
          size={18}
          className={status === 'running' ? 'spin' : ''}
        />
      </div>
      <div className="progress-step-text">
        <strong>{label}</strong>
        {detail && <span>{detail}</span>}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create PlanningProgress component**

Create `components/planning/PlanningProgress.tsx`:
```tsx
'use client';

import React from 'react';
import { ProgressStep } from './ProgressStep';

type PlanningProgressProps = {
  goal: string;
  progress: string[];
};

const pipelineSteps = [
  '解析需求',
  '构建上下文',
  '搜索候选',
  '排序推荐',
  '规划路线',
  '验证方案',
];

function getStepStatus(progress: string[], index: number): 'pending' | 'running' | 'done' {
  if (index < progress.length - 1) return 'done';
  if (index === progress.length - 1) return 'running';
  return 'pending';
}

export function PlanningProgress({ goal, progress }: PlanningProgressProps) {
  const steps = pipelineSteps.map((label, index) => ({
    label,
    status: progress.length === 0
      ? (index === 0 ? 'running' : 'pending')
      : getStepStatus(progress, index),
    detail: progress[index] ?? undefined,
  }));

  return (
    <section className="planning-progress">
      <div className="planning-progress-header">
        <div className="planning-progress-goal">
          <span>正在规划</span>
          <p>{goal}</p>
        </div>
      </div>

      <div className="planning-progress-bar">
        <div
          className="planning-progress-fill"
          style={{ width: `${Math.min(100, (progress.length / pipelineSteps.length) * 100)}%` }}
        />
      </div>

      <div className="planning-progress-steps">
        {steps.map((step, index) => (
          <ProgressStep
            key={step.label}
            label={step.label}
            detail={step.detail}
            status={step.status}
            index={index}
          />
        ))}
      </div>
    </section>
  );
}
```

- [ ] **Step 3: Add planning progress styles to globals.css**

Append to `app/globals.css`:

```css
/* ==========================================
   PLANNING PROGRESS
   ========================================== */

.planning-progress {
  max-width: 520px;
  margin: 0 auto;
  padding: 40px 16px;
  animation: fade-up 0.5s ease both;
}

.planning-progress-header {
  text-align: center;
  margin-bottom: 32px;
}

.planning-progress-goal span {
  font-size: 13px;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-weight: 600;
}

.planning-progress-goal p {
  font-size: 18px;
  font-weight: 600;
  color: var(--text);
  margin: 8px 0 0;
  line-height: 1.5;
}

.planning-progress-bar {
  height: 4px;
  background: var(--line);
  border-radius: 2px;
  overflow: hidden;
  margin-bottom: 28px;
}

.planning-progress-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--blue), var(--violet));
  border-radius: 2px;
  transition: width 0.6s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.planning-progress-steps {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.progress-step {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  border-radius: 12px;
  animation: step-in 0.4s ease both;
  transition: background 0.2s ease;
}

@keyframes step-in {
  from { opacity: 0; transform: translateX(-12px); }
  to { opacity: 1; transform: translateX(0); }
}

.progress-step--running {
  background: var(--blue-soft);
}

.progress-step--done {
  opacity: 0.7;
}

.progress-step-icon {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  flex-shrink: 0;
}

.progress-step--pending .progress-step-icon {
  color: var(--subtle);
}

.progress-step--running .progress-step-icon {
  color: var(--blue);
}

.progress-step--done .progress-step-icon {
  color: var(--green);
  background: var(--green-soft);
}

.progress-step--error .progress-step-icon {
  color: var(--danger);
  background: rgba(221, 75, 75, 0.1);
}

.progress-step-text strong {
  display: block;
  font-size: 14px;
  font-weight: 600;
}

.progress-step-text span {
  display: block;
  font-size: 12px;
  color: var(--muted);
  margin-top: 2px;
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
```

- [ ] **Step 4: Commit**

```bash
git add components/planning/
git commit -m "feat: add animated planning progress view with step-by-step indicators"
```

---

## Task 5: Create the Plan Results View

**Files:**
- Create: `components/plan/PlanResultsView.tsx`
- Create: `components/plan/ItineraryTimeline.tsx`
- Create: `components/plan/ItineraryCard.tsx`
- Create: `components/plan/OverviewCard.tsx`
- Create: `components/plan/ConstraintChips.tsx`
- Create: `components/plan/VariantSelector.tsx`

- [ ] **Step 1: Create OverviewCard component**

Create `components/plan/OverviewCard.tsx`:
```tsx
'use client';

import React from 'react';
import { Clock, DollarSign, Footprints, Gauge, Timer, Car } from 'lucide-react';

type OverviewCardProps = {
  overview: {
    theme?: string;
    totalDuration?: string;
    driveTime?: string;
    walkingDistance?: string;
    estimatedCost?: string;
    score?: number;
  };
};

export function OverviewCard({ overview }: OverviewCardProps) {
  const metrics = [
    { icon: Clock, label: '总时长', value: overview.totalDuration },
    { icon: Car, label: '车程', value: overview.driveTime },
    { icon: Footprints, label: '步行', value: overview.walkingDistance },
    { icon: DollarSign, label: '预算', value: overview.estimatedCost },
    { icon: Gauge, label: '评分', value: overview.score ? `${overview.score}分` : undefined },
  ].filter((m) => m.value);

  return (
    <div className="overview-card">
      {overview.theme && <div className="overview-theme">{overview.theme}</div>}
      <div className="overview-metrics">
        {metrics.map((metric, index) => {
          const Icon = metric.icon;
          return (
            <div
              key={metric.label}
              className="overview-metric"
              style={{ animationDelay: `${index * 60}ms` }}
            >
              <Icon size={16} />
              <span>{metric.label}</span>
              <strong>{metric.value}</strong>
            </div>
          );
        })}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create ItineraryCard component**

Create `components/plan/ItineraryCard.tsx`:
```tsx
'use client';

import React from 'react';
import { Car, DollarSign, Footprints, MapPin, Utensils, FlaskConical, TreePine, Music } from 'lucide-react';

type ItineraryCardProps = {
  step: {
    start?: string;
    end?: string;
    type?: string;
    title: string;
    reason?: string;
    cost?: string;
    travel?: string;
    travel_minutes?: number;
    mode?: string;
    risk?: string[];
  };
  index: number;
  isLast: boolean;
};

const typeIcons: Record<string, typeof MapPin> = {
  transport: Car,
  activity: FlaskConical,
  restaurant: Utensils,
  dessert_walk: TreePine,
  entertainment: Music,
};

const typeLabels: Record<string, string> = {
  transport: '交通',
  activity: '活动',
  restaurant: '餐厅',
  dessert_walk: '散步',
  entertainment: '娱乐',
};

export function ItineraryCard({ step, index, isLast }: ItineraryCardProps) {
  const Icon = typeIcons[step.type] ?? MapPin;
  const typeLabel = typeLabels[step.type] ?? step.type;

  return (
    <div
      className="itinerary-card"
      style={{ animationDelay: `${index * 120}ms` }}
    >
      <div className="itinerary-card-timeline">
        <div className="itinerary-dot">
          <Icon size={16} />
        </div>
        {!isLast && <div className="itinerary-line" />}
      </div>

      <div className="itinerary-card-body">
        <div className="itinerary-card-header">
          <div>
            <span className="itinerary-type">{typeLabel}</span>
            <h3>{step.title}</h3>
          </div>
          {(step.start || step.end) && (
            <div className="itinerary-time">
              {step.start && <span>{step.start}</span>}
              {step.end && step.start && <span> - {step.end}</span>}
              {!step.start && step.end && <span>{step.end}</span>}
            </div>
          )}
        </div>

        {step.reason && <p className="itinerary-reason">{step.reason}</p>}

        <div className="itinerary-meta">
          {step.cost && (
            <span><DollarSign size={14} /> {step.cost}</span>
          )}
          {step.travel && (
            <span><Car size={14} /> {step.travel}</span>
          )}
          {step.travel_minutes && !step.travel && (
            <span><Timer size={14} /> {step.travel_minutes}分钟</span>
          )}
          {step.mode && (
            <span><Footprints size={14} /> {step.mode}</span>
          )}
        </div>

        {step.risk && step.risk.length > 0 && (
          <div className="itinerary-risks">
            {step.risk.map((r) => (
              <span key={r} className="itinerary-risk">{r}</span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Create ItineraryTimeline component**

Create `components/plan/ItineraryTimeline.tsx`:
```tsx
'use client';

import React from 'react';
import { ItineraryCard } from './ItineraryCard';

type ItineraryTimelineProps = {
  itinerary: Array<Record<string, any>>;
};

export function ItineraryTimeline({ itinerary }: ItineraryTimelineProps) {
  if (!itinerary.length) return null;

  return (
    <section className="itinerary-timeline">
      <h2 className="section-title">行程安排</h2>
      <div className="itinerary-list">
        {itinerary.map((step, index) => (
          <ItineraryCard
            key={step.id ?? step.place_id ?? index}
            step={step}
            index={index}
            isLast={index === itinerary.length - 1}
          />
        ))}
      </div>
    </section>
  );
}
```

- [ ] **Step 4: Create ConstraintChips component**

Create `components/plan/ConstraintChips.tsx`:
```tsx
'use client';

import React from 'react';
import { CalendarClock, CircleDollarSign, MapPinned, Utensils, Users } from 'lucide-react';

type ConstraintChipsProps = {
  constraints: Record<string, any>;
  onPatch?: (updates: Record<string, unknown>) => void;
};

export function ConstraintChips({ constraints, onPatch }: ConstraintChipsProps) {
  const party = constraints.party ?? `${constraints.people?.adults ?? '?'} 人`;
  const radius = constraints.radiusKm ?? constraints.constraints?.radius_km ?? 5;
  const budget = constraints.preferences?.budget_level ?? 'medium';
  const start = constraints.time_window?.start ?? '??:??';
  const diet = constraints.preferences?.diet?.[0] ?? null;

  const budgetLabels: Record<string, string> = { low: '省钱', medium: '适中', high: '不限' };
  const dietLabels: Record<string, string> = {
    low_fat: '低脂', low_sugar: '低糖', vegetarian: '素食', no_gluten: '无麸质',
  };

  return (
    <div className="constraint-chips">
      <span className="constraint-chip">
        <Users size={14} /> {party}
      </span>
      <span className="constraint-chip">
        <MapPinned size={14} /> {radius}km
      </span>
      <span className="constraint-chip">
        <CircleDollarSign size={14} /> {budgetLabels[budget] ?? budget}
      </span>
      <span className="constraint-chip">
        <CalendarClock size={14} /> {start}
      </span>
      {diet && (
        <span className="constraint-chip">
          <Utensils size={14} /> {dietLabels[diet] ?? diet}
        </span>
      )}
    </div>
  );
}
```

- [ ] **Step 5: Create VariantSelector component**

Create `components/plan/VariantSelector.tsx`:
```tsx
'use client';

import React, { useState } from 'react';

type VariantSelectorProps = {
  variants: Array<Record<string, any>>;
  activeIndex: number;
  onSelect: (index: number) => void;
  onLoadMore?: () => void;
};

const kindLabels: Record<string, string> = {
  main: '推荐',
  budget: '省钱',
  comfort: '舒适',
  child_first: '亲子',
  experience_first: '体验',
};

export function VariantSelector({ variants, activeIndex, onSelect, onLoadMore }: VariantSelectorProps) {
  if (!variants.length) return null;

  return (
    <section className="variant-selector">
      <div className="variant-scroll">
        {variants.map((variant, index) => (
          <button
            key={variant.id ?? variant.kind ?? index}
            className={`variant-chip${index === activeIndex ? ' active' : ''}`}
            type="button"
            onClick={() => onSelect(index)}
          >
            <strong>{kindLabels[variant.kind] ?? variant.title ?? `方案${index + 1}`}</strong>
            {variant.overview?.score && <span>{variant.overview.score}分</span>}
          </button>
        ))}
        {onLoadMore && variants.length <= 1 && (
          <button className="variant-chip variant-chip--more" type="button" onClick={onLoadMore}>
            更多方案
          </button>
        )}
      </div>
    </section>
  );
}
```

- [ ] **Step 6: Create PlanResultsView component**

Create `components/plan/PlanResultsView.tsx`:
```tsx
'use client';

import React, { useState } from 'react';
import type { PlanResponse } from '../../types/weekendpilot';
import { OverviewCard } from './OverviewCard';
import { ConstraintChips } from './ConstraintChips';
import { ItineraryTimeline } from './ItineraryTimeline';
import { VariantSelector } from './VariantSelector';
import { RecoveryBanner } from '../recovery/RecoveryBanner';
import { RouteMap } from '../map/RouteMap';
import { TracePanel } from '../trace/TracePanel';

type PlanResultsViewProps = {
  result: PlanResponse;
  recoveredPlan: PlanResponse['plan'] | null;
  onConfirm: () => void;
  onRecover: (reason: string) => void;
  onLoadAlternatives: () => void;
  onPatchConstraints?: (updates: Record<string, unknown>) => void;
  error: string | null;
};

export function PlanResultsView({
  result,
  recoveredPlan,
  onConfirm,
  onRecover,
  onLoadAlternatives,
  onPatchConstraints,
  error,
}: PlanResultsViewProps) {
  const [activeVariant, setActiveVariant] = useState(0);
  const [showTrace, setShowTrace] = useState(false);

  const plan = recoveredPlan ?? result.plan;
  const displayItinerary = activeVariant === 0
    ? (plan.itinerary ?? [])
    : (result.variants?.[activeVariant]?.itinerary ?? plan.itinerary ?? []);

  return (
    <section className="plan-results">
      {error && (
        <div className="plan-error-banner" role="alert">{error}</div>
      )}

      {result.diff && (
        <RecoveryBanner diff={result.diff} adjustment={result.adjustment} />
      )}

      <ConstraintChips constraints={result.constraints} onPatch={onPatchConstraints} />
      <OverviewCard overview={plan.overview ?? {}} />

      <VariantSelector
        variants={result.variants?.length ? result.variants : [plan]}
        activeIndex={activeVariant}
        onSelect={setActiveVariant}
        onLoadMore={onLoadAlternatives}
      />

      <ItineraryTimeline itinerary={displayItinerary} />

      {result.route && (
        <section className="plan-map-section">
          <h2 className="section-title">路线预览</h2>
          <RouteMap route={result.route} />
        </section>
      )}

      <button
        className="trace-toggle"
        type="button"
        onClick={() => setShowTrace(!showTrace)}
      >
        {showTrace ? '隐藏' : '查看'} Agent 执行详情
      </button>
      {showTrace && (
        <TracePanel trace={result.trace ?? []} toolCalls={result.tool_calls ?? []} />
      )}

      <div className="plan-results-actions">
        <button className="primary-button plan-confirm-btn" type="button" onClick={onConfirm}>
          确认方案，查看执行项
        </button>
        <button className="secondary-button" type="button" onClick={() => onRecover('restaurant_unavailable')}>
          模拟故障恢复
        </button>
      </div>
    </section>
  );
}
```

- [ ] **Step 7: Add plan results styles to globals.css**

Append to `app/globals.css`:

```css
/* ==========================================
   PLAN RESULTS
   ========================================== */

.plan-results {
  max-width: 640px;
  margin: 0 auto;
  padding: 20px 16px 120px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

@media (min-width: 820px) {
  .plan-results {
    padding: 28px 24px 40px;
    max-width: 780px;
  }
}

.section-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--text);
  margin: 0 0 12px;
}

.plan-error-banner {
  padding: 12px 16px;
  background: rgba(221, 75, 75, 0.08);
  border: 1px solid rgba(221, 75, 75, 0.2);
  border-radius: 12px;
  color: var(--danger);
  font-size: 14px;
  font-weight: 500;
  animation: shake 0.4s ease;
}

@keyframes shake {
  0%, 100% { transform: translateX(0); }
  25% { transform: translateX(-4px); }
  75% { transform: translateX(4px); }
}

/* Constraint chips */
.constraint-chips {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.constraint-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 6px 12px;
  background: var(--surface-2);
  border-radius: 20px;
  font-size: 13px;
  font-weight: 500;
  color: var(--text);
  animation: chip-in 0.3s ease both;
}

/* Overview card */
.overview-card {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 16px;
  padding: 16px;
  box-shadow: var(--shadow-sm);
  animation: fade-up 0.4s ease both;
}

.overview-theme {
  font-size: 13px;
  font-weight: 600;
  color: var(--blue);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin-bottom: 12px;
}

.overview-metrics {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.overview-metric {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  background: var(--surface);
  border-radius: 10px;
  font-size: 13px;
  flex: 1;
  min-width: 100px;
  animation: fade-up 0.4s ease both;
}

.overview-metric svg {
  color: var(--muted);
  flex-shrink: 0;
}

.overview-metric span {
  color: var(--muted);
  font-size: 11px;
}

.overview-metric strong {
  margin-left: auto;
  font-weight: 600;
  font-size: 14px;
}

/* Variant selector */
.variant-selector {
  overflow: hidden;
}

.variant-scroll {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding: 2px;
  scrollbar-width: none;
}

.variant-scroll::-webkit-scrollbar {
  display: none;
}

.variant-chip {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 10px 18px;
  border-radius: 12px;
  background: var(--surface-2);
  color: var(--muted);
  font-size: 13px;
  white-space: nowrap;
  transition: all 0.2s ease;
  border: 2px solid transparent;
}

.variant-chip.active {
  background: var(--blue-soft);
  color: var(--blue);
  border-color: var(--blue);
  font-weight: 600;
}

.variant-chip:hover:not(.active) {
  background: var(--line);
}

.variant-chip strong {
  font-size: 14px;
}

.variant-chip span {
  font-size: 11px;
}

.variant-chip--more {
  border-style: dashed;
  border-color: var(--line-strong);
}

/* Itinerary timeline */
.itinerary-timeline {
  animation: fade-up 0.5s ease both;
}

.itinerary-list {
  display: flex;
  flex-direction: column;
}

.itinerary-card {
  display: flex;
  gap: 14px;
  animation: card-slide-in 0.5s cubic-bezier(0.34, 1.56, 0.64, 1) both;
}

@keyframes card-slide-in {
  from { opacity: 0; transform: translateY(16px); }
  to { opacity: 1; transform: translateY(0); }
}

.itinerary-card-timeline {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 36px;
  flex-shrink: 0;
}

.itinerary-dot {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: var(--blue-soft);
  color: var(--blue);
  flex-shrink: 0;
  z-index: 1;
}

.itinerary-line {
  width: 2px;
  flex: 1;
  background: var(--line);
  margin: 4px 0;
}

.itinerary-card-body {
  flex: 1;
  padding-bottom: 20px;
}

.itinerary-card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.itinerary-type {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--blue);
}

.itinerary-card-header h3 {
  font-size: 15px;
  font-weight: 650;
  margin: 2px 0 0;
  color: var(--text);
}

.itinerary-time {
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
  white-space: nowrap;
  padding-top: 2px;
}

.itinerary-reason {
  font-size: 13px;
  color: var(--muted);
  margin: 6px 0 0;
  line-height: 1.5;
}

.itinerary-meta {
  display: flex;
  gap: 12px;
  margin-top: 8px;
  flex-wrap: wrap;
}

.itinerary-meta span {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--muted);
}

.itinerary-risks {
  display: flex;
  gap: 6px;
  margin-top: 8px;
  flex-wrap: wrap;
}

.itinerary-risk {
  padding: 3px 8px;
  background: var(--coral-soft);
  color: var(--coral);
  border-radius: 6px;
  font-size: 11px;
  font-weight: 500;
}

/* Map section */
.plan-map-section {
  animation: fade-up 0.5s ease both;
}

/* Trace toggle */
.trace-toggle {
  padding: 8px 16px;
  background: var(--surface-2);
  border-radius: 10px;
  font-size: 13px;
  color: var(--muted);
  font-weight: 500;
  transition: background 0.15s ease;
  align-self: flex-start;
}

.trace-toggle:hover {
  background: var(--line);
  color: var(--text);
}

/* Plan results actions */
.plan-results-actions {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-top: 8px;
}

.plan-confirm-btn {
  padding: 14px 24px;
  font-size: 16px;
  font-weight: 600;
  border-radius: 14px;
  animation: pulse-glow 2s ease infinite;
}

@keyframes pulse-glow {
  0%, 100% { box-shadow: 0 4px 16px rgba(11, 119, 255, 0.2); }
  50% { box-shadow: 0 4px 24px rgba(11, 119, 255, 0.4); }
}

/* Primary / secondary buttons */
.primary-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 10px 20px;
  background: var(--blue);
  color: white;
  border-radius: 12px;
  font-weight: 600;
  font-size: 14px;
  transition: background 0.15s ease, transform 0.15s ease, box-shadow 0.15s ease;
}

.primary-button:hover {
  background: #0056b8;
}

.primary-button:active {
  transform: scale(0.97);
}

.primary-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.secondary-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 10px 20px;
  background: var(--surface-2);
  color: var(--text);
  border-radius: 12px;
  font-weight: 500;
  font-size: 14px;
  border: 1px solid var(--line);
  transition: background 0.15s ease, transform 0.15s ease;
}

.secondary-button:hover {
  background: var(--line);
}

.secondary-button:active {
  transform: scale(0.97);
}
```

- [ ] **Step 8: Commit**

```bash
git add components/plan/
git commit -m "feat: add plan results view with itinerary timeline, overview, and variants"
```

---

## Task 6: Create the Confirmation View

**Files:**
- Create: `components/confirm/ConfirmView.tsx`
- Create: `components/confirm/ActionToggle.tsx`
- Create: `components/confirm/ExecuteButton.tsx`

- [ ] **Step 1: Create ActionToggle component**

Create `components/confirm/ActionToggle.tsx`:
```tsx
'use client';

import React from 'react';
import { CalendarPlus, MessageSquareShare, ReceiptText, ShoppingBag, Ticket, Utensils } from 'lucide-react';

type ActionToggleProps = {
  action: Record<string, any>;
  selected: boolean;
  onToggle: () => void;
};

const actionLabels: Record<string, string> = {
  reserve_activity: '预约活动',
  create_reservation: '餐厅订座',
  claim_coupon: '领取团购券',
  create_order: '创建点单',
  send_plan_message: '发送计划',
  create_calendar_event: '创建日历',
};

const actionIcons: Record<string, typeof Ticket> = {
  reserve_activity: Ticket,
  create_reservation: Utensils,
  claim_coupon: ReceiptText,
  create_order: ShoppingBag,
  send_plan_message: MessageSquareShare,
  create_calendar_event: CalendarPlus,
};

export function ActionToggle({ action, selected, onToggle }: ActionToggleProps) {
  const tool = action.tool ?? action.type;
  const Icon = actionIcons[tool] ?? Ticket;
  const label = actionLabels[tool] ?? action.label ?? tool;

  return (
    <button
      className={`action-toggle${selected ? ' active' : ''}`}
      type="button"
      onClick={onToggle}
      aria-pressed={selected}
    >
      <div className="action-toggle-icon">
        <Icon size={20} />
      </div>
      <div className="action-toggle-text">
        <strong>{label}</strong>
        <span>{action.detail ?? action.target ?? '确认后执行'}</span>
      </div>
      <div className="action-toggle-switch">
        <div className="action-toggle-track">
          <div className="action-toggle-thumb" />
        </div>
      </div>
    </button>
  );
}
```

- [ ] **Step 2: Create ExecuteButton component**

Create `components/confirm/ExecuteButton.tsx`:
```tsx
'use client';

import React, { useState } from 'react';
import { Loader2, Zap } from 'lucide-react';

type ExecuteButtonProps = {
  selectedCount: number;
  totalCount: number;
  executing: boolean;
  onClick: () => void;
};

export function ExecuteButton({ selectedCount, totalCount, executing, onClick }: ExecuteButtonProps) {
  return (
    <div className="execute-button-wrapper">
      <div className="execute-button-info">
        <span>已选择 <strong>{selectedCount}</strong> / {totalCount} 项操作</span>
      </div>
      <button
        className="execute-button"
        type="button"
        onClick={onClick}
        disabled={selectedCount === 0 || executing}
      >
        {executing ? (
          <>
            <Loader2 size={20} className="spin" />
            执行中...
          </>
        ) : (
          <>
            <Zap size={20} />
            一键执行
          </>
        )}
      </button>
    </div>
  );
}
```

- [ ] **Step 3: Create ConfirmView component**

Create `components/confirm/ConfirmView.tsx`:
```tsx
'use client';

import React from 'react';
import type { PlanResponse } from '../../types/weekendpilot';
import { ActionToggle } from './ActionToggle';
import { ExecuteButton } from './ExecuteButton';

type ConfirmViewProps = {
  result: PlanResponse;
  selectedActions: Set<string>;
  onToggleAction: (key: string) => void;
  onSelectAll: () => void;
  onDeselectAll: () => void;
  onExecute: () => void;
  onBack: () => void;
  executing: boolean;
};

export function ConfirmView({
  result,
  selectedActions,
  onToggleAction,
  onSelectAll,
  onDeselectAll,
  onExecute,
  onBack,
  executing,
}: ConfirmViewProps) {
  const plan = result.plan;
  const actions = plan.actions ?? [];

  return (
    <section className="confirm-view">
      <div className="confirm-header">
        <button className="confirm-back" type="button" onClick={onBack}>
          返回方案
        </button>
        <h2>确认执行项</h2>
        <p>以下操作将在你确认后自动执行。点击可切换。</p>
      </div>

      <div className="confirm-bulk-actions">
        <button type="button" onClick={onSelectAll}>全选</button>
        <button type="button" onClick={onDeselectAll}>全不选</button>
      </div>

      <div className="confirm-actions-list">
        {actions.map((action) => {
          const key = `${action.tool ?? action.type}_${action.label ?? action.place_id ?? 'default'}`;
          return (
            <ActionToggle
              key={key}
              action={action}
              selected={selectedActions.has(key)}
              onToggle={() => onToggleAction(key)}
            />
          );
        })}
      </div>

      {actions.length === 0 && (
        <div className="confirm-empty">
          <p>该方案没有需要执行的操作。</p>
        </div>
      )}

      <ExecuteButton
        selectedCount={selectedActions.size}
        totalCount={actions.length}
        executing={executing}
        onClick={onExecute}
      />
    </section>
  );
}
```

- [ ] **Step 4: Add confirm view styles to globals.css**

Append to `app/globals.css`:

```css
/* ==========================================
   CONFIRM VIEW
   ========================================== */

.confirm-view {
  max-width: 560px;
  margin: 0 auto;
  padding: 20px 16px 140px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  animation: fade-up 0.4s ease both;
}

.confirm-header {
  text-align: center;
}

.confirm-back {
  font-size: 13px;
  color: var(--blue);
  background: none;
  padding: 4px 8px;
  border-radius: 6px;
  font-weight: 500;
  transition: background 0.15s ease;
}

.confirm-back:hover {
  background: var(--blue-soft);
}

.confirm-header h2 {
  font-size: 20px;
  font-weight: 700;
  margin: 8px 0 4px;
}

.confirm-header p {
  font-size: 14px;
  color: var(--muted);
  margin: 0;
}

.confirm-bulk-actions {
  display: flex;
  gap: 8px;
  justify-content: center;
}

.confirm-bulk-actions button {
  padding: 6px 14px;
  border-radius: 8px;
  background: var(--surface-2);
  color: var(--muted);
  font-size: 13px;
  font-weight: 500;
  transition: background 0.15s ease, color 0.15s ease;
}

.confirm-bulk-actions button:hover {
  background: var(--line);
  color: var(--text);
}

.confirm-actions-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.confirm-empty {
  text-align: center;
  padding: 32px 16px;
  color: var(--muted);
  font-size: 14px;
}

/* Action toggle */
.action-toggle {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  background: var(--panel);
  border: 1.5px solid var(--line);
  border-radius: 14px;
  text-align: left;
  transition: all 0.2s ease;
  animation: card-slide-in 0.4s ease both;
}

.action-toggle:hover {
  border-color: var(--line-strong);
  box-shadow: var(--shadow-sm);
}

.action-toggle.active {
  border-color: var(--blue);
  background: rgba(11, 119, 255, 0.03);
}

.action-toggle-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: grid;
  place-items: center;
  background: var(--surface-2);
  color: var(--muted);
  flex-shrink: 0;
  transition: background 0.2s ease, color 0.2s ease;
}

.action-toggle.active .action-toggle-icon {
  background: var(--blue-soft);
  color: var(--blue);
}

.action-toggle-text {
  flex: 1;
  min-width: 0;
}

.action-toggle-text strong {
  display: block;
  font-size: 14px;
  font-weight: 600;
}

.action-toggle-text span {
  display: block;
  font-size: 12px;
  color: var(--muted);
  margin-top: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.action-toggle-switch {
  flex-shrink: 0;
}

.action-toggle-track {
  width: 44px;
  height: 26px;
  border-radius: 13px;
  background: var(--line);
  padding: 3px;
  transition: background 0.2s ease;
}

.action-toggle.active .action-toggle-track {
  background: var(--blue);
}

.action-toggle-thumb {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: white;
  box-shadow: 0 1px 3px rgba(0,0,0,0.15);
  transition: transform 0.2s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.action-toggle.active .action-toggle-thumb {
  transform: translateX(18px);
}

/* Execute button wrapper */
.execute-button-wrapper {
  position: fixed;
  bottom: 80px;
  left: 0;
  right: 0;
  padding: 12px 16px;
  padding-bottom: max(12px, env(safe-area-inset-bottom));
  background: var(--panel);
  border-top: 1px solid var(--line);
  display: flex;
  flex-direction: column;
  gap: 8px;
  z-index: 50;
}

@media (min-width: 820px) {
  .execute-button-wrapper {
    position: sticky;
    bottom: 0;
    max-width: 560px;
    margin: 0 auto;
    width: 100%;
    border-radius: 16px 16px 0 0;
    box-shadow: var(--shadow-md);
  }
}

.execute-button-info {
  text-align: center;
  font-size: 13px;
  color: var(--muted);
}

.execute-button-info strong {
  color: var(--blue);
  font-weight: 700;
}

.execute-button {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  padding: 14px 24px;
  background: linear-gradient(135deg, #0b77ff, #0056b8);
  color: white;
  border-radius: 14px;
  font-size: 16px;
  font-weight: 700;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
  box-shadow: 0 4px 16px rgba(11, 119, 255, 0.3);
}

.execute-button:hover:not(:disabled) {
  box-shadow: 0 6px 24px rgba(11, 119, 255, 0.4);
}

.execute-button:active:not(:disabled) {
  transform: scale(0.97);
}

.execute-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
```

- [ ] **Step 5: Commit**

```bash
git add components/confirm/
git commit -m "feat: add confirmation view with action toggles and execute button"
```

---

## Task 7: Create Receipts and Recovery Views

**Files:**
- Create: `components/receipts/ReceiptsView.tsx`
- Create: `components/receipts/ReceiptCard.tsx`
- Create: `components/recovery/RecoveryBanner.tsx`

- [ ] **Step 1: Create ReceiptCard component**

Create `components/receipts/ReceiptCard.tsx`:
```tsx
'use client';

import React from 'react';
import { CalendarPlus, Check, MessageSquareShare, ReceiptText, ShoppingBag, Ticket, Utensils, X } from 'lucide-react';

type ReceiptCardProps = {
  receipt: {
    type: string;
    tool: string;
    id: string;
    status: string;
    detail: string;
    payload?: Record<string, unknown>;
  };
  index: number;
};

const toolIcons: Record<string, typeof Ticket> = {
  reserve_activity: Ticket,
  create_reservation: Utensils,
  claim_coupon: ReceiptText,
  create_order: ShoppingBag,
  send_plan_message: MessageSquareShare,
  create_calendar_event: CalendarPlus,
};

const toolLabels: Record<string, string> = {
  reserve_activity: '活动预约',
  create_reservation: '餐厅订座',
  claim_coupon: '团购券',
  create_order: '点单',
  send_plan_message: '发送计划',
  create_calendar_event: '日历事件',
};

export function ReceiptCard({ receipt, index }: ReceiptCardProps) {
  const Icon = toolIcons[receipt.tool] ?? Ticket;
  const label = toolLabels[receipt.tool] ?? receipt.tool;
  const isSuccess = receipt.status === 'success' || receipt.status === 'ok';

  return (
    <div
      className="receipt-card"
      style={{ animationDelay: `${index * 100}ms` }}
    >
      <div className={`receipt-card-status ${isSuccess ? 'success' : 'failed'}`}>
        {isSuccess ? <Check size={16} /> : <X size={16} />}
      </div>
      <div className="receipt-card-icon">
        <Icon size={20} />
      </div>
      <div className="receipt-card-body">
        <strong>{label}</strong>
        <span className="receipt-card-id">{receipt.id}</span>
        <p>{receipt.detail}</p>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create ReceiptsView component**

Create `components/receipts/ReceiptsView.tsx`:
```tsx
'use client';

import React from 'react';
import { PartyPopper } from 'lucide-react';
import { ReceiptCard } from './ReceiptCard';

type ReceiptsViewProps = {
  receipts: Array<{
    type: string;
    tool: string;
    id: string;
    status: string;
    detail: string;
    payload?: Record<string, unknown>;
  }>;
  onNewPlan: () => void;
};

export function ReceiptsView({ receipts, onNewPlan }: ReceiptsViewProps) {
  const successCount = receipts.filter(
    (r) => r.status === 'success' || r.status === 'ok'
  ).length;

  return (
    <section className="receipts-view">
      <div className="receipts-celebration">
        <div className="receipts-celebration-icon">
          <PartyPopper size={32} />
        </div>
        <h2>执行完成</h2>
        <p>成功 {successCount} / {receipts.length} 项操作</p>
      </div>

      <div className="receipts-list">
        {receipts.map((receipt, index) => (
          <ReceiptCard key={receipt.id} receipt={receipt} index={index} />
        ))}
      </div>

      <button className="primary-button" type="button" onClick={onNewPlan}>
        再来一局
      </button>
    </section>
  );
}
```

- [ ] **Step 3: Create RecoveryBanner component**

Create `components/recovery/RecoveryBanner.tsx`:
```tsx
'use client';

import React from 'react';
import { ArrowRight, RefreshCw } from 'lucide-react';

type RecoveryBannerProps = {
  diff: {
    changed?: string;
    reason?: string;
    from?: string;
    to?: string;
    costDelta?: string;
    travelDelta?: string;
    preserved?: string[];
  };
  adjustment?: {
    headline?: string;
    message?: string;
  };
};

export function RecoveryBanner({ diff, adjustment }: RecoveryBannerProps) {
  return (
    <div className="recovery-banner">
      <div className="recovery-banner-icon">
        <RefreshCw size={18} />
      </div>
      <div className="recovery-banner-body">
        <strong>{adjustment?.headline ?? '方案已调整'}</strong>
        <p>{adjustment?.message ?? diff.reason ?? '检测到问题，已自动替换。'}</p>
        {diff.from && diff.to && (
          <div className="recovery-diff">
            <span>{diff.from}</span>
            <ArrowRight size={14} />
            <span>{diff.to}</span>
          </div>
        )}
        {(diff.costDelta || diff.travelDelta) && (
          <div className="recovery-deltas">
            {diff.costDelta && <span>预算: {diff.costDelta}</span>}
            {diff.travelDelta && <span>路程: {diff.travelDelta}</span>}
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Add receipt and recovery styles to globals.css**

Append to `app/globals.css`:

```css
/* ==========================================
   RECEIPTS VIEW
   ========================================== */

.receipts-view {
  max-width: 560px;
  margin: 0 auto;
  padding: 40px 16px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 24px;
  animation: fade-up 0.5s ease both;
}

.receipts-celebration {
  text-align: center;
}

.receipts-celebration-icon {
  width: 64px;
  height: 64px;
  margin: 0 auto 12px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: var(--green-soft);
  color: var(--green);
  animation: celebrate-bounce 0.6s cubic-bezier(0.34, 1.56, 0.64, 1);
}

@keyframes celebrate-bounce {
  0% { transform: scale(0); }
  50% { transform: scale(1.15); }
  100% { transform: scale(1); }
}

.receipts-celebration h2 {
  font-size: 22px;
  font-weight: 700;
  margin: 0;
}

.receipts-celebration p {
  font-size: 14px;
  color: var(--muted);
  margin: 4px 0 0;
}

.receipts-list {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.receipt-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 14px;
  animation: card-slide-in 0.4s ease both;
}

.receipt-card-status {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  flex-shrink: 0;
}

.receipt-card-status.success {
  background: var(--green-soft);
  color: var(--green);
}

.receipt-card-status.failed {
  background: rgba(221, 75, 75, 0.1);
  color: var(--danger);
}

.receipt-card-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: grid;
  place-items: center;
  background: var(--surface-2);
  color: var(--muted);
  flex-shrink: 0;
}

.receipt-card-body {
  flex: 1;
  min-width: 0;
}

.receipt-card-body strong {
  display: block;
  font-size: 14px;
  font-weight: 600;
}

.receipt-card-id {
  display: block;
  font-size: 11px;
  color: var(--subtle);
  font-family: monospace;
  margin-top: 2px;
}

.receipt-card-body p {
  font-size: 13px;
  color: var(--muted);
  margin: 4px 0 0;
}

/* ==========================================
   RECOVERY BANNER
   ========================================== */

.recovery-banner {
  display: flex;
  gap: 12px;
  padding: 14px 16px;
  background: var(--coral-soft);
  border: 1px solid rgba(221, 108, 47, 0.2);
  border-radius: 14px;
  animation: fade-up 0.4s ease both;
}

.recovery-banner-icon {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: grid;
  place-items: center;
  background: white;
  color: var(--coral);
  flex-shrink: 0;
}

.recovery-banner-body strong {
  display: block;
  font-size: 14px;
  font-weight: 600;
  color: var(--coral);
}

.recovery-banner-body p {
  font-size: 13px;
  color: var(--text);
  margin: 4px 0 0;
  line-height: 1.5;
}

.recovery-diff {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
  font-size: 13px;
}

.recovery-diff span {
  padding: 4px 10px;
  background: white;
  border-radius: 8px;
  font-weight: 500;
}

.recovery-diff svg {
  color: var(--muted);
  flex-shrink: 0;
}

.recovery-deltas {
  display: flex;
  gap: 12px;
  margin-top: 6px;
  font-size: 12px;
  color: var(--muted);
}
```

- [ ] **Step 5: Commit**

```bash
git add components/receipts/ components/recovery/
git commit -m "feat: add receipts view and recovery banner components"
```

---

## Task 8: Rewrite the Root Page Component

**Files:**
- Modify: `app/page.tsx`

- [ ] **Step 1: Rewrite page.tsx to use new components and state machine**

Replace the entire contents of `app/page.tsx`:

```tsx
'use client';

import React, { useState } from 'react';
import { AppShell } from '@/components/layout/AppShell';
import { ChatView } from '@/components/chat/ChatView';
import { PlanningProgress } from '@/components/planning/PlanningProgress';
import { PlanResultsView } from '@/components/plan/PlanResultsView';
import { ConfirmView } from '@/components/confirm/ConfirmView';
import { ReceiptsView } from '@/components/receipts/ReceiptsView';
import { SavedPlansView } from '@/components/SavedPlansView';
import { ActivityView } from '@/components/ActivityView';
import { SettingsView } from '@/components/SettingsView';
import { usePlanMachine } from '@/features/planner/usePlanMachine';
import type { ActiveTab } from '@/types/views';

export default function WeekendPilotApp() {
  const [activeTab, setActiveTab] = useState<ActiveTab>('home');
  const machine = usePlanMachine();
  const { state } = machine;

  function handleNavigate(tab: ActiveTab) {
    setActiveTab(tab);
  }

  function handleNewPlan() {
    machine.reset();
    setActiveTab('home');
  }

  function handleSubmitGoal(goal: string) {
    machine.startPlan(goal);
  }

  function handleConfirm() {
    machine.goToConfirm();
  }

  function handleExecute() {
    machine.confirmAndExecute();
  }

  function handleRecover(reason: string) {
    machine.recoverCurrentPlan(reason);
  }

  function handleBackToResults() {
    machine.setPhase('results');
  }

  const planContent = (() => {
    switch (state.phase) {
      case 'idle':
        return (
          <ChatView
            onSubmitGoal={handleSubmitGoal}
            isPlanning={false}
            error={state.error}
          />
        );

      case 'planning':
        return (
          <PlanningProgress
            goal={state.goal}
            progress={[]}
          />
        );

      case 'results':
        if (!state.result) return null;
        return (
          <PlanResultsView
            result={state.result}
            recoveredPlan={state.recoveredPlan}
            onConfirm={handleConfirm}
            onRecover={handleRecover}
            onLoadAlternatives={machine.loadAlternatives}
            error={state.error}
          />
        );

      case 'confirming':
        if (!state.result) return null;
        return (
          <ConfirmView
            result={state.result}
            selectedActions={state.selectedActions}
            onToggleAction={machine.toggleAction}
            onSelectAll={machine.selectAllActions}
            onDeselectAll={machine.deselectAllActions}
            onExecute={handleExecute}
            onBack={handleBackToResults}
            executing={false}
          />
        );

      case 'executing':
        if (!state.result) return null;
        return (
          <ConfirmView
            result={state.result}
            selectedActions={state.selectedActions}
            onToggleAction={machine.toggleAction}
            onSelectAll={machine.selectAllActions}
            onDeselectAll={machine.deselectAllActions}
            onExecute={handleExecute}
            onBack={handleBackToResults}
            executing={true}
          />
        );

      case 'completed':
        return (
          <ReceiptsView
            receipts={state.receipts}
            onNewPlan={handleNewPlan}
          />
        );

      case 'recovering':
        return (
          <PlanningProgress
            goal="正在恢复方案..."
            progress={[]}
          />
        );

      default:
        return null;
    }
  })();

  return (
    <AppShell
      activeTab={activeTab}
      onNavigate={handleNavigate}
      onNewPlan={handleNewPlan}
    >
      {activeTab === 'home' && planContent}
      {activeTab === 'plans' && <SavedPlansView onPlan={() => handleSubmitGoal('今天下午带孩子出去玩')} />}
      {activeTab === 'activity' && <ActivityView />}
      {activeTab === 'settings' && <SettingsView />}
    </AppShell>
  );
}
```

- [ ] **Step 2: Verify build compiles**

Run: `npx next build 2>&1 | tail -10`
Expected: Build succeeds.

- [ ] **Step 3: Commit**

```bash
git add app/page.tsx
git commit -m "feat: rewrite root page with plan state machine and new view components"
```

---

## Task 9: Clean Up Old Components and Update Globals

**Files:**
- Modify: `app/globals.css` (remove old layout styles, consolidate)
- Remove: `components/AppChrome.jsx` (replaced by AppShell)
- Remove: `components/Sidebar.jsx` (replaced by DesktopSidebar)
- Keep: `components/HomeView.jsx` (deprecated, but keep for reference)
- Keep: `components/PlannerView.jsx` (deprecated, but keep for reference)

- [ ] **Step 1: Remove old AppChrome and Sidebar imports from any remaining files**

Run: `grep -r "AppChrome\|Sidebar" --include="*.tsx" --include="*.jsx" --include="*.ts" components/ app/`
Expected: Only found in the files being removed.

- [ ] **Step 2: Remove old files**

```bash
rm components/AppChrome.jsx components/Sidebar.jsx
```

- [ ] **Step 3: Clean up globals.css - remove old layout styles**

In `app/globals.css`, remove the old `.app-shell`, `.sidebar`, `.brand-block`, `.brand-avatar`, `.nav-list`, `.nav-item`, `.sidebar-footer`, `.sidebar-note`, `.global-topbar`, `.topbar-brand`, `.topbar-search`, `.execute-pill`, `.workspace-tabs` rules (approximately lines 56-250). Keep all other existing styles as they may still be used by `SavedPlansView`, `ActivityView`, `SettingsView`, and the planner sub-components.

- [ ] **Step 4: Verify build**

Run: `npx next build 2>&1 | tail -10`
Expected: Build succeeds.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor: remove old AppChrome/Sidebar, clean up unused CSS"
```

---

## Task 10: Wire Up `buildAlternatives` API in VariantSelector

**Files:**
- Modify: `components/plan/PlanResultsView.tsx` (pass loadAlternatives callback)
- Modify: `components/plan/VariantSelector.tsx` (handle loading state)

- [ ] **Step 1: Update VariantSelector to show loading state**

Update `components/plan/VariantSelector.tsx` to add a loading state:

```tsx
'use client';

import React from 'react';
import { Loader2 } from 'lucide-react';

type VariantSelectorProps = {
  variants: Array<Record<string, any>>;
  activeIndex: number;
  onSelect: (index: number) => void;
  onLoadMore?: () => void;
  loading?: boolean;
};

const kindLabels: Record<string, string> = {
  main: '推荐',
  budget: '省钱',
  comfort: '舒适',
  child_first: '亲子',
  experience_first: '体验',
};

export function VariantSelector({ variants, activeIndex, onSelect, onLoadMore, loading }: VariantSelectorProps) {
  if (!variants.length) return null;

  return (
    <section className="variant-selector">
      <div className="variant-scroll">
        {variants.map((variant, index) => (
          <button
            key={variant.id ?? variant.kind ?? index}
            className={`variant-chip${index === activeIndex ? ' active' : ''}`}
            type="button"
            onClick={() => onSelect(index)}
          >
            <strong>{kindLabels[variant.kind] ?? variant.title ?? `方案${index + 1}`}</strong>
            {variant.overview?.score && <span>{variant.overview.score}分</span>}
          </button>
        ))}
        {onLoadMore && variants.length <= 1 && (
          <button
            className="variant-chip variant-chip--more"
            type="button"
            onClick={onLoadMore}
            disabled={loading}
          >
            {loading ? <Loader2 size={14} className="spin" /> : '更多方案'}
          </button>
        )}
      </div>
    </section>
  );
}
```

- [ ] **Step 2: Update PlanResultsView to manage alternatives loading state**

In `components/plan/PlanResultsView.tsx`, add a `loadingAlternatives` state and pass it to `VariantSelector`:

```tsx
'use client';

import React, { useState } from 'react';
// ... existing imports ...

export function PlanResultsView({
  result,
  recoveredPlan,
  onConfirm,
  onRecover,
  onLoadAlternatives,
  onPatchConstraints,
  error,
}: PlanResultsViewProps) {
  const [activeVariant, setActiveVariant] = useState(0);
  const [showTrace, setShowTrace] = useState(false);
  const [loadingAlternatives, setLoadingAlternatives] = useState(false);

  async function handleLoadAlternatives() {
    setLoadingAlternatives(true);
    try {
      await onLoadAlternatives();
    } finally {
      setLoadingAlternatives(false);
    }
  }

  // ... rest of component stays the same, but update VariantSelector usage:

  return (
    <section className="plan-results">
      {/* ... existing content ... */}

      <VariantSelector
        variants={result.variants?.length ? result.variants : [plan]}
        activeIndex={activeVariant}
        onSelect={setActiveVariant}
        onLoadMore={handleLoadAlternatives}
        loading={loadingAlternatives}
      />

      {/* ... rest stays the same ... */}
    </section>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add components/plan/
git commit -m "feat: wire up buildAlternatives API with loading state in variant selector"
```

---

## Task 11: Add Page-Level Transition Animations

**Files:**
- Modify: `app/globals.css` (add view transition animations)

- [ ] **Step 1: Add view transition styles to globals.css**

Append to `app/globals.css`:

```css
/* ==========================================
   VIEW TRANSITIONS
   ========================================== */

.view-enter {
  animation: view-enter 0.4s cubic-bezier(0.34, 1.56, 0.64, 1) both;
}

@keyframes view-enter {
  from {
    opacity: 0;
    transform: translateY(20px) scale(0.98);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.view-exit {
  animation: view-exit 0.25s ease both;
}

@keyframes view-exit {
  from {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
  to {
    opacity: 0;
    transform: translateY(-10px) scale(0.98);
  }
}

/* Stagger children animation helper */
.stagger-children > * {
  animation: fade-up 0.4s ease both;
}

.stagger-children > *:nth-child(1) { animation-delay: 0ms; }
.stagger-children > *:nth-child(2) { animation-delay: 60ms; }
.stagger-children > *:nth-child(3) { animation-delay: 120ms; }
.stagger-children > *:nth-child(4) { animation-delay: 180ms; }
.stagger-children > *:nth-child(5) { animation-delay: 240ms; }
.stagger-children > *:nth-child(6) { animation-delay: 300ms; }
.stagger-children > *:nth-child(7) { animation-delay: 360ms; }
.stagger-children > *:nth-child(8) { animation-delay: 420ms; }

/* Skeleton loading */
.skeleton {
  background: linear-gradient(90deg, var(--surface-2) 25%, var(--line) 50%, var(--surface-2) 75%);
  background-size: 200% 100%;
  animation: skeleton-shimmer 1.5s ease infinite;
  border-radius: 8px;
}

@keyframes skeleton-shimmer {
  from { background-position: 200% 0; }
  to { background-position: -200% 0; }
}

/* Reduce motion for accessibility */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add app/globals.css
git commit -m "feat: add view transition animations and reduced-motion support"
```

---

## Task 12: End-to-End Integration Test

**Files:**
- Modify: `tests/e2e/plan-flow.spec.ts` (if exists, or create)

- [ ] **Step 1: Verify the app starts and renders the chat view**

Run: `npm run dev` (in background), then open `http://127.0.0.1:4174`
Expected: Chat view loads with AI welcome bubble and quick action buttons.

- [ ] **Step 2: Test the full planning flow manually**

1. Click "带娃出行" quick action
2. Verify planning progress animation appears
3. Verify plan results view loads with itinerary timeline
4. Click "确认方案，查看执行项"
5. Verify confirmation view shows action toggles
6. Toggle some actions on/off
7. Click "一键执行"
8. Verify receipts view shows with celebration animation
9. Click "再来一局"
10. Verify returns to chat view

- [ ] **Step 3: Test variant loading**

1. Generate a plan
2. Click "更多方案" in variant selector
3. Verify `buildAlternatives` API is called
4. Verify new variant tabs appear

- [ ] **Step 4: Test recovery flow**

1. Generate a plan
2. Click "模拟故障恢复"
3. Verify recovery banner appears with diff
4. Verify new itinerary replaces old one

- [ ] **Step 5: Test responsive layout**

1. Resize browser to mobile width (< 820px)
2. Verify bottom navigation appears
3. Verify sidebar disappears
4. Verify chat view takes full width
5. Resize back to desktop
6. Verify sidebar appears, bottom nav disappears

- [ ] **Step 6: Final commit**

```bash
git add -A
git commit -m "feat: complete frontend redesign with full API integration and animations"
```

---

## Summary of API Integration

| Backend API | Frontend Function | Where Called | Status |
|---|---|---|---|
| `POST /api/plans/build` | `buildPlan(goal)` | `usePlanMachine.startPlan()` | **Integrated** |
| `GET /api/plans/{planId}` | `getPlan(planId)` | Available but not yet needed | Defined |
| `PATCH /api/plans/{planId}/constraints` | `patchConstraints(planId, body)` | `ConstraintCards` (kept from existing) | **Integrated** |
| `POST /api/plans/{planId}/alternatives` | `buildAlternatives(planId)` | `usePlanMachine.loadAlternatives()` | **Integrated** |
| `POST /api/plans/{planId}/confirm` | `confirmPlan(planId)` | `usePlanMachine.confirmAndExecute()` | **Integrated** |
| `POST /api/plans/{planId}/execute` | `executePlan(planId)` | `usePlanMachine.confirmAndExecute()` | **Integrated** |
| `POST /api/plans/{planId}/recover` | `recoverPlan(planId, reason)` | `usePlanMachine.recoverCurrentPlan()` | **Integrated** |
| `GET /api/traces/{planId}` | `getTraces(planId)` | Available for future use | Defined |
| `GET /api/tool-schemas` | `getToolSchemas()` | Available for future use | Defined |
| `GET /api/health` | `getHealth()` | Available for future use | Defined |

## Key Design Decisions

1. **Mobile-first, responsive**: Bottom nav on mobile, sidebar on desktop. All components use responsive CSS.
2. **Chat-centric home**: AI assistant chat as the primary entry point, matching the prototype's UX.
3. **5-phase plan lifecycle**: idle → planning → results → confirming → executing → completed. Each phase is a distinct view with appropriate animations.
4. **Confirm before execute**: The backend's `confirm` → `execute` two-step is now properly exposed. Users toggle actions on/off before executing.
5. **Staggered animations**: Timeline cards, action toggles, and receipt cards animate in with staggered delays for a polished feel.
6. **Reduced motion**: `prefers-reduced-motion` media query disables animations for accessibility.
7. **State machine pattern**: `usePlanMachine` hook centralizes all plan lifecycle state, preventing inconsistent states.
8. **Preserved existing components**: `ConstraintCards`, `TracePanel`, `RouteMap`, `SavedPlansView`, `ActivityView`, `SettingsView` are kept as-is where they work well.
