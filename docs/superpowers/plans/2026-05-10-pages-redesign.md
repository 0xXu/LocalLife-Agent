# Pages Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign three secondary pages (Saved Plans, Activity, Settings) with a shared UI component library, CSS Modules, rich animations, and a mock API layer.

**Architecture:** Extract 8 reusable UI components into `components/ui/`, rewrite three JSX pages as TypeScript with CSS Modules, create a typed mock API layer in `features/planner/mockData.ts`, and integrate via custom hooks. Global CSS retains shared keyframes; each component gets its own `.module.css` for style isolation.

**Tech Stack:** React 19, Next.js 15, TypeScript 6, CSS Modules, lucide-react icons, Zod 4. No new dependencies.

---

## Phase 1: Foundation

### Task 1: Type Definitions

**Files:**
- Create: `types/api.ts`

- [ ] **Step 1: Create the API type definitions file**

```typescript
// types/api.ts

export type PlanStatus = 'draft' | 'saved' | 'executing' | 'completed';
export type ActivityStatus = 'completed' | 'failed' | 'partial';

export interface PlanSummary {
  id: string;
  title: string;
  status: PlanStatus;
  summary: string;
  created_at: string;
  updated_at: string;
  tags: string[];
  location?: string;
  estimated_cost?: string;
  itinerary_count: number;
}

export interface PlanListResponse {
  plans: PlanSummary[];
  total: number;
}

export interface ActivityRecord {
  id: string;
  plan_id: string;
  plan_title: string;
  executed_at: string;
  status: ActivityStatus;
  total_cost?: string;
  receipts: ActivityReceipt[];
  summary: string;
}

export interface ActivityReceipt {
  type: string;
  tool: string;
  id: string;
  status: string;
  detail: string;
}

export interface ActivityStats {
  total_plans: number;
  total_cost: number;
  frequent_type: string;
}

export interface ActivityListResponse {
  activities: ActivityRecord[];
  stats: ActivityStats;
}

export interface UserPreferences {
  profile: {
    display_name: string;
    email: string;
    avatar_url?: string;
  };
  diet: {
    fitness_friendly: boolean;
    vegetarian: boolean;
    gluten_free: boolean;
    allergies: string[];
  };
  location: {
    radius_km: number;
    home_address?: string;
    favorite_places: string[];
  };
  notifications: {
    execution_reminder: boolean;
    plan_change: boolean;
    weekly_digest: boolean;
  };
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `npx tsc --noEmit types/api.ts`
Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add types/api.ts
git commit -m "feat: add API type definitions for pages redesign"
```

---

### Task 2: Mock Data and API Functions

**Files:**
- Create: `features/planner/mockData.ts`

- [ ] **Step 1: Create the mock data module**

```typescript
// features/planner/mockData.ts
import type {
  PlanSummary,
  PlanListResponse,
  ActivityRecord,
  ActivityListResponse,
  UserPreferences,
} from '../../types/api';

const delay = (ms: number) => new Promise((r) => setTimeout(r, ms));

const STORAGE_KEYS = {
  plans: 'weekendpilot_plans',
  preferences: 'weekendpilot_preferences',
} as const;

const MOCK_PLANS: PlanSummary[] = [
  {
    id: 'plan_001',
    title: '亲子科学馆半日游',
    status: 'saved',
    summary: '带孩子去科学馆探索互动展区，下午茶休息，公园散步放风。',
    created_at: '2026-05-08T10:00:00Z',
    updated_at: '2026-05-08T10:30:00Z',
    tags: ['家庭', '教育', '半日'],
    location: '市中心 5 公里内',
    estimated_cost: '约 320 元',
    itinerary_count: 4,
  },
  {
    id: 'plan_002',
    title: '朋友拍照聚餐',
    status: 'draft',
    summary: '艺术街区拍照打卡，创意菜餐厅聚餐，夜市散步。',
    created_at: '2026-05-07T15:00:00Z',
    updated_at: '2026-05-07T15:20:00Z',
    tags: ['朋友', '拍照', '预算适中'],
    location: '艺术街区',
    estimated_cost: '约 480 元',
    itinerary_count: 3,
  },
  {
    id: 'plan_003',
    title: '雨天室内备选',
    status: 'saved',
    summary: '室内攀岩体验，商场美食广场，电影院新片。',
    created_at: '2026-05-06T09:00:00Z',
    updated_at: '2026-05-06T09:15:00Z',
    tags: ['雨天', '室内', '低等待'],
    location: '商场室内动线',
    estimated_cost: '约 260 元',
    itinerary_count: 3,
  },
  {
    id: 'plan_004',
    title: '周末约会路线',
    status: 'completed',
    summary: '咖啡馆早午餐，美术馆展览，河滨散步晚餐。',
    created_at: '2026-05-03T11:00:00Z',
    updated_at: '2026-05-04T20:00:00Z',
    tags: ['约会', '文艺', '全天'],
    location: '河滨区域',
    estimated_cost: '约 580 元',
    itinerary_count: 5,
  },
];

const MOCK_ACTIVITIES: ActivityRecord[] = [
  {
    id: 'activity_001',
    plan_id: 'plan_004',
    plan_title: '周末约会路线',
    executed_at: '2026-05-04T10:00:00Z',
    status: 'completed',
    total_cost: '约 560 元',
    receipts: [
      { type: 'payment', tool: 'booking', id: 'r_001', status: 'success', detail: '咖啡馆早午餐预约成功，2人' },
      { type: 'payment', tool: 'booking', id: 'r_002', status: 'success', detail: '美术馆门票 2 张' },
      { type: 'payment', tool: 'booking', id: 'r_003', status: 'success', detail: '河滨餐厅晚餐预约，2人' },
    ],
    summary: '咖啡馆 + 美术馆 + 河滨晚餐',
  },
  {
    id: 'activity_002',
    plan_id: 'plan_old_001',
    plan_title: '雨天手作体验',
    executed_at: '2026-05-02T14:00:00Z',
    status: 'completed',
    total_cost: '约 320 元',
    receipts: [
      { type: 'payment', tool: 'booking', id: 'r_004', status: 'success', detail: '陶艺工坊体验预约成功' },
      { type: 'payment', tool: 'booking', id: 'r_005', status: 'success', detail: '邻近咖啡馆午餐' },
    ],
    summary: '陶艺体验 + 咖啡馆',
  },
  {
    id: 'activity_003',
    plan_id: 'plan_old_002',
    plan_title: '海岸自驾与海鲜',
    executed_at: '2026-04-28T10:00:00Z',
    status: 'completed',
    total_cost: '约 810 元',
    receipts: [
      { type: 'payment', tool: 'booking', id: 'r_006', status: 'success', detail: '海鲜餐厅预订确认' },
      { type: 'info', tool: 'navigation', id: 'r_007', status: 'success', detail: '海岸路线导航完成' },
    ],
    summary: '海岸自驾 + 海鲜大餐',
  },
  {
    id: 'activity_004',
    plan_id: 'plan_old_003',
    plan_title: '独立电影首映',
    executed_at: '2026-04-20T19:30:00Z',
    status: 'completed',
    total_cost: '约 245 元',
    receipts: [
      { type: 'payment', tool: 'booking', id: 'r_008', status: 'success', detail: '《霓虹回声》首映票 2 张' },
    ],
    summary: '独立电影 + 周边酒吧',
  },
];

const DEFAULT_PREFERENCES: UserPreferences = {
  profile: {
    display_name: '用户',
    email: 'user@example.com',
  },
  diet: {
    fitness_friendly: true,
    vegetarian: false,
    gluten_free: false,
    allergies: [],
  },
  location: {
    radius_km: 5,
    favorite_places: [],
  },
  notifications: {
    execution_reminder: true,
    plan_change: true,
    weekly_digest: false,
  },
};

export async function fetchPlans(): Promise<PlanListResponse> {
  await delay(800);
  const stored = localStorage.getItem(STORAGE_KEYS.plans);
  const plans: PlanSummary[] = stored ? JSON.parse(stored) : MOCK_PLANS;
  return { plans, total: plans.length };
}

export async function updatePlan(planId: string, updates: Partial<PlanSummary>): Promise<PlanSummary> {
  await delay(500);
  const stored = localStorage.getItem(STORAGE_KEYS.plans);
  const plans: PlanSummary[] = stored ? JSON.parse(stored) : [...MOCK_PLANS];
  const index = plans.findIndex((p) => p.id === planId);
  if (index === -1) throw new Error('Plan not found');
  plans[index] = { ...plans[index], ...updates, updated_at: new Date().toISOString() };
  localStorage.setItem(STORAGE_KEYS.plans, JSON.stringify(plans));
  return plans[index];
}

export async function deletePlan(planId: string): Promise<void> {
  await delay(400);
  const stored = localStorage.getItem(STORAGE_KEYS.plans);
  const plans: PlanSummary[] = stored ? JSON.parse(stored) : [...MOCK_PLANS];
  const filtered = plans.filter((p) => p.id !== planId);
  localStorage.setItem(STORAGE_KEYS.plans, JSON.stringify(filtered));
}

export async function fetchActivities(): Promise<ActivityListResponse> {
  await delay(600);
  return {
    activities: MOCK_ACTIVITIES,
    stats: {
      total_plans: MOCK_ACTIVITIES.length,
      total_cost: MOCK_ACTIVITIES.reduce(
        (sum, a) => sum + parseInt(a.total_cost?.replace(/\D/g, '') || '0'),
        0,
      ),
      frequent_type: '餐饮',
    },
  };
}

export async function fetchPreferences(): Promise<UserPreferences> {
  await delay(400);
  const stored = localStorage.getItem(STORAGE_KEYS.preferences);
  return stored ? JSON.parse(stored) : DEFAULT_PREFERENCES;
}

export async function savePreferences(prefs: UserPreferences): Promise<void> {
  await delay(300);
  localStorage.setItem(STORAGE_KEYS.preferences, JSON.stringify(prefs));
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `npx tsc --noEmit features/planner/mockData.ts`
Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add features/planner/mockData.ts
git commit -m "feat: add mock data layer with typed API functions"
```

---

### Task 3: Custom Hooks

