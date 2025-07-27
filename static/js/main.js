// Banking Fraud Detection Platform - Main JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Initialize all components
    initializeProgressCircles();
    initializeUploadArea();
    initializeTooltips();
    initializeCharts();
    initializeClaudeAnalysis();
});

// Progress Circle Animation
function initializeProgressCircles() {
    const circles = document.querySelectorAll('.progress-circle');
    circles.forEach(circle => {
        const progressText = circle.querySelector('.progress-text');
        if (progressText) {
            const percentage = parseInt(progressText.textContent);
            updateProgressCircle(circle, percentage);
        }
    });
}

function updateProgressCircle(circle, percentage) {
    const degrees = (percentage / 100) * 360;
    circle.style.background = `conic-gradient(var(--primary-green) ${degrees}deg, var(--gray-200) ${degrees}deg)`;
}

// Upload Area Drag & Drop
function initializeUploadArea() {
    const uploadArea = document.querySelector('.upload-area');
    if (!uploadArea) return;

    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        uploadArea.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    ['dragenter', 'dragover'].forEach(eventName => {
        uploadArea.addEventListener(eventName, highlight, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        uploadArea.addEventListener(eventName, unhighlight, false);
    });

    function highlight(e) {
        uploadArea.classList.add('dragover');
    }

    function unhighlight(e) {
        uploadArea.classList.remove('dragover');
    }

    uploadArea.addEventListener('drop', handleDrop, false);

    function handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;
        handleFiles(files);
    }

    function handleFiles(files) {
        if (files.length > 0) {
            const file = files[0];
            if (file.type === 'text/csv' || file.name.endsWith('.csv')) {
                const fileInput = document.querySelector('#csv_file');
                if (fileInput) {
                    fileInput.files = files;
                    updateUploadAreaText(file.name);
                }
            } else {
                showAlert('Veuillez sélectionner un fichier CSV valide.', 'warning');
            }
        }
    }

    function updateUploadAreaText(filename) {
        const uploadText = uploadArea.querySelector('.upload-text');
        if (uploadText) {
            uploadText.innerHTML = `
                <div class="text-success">
                    <strong>✅ Fichier sélectionné:</strong><br>
                    ${filename}
                </div>
            `;
        }
    }
}

// Tooltips
function initializeTooltips() {
    const tooltipElements = document.querySelectorAll('[data-tooltip]');
    tooltipElements.forEach(element => {
        element.addEventListener('mouseenter', showTooltip);
        element.addEventListener('mouseleave', hideTooltip);
    });
}

function showTooltip(e) {
    const text = e.target.getAttribute('data-tooltip');
    const tooltip = document.createElement('div');
    tooltip.className = 'tooltip';
    tooltip.textContent = text;
    document.body.appendChild(tooltip);
    
    const rect = e.target.getBoundingClientRect();
    tooltip.style.left = rect.left + (rect.width / 2) - (tooltip.offsetWidth / 2) + 'px';
    tooltip.style.top = rect.top - tooltip.offsetHeight - 10 + 'px';
}

function hideTooltip() {
    const tooltip = document.querySelector('.tooltip');
    if (tooltip) {
        tooltip.remove();
    }
}

// Charts (placeholder for Chart.js integration)
function initializeCharts() {
    // Transaction volume chart
    const volumeChart = document.getElementById('volumeChart');
    if (volumeChart) {
        // Chart.js implementation would go here
        console.log('Volume chart initialized');
    }

    // Risk distribution chart
    const riskChart = document.getElementById('riskChart');
    if (riskChart) {
        // Chart.js implementation would go here
        console.log('Risk chart initialized');
    }
}

// Claude Analysis Functions
function initializeClaudeAnalysis() {
    const analyzeButtons = document.querySelectorAll('.btn-analyze-claude');
    analyzeButtons.forEach(button => {
        button.addEventListener('click', handleClaudeAnalysis);
    });
}

function handleClaudeAnalysis(e) {
    e.preventDefault();
    const button = e.target;
    const transactionId = button.getAttribute('data-transaction-id');
    const clientId = button.getAttribute('data-client-id');
    
    if (transactionId) {
        analyzeTransaction(transactionId, button);
    } else if (clientId) {
        analyzeClient(clientId, button);
    }
}

function analyzeTransaction(transactionId, button) {
    const originalText = button.textContent;
    button.textContent = 'Analyse en cours...';
    button.disabled = true;
    
    fetch(`/api/analyze-transaction/${transactionId}/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCsrfToken(),
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.analysis) {
            displayAnalysisResult(data.analysis, data.priority);
            button.style.display = 'none';
        } else {
            showAlert('Erreur lors de l\'analyse', 'danger');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showAlert('Erreur de connexion', 'danger');
        button.textContent = originalText;
        button.disabled = false;
    });
}

function analyzeClient(clientId, button) {
    const originalText = button.textContent;
    button.textContent = 'Analyse en cours...';
    button.disabled = true;
    
    fetch(`/api/analyze-client/${clientId}/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCsrfToken(),
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.analysis) {
            displayClientAnalysisResult(data.analysis, data.risk_level);
            button.style.display = 'none';
        } else {
            showAlert('Erreur lors de l\'analyse', 'danger');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showAlert('Erreur de connexion', 'danger');
        button.textContent = originalText;
        button.disabled = false;
    });
}

