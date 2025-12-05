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
# Schedules based on the user's existing setup. The midweek_schedule will be
# loaded dynamically from a JSON file.
MEETING_SCHEDULES = {
    # Midweek schedule is now loaded dynamically from JSON
    'midweek_schedule': [],

    # Weekend schedule from the original core.py
    'weekend_schedule': [
        {"section": "Opening", "name": "Song & Prayer", "duration_seconds": 4 * 60},
        {"section": "Main Talk", "name": "Public Discourse", "duration_seconds": 30 * 60},
        {"section": "WTS", "name": "Study Article", "duration_seconds": 60 * 60},
    ]
}

# --- SCHEDULE FILE CONFIGURATION ---
# Match the directory constant from schedule.py
SCHEDULES_DIR = "schedules"

# --- COMBINED INITIAL STATE ---
# The full dictionary used to initialize the timer's state in core.py
INITIAL_STATE = {
    **DEFAULT_TIMER_STATE,
    **MEETING_SCHEDULES,
    'schedules_dir': SCHEDULES_DIR  # Include the directory path in the initial state
}