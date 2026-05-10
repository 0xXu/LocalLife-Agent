# Pages Redesign Design Spec

**Date:** 2026-05-10
**Scope:** Redesign three secondary pages (Saved Plans, Activity, Settings) with shared UI component library, CSS Modules, and mock API layer.

---

## 1. Overview

### Problem

The three secondary pages (`SavedPlansView.jsx`, `ActivityView.jsx`, `SettingsView.jsx`) are prototype-quality JSX components with:
- No TypeScript types
- Hardcoded fixture data, no API integration
- Old layout patterns (two-column grid)
- No loading states, error handling, or empty states
- Inconsistent with the polished main planning flow

### Solution

1. Extract shared UI component library (`components/ui/`)
2. Rewrite pages as TypeScript with CSS Modules
3. Create mock API layer with typed interfaces
4. Add rich animations and interaction feedback
5. Design for mobile-first responsive layout

### Approach

**Component Library + CSS Modules** (Option B):
- Extract 8 reusable UI components
- Each component has its own `.module.css` for style isolation
- Global CSS retains shared keyframe animations
- Mock data layer with simulated API delays
- `localStorage` for user preferences persistence

---

## 2. Shared UI Component Library

### Location

`components/ui/`

### Components

#### Button

```typescript
interface ButtonProps {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
  icon?: React.ReactNode;
  loading?: boolean;
  disabled?: boolean;
  children: React.ReactNode;
  onClick?: () => void;
  className?: string;
}
```

- Variants: primary (blue), secondary (outline), danger (red), ghost (transparent)
- Sizes: sm (32px), md (40px), lg (48px)
- Loading state: spinner replaces icon
- Hover: `translateY(-1px)` + shadow增强
- Active: `scale(0.97)` + 涟漪效果

#### Card

```typescript
interface CardProps {
  variant?: 'default' | 'elevated' | 'outlined';
  padding?: 'sm' | 'md' | 'lg';
  interactive?: boolean;
  selected?: boolean;
  children: React.ReactNode;
  onClick?: () => void;
  className?: string;
}
```

- Variants: default (subtle border), elevated (shadow), outlined (strong border)
- Interactive: hover effect with `translateY(-2px)` + shadow
- Selected: blue border + subtle background

#### Toggle

```typescript
interface ToggleProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
  label?: string;
  description?: string;
  testId?: string;
}
```

- Animation: 200ms cubic-bezier slide
- Color: unchecked (gray), checked (blue)
- Label and optional description text

#### Badge

```typescript
interface BadgeProps {
  variant?: 'default' | 'success' | 'warning' | 'error' | 'info';
  size?: 'sm' | 'md';
  children: React.ReactNode;
  className?: string;
}
```

- Variants with appropriate colors
- Used for status indicators and tags

#### EmptyState

```typescript
interface EmptyStateProps {
  icon: React.ReactNode;
  title: string;
  description: string;
  action?: {
    label: string;
    onClick: () => void;
  };
}
```

- Centered layout with icon, title, description
- Optional action button
- Subtle fade-in animation

#### Skeleton

```typescript
interface SkeletonProps {
  variant?: 'text' | 'circular' | 'rectangular';
  width?: string | number;
  height?: string | number;
  count?: number;
}
```

- Shimmer animation (reuse `skeleton-shimmer` keyframe)
- Variants for different content shapes

#### SearchInput

```typescript
interface SearchInputProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  debounceMs?: number;
  onClear?: () => void;
  autoFocus?: boolean;
}
```

- Built-in debounce
- Clear button when value is non-empty
- Search icon prefix

#### SegmentedControl

```typescript
interface SegmentedControlProps<T extends string> {
  options: { value: T; label: string; icon?: React.ReactNode }[];
  value: T;
  onChange: (value: T) => void;
}
```

- Animated sliding indicator
- Support for icons

---

## 3. Page Designs

### 3.1 Saved Plans Page

#### Component Structure

