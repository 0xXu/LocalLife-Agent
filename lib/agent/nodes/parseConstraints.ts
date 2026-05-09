import { ParsedConstraintsSchema } from '../../contracts/schemas';
import { intentParserAgentName } from '../agents';
import { createOpenAIClient, responseOutputText, type ResponsesLikeClient } from '../openai';
import { PlanStatuses, type PlannerState } from '../state';

type ParseOptions = {
  openai?: ResponsesLikeClient | null;
  responsesEnabled?: boolean;
  model?: string;
};

export function parseConstraints(state: PlannerState): PlannerState {
  return deterministicParseConstraints(state, true);
}

export async function parseConstraintsNode(state: PlannerState, options: ParseOptions = {}): Promise<PlannerState> {
  const client = options.openai ?? createOpenAIClient();
  if (options.responsesEnabled === false || !client) {
    return deterministicParseConstraints(state, true);
  }

  try {
    const response = await client.responses.create({
      model: options.model ?? process.env.OPENAI_MODEL ?? 'gpt-4.1-mini',
      input: [
        {
          role: 'system',
          content: 'Return only strict JSON matching WeekendPilot ParsedConstraints. Do not recommend places.',
        },
        {
          role: 'user',
          content: state.goal ?? '',
        },
      ],
      text: {
        format: {
          type: 'json_object',
        },
      },
    });
    const parsed = ParsedConstraintsSchema.parse(JSON.parse(responseOutputText(response)));
    return {
      ...state,
      status: PlanStatuses.PARSE_CONSTRAINTS,
      clarifying_questions: [],
      constraints: parsed,
      openai_metadata: {
        llm_fallback: false,
        agent: intentParserAgentName,
      },
    };
  } catch {
    return deterministicParseConstraints(state, true);
  }
}

function deterministicParseConstraints(state: PlannerState, llmFallback: boolean): PlannerState {
  const goal = state.goal ?? '';
  const clarifying_questions: string[] = [];

  if (!hasPeople(goal)) {
    clarifying_questions.push('几个人出行？');
  }

  if (!hasConcreteTime(goal)) {
    clarifying_questions.push('希望从几点开始、玩多久？');
  }

  if (clarifying_questions.length > 0) {
    return {
      ...state,
      status: PlanStatuses.NEED_CLARIFICATION,
      clarifying_questions,
      receipts: [],
      pending_side_effects: [],
      plan_response: undefined,
      openai_metadata: {
        llm_fallback: llmFallback,
        agent: intentParserAgentName,
      },
    };
  }

  const friends = goal.includes('朋友');
  const date = /对象|约会|情侣/.test(goal);
  const rainy = /雨|下雨|室内/.test(goal);
  const scenario = rainy ? 'rainy_indoor' : date ? 'date' : friends ? 'friends' : 'family';
  return {
    ...state,
    status: PlanStatuses.PARSE_CONSTRAINTS,
    clarifying_questions: [],
    constraints: {
      scenario,
      origin: { type: 'current_location', label: 'home', lat: 38.2601, lng: 140.8824 },
      time_window: { date: '2026-05-09', start: extractStart(goal), duration_hours: extractDuration(goal), flexible: true },
      people: {
        adults: friends ? 4 : 2,
        children: friends || date ? [] : [{ age: 5 }],
        relationship: scenario,
      },
      preferences: {
        distance: 'nearby',
        diet: ['low_fat', 'low_sugar'],
        activity: scenario === 'date' ? ['quiet', 'romantic'] : friends ? ['photo_spot', 'chat'] : ['child_friendly', 'not_too_tiring'],
        budget_level: 'medium',
      },
      constraints: { radius_km: 5, max_wait_minutes: 15, avoid: ['heavy_oil', 'long_queue', 'smoking'] },
      required_actions: ['activity_reservation', 'restaurant_reservation', 'send_plan_message'],
      party: friends ? '4 位朋友' : '2 位成人，1 位 5 岁儿童',
      duration: '约 4.5 小时',
      dietary: '低脂友好',
      radiusKm: 5,
      transport: '打车 + 步行',
    },
    openai_metadata: {
      llm_fallback: llmFallback,
      agent: intentParserAgentName,
    },
  };
}

function hasPeople(goal: string) {
  return /朋友|家人|家庭|老婆|孩子|对象|约会|\d+\s*(个|位)?\s*(人|朋友)|\d+\s*男|\d+\s*女/.test(goal);
}

function hasConcreteTime(goal: string) {
  return /今天|明天|上午|下午|晚上|\d{1,2}\s*(点|:|：)|\d+(\.\d+)?\s*(个)?小时|几个小时/.test(goal);
}

function extractStart(goal: string) {
  const match = goal.match(/(\d{1,2})\s*点/);
  return match ? `${match[1].padStart(2, '0')}:00` : '14:00';
}

function extractDuration(goal: string) {
  const match = goal.match(/(\d+(?:\.\d+)?)\s*(个)?小时/);
  return match ? Number(match[1]) : 4.5;
}
