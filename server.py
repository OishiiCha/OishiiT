from flask import Flask, request, jsonify, render_template, redirect, url_for
from dotenv import load_dotenv
import os
import core  # Import the core logic file

# Load environment variables from .env file
load_dotenv()

# --- CONFIGURATION ---
HARDCODED_PIN = os.getenv('PIN_CODE')
if not HARDCODED_PIN:
    print("FATAL ERROR: PIN_CODE not found in .env file. Using default '0000'.")
    HARDCODED_PIN = '0000'  # Fallback for safety

app = Flask(__name__)
app.template_folder = 'templates'


# --- FLASK ROUTES ---

@app.route('/')
def index():
    """Redirects base URL to the login page."""
    return redirect(url_for('login_page'))


@app.route('/login')
def login_page():
    """Renders the login panel template."""
    return render_template('login.html')


@app.route('/logout')
def logout():
    """Handles client-side logout (clearing local storage) and redirects to login."""
    return redirect(url_for('login_page'))


@app.route('/control')
def control_panel():
    """Renders the control panel template (protected by client-side JS check)."""
    schedule_info = core.get_current_schedule()
    return render_template('control.html', schedule=schedule_info['schedule'], schedule_type=schedule_info['type'])


@app.route('/display')
def display_page():
    """Renders the timer display page."""
    return render_template('display.html')


@app.route('/api/login', methods=['POST'])
def api_login():
    """Authenticates the user using the PIN code."""
    data = request.get_json()
    pin = data.get('pin')

    if pin == HARDCODED_PIN:
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'error': 'Invalid PIN'}), 401


# --- API ENDPOINTS ---

@app.route('/api/update_schedules', methods=['POST'])
def update_schedules_route():
    """Endpoint to trigger the schedule scraping and file update."""
    try:
        result = core.update_schedules()
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 500
    except Exception as e:
        print(f"Server error during schedule update: {e}")
        return jsonify({'success': False, 'error': 'Internal server error during update process.'}), 500


@app.route('/api/start_timer', methods=['POST'])
def start_timer_route():
    """Endpoint to start the timer."""
    if core.start_timer():
        return jsonify({'success': True, 'message': 'Timer started.'})
    return jsonify({'success': False, 'error': 'No duration set to start.'}), 400


@app.route('/api/set_duration', methods=['POST'])
def set_duration():
    """Endpoint to set a timer duration in seconds."""
    try:
        data = request.get_json()
        seconds = int(data.get('seconds', 0))

        if core.set_timer_duration_seconds(seconds):
            return jsonify({'success': True, 'seconds': seconds})
        else:
            return jsonify({'success': False, 'error': 'Invalid duration value.'}), 400

    except Exception as e:
        return jsonify({'error': 'Invalid request format.'}), 400


@app.route('/api/set_target_time', methods=['POST'])
def set_target_time():
    """Endpoint to set a countdown target time (HH:MM)."""
    try:
        data = request.get_json()
        target_time = data.get('target_time')

        if core.set_absolute_target_time(target_time):
            return jsonify({'success': True, 'target_time': target_time})
        else:
            return jsonify({'success': False, 'error': 'Invalid time format or target time.'}), 400
    except Exception as e:
        return jsonify({'error': 'Invalid request format or server error.'}), 500


@app.route('/api/cancel', methods=['POST'])
def cancel_timer_route():
    """Endpoint to stop the timer and optionally freeze the display."""
    core.cancel_timer()
    return jsonify({'success': True, 'message': 'Timer cancelled.'})


@app.route('/api/adjust_time', methods=['POST'])
def adjust_time():
    """Endpoint to add or remove time from a running timer."""
    try:
        data = request.get_json()
        adjustment_seconds = int(data.get('adjustment_seconds', 0))

        if core.adjust_timer(adjustment_seconds):
            return jsonify({'success': True, 'adjustment_seconds': adjustment_seconds})
        else:
            # This path is generally unreachable with current core.py logic, but kept for robustness.
            return jsonify({'success': False, 'error': 'Invalid adjustment value.'}), 400

    except Exception as e:
        print(f"Error adjusting time: {e}")
        return jsonify({'error': 'Invalid request format or server error.'}), 500


@app.route('/api/toggle_negative', methods=['POST'])
def toggle_negative_route():
    """Endpoint to toggle the allow_negative state."""
    try:
        data = request.get_json()
        allow = data.get('allow_negative', False)
        core.toggle_negative(allow)
        return jsonify({'success': True, 'allow_negative': allow})
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/state', methods=['GET'])
def get_state():
    """Endpoint for the clients to poll the current timer state."""
    state = core.get_timer_state_details()
    return jsonify(state)


# Standard Flask run block (unchanged)
if __name__ == '__main__':
    # Ensure the schedules directory exists
    if not os.path.exists(core.timer_state['schedules_dir']):
        os.makedirs(core.timer_state['schedules_dir'])

    app.run(debug=True, host='0.0.0.0', port=80)