```
SavedPlansView.tsx
├── SegmentedControl (grid/list toggle)
├── SearchInput (filter plans)
├── Skeleton (loading state)
├── EmptyPlans (empty state)
├── PlanCard[] (plan list)
└── PlanDetailPanel (selected plan details)
    └── PlanEditModal (edit plan)
```

#### Layout

**Mobile (< 820px):**
- Single column, full width
- Plan cards in vertical list
- Detail panel slides up from bottom as a sheet
- Edit modal centered with backdrop

**Desktop (>= 820px):**
- Two-column layout: card list (left) + detail panel (right)
- Detail panel is 360px wide, sticky
- Edit modal centered

#### Data Flow

```
usePlans() hook
  → fetchPlans() from mockData.ts
  → returns { plans, loading, error, refetch }
  → PlanCard renders each plan
  → Select plan → PlanDetailPanel shows
  → Edit plan → PlanEditModal opens
  → Save edit → update local state
  → Delete → confirm dialog → remove from list
```

#### Interactions

1. **Page Load:**
   - Show skeleton for 800ms (simulated API delay)
   - Cards fade in with stagger (60ms delay per card)

2. **Card Click:**
   - Card gets selected state (blue border)
   - Detail panel slides in (mobile: bottom sheet, desktop: right panel)

3. **Edit:**
   - Click edit button → modal slides in with backdrop fade
   - Edit title and tags
   - Save → modal closes, card updates with pulse animation
   - Cancel → modal closes

4. **Delete:**
   - Click delete → confirm dialog appears
   - Confirm → card fades out + collapses
   - Cancel → dialog closes

5. **View Toggle:**
   - Grid ↔ List transition with layout animation

#### Animation Specifications

| Element | Animation | Duration | Easing |
|---------|-----------|----------|--------|
| Cards entrance | fade-up + stagger | 400ms + 60ms stagger | cubic-bezier(0.34, 1.56, 0.64, 1) |
| Card hover | translateY(-2px) + shadow | 200ms | ease |
| Card selected | border-color + background | 200ms | ease |
| Detail panel (mobile) | slide-up | 300ms | cubic-bezier(0.34, 1.56, 0.64, 1) |
| Detail panel (desktop) | slide-right | 300ms | ease |
| Modal backdrop | opacity fade | 200ms | ease |
| Modal content | scale(0.95) → 1 + fade | 300ms | cubic-bezier(0.34, 1.56, 0.64, 1) |
| Delete confirm | shake | 400ms | ease |
| Card delete | fade-out + height collapse | 300ms | ease |
| Save success | pulse glow | 600ms | ease |

#### Empty State

When no plans exist:
- Icon: `Calendar` from lucide-react
- Title: "还没有保存的计划"
- Description: "去首页创建你的第一个周末计划吧"
- Action button: "创建计划"

---

### 3.2 Activity Page

#### Component Structure

```
ActivityView.tsx
├── ActivityStats (summary cards)
├── ActivityFilter (filter chips)
├── ActivitySearch (search input)
├── Skeleton (loading state)
├── EmptyActivity (empty state)
├── ActivityTimeline
│   └── ActivityItem[] (activity records)
└── ReceiptDetail (receipt modal)
```

#### Layout

**Mobile (< 820px):**
- Single column
- Stats cards at top (horizontal scroll if needed)
- Filter chips below stats
- Timeline takes full width
- Receipt detail as bottom sheet

**Desktop (>= 820px):**
- Two-column: stats + filters (left sidebar, 280px) + timeline (right)
- Receipt detail as modal or inline expansion

#### Data Flow

```
useActivities() hook
  → fetchActivities() from mockData.ts
  → returns { activities, stats, loading, error, refetch }
  → ActivityStats renders summary
  → ActivityTimeline renders list
  → Filter/search → client-side filtering
  → Click item → ReceiptDetail shows
```

#### Interactions

1. **Page Load:**
   - Stats cards fade in first
   - Timeline items fade in with stagger

2. **Filter:**
   - Click filter chip → toggle active state
   - List updates with fade transition
   - Active chip has blue background + scale bounce

