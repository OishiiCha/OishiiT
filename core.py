import time
from datetime import datetime, timedelta
import pytz
import json
import os
from config import INITIAL_STATE
import schedule  # ADDED: Import the schedule module

# Define UTC timezone for consistency
TIMEZONE = pytz.utc

# --- Constants ---
GREEN_THRESHOLD = 300000
AMBER_THRESHOLD = 60000
FROZEN_DURATION_SECONDS = 10  # Duration to hold the time on screen

# --- Timer State Management ---
timer_state = INITIAL_STATE.copy()

# Add keys for the freeze feature if they don't exist
timer_state['frozen_end_time_ts'] = None
timer_state['frozen_remaining_ms'] = 0
timer_state['frozen_color'] = 'STOPPED'


# --- Schedule Loading Function (Standard) ---
def get_current_monday():
    today = datetime.now()
    days_to_subtract = today.weekday()
    return today - timedelta(days=days_to_subtract)


def load_midweek_schedule():
    schedules_dir = timer_state['schedules_dir']
    try:
        monday_date = get_current_monday()
        filename = monday_date.strftime('%Y%m%d') + ".json"
        path = os.path.join(schedules_dir, filename)

        with open(path, 'r', encoding='utf-8') as f:
            schedule_data = json.load(f)
            return [{
                "section": i.get("category") or i.get("week_title"),
                "name": i.get("title"),
                "duration_seconds": i.get('duration', 0) * 60
            } for i in schedule_data]
    except Exception as e:
        print(f"Schedule load error: {e}")
        return []


# --- Core Logic Helpers ---

def clear_frozen_display():
    """Resets the freeze state."""
    timer_state['frozen_end_time_ts'] = None
    timer_state['frozen_remaining_ms'] = 0
    timer_state['frozen_color'] = 'STOPPED'


def get_running_color(remaining_ms):
    """Calculates color for a running timer."""
    if remaining_ms < 0: return 'RED'

    # Calculate effective total duration for Absolute mode
    total = timer_state['total_duration_ms']
    if timer_state['mode'] == 'Absolute':
        if timer_state['target_end_time_ts'] and timer_state['start_time']:
            total = (timer_state['target_end_time_ts'] - timer_state['start_time']) * 1000

    if total <= 0: return 'GREEN'
    if remaining_ms <= AMBER_THRESHOLD: return 'AMBER'
    return 'GREEN'


def calculate_remaining_ms():
    """Calculates time, respecting the freeze state."""
    # 1. If Frozen, return frozen time
    if timer_state['frozen_end_time_ts'] and time.time() < timer_state['frozen_end_time_ts']:
        return timer_state['frozen_remaining_ms']

    # 2. If Stopped (and not frozen), return loaded total or 0
    if timer_state['start_time'] is None:
        return timer_state['total_duration_ms']

    # 3. If Running, calculate live time
    now = time.time()
    remaining = 0

    if timer_state['mode'] == 'Duration':
        elapsed = int((now - timer_state['start_time']) * 1000)
        remaining = timer_state['total_duration_ms'] - elapsed
    elif timer_state['mode'] == 'Absolute' and timer_state['target_end_time_ts']:
        remaining = int((timer_state['target_end_time_ts'] - now) * 1000)

    # Auto-freeze logic: If time runs out and negative is NOT allowed
    if not timer_state['allow_negative'] and remaining < 0:
        timer_state['frozen_remaining_ms'] = 0
        timer_state['frozen_color'] = 'RED'
        timer_state['frozen_end_time_ts'] = now + FROZEN_DURATION_SECONDS
        timer_state['start_time'] = None  # Stop the timer
        return 0

    return remaining


def get_status_color(remaining_ms):
    # 1. Return Frozen Color
    if timer_state['frozen_end_time_ts'] and time.time() < timer_state['frozen_end_time_ts']:
        return timer_state['frozen_color']
    # 2. Return Stopped/Ready Color
    if timer_state['start_time'] is None:
        return 'STOPPED'
    # 3. Return Running Color
    return get_running_color(remaining_ms)


