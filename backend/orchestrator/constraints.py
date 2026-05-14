"""Constraint parsing, normalization and enrichment helpers.

Extracted from pipeline.py to keep that module focused on the LangGraph workflow.
"""

from __future__ import annotations

import re

from backend.models.schemas import ParsedConstraints


def extract_json_object(content: str) -> str:
    stripped = content.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.I)
        stripped = re.sub(r"\s*```$", "", stripped)
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("llm_json_not_found")
    return stripped[start:end + 1]


def deterministic_constraints(goal: str) -> ParsedConstraints:
    scenario = detect_scenario(goal)
    child_age = parse_child_age(goal)
    adults = parse_adult_count(goal, child_age, scenario)
    radius = 5 if re.search(r"别.*远|附近|nearby|not too far|5km", goal, re.I) else 8
    diet = ["low_fat", "low_sugar"] if re.search(r"减脂|减肥|健康|低脂|diet|low[-\s]?fat", goal, re.I) else []
    if scenario == "date":
        activity = ["quiet", "romantic"]
    elif scenario == "friends":
        activity = ["social", "photo", "indoor"]
    elif scenario == "rainy_indoor":
        activity = ["indoor", "rain_safe"]
    else:
        activity = ["child_friendly", "not_too_tiring"]
    return ParsedConstraints(
        scenario=scenario,
        origin={"type": "current_location", "label": "home", "lat": 38.2601, "lng": 140.8824},
        time_window={"date": "today", "start": "13:30", "duration_hours": 4.5, "flexible": True},
        people={"adults": adults, "children": [{"age": child_age}] if child_age else [], "relationship": scenario},
        preferences={"distance": "nearby", "diet": diet, "activity": activity, "budget_level": "medium"},
        constraints={"radius_km": radius, "max_wait_minutes": 15, "avoid": ["heavy_oil", "long_queue", "smoking"]},
        required_actions=["activity_reservation", "restaurant_reservation", "claim_coupon", "create_order", "send_plan_message", "create_calendar_event"],
    )


def detect_scenario(goal: str) -> str:
    if "雨" in goal or "下雨" in goal or "室内" in goal:
        return "rainy_indoor"
    if "对象" in goal or "约会" in goal or "情侣" in goal:
        return "date"
    if "朋友" in goal or re.search(r"\d+\s*男\s*\d+\s*女", goal):
        return "friends"
    if re.search(r"孩子|小孩|亲子|老婆孩子|family|child|kid", goal, re.I):
        return "family"
    return "local_life"


def parse_child_age(goal: str) -> int | None:
    match = re.search(r"孩子\s*(\d{1,2})\s*岁|(\d{1,2})\s*(?:岁|yo).*(?:孩子|child|kid)", goal, re.I)
    if match:
        return int(next(group for group in match.groups() if group))
    return 5 if re.search(r"孩子|child|kid", goal, re.I) else None


def parse_adult_count(goal: str, child_age: int | None, scenario: str) -> int:
    if child_age:
        return 2
    gender = re.search(r"(\d{1,2})\s*男\s*(\d{1,2})\s*女", goal)
    if gender:
        return int(gender.group(1)) + int(gender.group(2))
    count = re.search(r"朋友\s*(\d{1,2})\s*个人|(\d{1,2})\s*个?人", goal)
    if count:
        return int(next(group for group in count.groups() if group))
    return 2 if scenario == "date" else 4 if scenario == "friends" else 2


def constraints_from_dict(data: dict) -> ParsedConstraints:
    fallback = deterministic_constraints("")
    scenario = normalize_scenario_label(data.get("scenario", fallback.scenario))
    people = normalize_people(data.get("people", fallback.people), fallback.people)
    time_window = normalize_time_window(data.get("time_window", fallback.time_window), fallback.time_window)
    preferences = normalize_preferences(data.get("preferences", fallback.preferences), fallback.preferences)
    constraints = normalize_constraints(data.get("constraints", fallback.constraints), fallback.constraints)
    return ParsedConstraints(
        scenario=scenario,
        origin=data.get("origin", fallback.origin),
        time_window=time_window,
        people=people,
        preferences=preferences,
        constraints=constraints,
        required_actions=normalize_required_actions(data.get("required_actions", fallback.required_actions)),
    )


def normalize_constraints_for_goal(goal: str, constraints: ParsedConstraints) -> ParsedConstraints:
    if not is_hiking_goal(goal):
        return enrich_constraints_for_goal(goal, constraints)

    if not has_family_signal(goal) and not has_date_signal(goal) and constraints.scenario != "rainy_indoor":
        constraints.scenario = "friends"
        constraints.people["relationship"] = "friends"
        constraints.people["children"] = []

    party_size = parse_party_size(goal)
    if party_size:
        constraints.people["adults"] = party_size

    activity_tags = as_list(constraints.preferences.get("activity", []))
    constraints.preferences["activity"] = unique_list(["hiking", "outdoor", "nature", "walkable", "group_friendly", *activity_tags])
    constraints.constraints["radius_km"] = max(float_or_default(constraints.constraints.get("radius_km"), 5), 10)

    if not has_explicit_duration(goal) and float_or_default(constraints.time_window.get("duration_hours"), 4.5) >= 4.5:
        constraints.time_window["duration_hours"] = 3

    if not has_food_signal(goal):
        constraints.required_actions = [
            action for action in as_list(constraints.required_actions)
            if action not in {"restaurant_reservation", "claim_coupon", "create_order"}
        ]
    return enrich_constraints_for_goal(goal, constraints)


