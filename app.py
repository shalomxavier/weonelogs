from flask import Flask, render_template, request, redirect, url_for, flash
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from collections import defaultdict
import os
from urllib.parse import urlencode

import firebase_admin
from firebase_admin import credentials, firestore

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FIREBASE_CREDENTIALS_PATH = os.getenv('FIREBASE_CREDENTIALS_PATH') or os.path.join(
    BASE_DIR,
    'weone-automation-backend-log-firebase-adminsdk-fbsvc-37b4b3fd3c.json'
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


def filter_recent_logs(logs, days=8):
    """Return logs whose log_date falls within the last `days` days inclusive."""
    if days <= 0:
        return []

    today = datetime.now().date()
    window_start = today - timedelta(days=days - 1)

    recent_logs = []
    for log in logs:
        date_str = (log.get('log_date') or '').strip()
        if not date_str:
            continue
        try:
            log_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            continue
        if window_start <= log_date <= today:
            recent_logs.append(log)

    return recent_logs


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


def resolve_known_location(value):
    for loc in LOCATIONS:
        if locations_match(value, loc):
            return loc
    return None


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


def find_campaign_location_gaps(logs):
    campaign_locations = defaultdict(set)

    for log in logs:
        campaign = (log.get('campaign_number') or '').strip()
        if not campaign:
            continue

        matched_location = resolve_known_location(log.get('location', ''))
        if matched_location:
            campaign_locations[campaign].add(matched_location)

    warnings = []
    for campaign, present_locations in campaign_locations.items():
        missing_locations = [loc for loc in LOCATIONS if loc not in present_locations]
        if missing_locations:
            warnings.append(
                {
                    'campaign': campaign,
                    'missing_locations': missing_locations,
                }
            )

    return sorted(warnings, key=lambda entry: entry['campaign'])


def campaign_location_exists(campaign_number, location, log_date, exclude_id=None):
    if not campaign_number or not location or not log_date:
        return False

    canonical_location = resolve_known_location(location)
    if not canonical_location:
        return False

    query = (
        logs_collection.where('campaign_number', '==', campaign_number)
        .where('log_date', '==', log_date)
    )
    for doc in query.stream():
        data = doc.to_dict() or {}
        existing_id = data.get('id') or doc.id
        if exclude_id and str(existing_id) == str(exclude_id):
            continue

        matched_location = resolve_known_location(data.get('location', ''))
        if matched_location == canonical_location:
            return True

    return False


def calculate_weekly_terminal_success(logs):
    today = datetime.now().date()
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=5)

    total = 0
    for log in logs:
        log_date_str = (log.get('log_date') or '').strip()
        if not log_date_str:
            continue
        try:
            log_date = datetime.strptime(log_date_str, '%Y-%m-%d').date()
        except ValueError:
            continue

        if start_of_week <= log_date <= end_of_week:
            total += parse_int(log.get('terminal_success'), 0)

    return total

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
    return render_template('add_log.html', locations=LOCATIONS)

