from flask import Flask, render_template, request, redirect, url_for, flash
from datetime import datetime
from difflib import SequenceMatcher
import os

import firebase_admin
from firebase_admin import credentials, firestore

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FIREBASE_CREDENTIALS_PATH = os.path.join(
    BASE_DIR,
    'weone-automation-backend-log-firebase-adminsdk-fbsvc-3334b93cc2.json'
)
FIREBASE_PROJECT_ID = 'weone-automation-backend-log'
FIRESTORE_COLLECTION = 'logs'

cred = credentials.Certificate(FIREBASE_CREDENTIALS_PATH)
firebase_admin.initialize_app(cred, {'projectId': FIREBASE_PROJECT_ID})
db = firestore.client()
logs_collection = db.collection(FIRESTORE_COLLECTION)
LOCATIONS = [
    'Great Yarmouth',
    'Ipswich',
    'Kingslynn',
    'Peterborough',
    'Cambridge',
    'Chelmsford',
    'Norwich',
    'Colchester',
    'Diss',
    'Clacton on Sea',
    'Cromer',
    'Halesworth',
]

def load_logs():
    """Load all logs from Firestore"""
    logs = []
    for doc in logs_collection.stream():
        data = doc.to_dict() or {}
        if 'id' not in data:
            try:
                data['id'] = int(doc.id)
            except ValueError:
                data['id'] = doc.id
        logs.append(data)
    return logs


def get_next_log_id():
    """Get the next sequential log ID"""
    query = logs_collection.order_by('id', direction=firestore.Query.DESCENDING).limit(1)
    docs = list(query.stream())
    if docs:
        latest = docs[0].to_dict() or {}
        return int(latest.get('id', 0)) + 1
    return 1


def upsert_log(log_id, payload):
    """Create or replace a log document"""
    doc_ref = logs_collection.document(str(log_id))
    payload['id'] = log_id
    doc_ref.set(payload)


def get_log(log_id):
    """Fetch a single log by ID"""
    doc = logs_collection.document(str(log_id)).get()
    if not doc.exists:
        return None
    data = doc.to_dict() or {}
    data['id'] = log_id
    return data


def current_date_str():
    return datetime.now().strftime('%Y-%m-%d')


def normalize_location(value):
    return value.strip() if value else ''


def locations_match(value, other, threshold=0.8):
    value_norm = normalize_location(value).lower()
    other_norm = normalize_location(other).lower()
    if not value_norm or not other_norm:
        return False
    return SequenceMatcher(None, value_norm, other_norm).ratio() >= threshold


def get_unique_locations(logs, threshold=0.85):
    unique = []
    for log in logs:
        loc = normalize_location(log.get('location', ''))
        if not loc:
            continue
        if not any(locations_match(loc, existing, threshold) for existing in unique):
            unique.append(loc)
    return sorted(unique)


def get_unique_campaigns(logs):
    campaigns = {log.get('campaign_number') for log in logs if log.get('campaign_number')}
    return sorted(campaigns)


def get_unique_dates(logs):
    dates = {log.get('log_date') for log in logs if log.get('log_date')}
    return sorted(dates)


def parse_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default

@app.route('/')
def landing():
    """Landing page with Posting Logs button"""
    return render_template('landing.html')

@app.route('/logs')
def logs():
    """Page with View Log and Add Log buttons"""
    return render_template('logs.html')

@app.route('/add_log')
def add_log_form():
    """Form page to add new log"""
    return render_template('add_log.html', locations=LOCATIONS, today=current_date_str())

@app.route('/submit_log', methods=['POST'])
def submit_log():
    """Handle log form submission"""
    try:
        # Get form data
        selections = request.form.getlist('locations')
        campaign_number = request.form.get('campaign_number', '').strip()
        errors = request.form.get('errors', '').strip()
        terminal_success = parse_int(request.form.get('terminal_success'))
        log_date = request.form.get('log_date', '').strip() or current_date_str()
        abnormal = request.form.get('abnormal') == 'on'
        
        # Validate required fields
        selected_locations = [loc for loc in selections if loc in LOCATIONS]

        if not selected_locations or not campaign_number:
            flash('Please select at least one valid location and provide a Campaign Number.', 'error')
            return redirect(url_for('add_log_form'))
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        next_id = get_next_log_id()

        for loc in selected_locations:
            new_log = {
                'location': loc,
                'campaign_number': campaign_number,
                'errors': errors,
                'terminal_success': terminal_success,
                'log_date': log_date,
                'abnormal': abnormal,
                'timestamp': timestamp,
            }
            upsert_log(next_id, new_log)
            next_id += 1
        
        if len(selected_locations) > 1:
            flash(f'Log added for {len(selected_locations)} locations.', 'success')
        else:
            flash('Log successfully added!', 'success')
        return redirect(url_for('view_logs'))
        
    except Exception as e:
        flash(f'Error saving log: {str(e)}', 'error')
        return redirect(url_for('add_log_form'))

