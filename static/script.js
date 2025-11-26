// Global variable to store analysis results
let analysisData = null;

// DOM elements
const uploadForm = document.getElementById('uploadForm');
const fileInput = document.getElementById('fileInput');
const fileName = document.getElementById('fileName');
const analyzeBtn = document.getElementById('analyzeBtn');
const btnText = document.getElementById('btnText');
const btnLoader = document.getElementById('btnLoader');
const dashboard = document.getElementById('dashboard');
const errorMessage = document.getElementById('errorMessage');

// File input change handler
fileInput.addEventListener('change', function(e) {
    if (e.target.files.length > 0) {
        fileName.textContent = e.target.files[0].name;
    } else {
        fileName.textContent = 'Choose a BPMN file...';
    }
});

// Form submit handler
uploadForm.addEventListener('submit', async function(e) {
    e.preventDefault();

    // Hide previous results and errors
    dashboard.style.display = 'none';
    errorMessage.style.display = 'none';

    // Check if file is selected
    if (!fileInput.files.length) {
        showError('Please select a file');
        return;
    }

    // Disable button and show loader
    analyzeBtn.disabled = true;
    btnText.textContent = 'Analyzing...';
    btnLoader.style.display = 'inline-block';

    // Create form data
    const formData = new FormData();
    formData.append('file', fileInput.files[0]);

    try {
        // Send request to backend
        const response = await fetch('/analyze', {
            method: 'POST',
            body: formData
        });

        const result = await response.json();

        if (response.ok && result.success) {
            // Store analysis data
            analysisData = result.data;

            // Display results
            displayResults(result.data);

            // Scroll to dashboard
            dashboard.scrollIntoView({ behavior: 'smooth' });
        } else {
            showError(result.error || 'Analysis failed');
        }
    } catch (error) {
        showError('Network error: ' + error.message);
    } finally {
        // Re-enable button
        analyzeBtn.disabled = false;
        btnText.textContent = 'Analyze BPMN';
        btnLoader.style.display = 'none';
    }
});

// Display results in dashboard
function displayResults(data) {
    // Update summary cards
    document.getElementById('totalElements').textContent = data.statistics.total_elements;
    document.getElementById('criticalIssues').textContent = data.statistics.issue_counts_by_severity.CRITICAL;
    document.getElementById('warningIssues').textContent = data.statistics.issue_counts_by_severity.WARNING;
    document.getElementById('infoIssues').textContent = data.statistics.issue_counts_by_severity.INFO;
    document.getElementById('totalVariables').textContent = data.statistics.total_variables_detected;

    // Update file info
    document.getElementById('fileName_display').textContent = data.file;
    document.getElementById('analysisDate').textContent = formatDate(data.timestamp);

    // Update complexity assessment
    updateComplexity(data.statistics.issue_counts_by_severity);

    // Update element breakdown
    updateElementTable(data.statistics.element_counts);

    // Update issues by category
    updateCategoryTable(data.statistics.issue_counts_by_category);

    // Update issues tabs
    updateIssuesTabs(data.issues, data.statistics.issue_counts_by_severity);

    // Update process variables
    updateVariables(data.process_variables);

    // Show dashboard
    dashboard.style.display = 'block';
}

// Update complexity assessment
function updateComplexity(issueCounts) {
    const criticalCount = issueCounts.CRITICAL;
    const warningCount = issueCounts.WARNING;

    let complexity, description, className;

    if (criticalCount === 0 && warningCount === 0) {
        complexity = 'LOW';
        description = 'Process appears largely compatible with minimal changes needed.';
        className = 'low';
    } else if (criticalCount <= 5 && warningCount <= 10) {
        complexity = 'MEDIUM';
        description = 'Moderate migration effort required. Focus on critical issues first.';
        className = 'medium';
    } else {
        complexity = 'HIGH';
        description = 'Significant migration effort required. Consider phased approach.';
        className = 'high';
    }

    const complexityBadge = document.getElementById('complexityBadge');
    complexityBadge.textContent = complexity;
    complexityBadge.className = 'complexity-badge ' + className;

    document.getElementById('complexityDescription').textContent = description;
}

// Update element breakdown table
function updateElementTable(elementCounts) {
    const tbody = document.getElementById('elementTableBody');
    tbody.innerHTML = '';

    const sortedElements = Object.entries(elementCounts)
        .filter(([_, count]) => count > 0)
        .sort(([a], [b]) => a.localeCompare(b));

    if (sortedElements.length === 0) {
        tbody.innerHTML = '<tr><td colspan="2">No elements found</td></tr>';
        return;
    }

    sortedElements.forEach(([element, count]) => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${formatElementName(element)}</td>
            <td><strong>${count}</strong></td>
        `;
        tbody.appendChild(row);
    });
}

// Update category table
function updateCategoryTable(categoryCounts) {
    const tbody = document.getElementById('categoryTableBody');
    tbody.innerHTML = '';

    const sortedCategories = Object.entries(categoryCounts)
        .sort(([a], [b]) => a.localeCompare(b));

    if (sortedCategories.length === 0) {
        tbody.innerHTML = '<tr><td colspan="2">No issues found</td></tr>';
        return;
    }

    sortedCategories.forEach(([category, count]) => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${category}</td>
            <td><strong>${count}</strong></td>
        `;
        tbody.appendChild(row);
    });
}

