# config.py

# --- TIMER STATE INITIALIZATION DEFAULTS ---
# These are the default runtime settings for the timer application.
DEFAULT_TIMER_STATE = {
    'total_duration_ms': 0,
    'start_time': None,  # Unix timestamp when timer started (None if stopped/loaded)
    'target_end_time_ts': None,  # Unix timestamp for absolute time countdown
    'allow_negative': True,  # Allows the timer to count past zero
    'mode': 'Duration',  # 'Duration' or 'Absolute'
}

# --- MEETING SCHEDULES ---
# Schedules based on the user's existing setup and the new detailed times (Jan 2020 C# comments)
MEETING_SCHEDULES = {
    # Detailed Midweek schedule based on the extracted C# comments (durations in seconds)
    'midweek_schedule': [
        # Opening
        {"section": "Opening", "name": "Song, Prayer & Remarks", "duration_seconds": 5 * 60},  # 5 min

        # Treasures from God's Word
        {"section": "Treasures", "name": "Treasures Talk", "duration_seconds": 10 * 60},  # 10 min
        {"section": "Treasures", "name": "Digging for Gems", "duration_seconds": 8 * 60},  # 8 min
        {"section": "Treasures", "name": "Bible Reading", "duration_seconds": 4 * 60},  # 4 min

        # Apply Yourself to the Field Ministry
        {"section": "Ministry", "name": "Initial Call", "duration_seconds": 2 * 60},  # 2 min
        {"section": "Ministry", "name": "Return Visit", "duration_seconds": 4 * 60},  # 4 min
        {"section": "Ministry", "name": "Bible Study/Talk", "duration_seconds": 6 * 60},  # 6 min

        # Living as Christians
        {"section": "Living", "name": "Living Part 1", "duration_seconds": 15 * 60},  # 15 min
        {"section": "Living", "name": "Congregation Bible Study", "duration_seconds": 30 * 60},  # 30 min

        # Concluding
        {"section": "Concluding", "name": "Concluding Comments", "duration_seconds": 3 * 60},  # 3 min
    ],
    # Weekend schedule from the original core.py
    'weekend_schedule': [
        {"section": "Opening", "name": "Song & Prayer", "duration_seconds": 4 * 60},
        {"section": "Main Talk", "name": "Public Discourse", "duration_seconds": 30 * 60},
        {"section": "WTS", "name": "Study Article", "duration_seconds": 60 * 60},
    ]
}

# --- COMBINED INITIAL STATE ---
# The full dictionary used to initialize the timer's state in core.py
INITIAL_STATE = {
    **DEFAULT_TIMER_STATE,
    **MEETING_SCHEDULES
}