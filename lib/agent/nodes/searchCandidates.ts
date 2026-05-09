import { PlanStatuses, type PlannerState } from '../state';

export function searchCandidates(state: PlannerState): PlannerState {
  return {
    ...state,
    status: PlanStatuses.SEARCH_CANDIDATES,
    candidates: {
      activities: [
        { id: 'act_001', title: '城市科学馆', score: 0.94, tags: ['child_friendly', 'indoor'] },
        { id: 'act_018', title: '儿童书店手作角', score: 0.82, tags: ['child_friendly', 'rainy_indoor'] },
      ],
      restaurants: [
        { id: 'res_014', title: '绿荫轻食餐厅', score: 0.92, tags: ['low_fat', 'child_seat'] },
        { id: 'res_022', title: '轻碗健康餐厅', score: 0.86, tags: ['low_fat', 'quiet'] },
      ],
      walks: [
        { id: 'walk_006', title: '河畔低糖甜品散步', score: 0.88, tags: ['short_walk', 'low_sugar'] },
      ],
    },
  };
}