**Files:**
- Create: `features/planner/usePlans.ts`
- Create: `features/planner/useActivities.ts`
- Create: `features/planner/usePreferences.ts`

- [ ] **Step 1: Create usePlans hook**

```typescript
// features/planner/usePlans.ts
'use client';

import { useState, useEffect, useCallback } from 'react';
import type { PlanSummary } from '../../types/api';
import { fetchPlans, updatePlan, deletePlan } from './mockData';

export function usePlans() {
  const [plans, setPlans] = useState<PlanSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchPlans();
      setPlans(data.plans);
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const update = useCallback(
    async (planId: string, updates: Partial<PlanSummary>) => {
      const updated = await updatePlan(planId, updates);
      setPlans((prev) => prev.map((p) => (p.id === planId ? updated : p)));
      return updated;
    },
    [],
  );

  const remove = useCallback(async (planId: string) => {
    await deletePlan(planId);
    setPlans((prev) => prev.filter((p) => p.id !== planId));
  }, []);

  return { plans, loading, error, refetch: load, update, remove };
}
```

- [ ] **Step 2: Create useActivities hook**

```typescript
// features/planner/useActivities.ts
'use client';

import { useState, useEffect, useCallback } from 'react';
import type { ActivityRecord, ActivityStats } from '../../types/api';
import { fetchActivities } from './mockData';

export function useActivities() {
  const [activities, setActivities] = useState<ActivityRecord[]>([]);
  const [stats, setStats] = useState<ActivityStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchActivities();
      setActivities(data.activities);
      setStats(data.stats);
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return { activities, stats, loading, error, refetch: load };
}
```

- [ ] **Step 3: Create usePreferences hook**

```typescript
// features/planner/usePreferences.ts
'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import type { UserPreferences } from '../../types/api';
import { fetchPreferences, savePreferences } from './mockData';

const DEFAULT_PREFERENCES: UserPreferences = {
  profile: { display_name: '用户', email: 'user@example.com' },
  diet: { fitness_friendly: true, vegetarian: false, gluten_free: false, allergies: [] },
  location: { radius_km: 5, favorite_places: [] },
  notifications: { execution_reminder: true, plan_change: true, weekly_digest: false },
};

export function usePreferences() {
  const [preferences, setPreferences] = useState<UserPreferences>(DEFAULT_PREFERENCES);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [showSaved, setShowSaved] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout>>();

  useEffect(() => {
    fetchPreferences().then((p) => {
      setPreferences(p);
      setLoading(false);
    });
  }, []);

  const update = useCallback(
    async (updater: (prev: UserPreferences) => UserPreferences) => {
      const updated = updater(preferences);
      setPreferences(updated);
      setSaving(true);
      try {
        await savePreferences(updated);
        setShowSaved(true);
        clearTimeout(timerRef.current);
        timerRef.current = setTimeout(() => setShowSaved(false), 1500);
      } finally {
        setSaving(false);
      }
    },
    [preferences],
  );

  return { preferences, loading, saving, showSaved, update };
}
```

- [ ] **Step 4: Verify TypeScript compiles**

Run: `npx tsc --noEmit features/planner/usePlans.ts features/planner/useActivities.ts features/planner/usePreferences.ts`
Expected: No errors.

- [ ] **Step 5: Commit**

```bash
git add features/planner/usePlans.ts features/planner/useActivities.ts features/planner/usePreferences.ts
git commit -m "feat: add custom hooks for plans, activities, and preferences"
```

---

## Phase 2: UI Components

### Task 4: Button Component

**Files:**
- Create: `components/ui/Button.tsx`
- Create: `components/ui/Button.module.css`

- [ ] **Step 1: Create the Button CSS Module**

```css
/* components/ui/Button.module.css */
.button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border: none;
  cursor: pointer;
  font-family: inherit;
  font-weight: 600;
  transition: background 0.15s ease, transform 0.15s ease, box-shadow 0.15s ease;
}

.button:active:not(:disabled) {
  transform: scale(0.97);
}

.button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Sizes */
.sm {
  height: 32px;
  padding: 0 12px;
  font-size: 13px;
  border-radius: 8px;
}

.md {
  height: 40px;
  padding: 0 18px;
  font-size: 14px;
  border-radius: 10px;
}

.lg {
  height: 48px;
  padding: 0 24px;
  font-size: 15px;
  border-radius: 12px;
}

/* Variants */
.primary {
  background: var(--blue);
  color: white;
  box-shadow: 0 4px 12px rgba(5, 99, 201, 0.2);
}

.primary:hover:not(:disabled) {
  background: #0458b3;
}

.secondary {
  background: var(--surface-2);
  color: var(--text);
  border: 1px solid var(--line);
}

.secondary:hover:not(:disabled) {
  background: var(--line);
}

.danger {
  background: var(--danger);
  color: white;
}

.danger:hover:not(:disabled) {
  background: #c93c3c;
}

.ghost {
  background: transparent;
  color: var(--muted);
}

.ghost:hover:not(:disabled) {
  background: var(--surface-2);
  color: var(--text);
}

/* Loading spinner */
.spinner {
  width: 16px;
  height: 16px;
  border: 2px solid currentColor;
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
```

- [ ] **Step 2: Create the Button component**

```tsx
// components/ui/Button.tsx
'use client';

import React from 'react';
import styles from './Button.module.css';

export interface ButtonProps {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
  icon?: React.ReactNode;
  loading?: boolean;
  disabled?: boolean;
  children: React.ReactNode;
  onClick?: () => void;
  className?: string;
  type?: 'button' | 'submit';
  'data-testid'?: string;
}

export function Button({
  variant = 'primary',
  size = 'md',
  icon,
  loading,
  disabled,
  children,
  onClick,
  className,
  type = 'button',
  'data-testid': testId,
}: ButtonProps) {
  return (
    <button
      type={type}
      className={`${styles.button} ${styles[size]} ${styles[variant]} ${className ?? ''}`}
      disabled={disabled || loading}
      onClick={onClick}
      data-testid={testId}
    >
      {loading ? <span className={styles.spinner} /> : icon}
      {children}
    </button>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add components/ui/Button.tsx components/ui/Button.module.css
git commit -m "feat: add Button UI component with CSS Module"
```

---

### Task 5: Card Component

**Files:**
- Create: `components/ui/Card.tsx`
- Create: `components/ui/Card.module.css`

- [ ] **Step 1: Create the Card CSS Module**

```css
/* components/ui/Card.module.css */
.card {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 16px;
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
}

/* Padding */
.paddingSm { padding: 12px; }
.paddingMd { padding: 16px; }
.paddingLg { padding: 24px; }

/* Variants */
.elevated {
  box-shadow: var(--shadow-sm);
  border-color: transparent;
}

.outlined {
  border-width: 1.5px;
  border-color: var(--line-strong);
}

/* Interactive */
.interactive {
  cursor: pointer;
}

.interactive:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}

.interactive:active {
  transform: translateY(0);
}

/* Selected */
.selected {
  border-color: var(--blue);
  background: var(--blue-soft);
}
```

- [ ] **Step 2: Create the Card component**

```tsx
// components/ui/Card.tsx
'use client';

import React from 'react';
import styles from './Card.module.css';

export interface CardProps {
  variant?: 'default' | 'elevated' | 'outlined';
  padding?: 'sm' | 'md' | 'lg';
  interactive?: boolean;
  selected?: boolean;
  children: React.ReactNode;
  onClick?: () => void;
  className?: string;
  style?: React.CSSProperties;
  'data-testid'?: string;
}

export function Card({
  variant = 'default',
  padding = 'md',
  interactive,
  selected,
  children,
  onClick,
  className,
  style,
  'data-testid': testId,
}: CardProps) {
  return (
    <div
      className={[
        styles.card,
        styles[`padding${padding.charAt(0).toUpperCase() + padding.slice(1)}`],
        variant !== 'default' ? styles[variant] : '',
        interactive ? styles.interactive : '',
        selected ? styles.selected : '',
        className ?? '',
      ]
        .filter(Boolean)
        .join(' ')}
      style={style}
      onClick={onClick}
      role={interactive ? 'button' : undefined}
      tabIndex={interactive ? 0 : undefined}
      data-testid={testId}
    >
      {children}
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add components/ui/Card.tsx components/ui/Card.module.css
git commit -m "feat: add Card UI component with CSS Module"
```

---

### Task 6: Toggle Component

**Files:**
- Create: `components/ui/Toggle.tsx`
- Create: `components/ui/Toggle.module.css`

- [ ] **Step 1: Create the Toggle CSS Module**

```css
/* components/ui/Toggle.module.css */
.row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.label {
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
}

.description {
  font-size: 13px;
  color: var(--muted);
}

.track {
  position: relative;
  width: 48px;
  height: 28px;
  padding: 3px;
  border-radius: 999px;
  background: #c4ccdd;
  border: none;
  cursor: pointer;
  flex-shrink: 0;
  transition: background 0.2s ease;
}

.track:hover {
  background: #b0b8cc;
}

.track.on {
  background: var(--blue-2);
}

.track.on:hover {
  background: var(--blue);
}

.thumb {
  display: block;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: white;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.15);
  transition: transform 0.2s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.track.on .thumb {
  transform: translateX(20px);
}

.track:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
```

- [ ] **Step 2: Create the Toggle component**

```tsx
// components/ui/Toggle.tsx
'use client';

import React from 'react';
import styles from './Toggle.module.css';

export interface ToggleProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
  label?: string;
  description?: string;
  testId?: string;
}

export function Toggle({ checked, onChange, disabled, label, description, testId }: ToggleProps) {
  return (
    <div className={styles.row}>
      {(label || description) && (
        <div className={styles.text}>
          {label && <strong className={styles.label}>{label}</strong>}
          {description && <span className={styles.description}>{description}</span>}
        </div>
      )}
      <button
        type="button"
        className={`${styles.track} ${checked ? styles.on : ''}`}
        aria-pressed={checked}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        data-testid={testId}
      >
        <span className={styles.thumb} />
      </button>
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add components/ui/Toggle.tsx components/ui/Toggle.module.css
git commit -m "feat: add Toggle UI component with CSS Module"
```

---

### Task 7: Badge Component

