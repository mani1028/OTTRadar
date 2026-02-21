// Admin-only JS logic for OTT Radar admin panel
// Add AJAX calls, background task triggers, and admin UI handlers here.

// Example: Run background script from admin panel
function runAdminScript(scriptName) {
    fetch(`/admin/run-script/${scriptName}`, { method: 'POST' })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                alert('Script started successfully!');
            } else {
                alert('Failed to start script.');
            }
        });
}

// Add more admin-specific JS as needed
