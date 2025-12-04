import time
from datetime import datetime
import pytz  # Need for handling absolute time (using UTC internally for safety)
from config import INITIAL_STATE # Import the configuration data

# Define UTC timezone for consistency
TIMEZONE = pytz.utc

# --- Constants ---
# NOTE: These constants are now functionally irrelevant for the color logic,
# as we are using a percentage-based threshold (20%).
GREEN_THRESHOLD = 300000  # 5 minutes in milliseconds
AMBER_THRESHOLD = 60000  # 1 minute in milliseconds

# --- Timer State Management ---
# Initialize the live timer state from the configuration file
# Use .copy() so runtime changes do not modify the imported INITIAL_STATE dictionary
timer_state = INITIAL_STATE.copy()


# --- Core Calculation Functions ---

def calculate_remaining_ms():
    """Calculates the time remaining in milliseconds based on current mode."""
    # If not running, return the set total duration (ready to start)
    # NOTE: This only occurs if the timer was loaded and then CANCELLED/STOPPED.
    if timer_state['start_time'] is None:
        return timer_state['total_duration_ms']

    now = time.time()

    if timer_state['mode'] == 'Duration':
        if timer_state['total_duration_ms'] == 0:
            return 0

        elapsed_ms = int((now - timer_state['start_time']) * 1000)
        remaining_ms = timer_state['total_duration_ms'] - elapsed_ms

    elif timer_state['mode'] == 'Absolute':
        if timer_state['target_end_time_ts'] is None:
            return 0

        remaining_s = timer_state['target_end_time_ts'] - now
        remaining_ms = int(remaining_s * 1000)

    else:
        return 0

    # If negative time is not allowed and the timer expired, cap it at 0
    if not timer_state['allow_negative'] and remaining_ms < 0:
        return 0

    return remaining_ms


def get_status_color(remaining_ms):
    """
    Determines the color state based on remaining time.
    RULES: Red only when negative. Amber at 20% or less remaining time.
    """

    # 1. Non-running check (loaded but stopped)
    if timer_state['start_time'] is None:
        return 'STOPPED'

    # 2. Red Check: When timer has gone past zero
    if remaining_ms < 0:
        return 'RED'

    # 3. Determine total duration for percentage calculation
    total_duration_ms = timer_state['total_duration_ms']

    if timer_state['mode'] == 'Absolute':
        if timer_state['target_end_time_ts'] is None or timer_state['start_time'] is None:
            return 'STOPPED'
        # Calculate the duration based on the actual start time
        total_duration_ms = (timer_state['target_end_time_ts'] - timer_state['start_time']) * 1000

    # Safety check: If running but duration is zero/invalid
    if total_duration_ms <= 0:
        return 'GREEN'

        # 4. Amber Check: 20% of the total planned duration
    twenty_percent_ms = total_duration_ms * 0.20

    if remaining_ms <= twenty_percent_ms:
        return 'AMBER'

    # 5. Green Check: Otherwise, it's green (running and positive, above 20%)
    return 'GREEN'


def get_timer_state_details():
    """Returns a dictionary with all details needed by client apps."""
    remaining_ms = calculate_remaining_ms()

    # The timer is running only if start_time is set
    is_running = timer_state['start_time'] is not None

    color = 'STOPPED'
    if is_running:
        color = get_status_color(remaining_ms)

    # Format current time of day (using the server's local time for display)
    server_time_of_day = datetime.now().strftime("%H:%M:%S")

    return {
        'remaining_ms': remaining_ms,
        'color': color,
        'is_running': is_running,
        'allow_negative': timer_state['allow_negative'],
        'total_duration_ms': timer_state['total_duration_ms'],
        'server_time_of_day': server_time_of_day,
        'mode': timer_state['mode']
    }


# --- CONTROL FUNCTIONS (Start/Stop/Set) ---