**Files:**
- Create: `components/ui/Badge.tsx`
- Create: `components/ui/Badge.module.css`

- [ ] **Step 1: Create the Badge CSS Module**

```css
/* components/ui/Badge.module.css */
.badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-weight: 600;
  white-space: nowrap;
}

.sm {
  padding: 2px 8px;
  font-size: 11px;
  border-radius: 6px;
}

.md {
  padding: 4px 10px;
  font-size: 12px;
  border-radius: 8px;
}

.default {
  background: var(--surface-2);
  color: var(--muted);
}

.success {
  background: var(--green-soft);
  color: var(--green);
}

.warning {
  background: var(--coral-soft);
  color: var(--coral);
}

.error {
  background: rgba(221, 75, 75, 0.1);
  color: var(--danger);
}

.info {
  background: var(--blue-soft);
  color: var(--blue);
}
```

- [ ] **Step 2: Create the Badge component**

```tsx
// components/ui/Badge.tsx
import React from 'react';
import styles from './Badge.module.css';

export interface BadgeProps {
  variant?: 'default' | 'success' | 'warning' | 'error' | 'info';
  size?: 'sm' | 'md';
  children: React.ReactNode;
  className?: string;
}

export function Badge({ variant = 'default', size = 'sm', children, className }: BadgeProps) {
  return (
    <span className={`${styles.badge} ${styles[size]} ${styles[variant]} ${className ?? ''}`}>
      {children}
    </span>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add components/ui/Badge.tsx components/ui/Badge.module.css
git commit -m "feat: add Badge UI component with CSS Module"
```

---

### Task 8: EmptyState Component

**Files:**
- Create: `components/ui/EmptyState.tsx`
- Create: `components/ui/EmptyState.module.css`

- [ ] **Step 1: Create the EmptyState CSS Module**

```css
/* components/ui/EmptyState.module.css */
.container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 48px 24px;
  animation: fade-up 0.4s ease both;
}

.icon {
  display: grid;
  place-items: center;
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: var(--surface-2);
  color: var(--subtle);
  margin-bottom: 16px;
}

.title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text);
  margin: 0 0 6px;
}

.description {
  font-size: 14px;
  color: var(--muted);
  margin: 0 0 20px;
  max-width: 280px;
}

.action {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 10px 20px;
  background: var(--blue);
  color: white;
  border: none;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s ease, transform 0.15s ease;
}

.action:hover {
  background: #0458b3;
}

.action:active {
  transform: scale(0.97);
}
```

- [ ] **Step 2: Create the EmptyState component**

```tsx
// components/ui/EmptyState.tsx
'use client';

import React from 'react';
import styles from './EmptyState.module.css';

export interface EmptyStateProps {
  icon: React.ReactNode;
  title: string;
  description: string;
  action?: {
    label: string;
    onClick: () => void;
  };
}

export function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div className={styles.container}>
      <div className={styles.icon}>{icon}</div>
      <h3 className={styles.title}>{title}</h3>
      <p className={styles.description}>{description}</p>
      {action && (
        <button type="button" className={styles.action} onClick={action.onClick}>
          {action.label}
        </button>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add components/ui/EmptyState.tsx components/ui/EmptyState.module.css
git commit -m "feat: add EmptyState UI component with CSS Module"
```

---

### Task 9: Skeleton Component

**Files:**
- Create: `components/ui/Skeleton.tsx`
- Create: `components/ui/Skeleton.module.css`

- [ ] **Step 1: Create the Skeleton CSS Module**

```css
/* components/ui/Skeleton.module.css */
.skeleton {
  background: linear-gradient(90deg, var(--surface-2) 25%, var(--line) 50%, var(--surface-2) 75%);
  background-size: 200% 100%;
  animation: skeleton-shimmer 1.5s ease-in-out infinite;
  border-radius: 8px;
}

.text {
  height: 16px;
  width: 100%;
}

.circular {
  border-radius: 50%;
}

.rectangular {
  border-radius: 8px;
}
```

- [ ] **Step 2: Create the Skeleton component**

```tsx
// components/ui/Skeleton.tsx
import React from 'react';
import styles from './Skeleton.module.css';

export interface SkeletonProps {
  variant?: 'text' | 'circular' | 'rectangular';
  width?: string | number;
  height?: string | number;
  className?: string;
}

export function Skeleton({ variant = 'text', width, height, className }: SkeletonProps) {
  return (
    <div
      className={`${styles.skeleton} ${styles[variant]} ${className ?? ''}`}
      style={{ width, height }}
    />
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add components/ui/Skeleton.tsx components/ui/Skeleton.module.css
git commit -m "feat: add Skeleton UI component with CSS Module"
```

---

### Task 10: SearchInput Component

**Files:**
- Create: `components/ui/SearchInput.tsx`
- Create: `components/ui/SearchInput.module.css`

- [ ] **Step 1: Create the SearchInput CSS Module**

```css
/* components/ui/SearchInput.module.css */
.wrapper {
  position: relative;
  display: flex;
  align-items: center;
}

.icon {
  position: absolute;
  left: 12px;
  color: var(--subtle);
  pointer-events: none;
}

.input {
  width: 100%;
  height: 40px;
  padding: 0 36px 0 38px;
  background: var(--surface-2);
  border: 1.5px solid transparent;
  border-radius: 10px;
  font-size: 14px;
  color: var(--text);
  font-family: inherit;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.input::placeholder {
  color: var(--subtle);
}

.input:focus {
  outline: none;
  border-color: var(--blue);
  box-shadow: 0 0 0 3px rgba(11, 119, 255, 0.1);
  background: var(--panel);
}

.clear {
  position: absolute;
  right: 8px;
  display: grid;
  place-items: center;
  width: 24px;
  height: 24px;
  border: none;
  background: var(--line);
  border-radius: 50%;
  color: var(--muted);
  cursor: pointer;
  transition: background 0.15s ease;
}

.clear:hover {
  background: var(--line-strong);
}
```

- [ ] **Step 2: Create the SearchInput component**

```tsx
// components/ui/SearchInput.tsx
'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Search, X } from 'lucide-react';
import styles from './SearchInput.module.css';

export interface SearchInputProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  debounceMs?: number;
  autoFocus?: boolean;
  className?: string;
}

export function SearchInput({
  value,
  onChange,
  placeholder = '搜索...',
  debounceMs = 300,
  autoFocus,
  className,
}: SearchInputProps) {
  const [local, setLocal] = useState(value);
  const timerRef = useRef<ReturnType<typeof setTimeout>>();

  useEffect(() => {
    setLocal(value);
  }, [value]);

  const debouncedChange = useCallback(
    (next: string) => {
      setLocal(next);
      clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => onChange(next), debounceMs);
    },
    [onChange, debounceMs],
  );

  useEffect(() => () => clearTimeout(timerRef.current), []);

  return (
    <div className={`${styles.wrapper} ${className ?? ''}`}>
      <Search size={16} className={styles.icon} />
      <input
        type="search"
        className={styles.input}
        value={local}
        onChange={(e) => debouncedChange(e.target.value)}
        placeholder={placeholder}
        autoFocus={autoFocus}
      />
      {local && (
        <button
          type="button"
          className={styles.clear}
          onClick={() => {
            setLocal('');
            onChange('');
          }}
          aria-label="清除搜索"
        >
          <X size={14} />
        </button>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add components/ui/SearchInput.tsx components/ui/SearchInput.module.css
git commit -m "feat: add SearchInput UI component with CSS Module"
```

---

### Task 11: SegmentedControl Component

**Files:**
- Create: `components/ui/SegmentedControl.tsx`
- Create: `components/ui/SegmentedControl.module.css`

- [ ] **Step 1: Create the SegmentedControl CSS Module**

```css
/* components/ui/SegmentedControl.module.css */
.control {
  display: inline-flex;
  padding: 4px;
  border-radius: 10px;
  background: #e7e6ee;
  gap: 2px;
}

.option {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-height: 34px;
  padding: 0 14px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: var(--muted);
  font-size: 13px;
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
  transition: color 0.2s ease, background 0.2s ease;
  white-space: nowrap;
}

.option:hover:not(.active) {
  color: var(--text);
}

.option.active {
  background: white;
  color: var(--text);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}
```

- [ ] **Step 2: Create the SegmentedControl component**

```tsx
// components/ui/SegmentedControl.tsx
'use client';

import React from 'react';
import styles from './SegmentedControl.module.css';

export interface SegmentedOption<T extends string> {
  value: T;
  label: string;
  icon?: React.ReactNode;
}

export interface SegmentedControlProps<T extends string> {
  options: SegmentedOption<T>[];
  value: T;
  onChange: (value: T) => void;
  className?: string;
}

export function SegmentedControl<T extends string>({
  options,
  value,
  onChange,
  className,
}: SegmentedControlProps<T>) {
  return (
    <div className={`${styles.control} ${className ?? ''}`} role="tablist">
      {options.map((opt) => (
        <button
          key={opt.value}
          type="button"
          role="tab"
          aria-selected={opt.value === value}
          className={`${styles.option} ${opt.value === value ? styles.active : ''}`}
          onClick={() => onChange(opt.value)}
        >
          {opt.icon}
          {opt.label}
        </button>
      ))}
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add components/ui/SegmentedControl.tsx components/ui/SegmentedControl.module.css
git commit -m "feat: add SegmentedControl UI component with CSS Module"
```

---

## Phase 3: Saved Plans Page

### Task 12: PlanCard Component

**Files:**
- Create: `components/saved/PlanCard.tsx`
- Create: `components/saved/PlanCard.module.css`

- [ ] **Step 1: Create the PlanCard CSS Module**

