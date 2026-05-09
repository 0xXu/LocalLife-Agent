import type { Receipt } from '../../types/weekendpilot';
import type { ToolAdapter } from './common';
import { buildItineraryTool } from './buildItinerary';
import { checkAvailabilityTool } from './checkAvailability';
import { claimCouponTool } from './claimCoupon';
import { compareAlternativesTool } from './compareAlternatives';
import { createCalendarEventTool } from './createCalendarEvent';
import { createOrderTool } from './createOrder';
import { createReservationTool } from './createReservation';
import { getWeatherTool } from './getWeather';
import { optimizeRouteTool } from './optimizeRoute';
import { parseUserGoalTool } from './parseUserGoal';
import { reserveActivityTool } from './reserveActivity';
import { searchPlacesTool } from './searchPlaces';
import { searchRestaurantsTool } from './searchRestaurants';
import { sendPlanMessageTool } from './sendPlanMessage';
import { validatePlanTool } from './validatePlan';

const tools: ToolAdapter[] = [
  parseUserGoalTool,
  getWeatherTool,
  searchPlacesTool,
  searchRestaurantsTool,
  checkAvailabilityTool,
  optimizeRouteTool,
  buildItineraryTool,
  validatePlanTool,
  compareAlternativesTool,
  reserveActivityTool,
  createReservationTool,
  claimCouponTool,
  createOrderTool,
  sendPlanMessageTool,
  createCalendarEventTool,
];

export const toolRegistry = {
  schemas() {
    return tools.map((tool) => tool.schema);
  },
  get(name: string) {
    const tool = tools.find((item) => item.schema.name === name);
    if (!tool) {
      throw new Error(`tool_not_found:${name}`);
    }
    return tool;
  },
};

export async function executeAllConfirmedActions(actions: Array<Record<string, any>>, context: { confirmed: boolean; idempotencyKey: string; humanConfirmationSnapshot?: Record<string, any> }): Promise<Receipt[]> {
  const receipts: Receipt[] = [];
  for (const action of actions) {
    const toolName = String(action.tool ?? action.type);
    const tool = toolRegistry.get(toolName);
    if (!tool.schema.side_effect) {
      continue;
    }
    const receipt = await tool.execute({ ...action.payload, type: action.type, detail: action.detail }, context);
    receipts.push(receipt as Receipt);
  }
  return receipts;
}