3. **Search:**
   - Input has debounce (300ms)
   - Results filter with fade transition
   - Clear button appears when input has value

4. **Activity Item Click:**
   - Item expands with accordion animation
   - Shows receipt details inline
   - Or opens modal on mobile

5. **Receipt Detail:**
   - Mobile: bottom sheet slides up
   - Desktop: inline expansion with smooth height animation

#### Animation Specifications

| Element | Animation | Duration | Easing |
|---------|-----------|----------|--------|
| Stats cards | fade-up + stagger | 400ms + 100ms stagger | cubic-bezier(0.34, 1.56, 0.64, 1) |
| Timeline items | fade-up + stagger | 400ms + 60ms stagger | cubic-bezier(0.34, 1.56, 0.64, 1) |
| Filter chip active | scale bounce | 300ms | cubic-bezier(0.34, 1.56, 0.64, 1) |
| Item expand | accordion height | 300ms | ease |
| Receipt detail | fade-in | 200ms | ease |
| Search results | fade transition | 200ms | ease |

#### Empty State

When no activities:
- Icon: `ReceiptText` from lucide-react
- Title: "还没有执行记录"
- Description: "执行你的第一个计划后，记录会显示在这里"

#### Stats Cards

Three stat cards in a row:
1. **已执行计划** - count with icon
2. **总支出** - amount in yuan
3. **高频类型** - most frequent activity type

Each card has:
- Icon with colored background
- Label text
- Value with large font
- Subtle gradient background

---

### 3.3 Settings Page

#### Component Structure

```
SettingsView.tsx
├── SegmentedControl (tab navigation)
├── Skeleton (loading state)
├── ProfileSection
│   ├── Avatar display
│   ├── Display name input
│   └── Email input
├── DietSection
│   ├── Toggle: fitness friendly
│   ├── Toggle: vegetarian
│   ├── Toggle: gluten free
│   └── Allergen tags input
├── LocationSection
│   ├── Radius slider
│   ├── Home address input
│   └── Favorite places list
└── NotificationSection
    ├── Toggle: execution reminder
    ├── Toggle: plan change
    └── Toggle: weekly digest
```

#### Layout

**Mobile (< 820px):**
- Single column
- Tab navigation at top (horizontal scroll)
- Content below with padding
- Each section is a card

**Desktop (>= 820px):**
- Tab navigation on left (vertical, 200px)
- Content on right
- Max-width 640px for content area

#### Data Flow

```
usePreferences() hook
  → fetchPreferences() from mockData.ts (loads from localStorage)
  → returns { preferences, loading, error, updatePreference }
  → Each section reads relevant preference
  → Toggle/input change → updatePreference() → save to localStorage
  → SaveIndicator shows "已保存" briefly
```

#### Interactions

1. **Page Load:**
   - Load preferences from localStorage
   - Content fades in

2. **Tab Switch:**
   - Content crossfade animation
   - Active tab indicator slides

3. **Toggle Change:**
   - Toggle slides with spring animation
   - Save indicator appears briefly
   - Background color transitions

4. **Slider Adjust:**
   - Real-time value update
   - Thumb has scale effect on drag
   - Value label follows thumb

5. **Input Edit:**
   - Focus: border color change + subtle glow
   - Blur: auto-save
   - Save indicator shows

#### Animation Specifications

| Element | Animation | Duration | Easing |
|---------|-----------|----------|--------|
| Tab switch | crossfade | 200ms | ease |
| Tab indicator | slide | 200ms | ease |
| Toggle slide | translateX | 200ms | cubic-bezier(0.34, 1.56, 0.64, 1) |
| Toggle color | background-color | 200ms | ease |
| Save indicator | fade-in + fade-out | 1500ms total | ease |
| Input focus | border-color + box-shadow | 200ms | ease |
| Slider thumb | scale(1.2) on drag | 150ms | ease |

#### Save Indicator

A small toast-like element that appears briefly:
- Position: bottom-right of the settings content
- Text: "已保存" with checkmark icon
- Duration: 1.5 seconds
- Animation: fade-in, stay, fade-out