```css
/* components/saved/PlanCard.module.css */
.card {
  background: var(--panel);
  border: 1.5px solid var(--line);
  border-radius: 16px;
  padding: 16px;
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
  animation: card-slide-in 0.4s cubic-bezier(0.34, 1.56, 0.64, 1) both;
  animation-delay: calc(var(--index, 0) * 60ms);
}

.card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}

.card.selected {
  border-color: var(--blue);
  background: var(--blue-soft);
}

.card.removing {
  opacity: 0;
  transform: scale(0.95);
  max-height: 0;
  padding: 0;
  margin: 0;
  overflow: hidden;
  transition: all 0.3s ease;
}

.header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}

.title {
  font-size: 15px;
  font-weight: 700;
  color: var(--text);
  margin: 0;
  line-height: 1.3;
}

.summary {
  font-size: 13px;
  color: var(--muted);
  margin: 0 0 10px;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  font-size: 12px;
  color: var(--subtle);
  margin-bottom: 10px;
}

.metaItem {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.tag {
  padding: 2px 8px;
  background: var(--surface-2);
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
  color: var(--muted);
}

.footer {
  display: flex;
  gap: 8px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--line);
}

.footer button {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  border: none;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease;
}

.editBtn {
  background: var(--surface-2);
  color: var(--muted);
}

.editBtn:hover {
  background: var(--line);
  color: var(--text);
}

.executeBtn {
  background: var(--blue-soft);
  color: var(--blue);
}

.executeBtn:hover {
  background: var(--blue);
  color: white;
}

.deleteBtn {
  background: transparent;
  color: var(--subtle);
  margin-left: auto;
}

.deleteBtn:hover {
  background: rgba(221, 75, 75, 0.08);
  color: var(--danger);
}
```

- [ ] **Step 2: Create the PlanCard component**

```tsx
// components/saved/PlanCard.tsx
'use client';

import React, { useState } from 'react';
import { Calendar, MapPin, Edit3, Play, Trash2 } from 'lucide-react';
import { Badge } from '../ui/Badge';
import type { PlanSummary } from '../../types/api';
import styles from './PlanCard.module.css';

const STATUS_BADGE: Record<PlanSummary['status'], { variant: 'info' | 'success' | 'default' | 'warning'; label: string }> = {
  draft: { variant: 'default', label: '草稿' },
  saved: { variant: 'info', label: '已保存' },
  executing: { variant: 'warning', label: '执行中' },
  completed: { variant: 'success', label: '已完成' },
};

export interface PlanCardProps {
  plan: PlanSummary;
  index: number;
  selected: boolean;
  onSelect: () => void;
  onEdit: () => void;
  onExecute: () => void;
  onDelete: () => void;
}

export function PlanCard({ plan, index, selected, onSelect, onEdit, onExecute, onDelete }: PlanCardProps) {
  const [removing, setRemoving] = useState(false);
  const status = STATUS_BADGE[plan.status];

  function handleDelete() {
    setRemoving(true);
    setTimeout(onDelete, 300);
  }

  return (
    <article
      className={`${styles.card} ${selected ? styles.selected : ''} ${removing ? styles.removing : ''}`}
      style={{ '--index': index } as React.CSSProperties}
      onClick={onSelect}
      data-testid={`plan-card-${plan.id}`}
    >
      <div className={styles.header}>
        <h3 className={styles.title}>{plan.title}</h3>
        <Badge variant={status.variant}>{status.label}</Badge>
      </div>
      <p className={styles.summary}>{plan.summary}</p>
      <div className={styles.meta}>
        {plan.location && (
          <span className={styles.metaItem}>
            <MapPin size={12} /> {plan.location}
          </span>
        )}
        {plan.estimated_cost && (
          <span className={styles.metaItem}>
            <Calendar size={12} /> {plan.estimated_cost}
          </span>
        )}
        <span className={styles.metaItem}>{plan.itinerary_count} 个行程</span>
      </div>
      <div className={styles.tags}>
        {plan.tags.map((tag) => (
          <span key={tag} className={styles.tag}>{tag}</span>
        ))}
      </div>
      <div className={styles.footer}>
        <button type="button" className={styles.editBtn} onClick={(e) => { e.stopPropagation(); onEdit(); }}>
          <Edit3 size={14} /> 编辑
        </button>
        <button type="button" className={styles.executeBtn} onClick={(e) => { e.stopPropagation(); onExecute(); }}>
          <Play size={14} /> 执行
        </button>
        <button type="button" className={styles.deleteBtn} onClick={(e) => { e.stopPropagation(); handleDelete(); }} data-testid={`plan-delete-${plan.id}`}>
          <Trash2 size={14} />
        </button>
      </div>
    </article>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add components/saved/PlanCard.tsx components/saved/PlanCard.module.css
git commit -m "feat: add PlanCard component with animations"
```

---

### Task 13: PlanDetailPanel Component

**Files:**
- Create: `components/saved/PlanDetailPanel.tsx`
- Create: `components/saved/PlanDetailPanel.module.css`

- [ ] **Step 1: Create the PlanDetailPanel CSS Module**

```css
/* components/saved/PlanDetailPanel.module.css */
.overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.3);
  z-index: 100;
  animation: fade-in 0.2s ease;
}

@keyframes fade-in {
  from { opacity: 0; }
  to { opacity: 1; }
}

.panel {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  max-height: 80vh;
  background: var(--panel);
  border-radius: 20px 20px 0 0;
  padding: 20px;
  z-index: 101;
  overflow-y: auto;
  animation: slide-up 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}

@keyframes slide-up {
  from { transform: translateY(100%); }
  to { transform: translateY(0); }
}

.handle {
  width: 36px;
  height: 4px;
  background: var(--line-strong);
  border-radius: 2px;
  margin: 0 auto 16px;
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.header h2 {
  font-size: 18px;
  font-weight: 700;
  margin: 0;
}

.closeBtn {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  border: none;
  background: var(--surface-2);
  border-radius: 50%;
  color: var(--muted);
  cursor: pointer;
  transition: background 0.15s ease;
}

.closeBtn:hover {
  background: var(--line);
  color: var(--text);
}

.section {
  margin-bottom: 16px;
}

.sectionLabel {
  font-size: 12px;
  font-weight: 600;
  color: var(--subtle);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 6px;
}

.sectionValue {
  font-size: 14px;
  color: var(--text);
  line-height: 1.5;
}

.detailGrid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.detailItem {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.detailLabel {
  font-size: 12px;
  color: var(--subtle);
}

.detailValue {
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
}

.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.tag {
  padding: 4px 10px;
  background: var(--surface-2);
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
  color: var(--muted);
}

@media (min-width: 820px) {
  .overlay { display: none; }

  .panel {
    position: sticky;
    top: 0;
    max-height: none;
    border-radius: 16px;
    animation: fade-up 0.3s ease;
    border: 1px solid var(--line);
    box-shadow: var(--shadow-sm);
  }

  .handle { display: none; }
  .closeBtn { display: none; }
}
```

- [ ] **Step 2: Create the PlanDetailPanel component**

```tsx
// components/saved/PlanDetailPanel.tsx
'use client';

import React from 'react';
import { X, MapPin, Calendar, DollarSign, ListChecks } from 'lucide-react';
import { Badge } from '../ui/Badge';
import type { PlanSummary } from '../../types/api';
import styles from './PlanDetailPanel.module.css';

const STATUS_MAP: Record<PlanSummary['status'], { variant: 'info' | 'success' | 'default' | 'warning'; label: string }> = {
  draft: { variant: 'default', label: '草稿' },
  saved: { variant: 'info', label: '已保存' },
  executing: { variant: 'warning', label: '执行中' },
  completed: { variant: 'success', label: '已完成' },
};

export interface PlanDetailPanelProps {
  plan: PlanSummary;
  onClose: () => void;
}

export function PlanDetailPanel({ plan, onClose }: PlanDetailPanelProps) {
  const status = STATUS_MAP[plan.status];
  const created = new Date(plan.created_at).toLocaleDateString('zh-CN', {
    year: 'numeric', month: 'long', day: 'numeric',
  });

  return (
    <>
      <div className={styles.overlay} onClick={onClose} />
      <aside className={styles.panel} data-testid="plan-detail-panel">
        <div className={styles.handle} />
        <div className={styles.header}>
          <h2>{plan.title}</h2>
          <button type="button" className={styles.closeBtn} onClick={onClose} aria-label="关闭">
            <X size={18} />
          </button>
        </div>

        <div className={styles.section}>
          <Badge variant={status.variant} size="md">{status.label}</Badge>
        </div>

        <div className={styles.section}>
          <div className={styles.sectionLabel}>方案摘要</div>
          <p className={styles.sectionValue}>{plan.summary}</p>
        </div>

        <div className={styles.detailGrid}>
          <div className={styles.detailItem}>
            <span className={styles.detailLabel}><MapPin size={12} /> 地点</span>
            <span className={styles.detailValue}>{plan.location ?? '未指定'}</span>
          </div>
          <div className={styles.detailItem}>
            <span className={styles.detailLabel}><DollarSign size={12} /> 预算</span>
            <span className={styles.detailValue}>{plan.estimated_cost ?? '未指定'}</span>
          </div>
          <div className={styles.detailItem}>
            <span className={styles.detailLabel}><ListChecks size={12} /> 行程数</span>
            <span className={styles.detailValue}>{plan.itinerary_count} 个</span>
          </div>
          <div className={styles.detailItem}>
            <span className={styles.detailLabel}><Calendar size={12} /> 创建时间</span>
            <span className={styles.detailValue}>{created}</span>
          </div>
        </div>

        <div className={styles.section}>
          <div className={styles.sectionLabel}>标签</div>
          <div className={styles.tags}>
            {plan.tags.map((tag) => (
              <span key={tag} className={styles.tag}>{tag}</span>
            ))}
          </div>
        </div>
      </aside>
    </>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add components/saved/PlanDetailPanel.tsx components/saved/PlanDetailPanel.module.css
git commit -m "feat: add PlanDetailPanel with mobile bottom sheet and desktop sidebar"
```

---

### Task 14: PlanEditModal Component

**Files:**
- Create: `components/saved/PlanEditModal.tsx`
- Create: `components/saved/PlanEditModal.module.css`

- [ ] **Step 1: Create the PlanEditModal CSS Module**

