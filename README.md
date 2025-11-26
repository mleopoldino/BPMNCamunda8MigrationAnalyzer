# BPMN Migration Analyzer - Web Application

A modern web application for analyzing Camunda 7 BPMN files for migration to Camunda 8.

## Features

- 📤 **Upload BPMN Files**: Drag and drop or browse for .bpmn and .xml files
- 🔍 **Comprehensive Analysis**: Deep analysis of all BPMN elements with migration impact assessment
- 📊 **Interactive Dashboard**: Beautiful, responsive dashboard with real-time results
- 🎯 **Severity Classification**: Issues categorized as CRITICAL, WARNING, or INFO
- 📈 **Migration Complexity Assessment**: Automatic evaluation of migration effort required
- 💾 **Export Results**: Download analysis results as JSON or CSV
- 🎨 **Modern UI**: Clean, professional interface with smooth animations

## Project Structure

```
Camunda7BPMNMigration/
├── app.py                  # Flask backend application
├── bpmn_migration.py       # Core BPMN analyzer (CLI version)
├── templates/
│   └── index.html          # Main web interface
├── static/
│   ├── style.css           # Stylesheet
│   └── script.js           # Frontend JavaScript
├── uploads/                # Temporary upload folder (auto-created)
├── requirements.txt        # Python dependencies
└── README_WEB_APP.md       # This file
```

## Installation

### Prerequisites

- Python 3.8 or higher
- pip (Python package manager)

### Setup

1. **Clone or navigate to the project directory**:
   ```bash
   cd /Users/marcelo/PycharmProjects/Camunda7BPMNMigration
   ```

2. **Activate the virtual environment** (if not already activated):
   ```bash
   source .venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## Running the Application

### Start the Web Server

```bash
python app.py
```

The application will start on `http://localhost:5001`

### Access the Application

1. Open your web browser
2. Navigate to `http://localhost:5001`
3. Upload a BPMN file using the interface
4. Click "Analyze BPMN" to process the file
5. View the comprehensive analysis results in the dashboard

## Using the Application

### Step 1: Upload BPMN File

- Click the "Browse" button or the file input area
- Select a `.bpmn` or `.xml` file (max 16MB)
- The filename will be displayed

### Step 2: Analyze

- Click the "Analyze BPMN" button
- Wait for the analysis to complete (usually takes a few seconds)
- The dashboard will automatically appear with results

### Step 3: Review Results

The dashboard displays:

- **Summary Cards**: Quick overview of elements, issues, and variables
- **File Information**: Name and analysis timestamp
- **Complexity Assessment**: Overall migration complexity (LOW/MEDIUM/HIGH)
- **Element Breakdown**: Count of each BPMN element type
- **Issues by Category**: Distribution of issues across categories
- **Detailed Issues**: Tabbed view of CRITICAL, WARNING, and INFO issues
- **Process Variables**: All variables detected in expressions

### Step 4: Export Results

- **Export JSON**: Download complete analysis data in JSON format
- **Export CSV**: Download issues list in CSV format for Excel/spreadsheets

## API Endpoints

The application provides the following REST API endpoints:

### POST /analyze

Analyze a BPMN file.

**Request:**
- Method: `POST`
- Content-Type: `multipart/form-data`
- Body: `file` (BPMN file)

**Response:**
```json
{
  "success": true,
  "data": {
    "file": "process.bpmn",
    "timestamp": "2025-11-25T10:30:00",
    "statistics": { ... },
    "issues": [ ... ],
    "process_variables": [ ... ]
  }
}
```

### GET /health

Health check endpoint.

**Response:**
```json
{
  "status": "ok"
}
```

## Configuration

You can modify the following settings in `app.py`:

- `UPLOAD_FOLDER`: Directory for temporary file uploads (default: `uploads`)
- `ALLOWED_EXTENSIONS`: Allowed file extensions (default: `bpmn`, `xml`)
- `MAX_FILE_SIZE`: Maximum upload size in bytes (default: 16MB)
- `host`: Server host (default: `0.0.0.0`)
- `port`: Server port (default: `5001`)

## Development

### File Structure

**Backend (`app.py`):**
- Flask web server
- File upload handling
- Analysis orchestration
- REST API endpoints

**Frontend (`templates/index.html`):**
- Responsive HTML5 layout
- Upload form
- Dashboard sections
- Export controls

**Styling (`static/style.css`):**
- Modern gradient design
- Responsive layout
- Card-based components
- Smooth animations

**JavaScript (`static/script.js`):**
- File upload handling
- AJAX communication
- Dynamic dashboard updates
- Export functionality

### Adding Features

To add new features:

1. **Backend**: Add new routes in `app.py`
2. **Frontend**: Update `index.html` for UI changes
3. **Styling**: Modify `style.css` for appearance
4. **Logic**: Update `script.js` for interactivity

## Troubleshooting

### Port Already in Use

The application uses port 5001 by default to avoid conflicts with macOS AirPlay Receiver (which uses port 5000).

If port 5001 is also in use, you can change it in `app.py`:
```python
# In app.py, change the port:
app.run(debug=True, host='0.0.0.0', port=8080)  # or any other available port
```

### File Upload Errors

- Ensure the file is a valid BPMN/XML file
- Check that file size is under 16MB
- Verify file permissions

### Analysis Errors

- Ensure the BPMN file is well-formed XML
- Check that BPMN uses standard BPMN 2.0 namespace
- Review console output for detailed error messages

## Command Line Alternative

You can still use the original command-line interface:

```bash
# Basic analysis
python bpmn_migration.py process.bpmn

# With exports
python bpmn_migration.py process.bpmn --json report.json --csv issues.csv --html report.html
```

See `CLAUDE.md` for more details on the CLI version.

## Security Notes

- Files are temporarily stored in the `uploads/` folder
- Files are automatically deleted after analysis
- File size is limited to 16MB
- Only `.bpmn` and `.xml` extensions are allowed
- Input validation is performed on all uploads

## Support

For issues or questions:
- Review the analysis output for guidance
- Check BPMN file structure and syntax
- Consult Camunda 7 to 8 migration documentation
- Review source code comments for technical details

## License

This tool is provided for migration assessment purposes.

---

**Built with:**
- Flask (Python web framework)
- Vanilla JavaScript (no dependencies)
- Modern CSS3 (responsive design)
- Python xml.etree.ElementTree (BPMN parsing)

**By NTConsult**
