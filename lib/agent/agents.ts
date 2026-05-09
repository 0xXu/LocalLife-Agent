import { Agent } from '@openai/agents';

export const intentParserAgentName = 'Intent Parser';
export const rankExplanationAgentName = 'Rank Explanation';
export const recoveryExplanationAgentName = 'Recovery Explanation';

export const intentParserAgent = new Agent({
  name: intentParserAgentName,
  instructions: 'Parse local-life half-day planning goals into the exact WeekendPilot ParsedConstraints JSON contract. Do not recommend places.',
});

export const rankExplanationAgent = new Agent({
  name: rankExplanationAgentName,
  instructions: 'Explain ranked POI choices using only supplied scoring factors and supplied facts. Never invent place details.',
});

export const recoveryExplanationAgent = new Agent({
  name: recoveryExplanationAgentName,
  instructions: 'Explain recovery diffs for local-life plans using only supplied before/after facts.',
});

export function agentMetadata() {
  return {
    intent_parser: intentParserAgent.name,
    rank_explanation: rankExplanationAgent.name,
    recovery_explanation: recoveryExplanationAgent.name,
  };
}