```css
/* components/saved/PlanEditModal.module.css */
.backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: grid;
  place-items: center;
  z-index: 200;
  animation: fade-in 0.2s ease;
  padding: 20px;
}

@keyframes fade-in {
  from { opacity: 0; }
  to { opacity: 1; }
}

.modal {
  width: 100%;
  max-width: 420px;
  background: var(--panel);
  border-radius: 16px;
  padding: 24px;
  animation: modal-in 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}

@keyframes modal-in {
  from { opacity: 0; transform: scale(0.95) translateY(8px); }
  to { opacity: 1; transform: scale(1) translateY(0); }
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
}

.header h2 {
  font-size: 17px;
  font-weight: 700;
  margin: 0;
}

.closeBtn {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  border: none;
  background: var(--surface-2);
  border-radius: 50%;
  color: var(--muted);
  cursor: pointer;
  transition: background 0.15s ease;
}

.closeBtn:hover {
  background: var(--line);
}

.field {
  margin-bottom: 16px;
}

.field label {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: var(--muted);
  margin-bottom: 6px;
}

.field input {
  width: 100%;
  height: 40px;
  padding: 0 12px;
  background: var(--surface-2);
  border: 1.5px solid transparent;
  border-radius: 10px;
  font-size: 14px;
  color: var(--text);
  font-family: inherit;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
  box-sizing: border-box;
}

.field input:focus {
  outline: none;
  border-color: var(--blue);
  box-shadow: 0 0 0 3px rgba(11, 119, 255, 0.1);
  background: var(--panel);
}

.tagInput {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 8px;
  background: var(--surface-2);
  border: 1.5px solid transparent;
  border-radius: 10px;
  min-height: 40px;
  transition: border-color 0.2s ease;
}

.tagInput:focus-within {
  border-color: var(--blue);
  background: var(--panel);
}

.tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  background: var(--blue-soft);
  color: var(--blue);
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
}

.tag button {
  display: grid;
  place-items: center;
  width: 14px;
  height: 14px;
  border: none;
  background: transparent;
  color: var(--blue);
  cursor: pointer;
  padding: 0;
}

.tagInput input {
  flex: 1;
  min-width: 80px;
  border: none;
  background: transparent;
  font-size: 13px;
  color: var(--text);
  font-family: inherit;
  outline: none;
}

.tagInput input::placeholder {
  color: var(--subtle);
}

.actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  margin-top: 20px;
}

.cancelBtn {
  height: 40px;
  padding: 0 18px;
  background: var(--surface-2);
  border: 1px solid var(--line);
  border-radius: 10px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
  font-family: inherit;
  cursor: pointer;
  transition: background 0.15s ease;
}

.cancelBtn:hover {
  background: var(--line);
}

.saveBtn {
  height: 40px;
  padding: 0 18px;
  background: var(--blue);
  border: none;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 600;
  color: white;
  font-family: inherit;
  cursor: pointer;
  transition: background 0.15s ease, transform 0.15s ease;
}

.saveBtn:hover {
  background: #0458b3;
}

.saveBtn:active {
  transform: scale(0.97);
}

.saveBtn.saved {
  background: var(--green);
  animation: pulse-save 0.6s ease;
}

@keyframes pulse-save {
  0%, 100% { box-shadow: 0 0 0 0 rgba(15, 138, 101, 0.3); }
  50% { box-shadow: 0 0 0 8px rgba(15, 138, 101, 0); }
}
```

- [ ] **Step 2: Create the PlanEditModal component**

```tsx
// components/saved/PlanEditModal.tsx
'use client';

import React, { useState, useRef, useEffect } from 'react';
import { X } from 'lucide-react';
import type { PlanSummary } from '../../types/api';
import styles from './PlanEditModal.module.css';

export interface PlanEditModalProps {
  plan: PlanSummary;
  onSave: (updates: Partial<PlanSummary>) => Promise<void>;
  onClose: () => void;
}

export function PlanEditModal({ plan, onSave, onClose }: PlanEditModalProps) {
  const [title, setTitle] = useState(plan.title);
  const [tags, setTags] = useState<string[]>(plan.tags);
  const [tagInput, setTagInput] = useState('');
  const [saved, setSaved] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  function addTag() {
    const tag = tagInput.trim();
    if (tag && !tags.includes(tag)) {
      setTags([...tags, tag]);
    }
    setTagInput('');
  }

  function removeTag(tag: string) {
    setTags(tags.filter((t) => t !== tag));
  }

  async function handleSave() {
    await onSave({ title, tags });
    setSaved(true);
    setTimeout(() => onClose(), 600);
  }

  return (
    <div className={styles.backdrop} onClick={onClose} data-testid="plan-edit-modal">
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div className={styles.header}>
          <h2>编辑计划</h2>
          <button type="button" className={styles.closeBtn} onClick={onClose} aria-label="关闭">
            <X size={18} />
          </button>
        </div>

        <div className={styles.field}>
          <label htmlFor="plan-title">标题</label>
          <input
            ref={inputRef}
            id="plan-title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
        </div>

        <div className={styles.field}>
          <label>标签</label>
          <div className={styles.tagInput}>
            {tags.map((tag) => (
              <span key={tag} className={styles.tag}>
                {tag}
                <button type="button" onClick={() => removeTag(tag)} aria-label={`移除 ${tag}`}>
                  <X size={10} />
                </button>
              </span>
            ))}
            <input
              value={tagInput}
              onChange={(e) => setTagInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') { e.preventDefault(); addTag(); }
                if (e.key === 'Backspace' && !tagInput && tags.length) removeTag(tags[tags.length - 1]);
              }}
              placeholder={tags.length ? '' : '输入标签后回车'}
            />
          </div>
        </div>

        <div className={styles.actions}>
          <button type="button" className={styles.cancelBtn} onClick={onClose}>取消</button>
          <button
            type="button"
            className={`${styles.saveBtn} ${saved ? styles.saved : ''}`}
            onClick={handleSave}
            disabled={!title.trim()}
          >
            {saved ? '已保存' : '保存'}
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add components/saved/PlanEditModal.tsx components/saved/PlanEditModal.module.css
git commit -m "feat: add PlanEditModal with tag editing and save animation"
```

---

### Task 15: SavedPlansView (Main Page)

**Files:**
- Create: `components/saved/SavedPlansView.tsx`
- Create: `components/saved/SavedPlansView.module.css`
- Create: `components/saved/EmptyPlans.tsx`

- [ ] **Step 1: Create the EmptyPlans component**

```tsx
// components/saved/EmptyPlans.tsx
'use client';

import React from 'react';
import { Calendar } from 'lucide-react';
import { EmptyState } from '../ui/EmptyState';

export interface EmptyPlansProps {
  onNavigateHome: () => void;
}

export function EmptyPlans({ onNavigateHome }: EmptyPlansProps) {
  return (
    <EmptyState
      icon={<Calendar size={28} />}
      title="还没有保存的计划"
      description="去首页创建你的第一个周末计划吧"
      action={{ label: '创建计划', onClick: onNavigateHome }}
    />
  );
}
```

- [ ] **Step 2: Create the SavedPlansView CSS Module**

```css
/* components/saved/SavedPlansView.module.css */
.view {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 16px;
  animation: view-enter 0.4s ease both;
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.title {
  font-size: 22px;
  font-weight: 700;
  color: var(--text);
  margin: 0;
}

.subtitle {
  font-size: 14px;
  color: var(--muted);
  margin: 4px 0 0;
}

.controls {
  display: flex;
  align-items: center;
  gap: 10px;
}

.grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 12px;
  flex: 1;
  min-height: 0;
}

.error {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: rgba(221, 75, 75, 0.06);
  border: 1px solid rgba(221, 75, 75, 0.15);
  border-radius: 10px;
  color: var(--danger);
  font-size: 14px;
  margin-bottom: 12px;
  animation: shake 0.4s ease;
}

.retryBtn {
  margin-left: auto;
  padding: 4px 12px;
  background: var(--danger);
  color: white;
  border: none;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

@media (min-width: 820px) {
  .content {
    display: grid;
    grid-template-columns: 1fr 360px;
    gap: 16px;
    flex: 1;
    min-height: 0;
  }

  .grid {
    overflow-y: auto;
    padding-right: 4px;
  }
}
```

- [ ] **Step 3: Create the SavedPlansView component**

```tsx
// components/saved/SavedPlansView.tsx
'use client';

import React, { useState } from 'react';
import { Calendar, Grid2X2, List, AlertCircle } from 'lucide-react';
import { SegmentedControl } from '../ui/SegmentedControl';
import { SearchInput } from '../ui/SearchInput';
import { Skeleton } from '../ui/Skeleton';
import { usePlans } from '../../features/planner/usePlans';
import { PlanCard } from './PlanCard';
import { PlanDetailPanel } from './PlanDetailPanel';
import { PlanEditModal } from './PlanEditModal';
import { EmptyPlans } from './EmptyPlans';
import type { PlanSummary } from '../../types/api';
import styles from './SavedPlansView.module.css';

const VIEW_OPTIONS = [
  { value: 'grid' as const, label: '网格', icon: <Grid2X2 size={15} /> },
  { value: 'list' as const, label: '列表', icon: <List size={15} /> },
];

export interface SavedPlansViewProps {
  onNavigateHome?: () => void;
}

export function SavedPlansView({ onNavigateHome }: SavedPlansViewProps) {
  const { plans, loading, error, refetch, update, remove } = usePlans();
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [editingPlan, setEditingPlan] = useState<PlanSummary | null>(null);
  const [search, setSearch] = useState('');

  const filtered = plans.filter((p) => {
    if (!search.trim()) return true;
    const q = search.toLowerCase();
    return (
      p.title.toLowerCase().includes(q) ||
      p.summary.toLowerCase().includes(q) ||
      p.tags.some((t) => t.toLowerCase().includes(q))
    );
  });

  const selected = plans.find((p) => p.id === selectedId) ?? null;

  if (loading) {
    return (
      <section className={styles.view}>
        <div className={styles.header}>
          <div>
            <h1 className={styles.title}>我的计划</h1>
            <p className={styles.subtitle}>管理并执行你收藏的周末行程</p>
          </div>
        </div>
        <div className={styles.grid}>
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} variant="rectangular" height={180} />
          ))}
        </div>
      </section>
    );
  }

  return (
    <section className={styles.view}>
      <div className={styles.header}>
        <div>
          <h1 className={styles.title}>我的计划</h1>
          <p className={styles.subtitle}>管理并执行你收藏的周末行程</p>
        </div>
        <div className={styles.controls}>
          <SearchInput value={search} onChange={setSearch} placeholder="搜索计划..." />
          <SegmentedControl options={VIEW_OPTIONS} value={viewMode} onChange={setViewMode} />
        </div>
      </div>

      {error && (
        <div className={styles.error}>
          <AlertCircle size={16} />
          {error}
          <button type="button" className={styles.retryBtn} onClick={refetch}>重试</button>
        </div>
      )}

      {filtered.length === 0 && !error ? (
        <EmptyPlans onNavigateHome={onNavigateHome ?? (() => {})} />
      ) : (
        <div className={styles.content}>
          <div className={styles.grid}>
            {filtered.map((plan, i) => (
              <PlanCard
                key={plan.id}
                plan={plan}
                index={i}
                selected={plan.id === selectedId}
                onSelect={() => setSelectedId(plan.id)}
                onEdit={() => setEditingPlan(plan)}
                onExecute={() => onNavigateHome?.()}
                onDelete={() => remove(plan.id)}
              />
            ))}
          </div>
          {selected && (
            <PlanDetailPanel
              plan={selected}
              onClose={() => setSelectedId(null)}
            />
          )}
        </div>
      )}

      {editingPlan && (
        <PlanEditModal
          plan={editingPlan}
          onSave={(updates) => update(editingPlan.id, updates)}
          onClose={() => setEditingPlan(null)}
        />
      )}
    </section>
  );
}
```

