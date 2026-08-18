from enum import StrEnum


class AllowedAICommand(StrEnum):
    CREATE_GOAL = "CreateGoal"
    CREATE_ROADMAP = "CreateRoadmap"
    CREATE_TASK = "CreateTask"
    SUGGEST_CALENDAR_SLOTS = "SuggestCalendarSlots"
    PROJECT_TASK_TO_CALENDAR = "ProjectTaskToCalendar"


ALLOWED_AI_COMMANDS = frozenset(command.value for command in AllowedAICommand)