@app.route('/submit_log', methods=['POST'])
def submit_log():
    """Handle log form submission"""
    try:
        # Get form data
        selections = request.form.getlist('locations')
        campaign_number = request.form.get('campaign_number', '').strip()
        errors = request.form.get('errors', '').strip()
        terminal_success_input = request.form.get('terminal_success', '').strip()
        log_date = request.form.get('log_date', '').strip()

        if not log_date:
            flash('Please select a log date.', 'error')
            return redirect(url_for('add_log_form'))

        if not terminal_success_input:
            flash('Please enter the terminal success count.', 'error')
            return redirect(url_for('add_log_form'))

        terminal_success = parse_int(terminal_success_input)

        status_normal = request.form.get('status_normal') == 'on'
        status_abnormal = request.form.get('status_abnormal') == 'on'
        if status_normal == status_abnormal:
            flash('Select exactly one status (Normal or Abnormal).', 'error')
            return redirect(url_for('add_log_form'))
        abnormal = status_abnormal
        
        # Validate required fields
        selected_locations = [loc for loc in selections if loc in LOCATIONS]

        if not selected_locations or not campaign_number:
            flash('Please select at least one valid location and provide a Campaign Number.', 'error')
            return redirect(url_for('add_log_form'))

        duplicates = [
            loc for loc in selected_locations
            if campaign_location_exists(campaign_number, loc, log_date)
        ]
        if duplicates:
            formatted = ', '.join(sorted(set(duplicates)))
            flash(f'Campaign {campaign_number} already has entries for: {formatted}. Remove duplicates before submitting.', 'error')
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
    logs = filter_recent_logs(load_logs(), days=8)
    unique_locations = get_unique_locations(logs)
    
    selected_locations = [
        value.strip() for value in request.args.getlist('location') if value.strip()
    ]
    selected_campaigns = [
        value.strip() for value in request.args.getlist('campaign') if value.strip()
    ]
    selected_date = request.args.get('log_date', '').strip()
    selected_abnormal = request.args.get('abnormal', '').strip()

    if selected_locations:
        filtered_logs = [
            log for log in logs
            if any(
                locations_match(log.get('location', ''), selected_location)
                for selected_location in selected_locations
            )
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

    if selected_campaigns:
        selected_campaigns = [
            campaign for campaign in selected_campaigns
            if campaign in unique_campaigns
        ]
    if selected_campaigns:
        filtered_logs = [
            log for log in filtered_logs
            if log.get('campaign_number', '').strip() in selected_campaigns
        ]

    unique_dates = get_unique_dates(filtered_logs)
    weekly_terminal_success = calculate_weekly_terminal_success(filtered_logs)

    other_filters_active = any(
        [selected_locations, selected_campaigns, selected_date, selected_abnormal]
    )
    if other_filters_active:
        campaign_warnings = []
    else:
        campaign_warnings = find_campaign_location_gaps(filtered_logs)

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
        selected_locations=selected_locations,
        selected_campaigns=selected_campaigns,
        selected_date=selected_date,
        selected_abnormal=selected_abnormal,
        weekly_terminal_success=weekly_terminal_success,
        campaign_warnings=campaign_warnings,
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
        terminal_success_input = request.form.get('terminal_success', '').strip()
        log_date = request.form.get('log_date', '').strip()

        if not log_date:
            flash('Please select a log date.', 'error')
            return redirect(url_for('edit_log', log_id=log_id))

        if not terminal_success_input:
            flash('Please enter the terminal success count.', 'error')
            return redirect(url_for('edit_log', log_id=log_id))

        terminal_success = parse_int(terminal_success_input)

        status_normal = request.form.get('status_normal') == 'on'
        status_abnormal = request.form.get('status_abnormal') == 'on'
        if status_normal == status_abnormal:
            flash('Select exactly one status (Normal or Abnormal).', 'error')
            return redirect(url_for('edit_log', log_id=log_id))
        abnormal = status_abnormal

        if location not in LOCATIONS or not campaign_number:
            flash('Please select a valid location and provide a Campaign Number.', 'error')
            return redirect(url_for('edit_log', log_id=log_id))

        if campaign_location_exists(campaign_number, location, log_date, exclude_id=log_id):
            flash('Another log already exists for this Campaign, Location, and Date combination.', 'error')
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
        redirect_url = url_for('view_logs')

        filter_pairs = []
        for key in ('location', 'campaign'):
            for value in request.form.getlist(key):
                if value.strip():
                    filter_pairs.append((key, value.strip()))

        log_date = request.form.get('log_date', '').strip()
        abnormal = request.form.get('abnormal', '').strip()
        if log_date:
            filter_pairs.append(('log_date', log_date))
        if abnormal:
            filter_pairs.append(('abnormal', abnormal))

        if filter_pairs:
            redirect_url = f"{redirect_url}?{urlencode(filter_pairs, doseq=True)}"

        return redirect(redirect_url)

    except Exception as e:
        flash(f'Error deleting log: {str(e)}', 'error')
        return redirect(url_for('view_logs'))

if __name__ == '__main__':
    app.run(debug=True)