- [ ] **Step 4: Commit**

```bash
git add components/saved/SavedPlansView.tsx components/saved/SavedPlansView.module.css components/saved/EmptyPlans.tsx
git commit -m "feat: add SavedPlansView page with search, view toggle, and detail panel"
```

---

## Phase 4: Activity Page

### Task 16: ActivityStats Component

**Files:**
- Create: `components/activity/ActivityStats.tsx`
- Create: `components/activity/ActivityStats.module.css`

- [ ] **Step 1: Create the ActivityStats CSS Module**

```css
/* components/activity/ActivityStats.module.css */
.stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  margin-bottom: 16px;
}

.card {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 14px;
  animation: card-slide-in 0.4s cubic-bezier(0.34, 1.56, 0.64, 1) both;
  animation-delay: calc(var(--index, 0) * 100ms);
}

.icon {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  margin-bottom: 8px;
}

.iconBlue { background: var(--blue-soft); color: var(--blue); }
.iconGreen { background: var(--green-soft); color: var(--green); }
.iconCoral { background: var(--coral-soft); color: var(--coral); }

.label {
  font-size: 12px;
  color: var(--subtle);
  margin-bottom: 2px;
}

.value {
  font-size: 18px;
  font-weight: 700;
  color: var(--text);
}

@media (max-width: 480px) {
  .stats {
    grid-template-columns: 1fr;
  }
}
```

- [ ] **Step 2: Create the ActivityStats component**

```tsx
// components/activity/ActivityStats.tsx
'use client';

import React from 'react';
import { BarChart3, DollarSign, Utensils } from 'lucide-react';
import type { ActivityStats as StatsType } from '../../types/api';
import styles from './ActivityStats.module.css';

export interface ActivityStatsProps {
  stats: StatsType;
}

export function ActivityStats({ stats }: ActivityStatsProps) {
  return (
    <div className={styles.stats}>
      <div className={styles.card} style={{ '--index': 0 } as React.CSSProperties}>
        <div className={`${styles.icon} ${styles.iconBlue}`}><BarChart3 size={16} /></div>
        <div className={styles.label}>已执行计划</div>
        <div className={styles.value}>{stats.total_plans}</div>
      </div>
      <div className={styles.card} style={{ '--index': 1 } as React.CSSProperties}>
        <div className={`${styles.icon} ${styles.iconGreen}`}><DollarSign size={16} /></div>
        <div className={styles.label}>总支出</div>
        <div className={styles.value}>约 {stats.total_cost.toLocaleString()} 元</div>
      </div>
      <div className={styles.card} style={{ '--index': 2 } as React.CSSProperties}>
        <div className={`${styles.icon} ${styles.iconCoral}`}><Utensils size={16} /></div>
        <div className={styles.label}>高频类型</div>
        <div className={styles.value}>{stats.frequent_type}</div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add components/activity/ActivityStats.tsx components/activity/ActivityStats.module.css
git commit -m "feat: add ActivityStats component with stagger animation"
```

---

### Task 17: ActivityItem Component

**Files:**
- Create: `components/activity/ActivityItem.tsx`
- Create: `components/activity/ActivityItem.module.css`

- [ ] **Step 1: Create the ActivityItem CSS Module**

```css
/* components/activity/ActivityItem.module.css */
.item {
  display: flex;
  gap: 12px;
  animation: card-slide-in 0.4s cubic-bezier(0.34, 1.56, 0.64, 1) both;
  animation-delay: calc(var(--index, 0) * 60ms);
}

.timeline {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex-shrink: 0;
}

.dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--line-strong);
  flex-shrink: 0;
  margin-top: 6px;
}

.dotActive {
  background: var(--blue);
  box-shadow: 0 0 0 3px var(--blue-soft);
}

.line {
  width: 2px;
  flex: 1;
  background: var(--line);
  min-height: 20px;
}

.body {
  flex: 1;
  min-width: 0;
  padding-bottom: 16px;
}

.meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--subtle);
  margin-bottom: 4px;
}

.statusBadge {
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
}

.statusCompleted {
  background: var(--green-soft);
  color: var(--green);
}

.statusFailed {
  background: rgba(221, 75, 75, 0.1);
  color: var(--danger);
}

.title {
  font-size: 15px;
  font-weight: 700;
  color: var(--text);
  margin: 0 0 4px;
}

.summary {
  font-size: 13px;
  color: var(--muted);
  margin: 0 0 8px;
  line-height: 1.4;
}

.cost {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
  margin-bottom: 8px;
}

.receiptToggle {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  background: var(--surface-2);
  border: none;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
  color: var(--muted);
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease;
}

.receiptToggle:hover {
  background: var(--line);
  color: var(--text);
}

.receipts {
  margin-top: 8px;
  padding: 10px;
  background: var(--surface);
  border-radius: 10px;
  border: 1px solid var(--line);
  animation: fade-up 0.2s ease;
}

.receiptItem {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
  font-size: 13px;
  color: var(--text);
}

.receiptItem + .receiptItem {
  border-top: 1px solid var(--line);
}

.receiptIcon {
  color: var(--green);
  flex-shrink: 0;
}
```

- [ ] **Step 2: Create the ActivityItem component**

```tsx
// components/activity/ActivityItem.tsx
'use client';

import React, { useState } from 'react';
import { CheckCircle2, ReceiptText, ChevronDown, ChevronUp } from 'lucide-react';
import type { ActivityRecord } from '../../types/api';
import styles from './ActivityItem.module.css';

export interface ActivityItemProps {
  activity: ActivityRecord;
  index: number;
  isLast: boolean;
}

export function ActivityItem({ activity, index, isLast }: ActivityItemProps) {
  const [showReceipts, setShowReceipts] = useState(false);
  const date = new Date(activity.executed_at).toLocaleDateString('zh-CN', {
    month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit',
  });

  return (
    <div className={styles.item} style={{ '--index': index } as React.CSSProperties}>
      <div className={styles.timeline}>
        <div className={`${styles.dot} ${index === 0 ? styles.dotActive : ''}`} />
        {!isLast && <div className={styles.line} />}
      </div>
      <div className={styles.body}>
        <div className={styles.meta}>
          <span>{date}</span>
          <span className={`${styles.statusBadge} ${activity.status === 'completed' ? styles.statusCompleted : styles.statusFailed}`}>
            {activity.status === 'completed' ? '已完成' : '失败'}
          </span>
        </div>
        <h3 className={styles.title}>{activity.plan_title}</h3>
        <p className={styles.summary}>{activity.summary}</p>
        {activity.total_cost && (
          <div className={styles.cost}>
            <ReceiptText size={14} /> {activity.total_cost}
          </div>
        )}
        {activity.receipts.length > 0 && (
          <>
            <button
              type="button"
              className={styles.receiptToggle}
              onClick={() => setShowReceipts(!showReceipts)}
            >
              <ReceiptText size={14} />
              {showReceipts ? '收起回执' : `查看回执（${activity.receipts.length}）`}
              {showReceipts ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            </button>
            {showReceipts && (
              <div className={styles.receipts}>
                {activity.receipts.map((r) => (
                  <div key={r.id} className={styles.receiptItem}>
                    <CheckCircle2 size={14} className={styles.receiptIcon} />
                    {r.detail}
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add components/activity/ActivityItem.tsx components/activity/ActivityItem.module.css
git commit -m "feat: add ActivityItem with timeline and expandable receipts"
```

---

### Task 18: ActivityView (Main Page)

**Files:**
- Create: `components/activity/ActivityView.tsx`
- Create: `components/activity/ActivityView.module.css`

- [ ] **Step 1: Create the ActivityView CSS Module**

```css
/* components/activity/ActivityView.module.css */
.view {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 16px;
  animation: view-enter 0.4s ease both;
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.title {
  font-size: 22px;
  font-weight: 700;
  color: var(--text);
  margin: 0;
}

.controls {
  display: flex;
  align-items: center;
  gap: 8px;
}

.filterChips {
  display: flex;
  gap: 6px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.chip {
  padding: 6px 14px;
  background: var(--surface-2);
  border: 1.5px solid transparent;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 600;
  color: var(--muted);
  cursor: pointer;
  transition: all 0.2s ease;
}

.chip:hover {
  background: var(--line);
  color: var(--text);
}

.chipActive {
  background: var(--blue-soft);
  border-color: var(--blue);
  color: var(--blue);
}

.timeline {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
}

.error {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: rgba(221, 75, 75, 0.06);
  border: 1px solid rgba(221, 75, 75, 0.15);
  border-radius: 10px;
  color: var(--danger);
  font-size: 14px;
  margin-bottom: 12px;
  animation: shake 0.4s ease;
}

.retryBtn {
  margin-left: auto;
  padding: 4px 12px;
  background: var(--danger);
  color: white;
  border: none;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

@media (min-width: 820px) {
  .content {
    display: grid;
    grid-template-columns: 1fr 280px;
    gap: 16px;
    flex: 1;
    min-height: 0;
  }

  .sidebar {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
}
```

