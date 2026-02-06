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
- **Data Persistence**: Logs stored in JSON file

## Installation

1. Install Flask:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the application:
   ```bash
   python app.py
   ```

3. Open your browser and navigate to `http://127.0.0.1:5000`

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

Logs are stored in `logs.json` in the project root directory. Each log entry contains:
- ID
- Location
- Campaign Number
- Errors (if any)
- Terminal posting count
- Facebook posting count
- Timestamp

## Technologies Used

- **Flask**: Web framework
- **HTML5**: Markup
- **CSS3**: Styling with responsive design
- **JavaScript**: Basic interactivity
- **JSON**: Data storage