def enrich_constraints_for_goal(goal: str, constraints: ParsedConstraints) -> ParsedConstraints:
    tags = unique_list([*infer_activity_tags(goal), *as_list(constraints.preferences.get("activity", []))])
    if tags:
        constraints.preferences["activity"] = tags
    if "intent_label" not in constraints.preferences or not str(constraints.preferences.get("intent_label", "")).strip():
        constraints.preferences["intent_label"] = infer_intent_label(goal, constraints)
    party_size = parse_party_size(goal)
    if party_size:
        constraints.people["adults"] = party_size
        if not has_family_signal(goal):
            constraints.people["children"] = []
    if has_food_signal(goal):
        constraints.required_actions = unique_list([*as_list(constraints.required_actions), "restaurant_reservation", "claim_coupon", "create_order"])
    else:
        constraints.required_actions = [
            action for action in as_list(constraints.required_actions)
            if action not in {"restaurant_reservation", "claim_coupon", "create_order"}
        ]
    return constraints


def normalize_scenario_label(value) -> str:
    label = str(value or "local_life").strip()
    if not label or "|" in label or "," in label:
        return "local_life"
    normalized = re.sub(r"\s+", "_", label.lower())
    normalized = re.sub(r"[^0-9a-zA-Z_\-一-鿿]", "", normalized)
    return normalized or "local_life"


def infer_activity_tags(goal: str) -> list[str]:
    patterns = [
        (r"爬山|登山|徒步|山野|步道|hiking?|mountain|trail|trek", ["hiking", "outdoor", "nature", "walkable"]),
        (r"狗|宠物|猫|pet|dog|cat", ["pet", "outdoor", "walkable"]),
        (r"写代码|自习|学习|办公|工作|电脑|咖啡|coffee|cafe|work|study", ["work", "quiet", "cafe", "wifi"]),
        (r"羽毛球|篮球|足球|网球|运动|健身|badminton|basketball|sports|fitness", ["sports", "group_friendly"]),
        (r"生日|惊喜|纪念日|庆祝|birthday|celebration", ["birthday", "celebration", "photo"]),
        (r"展|博物馆|美术馆|艺术|museum|gallery|art", ["museum", "art", "quiet", "indoor"]),
        (r"电影|影院|cinema|movie", ["cinema", "indoor", "low_noise"]),
        (r"逛街|商场|买东西|shopping|mall", ["shopping", "indoor", "walkable"]),
        (r"KTV|酒吧|夜生活|唱歌|bar|nightlife", ["ktv", "nightlife", "group_friendly"]),
        (r"按摩|spa|放松|疗愈|wellness|relax", ["wellness", "spa", "quiet"]),
        (r"密室|剧本杀|escape|mystery", ["immersive", "mystery", "group_friendly"]),
        (r"孩子|小孩|亲子|family|child|kid", ["child_friendly", "not_too_tiring"]),
        (r"雨|下雨|室内|rain|indoor", ["indoor", "rain_safe"]),
    ]
    tags: list[str] = []
    for pattern, values in patterns:
        if re.search(pattern, goal, re.I):
            tags.extend(values)
    return unique_list(tags)


def infer_intent_label(goal: str, constraints: ParsedConstraints) -> str:
    tag_labels = [
        ({"pet"}, "宠物散步"),
        ({"work", "cafe"}, "写代码自习"),
        ({"hiking"}, "户外徒步"),
        ({"sports"}, "运动计划"),
        ({"birthday"}, "生日惊喜"),
        ({"museum", "art"}, "看展计划"),
        ({"cinema"}, "电影计划"),
        ({"shopping"}, "逛街计划"),
        ({"ktv", "nightlife"}, "夜生活聚会"),
        ({"wellness", "spa"}, "放松疗愈"),
        ({"child_friendly"}, "亲子活动"),
        ({"rain_safe"}, "雨天室内"),
    ]
    tags = set(constraints.preferences.get("activity", [])) | set(infer_activity_tags(goal))
    for required, label in tag_labels:
        if required <= tags:
            return label
    scenario = constraints.scenario.replace("_", " ").strip()
    return scenario if re.search(r"[一-鿿]", scenario) else "本地生活"


def missing_required_fields(goal: str, constraints: ParsedConstraints) -> list[str]:
    missing: list[str] = []
    activity_present = bool(constraints.preferences.get("activity"))
    if goal.strip() in {"周末安排一下", "帮我安排一下"} or (len(goal.strip()) < 8 and not activity_present):
        missing.extend(["time_window", "activity_intent"])
    if not activity_present:
        missing.append("activity_intent")
    if constraints.people.get("adults", 0) <= 0:
        missing.append("people")
    return list(dict.fromkeys(missing))