- [ ] **Step 2: Create the ActivityView component**

```tsx
// components/activity/ActivityView.tsx
'use client';

import React, { useState, useMemo } from 'react';
import { AlertCircle } from 'lucide-react';
import { SearchInput } from '../ui/SearchInput';
import { Skeleton } from '../ui/Skeleton';
import { EmptyState } from '../ui/EmptyState';
import { useActivities } from '../../features/planner/useActivities';
import { ActivityStats } from './ActivityStats';
import { ActivityItem } from './ActivityItem';
import { ReceiptText } from 'lucide-react';
import type { ActivityRecord } from '../../types/api';
import styles from './ActivityView.module.css';

type Filter = 'all' | 'completed' | 'failed';

const FILTER_OPTIONS: { value: Filter; label: string }[] = [
  { value: 'all', label: '全部' },
  { value: 'completed', label: '已完成' },
  { value: 'failed', label: '失败' },
];

export function ActivityView() {
  const { activities, stats, loading, error, refetch } = useActivities();
  const [filter, setFilter] = useState<Filter>('all');
  const [search, setSearch] = useState('');

  const filtered = useMemo(() => {
    let result = activities;
    if (filter !== 'all') {
      result = result.filter((a) => a.status === filter);
    }
    if (search.trim()) {
      const q = search.toLowerCase();
      result = result.filter(
        (a) =>
          a.plan_title.toLowerCase().includes(q) ||
          a.summary.toLowerCase().includes(q) ||
          a.receipts.some((r) => r.detail.toLowerCase().includes(q)),
      );
    }
    return result;
  }, [activities, filter, search]);

  if (loading) {
    return (
      <section className={styles.view}>
        <h1 className={styles.title}>执行记录</h1>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10, marginBottom: 16 }}>
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} variant="rectangular" height={80} />
          ))}
        </div>
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} variant="rectangular" height={100} style={{ marginBottom: 8 }} />
        ))}
      </section>
    );
  }

  return (
    <section className={styles.view}>
      <div className={styles.header}>
        <h1 className={styles.title}>执行记录</h1>
        <div className={styles.controls}>
          <SearchInput value={search} onChange={setSearch} placeholder="搜索记录..." />
        </div>
      </div>

      {error && (
        <div className={styles.error}>
          <AlertCircle size={16} />
          {error}
          <button type="button" className={styles.retryBtn} onClick={refetch}>重试</button>
        </div>
      )}

      {stats && <ActivityStats stats={stats} />}

      <div className={styles.filterChips}>
        {FILTER_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            type="button"
            className={`${styles.chip} ${filter === opt.value ? styles.chipActive : ''}`}
            onClick={() => setFilter(opt.value)}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {filtered.length === 0 && !error ? (
        <EmptyState
          icon={<ReceiptText size={28} />}
          title="还没有执行记录"
          description="执行你的第一个计划后，记录会显示在这里"
        />
      ) : (
        <div className={styles.content}>
          <div className={styles.timeline}>
            {filtered.map((activity, i) => (
              <ActivityItem
                key={activity.id}
                activity={activity}
                index={i}
                isLast={i === filtered.length - 1}
              />
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add components/activity/ActivityView.tsx components/activity/ActivityView.module.css
git commit -m "feat: add ActivityView page with stats, filters, and search"
```

---

## Phase 5: Settings Page

### Task 19: Settings Sections

**Files:**
- Create: `components/settings/ProfileSection.tsx`
- Create: `components/settings/DietSection.tsx`
- Create: `components/settings/LocationSection.tsx`
- Create: `components/settings/NotificationSection.tsx`
- Create: `components/settings/SettingsView.module.css`

- [ ] **Step 1: Create the shared SettingsView CSS Module**

```css
/* components/settings/SettingsView.module.css */
.view {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 16px;
  animation: view-enter 0.4s ease both;
}

.title {
  font-size: 22px;
  font-weight: 700;
  color: var(--text);
  margin: 0 0 16px;
}

.layout {
  display: flex;
  flex-direction: column;
  gap: 16px;
  flex: 1;
  min-height: 0;
}

.section {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 16px;
  padding: 20px;
  animation: card-slide-in 0.4s ease both;
}

.sectionTitle {
  font-size: 16px;
  font-weight: 700;
  color: var(--text);
  margin: 0 0 16px;
}

.field {
  margin-bottom: 16px;
}

.field:last-child {
  margin-bottom: 0;
}

.field label {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: var(--muted);
  margin-bottom: 6px;
}

.field input {
  width: 100%;
  height: 40px;
  padding: 0 12px;
  background: var(--surface-2);
  border: 1.5px solid transparent;
  border-radius: 10px;
  font-size: 14px;
  color: var(--text);
  font-family: inherit;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
  box-sizing: border-box;
}

.field input:focus {
  outline: none;
  border-color: var(--blue);
  box-shadow: 0 0 0 3px rgba(11, 119, 255, 0.1);
  background: var(--panel);
}

.preferenceRow {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 0;
}

.preferenceRow + .preferenceRow {
  border-top: 1px solid var(--line);
}

.preferenceText {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.preferenceLabel {
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
}

.preferenceDesc {
  font-size: 13px;
  color: var(--muted);
}

.sliderContainer {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.sliderHeader {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.sliderValue {
  font-size: 16px;
  font-weight: 700;
  color: var(--blue);
}

.slider {
  width: 100%;
  height: 6px;
  appearance: none;
  background: var(--line);
  border-radius: 3px;
  outline: none;
}

.slider::-webkit-slider-thumb {
  appearance: none;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: var(--blue);
  cursor: pointer;
  box-shadow: 0 2px 6px rgba(5, 99, 201, 0.3);
  transition: transform 0.15s ease;
}

.slider::-webkit-slider-thumb:hover {
  transform: scale(1.2);
}

.sliderLabels {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: var(--subtle);
}

.saveIndicator {
  position: fixed;
  bottom: 80px;
  right: 20px;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  background: var(--green);
  color: white;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 600;
  box-shadow: var(--shadow-md);
  animation: save-toast 1.5s ease forwards;
  z-index: 50;
}

@keyframes save-toast {
  0% { opacity: 0; transform: translateY(8px); }
  15% { opacity: 1; transform: translateY(0); }
  85% { opacity: 1; transform: translateY(0); }
  100% { opacity: 0; transform: translateY(-8px); }
}

@media (min-width: 820px) {
  .layout {
    max-width: 640px;
  }

  .saveIndicator {
    bottom: 20px;
  }
}
```

- [ ] **Step 2: Create the ProfileSection component**

```tsx
// components/settings/ProfileSection.tsx
'use client';

import React from 'react';
import { User } from 'lucide-react';
import styles from './SettingsView.module.css';

export interface ProfileSectionProps {
  displayName: string;
  email: string;
  onChange: (field: 'display_name' | 'email', value: string) => void;
}

export function ProfileSection({ displayName, email, onChange }: ProfileSectionProps) {
  return (
    <div className={styles.section}>
      <h2 className={styles.sectionTitle}><User size={18} /> 用户资料</h2>
      <div className={styles.field}>
        <label htmlFor="display-name">显示名称</label>
        <input
          id="display-name"
          value={displayName}
          onChange={(e) => onChange('display_name', e.target.value)}
        />
      </div>
      <div className={styles.field}>
        <label htmlFor="email">邮箱</label>
        <input
          id="email"
          type="email"
          value={email}
          onChange={(e) => onChange('email', e.target.value)}
        />
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Create the DietSection component**

```tsx
// components/settings/DietSection.tsx
'use client';

import React from 'react';
import { Utensils } from 'lucide-react';
import { Toggle } from '../ui/Toggle';
import styles from './SettingsView.module.css';

export interface DietSectionProps {
  fitnessFriendly: boolean;
  vegetarian: boolean;
  glutenFree: boolean;
  onToggle: (key: 'fitness_friendly' | 'vegetarian' | 'gluten_free') => void;
}

export function DietSection({ fitnessFriendly, vegetarian, glutenFree, onToggle }: DietSectionProps) {
  return (
    <div className={styles.section}>
      <h2 className={styles.sectionTitle}><Utensils size={18} /> 饮食偏好</h2>
      <Toggle
        checked={fitnessFriendly}
        onChange={() => onToggle('fitness_friendly')}
        label="减脂友好"
        description="优先推荐低热量、高蛋白的餐厅选项"
        testId="pref-fitness"
      />
      <Toggle
        checked={vegetarian}
        onChange={() => onToggle('vegetarian')}
        label="素食"
        testId="pref-vegetarian"
      />
      <Toggle
        checked={glutenFree}
        onChange={() => onToggle('gluten_free')}
        label="无麸质"
        testId="pref-gluten-free"
      />
    </div>
  );
}
```

- [ ] **Step 4: Create the LocationSection component**

```tsx
// components/settings/LocationSection.tsx
'use client';

import React from 'react';
import { MapPin } from 'lucide-react';
import styles from './SettingsView.module.css';

export interface LocationSectionProps {
  radiusKm: number;
  onChange: (radius: number) => void;
}