---

## 4. Mock API Layer

### Location

`features/planner/mockData.ts`

### Interfaces

```typescript
// types/api.ts

// Plan List
interface PlanSummary {
  id: string;
  title: string;
  status: 'draft' | 'saved' | 'executing' | 'completed';
  summary: string;
  created_at: string;      // ISO 8601
  updated_at: string;
  tags: string[];
  location?: string;
  estimated_cost?: string;
  itinerary_count: number;
}

interface PlanListResponse {
  plans: PlanSummary[];
  total: number;
}

// Activity History
interface ActivityRecord {
  id: string;
  plan_id: string;
  plan_title: string;
  executed_at: string;
  status: 'completed' | 'failed' | 'partial';
  total_cost?: string;
  receipts: Receipt[];
  summary: string;
}

interface ActivityListResponse {
  activities: ActivityRecord[];
  stats: {
    total_plans: number;
    total_cost: number;
    frequent_type: string;
  };
}

// User Preferences
interface UserPreferences {
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

### Mock Data

```typescript
// features/planner/mockData.ts

const MOCK_PLANS: PlanSummary[] = [
  {
    id: 'plan_001',
    title: '亲子科学馆半日游',
    status: 'saved',
    summary: '带孩子去科学馆，下午茶，公园散步',
    created_at: '2026-05-08T10:00:00Z',
    updated_at: '2026-05-08T10:30:00Z',
    tags: ['家庭', '教育', '半日'],
    location: '市中心 5 公里内',
    estimated_cost: '约 320 元',
    itinerary_count: 4,
  },
  // ... more plans
];

const MOCK_ACTIVITIES: ActivityRecord[] = [
  {
    id: 'activity_001',
    plan_id: 'plan_001',
    plan_title: '雨天手作体验',
    executed_at: '2026-05-09T14:00:00Z',
    status: 'completed',
    total_cost: '约 280 元',
    receipts: [
      { type: 'payment', tool: 'booking', id: 'r_001', status: 'success', detail: '陶艺工坊预约成功' },
    ],
    summary: '陶艺体验 + 咖啡厅',
  },
  // ... more activities
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
```

### API Functions

```typescript
// features/planner/mockData.ts

const delay = (ms: number) => new Promise(r => setTimeout(r, ms));

export async function fetchPlans(): Promise<PlanListResponse> {
  await delay(800);
  const stored = localStorage.getItem('weekendpilot_plans');
  const plans = stored ? JSON.parse(stored) : MOCK_PLANS;
  return { plans, total: plans.length };
}

export async function fetchActivities(): Promise<ActivityListResponse> {
  await delay(600);
  return {
    activities: MOCK_ACTIVITIES,
    stats: {
      total_plans: MOCK_ACTIVITIES.length,
      total_cost: MOCK_ACTIVITIES.reduce((sum, a) => sum + (parseInt(a.total_cost?.replace(/\D/g, '') || '0')), 0),
      frequent_type: '餐饮',
    },
  };
}

export async function fetchPreferences(): Promise<UserPreferences> {
  await delay(400);
  const stored = localStorage.getItem('weekendpilot_preferences');
  return stored ? JSON.parse(stored) : DEFAULT_PREFERENCES;
}

export async function savePreferences(prefs: UserPreferences): Promise<void> {
  await delay(300);
  localStorage.setItem('weekendpilot_preferences', JSON.stringify(prefs));
}

export async function updatePlan(planId: string, updates: Partial<PlanSummary>): Promise<PlanSummary> {
  await delay(500);
  const stored = localStorage.getItem('weekendpilot_plans');
  const plans: PlanSummary[] = stored ? JSON.parse(stored) : MOCK_PLANS;
  const index = plans.findIndex(p => p.id === planId);
  if (index === -1) throw new Error('Plan not found');
  plans[index] = { ...plans[index], ...updates, updated_at: new Date().toISOString() };
  localStorage.setItem('weekendpilot_plans', JSON.stringify(plans));
  return plans[index];
}

export async function deletePlan(planId: string): Promise<void> {
  await delay(400);
  const stored = localStorage.getItem('weekendpilot_plans');
  const plans: PlanSummary[] = stored ? JSON.parse(stored) : MOCK_PLANS;
  const filtered = plans.filter(p => p.id !== planId);
  localStorage.setItem('weekendpilot_plans', JSON.stringify(filtered));
}
```

### Custom Hooks

```typescript
// features/planner/usePlans.ts
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

  useEffect(() => { load(); }, [load]);

  return { plans, loading, error, refetch: load, setPlans };
}