def clarifying_questions_for(missing: list[str]) -> list[dict[str, str]]:
    questions = []
    if "time_window" in missing:
        questions.append({"field": "time_window", "question": "你想安排今天、周六还是周日？大概几小时？"})
    if "activity_intent" in missing:
        questions.append({"field": "activity_intent", "question": "你更想户外走走、室内放松、吃饭聚会，还是亲子活动？"})
    if "people" in missing:
        questions.append({"field": "people", "question": "这次几个人一起去？有没有孩子、老人或宠物？"})
    return questions


def is_hiking_goal(goal: str) -> bool:
    return bool(re.search(r"爬山|登山|徒步|山野|步道|hiking?|mountain|trail|trek", goal, re.I))


def has_family_signal(goal: str) -> bool:
    return bool(re.search(r"孩子|小孩|亲子|老婆孩子|family|child|kid", goal, re.I))


def has_date_signal(goal: str) -> bool:
    return bool(re.search(r"对象|约会|情侣|老婆(?!孩子)|date|couple", goal, re.I))


def has_food_signal(goal: str) -> bool:
    return bool(re.search(r"吃饭|吃点|吃个|吃些|用餐|聚餐|餐厅|晚饭|午饭|早饭|饭|dinner|lunch|restaurant|meal|dining", goal, re.I))


def has_explicit_duration(goal: str) -> bool:
    return bool(re.search(r"\d+(?:\.\d+)?\s*(小时|钟头|h|hour)|半天|全天|一小时|两小时|三小时|四小时|五小时", goal, re.I))


def parse_party_size(goal: str) -> int | None:
    digit = re.search(r"(\d{1,2})\s*(?:个)?人", goal)
    if digit:
        return int(digit.group(1))
    chinese_numbers = {
        "一": 1,
        "两": 2,
        "二": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
        "十": 10,
    }
    chinese = re.search(r"([一两二三四五六七八九十])\s*(?:个)?人", goal)
    if chinese:
        return chinese_numbers[chinese.group(1)]
    return None


def unique_list(values: list) -> list:
    result = []
    for value in values:
        if value not in result:
            result.append(value)
    return result


def normalize_people(value: dict, fallback: dict) -> dict:
    people = {**fallback, **value} if isinstance(value, dict) else dict(fallback)
    people["adults"] = int_or_default(people.get("adults"), int(fallback.get("adults", 2)))
    children = people.get("children", [])
    if children is None or children == 0:
        people["children"] = []
    elif isinstance(children, int):
        people["children"] = [{"age": None} for _ in range(children)]
    elif isinstance(children, dict):
        people["children"] = [children]
    elif isinstance(children, list):
        people["children"] = children
    else:
        people["children"] = []
    return people


def normalize_time_window(value: dict, fallback: dict) -> dict:
    time_window = {**fallback, **value} if isinstance(value, dict) else dict(fallback)
    time_window["duration_hours"] = float_or_default(time_window.get("duration_hours"), float(fallback.get("duration_hours", 4.5)))
    time_window["flexible"] = bool(time_window.get("flexible", fallback.get("flexible", True)))
    return time_window


def normalize_preferences(value: dict, fallback: dict) -> dict:
    preferences = {**fallback, **value} if isinstance(value, dict) else dict(fallback)
    preferences["diet"] = as_list(preferences.get("diet", fallback.get("diet", [])))
    preferences["activity"] = as_list(preferences.get("activity", fallback.get("activity", [])))
    return preferences


def normalize_constraints(value: dict, fallback: dict) -> dict:
    constraints = {**fallback, **value} if isinstance(value, dict) else dict(fallback)
    constraints["radius_km"] = float_or_default(constraints.get("radius_km"), float(fallback.get("radius_km", 5)))
    constraints["max_wait_minutes"] = int_or_default(constraints.get("max_wait_minutes"), int(fallback.get("max_wait_minutes", 15)))
    constraints["avoid"] = as_list(constraints.get("avoid", fallback.get("avoid", [])))
    return constraints


ACTION_ALIASES = {
    "restaurant_search": "restaurant_reservation",
    "book_restaurant": "restaurant_reservation",
    "reserve_restaurant": "restaurant_reservation",
    "coupon_search": "claim_coupon",
    "coupon": "claim_coupon",
    "order_food": "create_order",
    "food_order": "create_order",
    "calendar": "create_calendar_event",
    "message": "send_plan_message",
}

SUPPORTED_REQUIRED_ACTIONS = {
    "activity_reservation",
    "restaurant_reservation",
    "claim_coupon",
    "create_order",
    "send_plan_message",
    "create_calendar_event",
}


def normalize_required_actions(value) -> list[str]:
    normalized = []
    for item in as_list(value):
        action = ACTION_ALIASES.get(str(item), str(item))
        if action in SUPPORTED_REQUIRED_ACTIONS and action not in normalized:
            normalized.append(action)
    return normalized


def as_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def int_or_default(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def float_or_default(value, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
