# Log Management System

A Flask-based web application for managing posting logs with a clean, modern interface.

## Features

- **Landing Page**: Welcome page with "Posting Logs" button
- **Logs Management Page**: Access to "View Log" and "Add Log" functions
- **Add Log Form**: Comprehensive form with the following fields:
  - Location (required)
  - Campaign Number (required)
  - Errors (paragraph text area)
  - Total Items Successfully Posted (Terminal)
  - Total Items Successfully Posted (Facebook)
- **View Logs Page**: Display all submitted logs with timestamps and statistics
- **Responsive Design**: Works on desktop and mobile devices
- **Data Persistence**: Logs stored in Firebase Firestore

## Installation

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Provide Firebase credentials:
   - Obtain the shared Firebase service-account JSON file (not tracked in git)
   - Either place it in the project root with the name `weone-automation-backend-log-firebase-adminsdk-fbsvc-37b4b3fd3c.json`, **or** set an environment variable pointing to its location:
     ```bash
     # Windows (PowerShell)
     setx FIREBASE_CREDENTIALS_PATH "C:\\path\\to\\service-account.json"

     # macOS/Linux
     export FIREBASE_CREDENTIALS_PATH="/path/to/service-account.json"
     ```

3. Run the application:
   ```bash
   python app.py
   ```

4. Open your browser and navigate to `http://127.0.0.1:5000`

## Usage

1. **Start**: Open the landing page at `http://127.0.0.1:5000`
2. **Access Logs**: Click "Posting Logs" to go to the logs management page
3. **Add Log**: Click "Add Log" to fill out the form with your posting data
4. **View Logs**: Click "View Log" to see all previously submitted logs

## File Structure

```
windsurf-project/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── logs.json             # Data storage (created automatically)
├── templates/
│   ├── landing.html      # Landing page
│   ├── logs.html         # Logs management page
│   ├── add_log.html      # Add log form
│   └── view_logs.html    # View all logs
└── static/
    └── css/
        └── style.css     # Styling
```

## Data Storage

Logs are stored in the `logs` collection inside the Firebase project (`weone-automation-backend-log`). Each log entry contains:
- ID
- Location
- Campaign Number
- Errors (if any)
- Terminal posting count
- Facebook posting count
- Abnormal flag
- Timestamp

## Collaborating Securely

1. **Credential sharing**: Exchange the Firebase service-account JSON file via a secure channel (password manager, encrypted archive, etc.). Do **not** commit it to the repository—`.gitignore` already excludes `*-firebase-adminsdk-*.json`.
2. **Environment configuration**: Each collaborator sets `FIREBASE_CREDENTIALS_PATH` (or stores the file at the default path) so the Flask app can authenticate with Firebase.
3. **Data sync**: Because Firestore is the single source of truth, all teammates automatically see the same data once authenticated.

## Technologies Used

- **Flask**: Web framework
- **HTML5**: Markup
- **CSS3**: Styling with responsive design
- **JavaScript**: Basic interactivity
- **JSON**: Data storage