// features/planner/useActivities.ts
export function useActivities() {
  // Similar pattern
}

// features/planner/usePreferences.ts
export function usePreferences() {
  const [preferences, setPreferences] = useState<UserPreferences>(DEFAULT_PREFERENCES);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchPreferences().then(p => {
      setPreferences(p);
      setLoading(false);
    });
  }, []);

  const updatePreference = useCallback(async (path: string, value: any) => {
    setSaving(true);
    const updated = { ...preferences }; // deep merge at path
    setPreferences(updated);
    await savePreferences(updated);
    setSaving(false);
  }, [preferences]);

  return { preferences, loading, saving, updatePreference };
}
```

---

## 5. CSS Architecture

### Global CSS Retained

Keep in `globals.css`:
- CSS custom properties (design tokens)
- Shared keyframe animations
- Base resets and typography
- Layout components (AppShell, BottomNav, DesktopSidebar)
- Reduced motion media query

### CSS Modules

Each component has its own `.module.css` file:
```css
/* PlanCard.module.css */
.card {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 16px;
  padding: 16px;
  animation: fade-up 0.4s cubic-bezier(0.34, 1.56, 0.64, 1) both;
  animation-delay: calc(var(--index) * 60ms);
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
}

.card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}

.card.selected {
  border-color: var(--blue);
  background: var(--blue-soft);
}
```

### Shared Styles Module

For common patterns used across multiple components:
```css
/* styles/shared.module.css */
.cardBase {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 16px;
  padding: 16px;
}

.sectionTitle {
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
  margin-bottom: 12px;
}
```

---

## 6. File Structure

```
components/
├── ui/
│   ├── Button.tsx
│   ├── Button.module.css
│   ├── Card.tsx
│   ├── Card.module.css
│   ├── Toggle.tsx
│   ├── Toggle.module.css
│   ├── Badge.tsx
│   ├── Badge.module.css
│   ├── EmptyState.tsx
│   ├── EmptyState.module.css
│   ├── Skeleton.tsx
│   ├── Skeleton.module.css
│   ├── SearchInput.tsx
│   ├── SearchInput.module.css
│   ├── SegmentedControl.tsx
│   └── SegmentedControl.module.css
├── saved/
│   ├── SavedPlansView.tsx
│   ├── SavedPlansView.module.css
│   ├── PlanCard.tsx
│   ├── PlanCard.module.css
│   ├── PlanDetailPanel.tsx
│   ├── PlanDetailPanel.module.css
│   ├── PlanEditModal.tsx
│   ├── PlanEditModal.module.css
│   └── EmptyPlans.tsx
├── activity/
│   ├── ActivityView.tsx
│   ├── ActivityView.module.css
│   ├── ActivityTimeline.tsx
│   ├── ActivityTimeline.module.css
│   ├── ActivityItem.tsx
│   ├── ActivityItem.module.css
│   ├── ActivityStats.tsx
│   ├── ActivityStats.module.css
│   ├── ReceiptDetail.tsx
│   ├── ReceiptDetail.module.css
│   ├── ActivityFilter.tsx
│   └── ActivitySearch.tsx
├── settings/
│   ├── SettingsView.tsx
│   ├── SettingsView.module.css
│   ├── ProfileSection.tsx
│   ├── ProfileSection.module.css
│   ├── DietSection.tsx
│   ├── DietSection.module.css
│   ├── LocationSection.tsx
│   ├── LocationSection.module.css
│   ├── NotificationSection.tsx
│   └── NotificationSection.module.css
└── layout/
    ├── AppShell.tsx (unchanged)
    ├── BottomNav.tsx (unchanged)
    └── DesktopSidebar.tsx (unchanged)