// Update issues tabs
function updateIssuesTabs(issues, issueCounts) {
    // Update counts in tab buttons
    document.getElementById('criticalCount').textContent = issueCounts.CRITICAL;
    document.getElementById('warningCount').textContent = issueCounts.WARNING;
    document.getElementById('infoCount').textContent = issueCounts.INFO;

    // Group issues by severity
    const criticalIssues = issues.filter(i => i.severity === 'CRITICAL');
    const warningIssues = issues.filter(i => i.severity === 'WARNING');
    const infoIssues = issues.filter(i => i.severity === 'INFO');

    // Update each tab
    updateIssueTab('criticalTab', criticalIssues, 'critical');
    updateIssueTab('warningTab', warningIssues, 'warning');
    updateIssueTab('infoTab', infoIssues, 'info');
}

// Update individual issue tab
function updateIssueTab(tabId, issues, severity) {
    const tab = document.getElementById(tabId);

    if (issues.length === 0) {
        tab.innerHTML = `<div class="no-issues">No ${severity} issues found</div>`;
        return;
    }

    tab.innerHTML = '';

    issues.forEach(issue => {
        const issueDiv = document.createElement('div');
        issueDiv.className = `issue-item ${severity}`;
        issueDiv.innerHTML = `
            <div class="issue-header">
                <div class="issue-category">${issue.category}</div>
            </div>
            <div class="issue-message">${escapeHtml(issue.message)}</div>
            <div class="issue-element">
                <strong>Element:</strong> ${escapeHtml(issue.element_name)}
                <span style="color: #a0aec0;">(ID: ${escapeHtml(issue.element_id)})</span>
            </div>
            ${issue.details ? `<div class="issue-details">${escapeHtml(issue.details)}</div>` : ''}
        `;
        tab.appendChild(issueDiv);
    });
}

// Update process variables
function updateVariables(variables) {
    const variablesSection = document.getElementById('variablesSection');
    const variablesList = document.getElementById('variablesList');

    if (variables.length === 0) {
        variablesSection.style.display = 'none';
        return;
    }

    variablesSection.style.display = 'block';
    variablesList.innerHTML = '';

    variables.forEach(variable => {
        const tag = document.createElement('span');
        tag.className = 'variable-tag';
        tag.textContent = variable;
        variablesList.appendChild(tag);
    });
}

// Tab switching functionality
document.querySelectorAll('.tab-btn').forEach(button => {
    button.addEventListener('click', function() {
        // Remove active class from all tabs
        document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
        document.querySelectorAll('.tab-pane').forEach(pane => pane.classList.remove('active'));

        // Add active class to clicked tab
        this.classList.add('active');
        const tabName = this.dataset.tab;
        document.getElementById(tabName + 'Tab').classList.add('active');
    });
});

// Export JSON
document.getElementById('exportJsonBtn').addEventListener('click', function() {
    if (!analysisData) return;

    const dataStr = JSON.stringify(analysisData, null, 2);
    const dataBlob = new Blob([dataStr], { type: 'application/json' });

    const link = document.createElement('a');
    link.href = URL.createObjectURL(dataBlob);
    link.download = 'bpmn_analysis_' + getTimestamp() + '.json';
    link.click();
});

// Export CSV
document.getElementById('exportCsvBtn').addEventListener('click', function() {
    if (!analysisData) return;

    // Create CSV header
    let csv = 'Severity,Category,Element ID,Element Name,Message,Details\n';

    // Add rows
    analysisData.issues.forEach(issue => {
        csv += `"${issue.severity}","${issue.category}","${issue.element_id}","${issue.element_name}","${issue.message}","${issue.details}"\n`;
    });

    // Download
    const blob = new Blob([csv], { type: 'text/csv' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = 'bpmn_issues_' + getTimestamp() + '.csv';
    link.click();
});

// Helper functions
function showError(message) {
    errorMessage.textContent = message;
    errorMessage.style.display = 'block';
    errorMessage.scrollIntoView({ behavior: 'smooth' });
}

function formatDate(timestamp) {
    const date = new Date(timestamp);
    return date.toLocaleString('en-US', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function formatElementName(name) {
    // Convert camelCase to Title Case with spaces
    return name.replace(/([A-Z])/g, ' $1')
        .replace(/^./, str => str.toUpperCase())
        .trim();
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function getTimestamp() {
    const now = new Date();
    return now.toISOString().replace(/:/g, '-').split('.')[0];
}
