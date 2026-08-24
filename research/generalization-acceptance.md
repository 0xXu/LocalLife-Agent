# 泛化验收结果

- 时间：2026-08-20T06:00:52.877683+00:00
- 通过：26/26
- 平均首轮延迟：15.23s
- 接口：`POST /api/tasks`（真实 DeepSeek + ADK + MCP）

| 案例 | 结果 | 阶段 | Scout | 延迟 | 失败原因 |
|---|---|---|---|---:|---|
| food_sushi_exact | 通过 | awaiting_mandate | dining_scout | 18.18s | - |
| food_hotpot_group | 通过 | awaiting_mandate | dining_scout | 20.03s | - |
| activity_family | 通过 | awaiting_mandate | experiences_scout | 19.57s | - |
| activity_exhibition_solo | 通过 | awaiting_mandate | experiences_scout | 16.48s | - |
| service_massage | 通过 | awaiting_mandate | appointments_scout | 18.24s | - |
| service_hair | 通过 | awaiting_mandate | appointments_scout | 16.23s | - |
| service_nails_pair | 通过 | awaiting_mandate | appointments_scout | 17.16s | - |
| delivery_congee | 通过 | awaiting_mandate | delivery_scout | 23.34s | - |
| delivery_flowers | 通过 | awaiting_mandate | delivery_scout | 19.63s | - |
| delivery_cake | 通过 | awaiting_mandate | delivery_scout | 16.33s | - |
| delivery_grocery | 通过 | awaiting_mandate | delivery_scout | 18.44s | - |
| mobility_ride | 通过 | awaiting_mandate | mobility_scout | 22.70s | - |
| mobility_navigation | 通过 | awaiting_mandate | mobility_scout | 16.60s | - |
| cross_dinner_movie | 通过 | awaiting_mandate | dining_scout, experiences_scout, mobility_scout | 35.75s | - |
| cross_service_delivery | 通过 | awaiting_mandate | appointments_scout, delivery_scout | 18.76s | - |
| cross_flowers_dinner | 通过 | awaiting_mandate | delivery_scout, dining_scout | 25.77s | - |
| vague_relax | 通过 | clarifying | - | 4.67s | - |
| vague_arrange | 通过 | clarifying | - | 3.94s | - |
| vague_surprise | 通过 | clarifying | - | 5.50s | - |
| vague_solo | 通过 | clarifying | - | 4.31s | - |
| budget_conflict | 通过 | clarifying | dining_scout | 20.38s | - |
| deadline_conflict | 通过 | clarifying | experiences_scout | 21.27s | - |
| unsupported_hotel | 通过 | unsupported | - | 3.37s | - |
| medical_emergency | 通过 | unsupported | - | 2.87s | - |
| medical_diagnosis | 通过 | unsupported | - | 3.22s | - |
| unsupported_long_trip | 通过 | unsupported | - | 3.32s | - |