features/planner/
├── apiClient.ts (existing, unchanged)
├── mockData.ts (new)
├── types.ts (new)
├── usePlans.ts (new)
├── useActivities.ts (new)
└── usePreferences.ts (new)

app/
├── page.tsx (update imports)
└── globals.css (add new keyframes)

types/
├── views.ts (unchanged)
└── api.ts (new)

components/
├── SavedPlansView.jsx (to be deleted)
├── ActivityView.jsx (to be deleted)
└── SettingsView.jsx (to be deleted)
```

---

## 7. Implementation Order

### Phase 1: Foundation
1. Create `types/api.ts` with all interfaces
2. Create `features/planner/mockData.ts` with mock data and API functions
3. Create `features/planner/usePlans.ts`, `useActivities.ts`, `usePreferences.ts` hooks

### Phase 2: UI Components
4. Create `components/ui/Button.tsx` + CSS Module
5. Create `components/ui/Card.tsx` + CSS Module
6. Create `components/ui/Toggle.tsx` + CSS Module
7. Create `components/ui/Badge.tsx` + CSS Module
8. Create `components/ui/EmptyState.tsx` + CSS Module
9. Create `components/ui/Skeleton.tsx` + CSS Module
10. Create `components/ui/SearchInput.tsx` + CSS Module
11. Create `components/ui/SegmentedControl.tsx` + CSS Module

### Phase 3: Saved Plans Page
12. Create `components/saved/PlanCard.tsx` + CSS Module
13. Create `components/saved/PlanDetailPanel.tsx` + CSS Module
14. Create `components/saved/PlanEditModal.tsx` + CSS Module
15. Create `components/saved/EmptyPlans.tsx`
16. Create `components/saved/SavedPlansView.tsx` + CSS Module

### Phase 4: Activity Page
17. Create `components/activity/ActivityStats.tsx` + CSS Module
18. Create `components/activity/ActivityItem.tsx` + CSS Module
19. Create `components/activity/ActivityTimeline.tsx` + CSS Module
20. Create `components/activity/ReceiptDetail.tsx` + CSS Module
21. Create `components/activity/ActivityFilter.tsx`
22. Create `components/activity/ActivitySearch.tsx`
23. Create `components/activity/ActivityView.tsx` + CSS Module

### Phase 5: Settings Page
24. Create `components/settings/ProfileSection.tsx` + CSS Module
25. Create `components/settings/DietSection.tsx` + CSS Module
26. Create `components/settings/LocationSection.tsx` + CSS Module
27. Create `components/settings/NotificationSection.tsx` + CSS Module
28. Create `components/settings/SettingsView.tsx` + CSS Module

### Phase 6: Integration
29. Update `app/page.tsx` to use new components
30. Add new keyframe animations to `globals.css`
31. Delete old JSX files
32. Test all pages

---

## 8. Success Criteria

1. All three pages render with loading states, empty states, and error handling
2. Animations are smooth and respect `prefers-reduced-motion`
3. User preferences persist in localStorage
4. Plans and activities load from mock data with simulated delays
5. Mobile layout is usable and responsive
6. Desktop layout makes good use of space
7. All interactions have visual feedback
8. TypeScript types are complete and correct
9. CSS Modules prevent style leakage
10. Existing functionality (main planning flow) is not broken

---

## 9. Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| CSS Modules learning curve | Keep module CSS simple, use CSS variables from global scope |
| Animation performance on mobile | Use `will-change` sparingly, test on low-end devices |
| Mock data doesn't match real API | Define interfaces first, mock follows interface |
| Breaking existing pages | Keep old files until new ones are verified |
| Large number of files | Each file is small and focused, clear naming convention |
