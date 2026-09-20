"""Tunable weights for the rule-based recommendation engine (§7).

score = priority_weight + deadline_weight + overdue_weight
        + available_time_match + project_importance + continuation_bonus
        + context_match - excessive_duration_penalty

All values are plain ints so product can tune without redeploying logic.
"""

PRIORITY_WEIGHTS = {
    "Urgent": 100,
    "High": 70,
    "Medium": 40,
    "Low": 20,
}

# Due within N days -> bonus
DEADLINE_BONUS = {
    "overdue_per_day_cap": 60,      # max extra for overdue ageing
    "overdue_per_day": 10,
    "due_today": 40,
    "due_tomorrow": 25,
    "due_within_3_days": 15,
    "due_within_7_days": 8,
}

CONTINUATION_BONUS = 30        # task was recently interrupted / has WorkState
TODAY_PLAN_BONUS = 20          # task is in today's top priorities
CONTEXT_MATCH_BONUS = 12       # task.context == requested context
TIME_FIT_BONUS = 15            # estimated_minutes <= available minutes
TIME_MISMATCH_PENALTY = 25     # estimated_minutes > available minutes
FUTURE_START_PENALTY = 30      # start_date in the future
BLOCKED_PENALTY = 100          # status Waiting or postponed heavily
DEPENDENCY_PENALTY = 50        # parent task incomplete
PROJECT_IMPORTANCE = {         # project.priority -> bonus
    "Urgent": 15,
    "High": 10,
    "Medium": 5,
    "Low": 0,
}

# Task larger than this triggers the "split it?" nudge (§18)
BREAKDOWN_THRESHOLD_MINUTES = 90
BREAKDOWN_CHUNK_OPTIONS = (15, 25, 45)

# Planning: always keep this much buffer unscheduled (§36)
BUFFER_MINUTES_PER_DAY = 60

# Postponed >= this many times triggers the "break it down?" nudge (§34)
POSTPONE_NUDGE_THRESHOLD = 3

# Spaced repetition intervals in days (§26). index = review_stage.
REVIEW_INTERVALS_DAYS = [0, 1, 3, 7, 14, 30]
# If user marks topic difficult, step back this many stages (min 0).
DIFFICULT_STEP_BACK = 1
