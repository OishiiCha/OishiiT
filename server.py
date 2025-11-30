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
def display_screen():
    """Renders the full-screen display template (no authentication needed here)."""
    return render_template('display.html')


# --- API ENDPOINTS ---

@app.route('/api/login', methods=['POST'])
def login():
    """Endpoint to validate the login PIN against the .env variable."""
    try:
        data = request.get_json()
        pin = data.get('pin')

        if not pin or len(pin) != 4 or not pin.isdigit():
            return jsonify({'error': 'Invalid PIN format.'}), 400

        # Authentication check uses the securely loaded environment variable
        if pin == HARDCODED_PIN:
            return jsonify({'success': True, 'token': 'mock-secure-token-123'}), 200
        else:
            return jsonify({'error': 'Invalid PIN.'}), 401

    except Exception as e:
        print(f"Error during login: {e}")
        return jsonify({'error': 'Server error.'}), 500


@app.route('/api/set_duration', methods=['POST'])
def set_duration():
    """Endpoint to set the total timer duration (in seconds) and start the timer."""
    try:
        data = request.get_json()
        seconds = int(data.get('seconds', 0))

        if core.set_timer_duration_seconds(seconds):
            return jsonify({'success': True, 'total_duration_seconds': seconds})
        else:
            return jsonify({'error': 'Time must be positive.'}), 400

    except Exception as e:
        print(f"Error setting duration: {e}")
        return jsonify({'error': 'Invalid request format or server error.'}), 500


@app.route('/api/set_target_time', methods=['POST'])
def set_target_time():
    """Endpoint to set the timer to count down to a specific time (HH:MM)."""
    try:
        data = request.get_json()
        target_time = data.get('target_time')  # e.g., "14:30"

        if core.set_absolute_target_time(target_time):
            return jsonify({'success': True, 'target_time': target_time})
        else:
            return jsonify({'error': 'Invalid target time format or setting error.'}), 400

    except Exception as e:
        print(f"Error setting target time: {e}")
        return jsonify({'error': 'Invalid request format or server error.'}), 500


@app.route('/api/cancel', methods=['POST'])
def cancel_timer_route():
    """Endpoint to stop the timer and reset the state."""
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
    state_details = core.get_timer_state_details()
    return jsonify(state_details)


# --- RUN APPLICATION ---
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80, debug=False)