def start_timer():
    """Starts the currently loaded timer (Duration or Absolute)."""
    # Only start if a duration or target time has been set AND it's not already running
    if timer_state['total_duration_ms'] > 0 or timer_state['target_end_time_ts'] is not None:
        # If start_time is None, it means the timer is loaded but stopped/paused, so start it now
        if timer_state['start_time'] is None:
            timer_state['start_time'] = time.time()
        return True
    return False  # Cannot start if nothing is loaded.


def set_timer_duration_seconds(seconds):
    """Sets the timer duration from seconds and starts the timer immediately."""
    if seconds <= 0:
        cancel_timer()
        return True

    timer_state['total_duration_ms'] = seconds * 1000
    # FIX: Set start_time to now so the timer starts immediately upon "loading"
    timer_state['start_time'] = time.time()
    timer_state['target_end_time_ts'] = None  # Clear absolute target
    timer_state['mode'] = 'Duration'
    return True


def set_absolute_target_time(target_time_str):
    """
    Sets the timer to count down until a specific time today (HH:MM format) and starts it.
    """
    try:
        now_local = datetime.now()

        # Parse the target time components
        target_hour = int(target_time_str[:2])
        target_minute = int(target_time_str[3:5])

        # Create a datetime object for the target today
        target_dt_local = now_local.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)

        # If the target time is already past today, set it for tomorrow
        if target_dt_local <= now_local:
            target_dt_local = target_dt_local.replace(day=now_local.day + 1)

        # Convert to Unix timestamp
        target_ts = target_dt_local.timestamp()

        # Calculate the total duration from the moment of loading until the target time,
        # to correctly inform the color-coding logic.
        current_ts = time.time()
        initial_duration_s = target_ts - current_ts

        # Set the state
        timer_state['target_end_time_ts'] = target_ts
        # FIX: Set start_time to now so the timer starts immediately upon "loading"
        timer_state['start_time'] = current_ts
        timer_state['total_duration_ms'] = int(initial_duration_s * 1000)
        timer_state['mode'] = 'Absolute'

        return True

    except Exception as e:
        print(f"Error setting absolute time: {e}")
        return False


# --- Utility Functions ---

def cancel_timer():
    """Stops the timer and resets duration."""
    timer_state['total_duration_ms'] = 0
    timer_state['start_time'] = None
    timer_state['target_end_time_ts'] = None
    timer_state['mode'] = 'Duration'  # Reset to default mode


def adjust_timer(adjustment_seconds):
    """Adjusts the timer's remaining time by modifying the start time or total duration."""
    now = time.time()

    # If nothing is loaded, set a new duration
    if timer_state['total_duration_ms'] == 0 and timer_state['target_end_time_ts'] is None:
        return set_timer_duration_seconds(adjustment_seconds)

    # If running (start_time is set), adjust start/target time
    if timer_state['start_time'] is not None:
        if timer_state['mode'] == 'Duration':
            # Adjust the effective start time backwards to increase remaining time
            timer_state['start_time'] += adjustment_seconds

        elif timer_state['mode'] == 'Absolute':
            # Adjust the target end time
            timer_state['target_end_time_ts'] += adjustment_seconds
            # Recalculate duration for color logic
            timer_state['total_duration_ms'] = (timer_state['target_end_time_ts'] - timer_state['start_time']) * 1000

    # If loaded but not running (start_time is None), just adjust the total duration
    else:
        timer_state['total_duration_ms'] += int(adjustment_seconds * 1000)
        if timer_state['total_duration_ms'] < 0:
            timer_state['total_duration_ms'] = 0

    return True


def toggle_negative(allow):
    """Toggles whether the timer can count into negative numbers."""
    timer_state['allow_negative'] = allow


def get_current_schedule():
    """Determines if it's a weekday or weekend and returns the schedule."""
    today = datetime.now().weekday()  # Monday is 0, Sunday is 6
    is_weekend = today >= 5  # 5 is Saturday, 6 is Sunday

    if is_weekend:
        return {
            'schedule': timer_state['weekend_schedule'],
            'type': 'Weekend'
        }
    else:
        return {
            'schedule': timer_state['midweek_schedule'],
            'type': 'Midweek'

        }