export function LocationSection({ radiusKm, onChange }: LocationSectionProps) {
  return (
    <div className={styles.section}>
      <h2 className={styles.sectionTitle}><MapPin size={18} /> 位置偏好</h2>
      <div className={styles.sliderContainer}>
        <div className={styles.sliderHeader}>
          <span className={styles.preferenceLabel}>活动半径</span>
          <span className={styles.sliderValue}>{radiusKm} 公里</span>
        </div>
        <input
          type="range"
          className={styles.slider}
          min={1}
          max={10}
          value={radiusKm}
          onChange={(e) => onChange(Number(e.target.value))}
          aria-label="活动半径"
          data-testid="radius-slider"
        />
        <div className={styles.sliderLabels}>
          <span>1 公里</span>
          <span>10 公里</span>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Create the NotificationSection component**

```tsx
// components/settings/NotificationSection.tsx
'use client';

import React from 'react';
import { Bell } from 'lucide-react';
import { Toggle } from '../ui/Toggle';
import styles from './SettingsView.module.css';

export interface NotificationSectionProps {
  executionReminder: boolean;
  planChange: boolean;
  weeklyDigest: boolean;
  onToggle: (key: 'execution_reminder' | 'plan_change' | 'weekly_digest') => void;
}

export function NotificationSection({ executionReminder, planChange, weeklyDigest, onToggle }: NotificationSectionProps) {
  return (
    <div className={styles.section}>
      <h2 className={styles.sectionTitle}><Bell size={18} /> 通知设置</h2>
      <Toggle
        checked={executionReminder}
        onChange={() => onToggle('execution_reminder')}
        label="执行前提醒"
        description="计划执行前 30 分钟发送提醒"
        testId="notif-execution"
      />
      <Toggle
        checked={planChange}
        onChange={() => onToggle('plan_change')}
        label="计划变更提醒"
        description="计划有更新时通知你"
        testId="notif-change"
      />
      <Toggle
        checked={weeklyDigest}
        onChange={() => onToggle('weekly_digest')}
        label="每周摘要"
        description="每周一发送上周执行总结"
        testId="notif-digest"
      />
    </div>
  );
}
```

- [ ] **Step 6: Commit**

```bash
git add components/settings/ProfileSection.tsx components/settings/DietSection.tsx components/settings/LocationSection.tsx components/settings/NotificationSection.tsx components/settings/SettingsView.module.css
git commit -m "feat: add settings section components with Toggle integration"
```

---

### Task 20: SettingsView (Main Page)

**Files:**
- Create: `components/settings/SettingsView.tsx`

- [ ] **Step 1: Create the SettingsView component**

```tsx
// components/settings/SettingsView.tsx
'use client';

import React, { useCallback } from 'react';
import { CheckCircle2 } from 'lucide-react';
import { SegmentedControl } from '../ui/SegmentedControl';
import { Skeleton } from '../ui/Skeleton';
import { usePreferences } from '../../features/planner/usePreferences';
import { ProfileSection } from './ProfileSection';
import { DietSection } from './DietSection';
import { LocationSection } from './LocationSection';
import { NotificationSection } from './NotificationSection';
import { User, Utensils, MapPin, Bell } from 'lucide-react';
import styles from './SettingsView.module.css';

type SettingsTab = 'profile' | 'diet' | 'location' | 'notifications';

const TAB_OPTIONS = [
  { value: 'profile' as const, label: '用户资料', icon: <User size={15} /> },
  { value: 'diet' as const, label: '饮食偏好', icon: <Utensils size={15} /> },
  { value: 'location' as const, label: '位置偏好', icon: <MapPin size={15} /> },
  { value: 'notifications' as const, label: '通知', icon: <Bell size={15} /> },
];

export function SettingsView() {
  const { preferences, loading, showSaved, update } = usePreferences();
  const [activeTab, setActiveTab] = React.useState<SettingsTab>('profile');

  const handleProfileChange = useCallback(
    (field: 'display_name' | 'email', value: string) => {
      update((prev) => ({
        ...prev,
        profile: { ...prev.profile, [field]: value },
      }));
    },
    [update],
  );

  const handleDietToggle = useCallback(
    (key: 'fitness_friendly' | 'vegetarian' | 'gluten_free') => {
      update((prev) => ({
        ...prev,
        diet: { ...prev.diet, [key]: !prev.diet[key] },
      }));
    },
    [update],
  );

  const handleLocationChange = useCallback(
    (radius: number) => {
      update((prev) => ({
        ...prev,
        location: { ...prev.location, radius_km: radius },
      }));
    },
    [update],
  );

  const handleNotifToggle = useCallback(
    (key: 'execution_reminder' | 'plan_change' | 'weekly_digest') => {
      update((prev) => ({
        ...prev,
        notifications: { ...prev.notifications, [key]: !prev.notifications[key] },
      }));
    },
    [update],
  );

  if (loading) {
    return (
      <section className={styles.view}>
        <h1 className={styles.title}>设置</h1>
        <Skeleton variant="rectangular" height={40} style={{ marginBottom: 16 }} />
        <Skeleton variant="rectangular" height={200} />
      </section>
    );
  }

  return (
    <section className={styles.view}>
      <h1 className={styles.title}>设置</h1>
      <SegmentedControl
        options={TAB_OPTIONS}
        value={activeTab}
        onChange={setActiveTab}
      />
      <div className={styles.layout}>
        {activeTab === 'profile' && (
          <ProfileSection
            displayName={preferences.profile.display_name}
            email={preferences.profile.email}
            onChange={handleProfileChange}
          />
        )}
        {activeTab === 'diet' && (
          <DietSection
            fitnessFriendly={preferences.diet.fitness_friendly}
            vegetarian={preferences.diet.vegetarian}
            glutenFree={preferences.diet.gluten_free}
            onToggle={handleDietToggle}
          />
        )}
        {activeTab === 'location' && (
          <LocationSection
            radiusKm={preferences.location.radius_km}
            onChange={handleLocationChange}
          />
        )}
        {activeTab === 'notifications' && (
          <NotificationSection
            executionReminder={preferences.notifications.execution_reminder}
            planChange={preferences.notifications.plan_change}
            weeklyDigest={preferences.notifications.weekly_digest}
            onToggle={handleNotifToggle}
          />
        )}
      </div>
      {showSaved && (
        <div className={styles.saveIndicator}>
          <CheckCircle2 size={16} /> 已保存
        </div>
      )}
    </section>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add components/settings/SettingsView.tsx
git commit -m "feat: add SettingsView page with tab navigation and auto-save"
```

---

## Phase 6: Integration

### Task 21: Update page.tsx and globals.css

**Files:**
- Modify: `app/page.tsx`
- Modify: `app/globals.css`

- [ ] **Step 1: Update page.tsx to use new components**

Replace the imports in `app/page.tsx`:

```tsx
// Remove these lines:
// import { SavedPlansView } from '@/components/SavedPlansView';
// import { ActivityView } from '@/components/ActivityView';
// import { SettingsView } from '@/components/SettingsView';

// Add these lines:
import { SavedPlansView } from '@/components/saved/SavedPlansView';
import { ActivityView } from '@/components/activity/ActivityView';
import { SettingsView } from '@/components/settings/SettingsView';
```

Also update the SavedPlansView usage to pass `onNavigateHome`:

```tsx
// Change this line:
// {activeTab === 'plans' && <SavedPlansView onPlan={() => handleSubmitGoal('今天下午带孩子出去玩')} />}

// To this:
{activeTab === 'plans' && <SavedPlansView onNavigateHome={handleNewPlan} />}
```

- [ ] **Step 2: Add new keyframe animations to globals.css**

Add these animations at the end of `globals.css` (before the reduced-motion media query):

```css
/* Pages redesign animations */
@keyframes slide-up-panel {
  from { transform: translateY(100%); }
  to { transform: translateY(0); }
}

@keyframes modal-backdrop {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes modal-content {
  from { opacity: 0; transform: scale(0.95) translateY(8px); }
  to { opacity: 1; transform: scale(1) translateY(0); }
}

@keyframes save-pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(15, 138, 101, 0.3); }
  50% { box-shadow: 0 0 0 8px rgba(15, 138, 101, 0); }
}

@keyframes toast-in-out {
  0% { opacity: 0; transform: translateY(8px); }
  15% { opacity: 1; transform: translateY(0); }
  85% { opacity: 1; transform: translateY(0); }
  100% { opacity: 0; transform: translateY(-8px); }
}
```

- [ ] **Step 3: Verify the app builds**

Run: `npm run build`
Expected: Build succeeds with no errors.

- [ ] **Step 4: Commit**

```bash
git add app/page.tsx app/globals.css
git commit -m "feat: integrate redesigned pages and add new animations"
```

---

### Task 22: Delete Old Files and Final Cleanup

**Files:**
- Delete: `components/SavedPlansView.jsx`
- Delete: `components/ActivityView.jsx`
- Delete: `components/SettingsView.jsx`

- [ ] **Step 1: Delete the old JSX files**

```bash
rm components/SavedPlansView.jsx components/ActivityView.jsx components/SettingsView.jsx
```

- [ ] **Step 2: Verify no remaining imports reference the old files**

Run: `grep -r "SavedPlansView.jsx\|ActivityView.jsx\|SettingsView.jsx" --include="*.ts" --include="*.tsx" --include="*.js" --include="*.jsx" .`
Expected: No output (no references found).

- [ ] **Step 3: Run the full build**

Run: `npm run build`
Expected: Build succeeds.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore: remove old JSX page components"
```

---

### Task 23: Verify All Pages Work

- [ ] **Step 1: Start the dev server**

Run: `npm run dev`

- [ ] **Step 2: Test the Saved Plans page**

1. Navigate to the "我的计划" tab
2. Verify skeleton loading appears briefly
3. Verify plan cards appear with stagger animation
4. Click a card → verify detail panel appears
5. Click edit → verify modal opens, edit title/tags, save
6. Click delete → verify card removes with animation
7. Type in search → verify filtering works
8. Toggle grid/list view

- [ ] **Step 3: Test the Activity page**

1. Navigate to the "执行记录" tab
2. Verify stats cards appear with stagger animation
3. Verify timeline items appear
4. Click filter chips → verify filtering works
5. Search for a term → verify filtering works
6. Click "查看回执" → verify receipts expand
7. Click "收起回执" → verify receipts collapse

- [ ] **Step 4: Test the Settings page**

1. Navigate to the "设置" tab
2. Switch between tabs → verify crossfade animation
3. Toggle diet preferences → verify save indicator appears
4. Adjust radius slider → verify value updates
5. Edit profile fields → verify values persist
6. Refresh page → verify preferences load from localStorage

- [ ] **Step 5: Test responsive layout**

1. Resize browser to mobile width (< 820px)
2. Verify single-column layout on all pages
3. Verify bottom sheet behavior for detail panel
4. Resize back to desktop → verify two-column layout

- [ ] **Step 6: Test accessibility**

1. Enable "Reduce motion" in OS settings
2. Verify all animations are disabled
3. Tab through all interactive elements → verify focus styles