@app.route('/view_logs')
def view_logs():
    """Display all submitted logs"""
    logs = load_logs()
    unique_locations = get_unique_locations(logs)
    
    selected_location = request.args.get('location', '').strip()
    selected_campaign = request.args.get('campaign', '').strip()
    selected_date = request.args.get('log_date', '').strip()
    selected_abnormal = request.args.get('abnormal', '').strip()

    if selected_location:
        filtered_logs = [
            log for log in logs
            if locations_match(log.get('location', ''), selected_location)
        ]
    else:
        filtered_logs = logs

    if selected_date:
        filtered_logs = [
            log for log in filtered_logs
            if log.get('log_date', '').strip() == selected_date
        ]

    if selected_abnormal in {'abnormal', 'normal'}:
        should_be_abnormal = selected_abnormal == 'abnormal'
        filtered_logs = [
            log for log in filtered_logs
            if bool(log.get('abnormal')) == should_be_abnormal
        ]

    unique_campaigns = get_unique_campaigns(filtered_logs)

    if selected_campaign and selected_campaign not in unique_campaigns:
        selected_campaign = ''
    if selected_campaign:
        filtered_logs = [
            log for log in filtered_logs
            if log.get('campaign_number', '').strip() == selected_campaign
        ]

    unique_dates = get_unique_dates(filtered_logs)

    sorted_logs = sorted(
        filtered_logs,
        key=lambda log: (not log.get('abnormal', False), log.get('timestamp', ''))
    )

    return render_template(
        'view_logs.html',
        logs=sorted_logs,
        unique_locations=unique_locations,
        unique_campaigns=unique_campaigns,
        unique_dates=unique_dates,
        selected_location=selected_location,
        selected_campaign=selected_campaign,
        selected_date=selected_date,
        selected_abnormal=selected_abnormal,
    )


@app.route('/edit_log/<int:log_id>')
def edit_log(log_id):
    """Render edit form for a specific log entry"""
    log = get_log(log_id)

    if not log:
        flash('Log entry not found.', 'error')
        return redirect(url_for('view_logs'))

    return render_template('edit_log.html', log=log, locations=LOCATIONS, today=current_date_str())


@app.route('/update_log/<int:log_id>', methods=['POST'])
def update_log(log_id):
    """Persist edits for an existing log entry"""
    try:
        existing_log = get_log(log_id)
        if existing_log is None:
            flash('Log entry not found.', 'error')
            return redirect(url_for('view_logs'))

        location = request.form.get('location', '').strip()
        campaign_number = request.form.get('campaign_number', '').strip()
        errors = request.form.get('errors', '').strip()
        terminal_items = request.form.get('terminal_items', '').strip()
        facebook_items = request.form.get('facebook_items', '').strip()
        log_date = request.form.get('log_date', '').strip() or current_date_str()
        abnormal = request.form.get('abnormal') == 'on'

        if location not in LOCATIONS or not campaign_number:
            flash('Please select a valid location and provide a Campaign Number.', 'error')
            return redirect(url_for('edit_log', log_id=log_id))

        updated_log = {
            'location': location,
            'campaign_number': campaign_number,
            'errors': errors,
            'terminal_success': terminal_success,
            'log_date': log_date,
            'abnormal': abnormal,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }

        upsert_log(log_id, updated_log)

        flash('Log successfully updated!', 'success')
        return redirect(url_for('view_logs'))

    except Exception as e:
        flash(f'Error updating log: {str(e)}', 'error')
        return redirect(url_for('edit_log', log_id=log_id))


@app.route('/delete_log/<int:log_id>', methods=['POST'])
def delete_log(log_id):
    """Delete a log entry"""
    try:
        doc_ref = logs_collection.document(str(log_id))
        if not doc_ref.get().exists:
            flash('Log entry not found.', 'error')
            return redirect(url_for('view_logs'))

        doc_ref.delete()
        flash('Log deleted successfully.', 'success')
        return redirect(url_for('view_logs'))

    except Exception as e:
        flash(f'Error deleting log: {str(e)}', 'error')
        return redirect(url_for('view_logs'))

if __name__ == '__main__':
    app.run(debug=True)