def get_timer_state_details():
    # Expire freeze if time passed
    if timer_state['frozen_end_time_ts'] and time.time() >= timer_state['frozen_end_time_ts']:
        clear_frozen_display()

    ms = calculate_remaining_ms()
    is_frozen = timer_state['frozen_end_time_ts'] is not None
    is_running = timer_state['start_time'] is not None

    # Force color calculation if running or frozen
    color = get_status_color(ms) if (is_running or is_frozen) else 'STOPPED'

    return {
        'remaining_ms': ms,
        'color': color,
        'is_running': is_running,
        'is_frozen': is_frozen,
        'allow_negative': timer_state['allow_negative'],
        'total_duration_ms': timer_state['total_duration_ms'],
        'server_time_of_day': datetime.now().strftime("%H:%M:%S"),
        'mode': timer_state['mode']
    }


# --- Actions ---

def update_schedules():
    """Triggers the schedule scraping logic from schedule.py."""
    try:
        # Assumes schedule.py exposes 'get_schedules_for_weeks' to scrape the next 4 weeks
        saved_count = schedule.get_schedules_for_weeks(4)

        return {'success': True, 'message': f'Successfully saved {saved_count} new meeting schedules.'}
    except Exception as e:
        # Log the error for server-side debugging
        print(f"Schedule update failed: {e}")
        return {'success': False, 'error': f'Schedule update failed: {e}'}


def start_timer():
    if timer_state['total_duration_ms'] > 0 or timer_state['target_end_time_ts']:
        if not timer_state['start_time']:
            clear_frozen_display()
            timer_state['start_time'] = time.time()
        return True
    return False


def set_timer_duration_seconds(seconds):
    clear_frozen_display()
    if seconds <= 0:
        cancel_timer()
        return True
    timer_state['total_duration_ms'] = seconds * 1000
    timer_state['start_time'] = time.time()
    timer_state['target_end_time_ts'] = None
    timer_state['mode'] = 'Duration'
    return True


def set_absolute_target_time(target_time_str):
    try:
        clear_frozen_display()
        now = datetime.now()
        h, m = map(int, target_time_str.split(':'))
        target = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if target <= now: target += timedelta(days=1)

        timer_state['target_end_time_ts'] = target.timestamp()
        timer_state['start_time'] = time.time()
        timer_state['total_duration_ms'] = int((target.timestamp() - time.time()) * 1000)
        timer_state['mode'] = 'Absolute'
        return True
    except:
        return False


def cancel_timer():
    """Stops timer. If it WAS running, freeze the display on the final time."""
    was_running = timer_state['start_time'] is not None

    # Calculate final state before clearing
    final_ms = 0
    final_color = 'STOPPED'

    if was_running:
        now = time.time()
        if timer_state['mode'] == 'Duration':
            elapsed = int((now - timer_state['start_time']) * 1000)
            final_ms = timer_state['total_duration_ms'] - elapsed
        elif timer_state['mode'] == 'Absolute' and timer_state['target_end_time_ts']:
            final_ms = int((timer_state['target_end_time_ts'] - now) * 1000)

        final_color = get_running_color(final_ms)

    # Reset
    timer_state['total_duration_ms'] = 0
    timer_state['start_time'] = None
    timer_state['target_end_time_ts'] = None
    timer_state['mode'] = 'Duration'
    clear_frozen_display()

    # Apply Freeze
    if was_running:
        # If negative not allowed and we went negative, snap to 0
        if not timer_state['allow_negative'] and final_ms < 0:
            final_ms = 0

        timer_state['frozen_remaining_ms'] = final_ms
        timer_state['frozen_color'] = final_color
        timer_state['frozen_end_time_ts'] = time.time() + FROZEN_DURATION_SECONDS


def adjust_timer(seconds):
    clear_frozen_display()
    if not timer_state['start_time']:
        # If stopped, just change the loaded duration
        timer_state['total_duration_ms'] = max(0, timer_state['total_duration_ms'] + (seconds * 1000))
        return True

    if timer_state['mode'] == 'Duration':
        timer_state['start_time'] += seconds
    elif timer_state['mode'] == 'Absolute' and timer_state['target_end_time_ts']:
        timer_state['target_end_time_ts'] += seconds
        timer_state['total_duration_ms'] = int((timer_state['target_end_time_ts'] - timer_state['start_time']) * 1000)
    return True


def toggle_negative(allow):
    timer_state['allow_negative'] = allow


def get_current_schedule():
    # (Simplified for brevity, assumes dynamic loading works as before)
    is_weekend = datetime.now().weekday() >= 5
    if is_weekend: return {'schedule': timer_state['weekend_schedule'], 'type': 'Weekend'}
    return {'schedule': load_midweek_schedule(), 'type': 'Midweek'}