function displayAnalysisResult(analysis, priority) {
    const container = document.querySelector('.claude-analysis-result');
    if (container) {
        container.innerHTML = `
            <div class="analysis-content">
                <div class="d-flex justify-content-between align-items-center mb-3">
                    <h4>🤖 Analyse IA</h4>
                    <span class="badge priority-${priority.toLowerCase()}">${priority}</span>
                </div>
                <div class="analysis-text">
                    ${analysis.replace(/\n/g, '<br>')}
                </div>
                <small class="text-muted">Analysé le ${new Date().toLocaleString('fr-FR')}</small>
            </div>
        `;
        container.style.display = 'block';
    }
}

function displayClientAnalysisResult(analysis, riskLevel) {
    const container = document.querySelector('.client-analysis-result');
    if (container) {
        container.innerHTML = `
            <div class="risk-assessment">
                <div class="d-flex justify-content-between align-items-center mb-3">
                    <h4>🤖 Évaluation IA du Profil</h4>
                    <span class="badge risk-${riskLevel.toLowerCase()}">${riskLevel}</span>
                </div>
                <div class="assessment-content">
                    ${analysis.replace(/\n/g, '<br>')}
                </div>
                <small class="text-muted">Analysé le ${new Date().toLocaleString('fr-FR')}</small>
            </div>
        `;
        container.style.display = 'block';
    }
}

// CSV Processing with Server-Sent Events
function startCsvProcessing(filename) {
    const eventSource = new EventSource('/upload/process-stream/');
    const progressCircle = document.getElementById('progressCircle');
    const progressText = document.getElementById('progressText');
    const processedCount = document.getElementById('processedCount');
    const fraudCount = document.getElementById('fraudCount');
    const claudeCount = document.getElementById('claudeCount');
    const completionMessage = document.getElementById('completionMessage');
    const claudeStatus = document.querySelector('.claude-status');
    
    eventSource.onmessage = function(event) {
        const data = JSON.parse(event.data);
        
        if (data.error) {
            showAlert(data.error, 'danger');
            eventSource.close();
            return;
        }
        
        if (data.completed) {
            // Traitement terminé
            progressText.textContent = '100%';
            updateProgressCircle(progressCircle, 100);
            completionMessage.style.display = 'block';
            claudeStatus.style.display = 'none';
            eventSource.close();
            
            // Redirection automatique après 3 secondes
            setTimeout(() => {
                window.location.href = '/dashboard/';
            }, 3000);
        } else {
            // Mise à jour du progrès
            const progress = Math.round(data.progress);
            progressText.textContent = progress + '%';
            processedCount.textContent = data.processed;
            fraudCount.textContent = data.frauds;
            claudeCount.textContent = data.frauds;
            updateProgressCircle(progressCircle, progress);
            
            // Mise à jour du statut Claude
            if (data.current_transaction) {
                document.getElementById('claudeStatus').textContent = 
                    `Analyse de la transaction ${data.current_transaction}...`;
            }
        }
    };
    
    eventSource.onerror = function(event) {
        console.error('EventSource failed:', event);
        showAlert('Erreur de connexion au serveur', 'danger');
        eventSource.close();
    };
}

// Utility Functions
function getCsrfToken() {
    return document.querySelector('[name=csrfmiddlewaretoken]').value;
}

function showAlert(message, type = 'info') {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type}`;
    alertDiv.textContent = message;
    
    const container = document.querySelector('.content-wrapper');
    container.insertBefore(alertDiv, container.firstChild);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        alertDiv.remove();
    }, 5000);
}

function formatNumber(num) {
    return new Intl.NumberFormat('fr-FR').format(num);
}

function formatCurrency(amount) {
    return new Intl.NumberFormat('fr-FR', {
        style: 'currency',
        currency: 'EUR'
    }).format(amount);
}

// Table sorting
function sortTable(columnIndex, tableId) {
    const table = document.getElementById(tableId);
    const tbody = table.querySelector('tbody');
    const rows = Array.from(tbody.querySelectorAll('tr'));
    
    const isNumeric = !isNaN(parseFloat(rows[0].cells[columnIndex].textContent));
    
    rows.sort((a, b) => {
        const aVal = a.cells[columnIndex].textContent.trim();
        const bVal = b.cells[columnIndex].textContent.trim();
        
        if (isNumeric) {
            return parseFloat(aVal) - parseFloat(bVal);
        } else {
            return aVal.localeCompare(bVal);
        }
    });
    
    // Toggle sort direction
    const currentDirection = table.getAttribute('data-sort-direction') || 'asc';
    if (currentDirection === 'asc') {
        rows.reverse();
        table.setAttribute('data-sort-direction', 'desc');
    } else {
        table.setAttribute('data-sort-direction', 'asc');
    }
    
    // Rebuild table
    rows.forEach(row => tbody.appendChild(row));
}

// Search functionality
function initializeSearch() {
    const searchInputs = document.querySelectorAll('.search-input');
    searchInputs.forEach(input => {
        input.addEventListener('input', handleSearch);
    });
}

function handleSearch(e) {
    const searchTerm = e.target.value.toLowerCase();
    const tableId = e.target.getAttribute('data-table');
    const table = document.getElementById(tableId);
    const rows = table.querySelectorAll('tbody tr');
    
    rows.forEach(row => {
        const text = row.textContent.toLowerCase();
        if (text.includes(searchTerm)) {
            row.style.display = '';
        } else {
            row.style.display = 'none';
        }
    });
}

// Initialize search on page load
document.addEventListener('DOMContentLoaded', initializeSearch);

