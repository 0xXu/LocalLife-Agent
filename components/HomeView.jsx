'use client';

import { CloudRain, Heart, Mic, SendHorizontal, Users, Utensils } from 'lucide-react';
import { scenarioPrompts } from '@/features/planner/mockAgent';

const scenarios = [
  {
    id: 'family',
    title: '家庭半日',
    body: '亲子友好地点，节奏轻松。',
    icon: Users,
    tone: 'blue'
  },
  {
    id: 'friends',
    title: '朋友聚会',
    body: '活动、餐食和小酌顺路安排。',
    icon: Utensils,
    tone: 'violet'
  },
  {
    id: 'date',
    title: '约会安排',
    body: '安静、有氛围、低排队。',
    icon: Heart,
    tone: 'green'
  },
  {
    id: 'rainy',
    title: '雨天室内',
    body: '室内活动和舒服餐厅。',
    icon: CloudRain,
    tone: 'coral'
  }
];

export function HomeView({ goal, onGoalChange, onPlan }) {
  return (
    <section className="home-view">
      <div className="home-center">
        <h1>问问 WeekendPilot</h1>
        <p>这个周末想怎么安排？</p>

        <div className="prompt-composer">
          <textarea
            value={goal}
            onChange={(event) => onGoalChange(event.target.value)}
            placeholder="我想要...（例如：找一家附近安静的咖啡店，再安排一段轻松散步）"
          />
          <div className="composer-actions">
            <button className="voice-button" type="button" aria-label="语音输入">
              <Mic size={22} />
            </button>
            <button className="primary-button plan-button" type="button" onClick={() => onPlan(goal)}>
              生成计划
              <SendHorizontal size={17} />
            </button>
          </div>
        </div>

        <div className="scenario-heading">也可以从场景开始</div>
        <div className="scenario-grid">
          {scenarios.map((scenario) => {
            const Icon = scenario.icon;
            return (
              <button
                key={scenario.id}
                className="scenario-card"
                type="button"
                onClick={() => onPlan(scenarioPrompts[scenario.id])}
              >
                <span className={`scenario-icon ${scenario.tone}`}>
                  <Icon size={28} />
                </span>
                <strong>{scenario.title}</strong>
                <small>{scenario.body}</small>
              </button>
            );
          })}
        </div>
      </div>
    </section>
  );
}
