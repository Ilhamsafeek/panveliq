/**
 * Communication Hub - JavaScript Implementation
 * File: static/js/communication.js
 */

const API_BASE = '/api/v1/communication';
let emailEditor = null;
let currentTab = 'whatsapp';
let clientsList = [];
let segmentsList = [];
let csvData = null;

// =====================================================
// INITIALIZATION
// =====================================================

document.addEventListener('DOMContentLoaded', async function () {
    await initializePage();
    initializeEmailEditor();
    initializeFileUpload();
});

// =====================================================
// GET CURRENT USER
// =====================================================


async function initializePage() {
    try {
        // Get current user
        // await getCurrentUser();

        // Load clients for dropdowns
        await loadClients();

        // Load segments for audience selection
        await loadSegmentsForDropdown();

        // Load analytics
        await loadAnalytics();

        // Load initial tab content
        await loadWhatsAppCampaigns();

        // Setup form handlers
        setupFormHandlers();

    } catch (error) {
        console.error('Initialization error:', error);
        showNotification('Failed to initialize page', 'error');
    }
}

// =====================================================
// LOAD CLIENTS FOR DROPDOWNS
// =====================================================

async function loadClients() {
    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch('/api/v1/clients/list', {  // Use absolute path
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (!response.ok) {
            console.error('Response status:', response.status);
            const errorText = await response.text();
            console.error('Error response:', errorText);
            return;
        }

        const data = await response.json();

        if (data.success) {
            clientsList = data.clients;
            populateClientDropdowns();
        }
    } catch (error) {
        console.error('Error loading clients:', error);
    }
}

function populateClientDropdowns() {
    const dropdowns = [
        'wa_client_id',
        'email_client_id',
        'flow_client_id',
        'segment_client_id',
        'csv_client_id'
    ];

    dropdowns.forEach(id => {
        const select = document.getElementById(id);
        if (select) {
            select.innerHTML = '<option value="">Choose client...</option>';
            clientsList.forEach(client => {
                const option = document.createElement('option');
                option.value = client.user_id;
                option.textContent = `${client.full_name} ${client.business_name ? '(' + client.business_name + ')' : ''}`;
                select.appendChild(option);
            });
        }
    });
}

// =====================================================
// LOAD SEGMENTS FOR DROPDOWN
// =====================================================

async function loadSegmentsForDropdown() {
    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`${API_BASE}/segments/list`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        const data = await response.json();

        if (data.success) {
            segmentsList = data.segments;
            populateSegmentDropdowns();
        }
    } catch (error) {
        console.error('Error loading segments:', error);
    }
}


function populateSegmentDropdowns() {
    const dropdowns = [
        { id: 'wa_audience_segment', platform: 'whatsapp' },
        { id: 'email_audience_segment', platform: 'email' }
    ];

    dropdowns.forEach(({ id, platform }) => {
        const select = document.getElementById(id);
        if (select) {
            select.innerHTML = '<option value="">Choose audience segment...</option>';

            // Filter segments by platform - match with 'both' or exact platform
            const filteredSegments = segmentsList.filter(seg => {
                const segPlatform = seg.platform ? seg.platform.toLowerCase() : '';
                const targetPlatform = platform.toLowerCase();

                return segPlatform === targetPlatform ||
                    segPlatform === 'both' ||
                    segPlatform === 'all' ||
                    segPlatform === 'email' && targetPlatform === 'email' ||
                    segPlatform === 'whatsapp' && targetPlatform === 'whatsapp';
            });

            console.log(`Populating ${id} with ${filteredSegments.length} segments`);

            filteredSegments.forEach(segment => {
                const option = document.createElement('option');
                option.value = segment.segment_id;
                option.textContent = `${segment.segment_name} (${segment.estimated_size || 0} contacts)`;
                option.dataset.recipients = segment.estimated_size || 0;
                select.appendChild(option);
            });
        }
    });
}

// =====================================================
// LOAD AUDIENCE RECIPIENTS
// =====================================================

async function loadAudienceRecipients(type) {
    const segmentSelect = document.getElementById(`${type}_audience_segment`);
    const countElement = document.getElementById(`${type}_recipient_count`);

    if (!segmentSelect || !countElement) return;

    const segmentId = segmentSelect.value;

    if (!segmentId) {
        countElement.textContent = '0 recipients selected';
        return;
    }

    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`${API_BASE}/segments/${segmentId}/recipients`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        const data = await response.json();

        if (data.success) {
            // Get count from the correct field
            const count = data.total_recipients || data.estimated_size || 0;
            countElement.textContent = `${count} recipients selected`;

            // Store recipients for form submission
            const recipients = data.recipients || [];

            if (type === 'wa') {
                // For WhatsApp, we need phone numbers
                window.waRecipients = recipients.filter(r => r && r.trim());
            } else {
                // For Email, we need email addresses
                window.emailRecipients = recipients.filter(r => r && r.trim());
            }

            console.log(`Loaded ${recipients.length} recipients for ${type}`);
        } else {
            countElement.textContent = 'Error loading recipients';
        }
    } catch (error) {
        console.error('Error loading recipients:', error);
        countElement.textContent = 'Error loading recipients';
    }
}

// =====================================================
// FILE UPLOAD & CSV HANDLING
// =====================================================

function initializeFileUpload() {
    const fileInput = document.getElementById('csv_file');
    const uploadArea = document.getElementById('fileUploadArea');

    if (!fileInput || !uploadArea) return;

    // Drag and drop handlers
    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.style.borderColor = 'var(--primary-purple)';
        uploadArea.style.background = 'var(--color-gray-100)';
    });

    uploadArea.addEventListener('dragleave', () => {
        uploadArea.style.borderColor = 'var(--color-gray-300)';
        uploadArea.style.background = 'var(--color-gray-50)';
    });

    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.style.borderColor = 'var(--color-gray-300)';
        uploadArea.style.background = 'var(--color-gray-50)';

        const files = e.dataTransfer.files;
        if (files.length > 0) {
            fileInput.files = files;
            handleFileSelect({ target: fileInput });
        }
    });
}


function handleFileSelect(event) {
    const file = event.target.files[0];
    if (!file) return;

    document.getElementById('fileName').textContent = `Selected: ${file.name}`;

    // Parse CSV
    Papa.parse(file, {
        header: true,
        skipEmptyLines: true,
        complete: function (results) {
            csvData = results.data;
            displayCSVPreview(results.data);
        },
        error: function (error) {
            console.error('CSV Parse Error:', error);
            showNotification('Error parsing CSV file', 'error');
        }
    });
}

function displayCSVPreview(data) {
    const previewDiv = document.getElementById('csvPreview');
    const previewTable = document.getElementById('previewTable');
    const previewStats = document.getElementById('previewStats');

    if (data.length === 0) {
        showNotification('CSV file is empty', 'error');
        return;
    }

    // Show preview
    previewDiv.style.display = 'block';

    // Create table
    const headers = Object.keys(data[0]);
    const previewData = data.slice(0, 5); // First 5 rows

    let tableHTML = '<table><thead><tr>';
    headers.forEach(header => {
        tableHTML += `<th>${header}</th>`;
    });
    tableHTML += '</tr></thead><tbody>';

    previewData.forEach(row => {
        tableHTML += '<tr>';
        headers.forEach(header => {
            tableHTML += `<td>${row[header] || ''}</td>`;
        });
        tableHTML += '</tr>';
    });
    tableHTML += '</tbody></table>';

    previewTable.innerHTML = tableHTML;

    // Show stats
    previewStats.innerHTML = `
        <span><strong>${data.length}</strong> contacts found</span>
        <span><strong>${headers.length}</strong> columns</span>
    `;
}

// Download CSV template
function downloadCSVTemplate() {
    const csvContent = 'name,email,phone,company\nLinson Dominic,linson@example.com,+1234567890,Example Corp\nJane Smith,jane@example.com,+0987654321,Another Company';
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'audience_template.csv';
    a.click();
    window.URL.revokeObjectURL(url);
}


async function loadAnalytics() {
    try {
        // For demo, use first client or allow admin to select
        const clientId = clientsList[0]?.user_id || 1;

        const token = localStorage.getItem('access_token');
        const response = await fetch(`${API_BASE}/analytics/overview?client_id=${clientId}`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        const data = await response.json();

        if (data.success) {
            const analytics = data.analytics;

            // Update WhatsApp stats - check if elements exist first
            const whatsappCampaigns = document.getElementById('whatsappCampaigns');
            const whatsappDeliveryRate = document.getElementById('whatsappDeliveryRate');
            if (whatsappCampaigns) whatsappCampaigns.textContent = analytics.whatsapp.total_campaigns;
            if (whatsappDeliveryRate) whatsappDeliveryRate.textContent = `${analytics.whatsapp.delivery_rate}% delivery rate`;

            // Update Email stats - check if elements exist first
            const emailCampaigns = document.getElementById('emailCampaigns');
            const emailOpenRate = document.getElementById('emailOpenRate');
            if (emailCampaigns) emailCampaigns.textContent = analytics.email.total_campaigns;
            if (emailOpenRate) emailOpenRate.textContent = `${analytics.email.open_rate}% open rate`;

            // Update Flows stats - check if elements exist first
            const activeFlows = document.getElementById('activeFlows');
            const totalFlows = document.getElementById('totalFlows');
            if (activeFlows) activeFlows.textContent = analytics.flows.active_flows;
            if (totalFlows) totalFlows.textContent = `${analytics.flows.total_flows} total automation flows`;
        }
    } catch (error) {
        console.error('Error loading analytics:', error);
        // Don't show error to user as analytics cards may be intentionally hidden
    }
}


// =====================================================
// TAB SWITCHING
// =====================================================

function switchTab(tabName) {
    currentTab = tabName;

    // Update tab buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');

    // Update tab content
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });
    document.getElementById(`${tabName}-tab`).classList.add('active');

    // Load content based on tab
    switch (tabName) {
        case 'whatsapp':
            loadWhatsAppCampaigns();
            break;
        case 'email':
            loadEmailCampaigns();
            break;
        case 'flows':
            loadAutomationFlows();
            break;
        case 'segments':
            loadAudienceSegments();
            break;
    }
}

// =====================================================
// WHATSAPP CAMPAIGNS
// =====================================================

async function loadWhatsAppCampaigns() {
    const container = document.getElementById('whatsappCampaignsList');
    container.innerHTML = '<div class="loading-state"><div class="loader-spinner"></div><p>Loading campaigns...</p></div>';

    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`${API_BASE}/whatsapp/campaigns/list`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        const data = await response.json();

        if (data.success && data.campaigns.length > 0) {
            container.innerHTML = data.campaigns.map(campaign => `
                <div class="campaign-card whatsapp-campaign">
                    <div class="campaign-header">
                        <div class="campaign-icon">
                            <i class="ti ti-brand-whatsapp"></i>
                        </div>
                        <div class="campaign-info">
                            <h3>${campaign.campaign_name}</h3>
                            <p class="campaign-meta">
                                <i class="ti ti-user"></i> ${campaign.client_name}
                                <span class="separator">•</span>
                                <i class="ti ti-calendar"></i> ${formatDate(campaign.created_at)}
                            </p>
                        </div>
                        <div class="campaign-status">
                            <span class="status-badge status-${campaign.status}">${campaign.status}</span>
                        </div>
                    </div>
                    <div class="campaign-stats">
                        <div class="stat-item">
                            <div class="stat-value">${campaign.total_recipients}</div>
                            <div class="stat-label">Recipients</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-value">${campaign.delivered_count}</div>
                            <div class="stat-label">Delivered</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-value">${campaign.total_recipients > 0 ? Math.round((campaign.delivered_count / campaign.total_recipients) * 100) : 0}%</div>
                            <div class="stat-label">Delivery Rate</div>
                        </div>
                    </div>
                    <div class="campaign-actions">
                        <button class="btn-action" onclick="viewCampaign('whatsapp', ${campaign.campaign_id})">
                            <i class="ti ti-eye"></i> View
                        </button>
                        ${campaign.status === 'draft' ? `
                            <button class="btn-action" onclick="editCampaign('whatsapp', ${campaign.campaign_id})">
                                <i class="ti ti-edit"></i> Edit
                            </button>
                        ` : ''}
                    </div>
                </div>
            `).join('');
        } else {
            container.innerHTML = `
                <div class="empty-state">
                    <i class="ti ti-brand-whatsapp"></i>
                    <h3>No WhatsApp Campaigns Yet</h3>
                    <p>Create your first WhatsApp campaign to engage with your audience</p>
                    
                </div>
            `;
        }
    } catch (error) {
        console.error('Error loading WhatsApp campaigns:', error);
        container.innerHTML = '<div class="error-state">Failed to load campaigns</div>';
    }
}

// =====================================================
// EMAIL CAMPAIGNS
// =====================================================

async function loadEmailCampaigns() {
    const container = document.getElementById('emailCampaignsList');
    container.innerHTML = '<div class="loading-state"><div class="loader-spinner"></div><p>Loading campaigns...</p></div>';

    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`${API_BASE}/email/campaigns/list`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        const data = await response.json();

        if (data.success && data.campaigns.length > 0) {
            container.innerHTML = data.campaigns.map(campaign => `
                <div class="campaign-card email-campaign">
                    <div class="campaign-header">
                        <div class="campaign-icon">
                            <i class="ti ti-mail"></i>
                        </div>
                        <div class="campaign-info">
                            <h3>${campaign.campaign_name}</h3>
                            <p class="campaign-subject">${campaign.subject_line}</p>
                            <p class="campaign-meta">
                                <i class="ti ti-user"></i> ${campaign.client_name}
                                <span class="separator">•</span>
                                <i class="ti ti-calendar"></i> ${formatDate(campaign.created_at)}
                                ${campaign.is_ab_test ? '<span class="ab-badge">A/B Test</span>' : ''}
                            </p>
                        </div>
                        <div class="campaign-status">
                            <span class="status-badge status-${campaign.status}">${campaign.status}</span>
                        </div>
                    </div>
                    <div class="campaign-stats">
                        <div class="stat-item">
                            <div class="stat-value">${campaign.total_recipients}</div>
                            <div class="stat-label">Sent</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-value">${campaign.open_rate}%</div>
                            <div class="stat-label">Open Rate</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-value">${campaign.click_rate}%</div>
                            <div class="stat-label">Click Rate</div>
                        </div>
                    </div>
                    <div class="campaign-actions">
                        <button class="btn-action" onclick="viewCampaign('email', ${campaign.email_campaign_id})">
                            <i class="ti ti-eye"></i> View
                        </button>
                        ${campaign.status === 'draft' ? `
                            <button class="btn-action" onclick="editCampaign('email', ${campaign.email_campaign_id})">
                                <i class="ti ti-edit"></i> Edit
                            </button>
                        ` : ''}
                    </div>
                </div>
            `).join('');
        } else {
            container.innerHTML = `
                <div class="empty-state">
                    <i class="ti ti-mail"></i>
                    <h3>No Email Campaigns Yet</h3>
                    <p>Create your first email campaign with AI-powered copy</p>
                   
                </div>
            `;
        }
    } catch (error) {
        console.error('Error loading email campaigns:', error);
        container.innerHTML = '<div class="error-state">Failed to load campaigns</div>';
    }
}

// =====================================================
// AUTOMATION FLOWS
// =====================================================

async function loadAutomationFlows() {
    const container = document.getElementById('flowsList');
    container.innerHTML = '<div class="loading-state"><div class="loader-spinner"></div><p>Loading flows...</p></div>';

    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`${API_BASE}/flows/list`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        const data = await response.json();

        if (data.success && data.flows.length > 0) {
            container.innerHTML = data.flows.map(flow => `
                <div class="flow-card">
                    <div class="flow-header">
                        <div class="flow-icon">
                            <i class="ti ti-git-branch"></i>
                        </div>
                        <div class="flow-info">
                            <h3>${flow.flow_name}</h3>
                            <p class="flow-meta">
                                <span class="trigger-type"><i class="ti ti-bolt"></i> ${formatTriggerType(flow.trigger_type)}</span>
                                <span class="separator">•</span>
                                <span class="channel-badge channel-${flow.channel}">
                                    <i class="ti ti-${flow.channel === 'whatsapp' ? 'brand-whatsapp' : flow.channel === 'email' ? 'mail' : 'device-mobile'}"></i>
                                    ${flow.channel}
                                </span>
                            </p>
                            <p class="flow-client">
                                <i class="ti ti-user"></i> ${flow.client_name}
                            </p>
                        </div>
                        <div class="flow-toggle">
                            <label class="toggle-switch">
                                <input type="checkbox" ${flow.is_active ? 'checked' : ''} onchange="toggleFlow(${flow.flow_id}, this.checked)">
                                <span class="toggle-slider"></span>
                            </label>
                            <span class="toggle-label">${flow.is_active ? 'Active' : 'Inactive'}</span>
                        </div>
                    </div>
                    <div class="flow-stats">
                        <div class="stat-item">
                            <div class="stat-value">${flow.total_executions}</div>
                            <div class="stat-label">Total Executions</div>
                        </div>
                    </div>
                    <div class="flow-actions">
                        <button class="btn-action" onclick="viewFlow(${flow.flow_id})">
                            <i class="ti ti-eye"></i> View Details
                        </button>
                        <button class="btn-action" onclick="editFlow(${flow.flow_id})">
                            <i class="ti ti-edit"></i> Edit
                        </button>
                    </div>
                </div>
            `).join('');
        } else {
            container.innerHTML = `
                <div class="empty-state">
                    <i class="ti ti-git-branch"></i>
                    <h3>No Automation Flows Yet</h3>
                    <p>Set up automated workflows to engage users at the right time</p>
                   
                </div>
            `;
        }
    } catch (error) {
        console.error('Error loading automation flows:', error);
        container.innerHTML = '<div class="error-state">Failed to load flows</div>';
    }
}

// =====================================================
// AUDIENCE SEGMENTS
// =====================================================

async function loadAudienceSegments() {
    const container = document.getElementById('segmentsList');
    container.innerHTML = '<div class="loading-state"><div class="loader-spinner"></div><p>Loading segments...</p></div>';

    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`${API_BASE}/segments/list`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        const data = await response.json();

        if (data.success && data.segments.length > 0) {
            container.innerHTML = data.segments.map(segment => `
                <div class="segment-card">
                    <div class="segment-header">
                        <div class="segment-icon">
                            <i class="ti ti-users"></i>
                        </div>
                        <div class="segment-info">
                            <h3>${segment.segment_name}</h3>
                            <p class="segment-description">${segment.description || 'No description'}</p>
                            <p class="segment-meta">
                                <span class="platform-badge platform-${segment.platform}">
                                    <i class="ti ti-device-mobile"></i> ${segment.platform}
                                </span>
                                <span class="separator">•</span>
                                <i class="ti ti-user"></i> ${segment.client_name}
                            </p>
                        </div>
                    </div>
                    <div class="segment-stats">
                        <div class="stat-item">
                            <div class="stat-value">${segment.estimated_size || 'N/A'}</div>
                            <div class="stat-label">Estimated Size</div>
                        </div>
                    </div>
                    <div class="segment-actions">
                        <button class="btn-action" onclick="viewSegment(${segment.segment_id})">
                            <i class="ti ti-eye"></i> View
                        </button>
                        <button class="btn-action" onclick="editSegment(${segment.segment_id})">
                            <i class="ti ti-edit"></i> Edit
                        </button>
                    </div>
                </div>
            `).join('');
        } else {
            container.innerHTML = `
                <div class="empty-state">
                    <i class="ti ti-users"></i>
                    <h3>No Audience Segments Yet</h3>
                    <p>Create targeted segments to personalize your campaigns</p>
                    
                </div>
            `;
        }
    } catch (error) {
        console.error('Error loading segments:', error);
        container.innerHTML = '<div class="error-state">Failed to load segments</div>';
    }
}

// =====================================================
// MODAL FUNCTIONS
// =====================================================

function openWhatsAppModal() {
    document.getElementById('whatsappModal').classList.add('show');
    document.getElementById('whatsappForm').reset();
}

function openEmailModal() {
    document.getElementById('emailModal').classList.add('show');
    document.getElementById('emailForm').reset();
    if (emailEditor) {
        emailEditor.setContents([]);
    }
}

function openFlowModal() {
    document.getElementById('flowModal').classList.add('show');
    document.getElementById('flowForm').reset();
}


function openSegmentModal() {
    document.getElementById('segmentModal').classList.add('show');
    document.getElementById('segmentForm').reset();

    // Reset CSV data and preview
    csvData = null;
    document.getElementById('csvPreview').style.display = 'none';
    document.getElementById('fileName').textContent = '';
}

function openCreateCampaignModal() {
    // Show selection modal or default to email
    openEmailModal();
}

function closeModal(modalId) {
    document.getElementById(modalId).classList.remove('show');
}

// Close modal on backdrop click
document.addEventListener('click', function (e) {
    if (e.target.classList.contains('modal')) {
        e.target.classList.remove('show');
    }
});

// =====================================================
// EMAIL EDITOR
// =====================================================

function initializeEmailEditor() {
    const editorElement = document.getElementById('emailEditor');
    if (editorElement && !emailEditor) {
        emailEditor = new Quill('#emailEditor', {
            theme: 'snow',
            modules: {
                toolbar: [
                    [{ 'header': [1, 2, 3, false] }],
                    ['bold', 'italic', 'underline', 'strike'],
                    [{ 'color': [] }, { 'background': [] }],
                    [{ 'list': 'ordered' }, { 'list': 'bullet' }],
                    [{ 'align': [] }],
                    ['link', 'image'],
                    ['clean']
                ]
            },
            placeholder: 'Write your email content here...'
        });
    }
}

// =====================================================
// AI EMAIL GENERATION
// =====================================================

async function generateEmailCopy() {
    document.getElementById('aiEmailModal').classList.add('show');
}

// =====================================================
// FORM HANDLERS
// =====================================================

function setupFormHandlers() {
    // WhatsApp Form
    const whatsappForm = document.getElementById('whatsappForm');
    if (whatsappForm) {
        whatsappForm.addEventListener('submit', async function (e) {
            e.preventDefault();
            await submitWhatsAppCampaign();
        });
    }

    // Email Form
    const emailForm = document.getElementById('emailForm');
    if (emailForm) {
        emailForm.addEventListener('submit', async function (e) {
            e.preventDefault();
            await submitEmailCampaign();
        });
    }

    // Flow Form
    const flowForm = document.getElementById('flowForm');
    if (flowForm) {
        flowForm.addEventListener('submit', async function (e) {
            e.preventDefault();
            await submitAutomationFlow();
        });
    }

    // Segment Form
    const segmentForm = document.getElementById('segmentForm');
    if (segmentForm) {
        segmentForm.addEventListener('submit', async function (e) {
            e.preventDefault();
            await submitAudienceSegment();
        });
    }

    // AI Email Form (optional - only if exists)
    const aiEmailForm = document.getElementById('aiEmailForm');
    if (aiEmailForm) {
        aiEmailForm.addEventListener('submit', async function (e) {
            e.preventDefault();
            await submitAIEmailGeneration();
        });
    }
}


async function submitWhatsAppCampaign() {
    try {
        const recipients = window.waRecipients || [];

        if (recipients.length === 0) {
            showNotification('Please select an audience segment', 'error');
            return;
        }

        const form = document.getElementById('whatsappForm');
        const isEditMode = form.dataset.editMode === 'true';
        const campaignId = form.dataset.campaignId;

        const data = {
            client_id: parseInt(document.getElementById('wa_client_id').value),
            campaign_name: document.getElementById('wa_campaign_name').value,
            template_name: document.getElementById('wa_template_name').value,
            message_content: document.getElementById('wa_message_content').value,
            recipient_list: recipients,
            schedule_type: document.getElementById('wa_schedule_type').value,
            scheduled_at: document.getElementById('wa_scheduled_at').value || null
        };

        const token = localStorage.getItem('access_token');
        const url = isEditMode
            ? `${API_BASE}/whatsapp/campaigns/${campaignId}`
            : `${API_BASE}/whatsapp/campaigns/create`;
        const method = isEditMode ? 'PUT' : 'POST';

        const response = await fetch(url, {
            method: method,
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify(data)
        });

        const result = await response.json();

        if (result.success) {
            showNotification(`WhatsApp campaign ${isEditMode ? 'updated' : 'created'} successfully!`, 'success');
            closeModal('whatsappModal');

            // Reset edit mode
            delete form.dataset.editMode;
            delete form.dataset.campaignId;

            loadWhatsAppCampaigns();
            loadAnalytics();
        } else {
            showNotification(result.detail || `Failed to ${isEditMode ? 'update' : 'create'} campaign`, 'error');
        }
    } catch (error) {
        console.error('Error with WhatsApp campaign:', error);
        showNotification('An error occurred', 'error');
    }
}


async function submitEmailCampaign() {
    try {
        // Validate audience selection
        const audienceSelect = document.getElementById('email_audience_segment');
        if (!audienceSelect || !audienceSelect.value) {
            showNotification('Please select an audience segment', 'error');
            return;
        }

        const recipients = window.emailRecipients || [];

        if (recipients.length === 0) {
            showNotification('Please select an audience segment', 'error');
            return;
        }

        const data = {
            client_id: parseInt(document.getElementById('email_client_id').value),
            campaign_name: document.getElementById('email_campaign_name').value,
            subject_line: document.getElementById('email_subject').value,
            email_body: emailEditor ? emailEditor.root.innerHTML : '',
            recipient_list: recipients,
            schedule_type: document.getElementById('email_schedule_type').value,
            scheduled_at: document.getElementById('email_scheduled_at').value || null,
            is_ab_test: document.getElementById('email_ab_test').checked,
            segment_criteria: {},
            ab_test_config: {}
        };

        const token = localStorage.getItem('access_token');
        const response = await fetch(`${API_BASE}/email/campaigns/create`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify(data)
        });

        const result = await response.json();

        if (result.success) {
            showNotification('Email campaign created successfully!', 'success');
            closeModal('emailModal');
            loadEmailCampaigns();
            loadAnalytics();
        } else {
            showNotification(result.detail || 'Failed to create campaign', 'error');
        }
    } catch (error) {
        console.error('Error creating email campaign:', error);
        showNotification('An error occurred', 'error');
    }
}


async function submitAutomationFlow() {
    try {
        const data = {
            client_id: parseInt(document.getElementById('flow_client_id').value),
            flow_name: document.getElementById('flow_name').value,
            trigger_type: document.getElementById('flow_trigger_type').value,
            channel: document.getElementById('flow_channel').value,
            trigger_conditions: {},
            flow_actions: JSON.parse(document.getElementById('flow_actions').value),
            is_active: document.getElementById('flow_active').checked
        };

        const token = localStorage.getItem('access_token');
        const response = await fetch(`${API_BASE}/flows/create`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify(data)
        });

        const result = await response.json();

        if (result.success) {
            showNotification('Automation flow created successfully!', 'success');
            closeModal('flowModal');
            loadAutomationFlows();
            loadAnalytics();
        } else {
            showNotification(result.detail || 'Failed to create flow', 'error');
        }
    } catch (error) {
        console.error('Error creating automation flow:', error);
        showNotification('Invalid JSON or error occurred', 'error');
    }
}


async function submitAudienceSegment() {
    try {
        // Validate CSV upload
        if (!csvData || csvData.length === 0) {
            showNotification('Please upload a CSV file with contacts', 'error');
            return;
        }

        const clientId = parseInt(document.getElementById('segment_client_id').value);
        const segmentName = document.getElementById('segment_name').value;
        const platform = document.getElementById('segment_platform').value;
        const description = document.getElementById('segment_description')?.value || '';

        if (!clientId || !segmentName) {
            showNotification('Please fill all required fields', 'error');
            return;
        }

        // Prepare segment data with full CSV contact data
        const data = {
            client_id: clientId,
            segment_name: segmentName,
            description: description || `Uploaded segment with ${csvData.length} contacts`,
            platform: platform,
            segment_criteria: {
                upload_type: 'csv',
                total_contacts: csvData.length,
                columns: Object.keys(csvData[0] || {}),
                uploaded_at: new Date().toISOString()
            },
            estimated_size: csvData.length,
            contacts_data: csvData  // Send full CSV data to store in database
        };

        console.log('Submitting segment with', csvData.length, 'contacts');

        const token = localStorage.getItem('access_token');
        const response = await fetch(`${API_BASE}/segments/create`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify(data)
        });

        const result = await response.json();

        if (result.success) {
            showNotification(`✅ Segment created with ${csvData.length} contacts!`, 'success');
            closeModal('segmentModal');
            loadAudienceSegments();
            loadSegmentsForDropdown(); // Reload dropdowns
            loadAnalytics();

            // Reset form and CSV data
            csvData = null;
            document.getElementById('segmentForm').reset();
            document.getElementById('csvPreview').style.display = 'none';
            document.getElementById('fileName').textContent = '';
        } else {
            showNotification(result.detail || 'Failed to create segment', 'error');
        }
    } catch (error) {
        console.error('Error creating segment:', error);
        showNotification('An error occurred while creating segment', 'error');
    }
}



async function submitAIEmailGeneration() {
    // Get the submit button
    const submitButton = document.querySelector('#aiEmailForm button[type="submit"]');
    const originalContent = submitButton ? submitButton.innerHTML : '';

    try {
        // Show loading state on button
        if (submitButton) {
            submitButton.disabled = true;
            submitButton.innerHTML = `
                <div class="spinner-border spinner-border-sm" role="status" style="display: inline-block; width: 16px; height: 16px; border: 2px solid currentColor; border-right-color: transparent; border-radius: 50%; animation: spin 0.6s linear infinite;">
                    <span class="visually-hidden"></span>
                </div>
                <span style="margin-left: 8px;">Generating...</span>
            `;
        }

        const data = {
            campaign_goal: document.getElementById('ai_campaign_goal').value,
            target_audience: document.getElementById('ai_target_audience').value,
            tone: document.getElementById('ai_tone').value,
            industry: document.getElementById('ai_industry').value,
            include_cta: document.getElementById('ai_include_cta').checked
        };

        const token = localStorage.getItem('access_token');
        const response = await fetch(`${API_BASE}/email/generate-copy`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify(data)
        });

        const result = await response.json();

        if (result.success && result.email_copy) {
            const copy = result.email_copy;

            // Populate email form
            if (copy.subject_line) {
                document.getElementById('email_subject').value = copy.subject_line;
            }

            if (copy.email_body && emailEditor) {
                emailEditor.root.innerHTML = copy.email_body;
            }

            showNotification('AI email copy generated successfully!', 'success');
            closeModal('aiEmailModal');
        } else {
            showNotification('Failed to generate email copy', 'error');
        }
    } catch (error) {
        console.error('Error generating AI email:', error);
        showNotification('An error occurred', 'error');
    } finally {
        // Restore button state
        if (submitButton) {
            submitButton.disabled = false;
            submitButton.innerHTML = originalContent;
        }
    }
}


// =====================================================
// TOGGLE FUNCTIONS
// =====================================================

function toggleScheduleTime(type) {
    const scheduleType = document.getElementById(`${type}_schedule_type`).value;
    const scheduleGroup = document.getElementById(`${type}_schedule_time_group`);

    if (scheduleType === 'scheduled') {
        scheduleGroup.style.display = 'block';
    } else {
        scheduleGroup.style.display = 'none';
    }
}

async function toggleFlow(flowId, isActive) {
    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`${API_BASE}/flows/${flowId}/toggle`, {
            method: 'PUT',
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        const result = await response.json();

        if (result.success) {
            showNotification(`Flow ${isActive ? 'activated' : 'deactivated'} successfully`, 'success');
            loadAutomationFlows();
        } else {
            showNotification('Failed to toggle flow status', 'error');
        }
    } catch (error) {
        console.error('Error toggling flow:', error);
        showNotification('An error occurred', 'error');
    }
}

// =====================================================
// VIEW FUNCTIONS (Placeholder)
// =====================================================

function viewCampaign(type, id) {
    showNotification(`Viewing ${type} campaign ${id}`, 'info');
    // Implement detailed view modal
}



async function editCampaign(type, id) {

    try {
        const token = localStorage.getItem('access_token');
        let endpoint, modal, formPrefix;

        if (type === 'whatsapp') {
            endpoint = `${API_BASE}/whatsapp/campaigns/${id}`;
            modal = 'whatsappModal';
            formPrefix = 'wa';
        } else if (type === 'email') {
            endpoint = `${API_BASE}/email/campaigns/${id}`;
            modal = 'emailModal';
            formPrefix = 'email';
        }

        const response = await fetch(endpoint, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        const result = await response.json();

        if (result.success) {
            const campaign = result.campaign;

            // Populate form fields
            if (type === 'whatsapp') {
                document.getElementById('wa_campaign_name').value = campaign.campaign_name;
                document.getElementById('wa_client_id').value = campaign.client_id;
                document.getElementById('wa_template_name').value = campaign.template_name || '';
                document.getElementById('wa_message_content').value = campaign.message_content;
                document.getElementById('wa_schedule_type').value = campaign.schedule_type;
                if (campaign.scheduled_at) {
                    const scheduledDate = new Date(campaign.scheduled_at);
                    const dateTimeLocalValue = scheduledDate.toISOString().slice(0, 16);
                    document.getElementById('wa_scheduled_at').value = dateTimeLocalValue;
                }

                // Store campaign ID for update
                document.getElementById('whatsappForm').dataset.campaignId = id;
                document.getElementById('whatsappForm').dataset.editMode = 'true';

            } else if (type === 'email') {
                document.getElementById('email_campaign_name').value = campaign.campaign_name;
                document.getElementById('email_client_id').value = campaign.client_id;
                document.getElementById('email_subject').value = campaign.subject_line;
                if (emailEditor) {
                    emailEditor.root.innerHTML = campaign.email_body;
                }
                document.getElementById('email_schedule_type').value = campaign.schedule_type;
                if (campaign.scheduled_at) {
                    const scheduledDate = new Date(campaign.scheduled_at);
                    const dateTimeLocalValue = scheduledDate.toISOString().slice(0, 16);
                    document.getElementById('email_scheduled_at').value = dateTimeLocalValue;
                }
                document.getElementById('email_ab_test').checked = campaign.is_ab_test;

                // Store campaign ID for update
                document.getElementById('emailForm').dataset.campaignId = id;
                document.getElementById('emailForm').dataset.editMode = 'true';
            }

            // Open modal
            openModal(modal);

        } else {
            showNotification('Failed to load campaign details', 'error');
        }

    } catch (error) {
        console.error('Error loading campaign for edit:', error);
        showNotification('Failed to load campaign', 'error');
    }
}



function viewFlow(flowId) {
    showNotification(`Viewing flow ${flowId}`, 'info');
    // Implement flow details modal
}

function editFlow(flowId) {
    showNotification(`Editing flow ${flowId}`, 'info');
    // Implement edit functionality
}

function viewSegment(segmentId) {
    showNotification(`Viewing segment ${segmentId}`, 'info');
    // Implement segment details modal
}

function editSegment(segmentId) {
    showNotification(`Editing segment ${segmentId}`, 'info');
    // Implement edit functionality
}

// =====================================================
// UTILITY FUNCTIONS
// =====================================================

function formatDate(dateString) {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    });
}

function formatTriggerType(trigger) {
    return trigger.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
}

function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <i class="ti ti-${type === 'success' ? 'check' : type === 'error' ? 'x' : 'info-circle'}"></i>
        <span>${message}</span>
    `;

    document.body.appendChild(notification);

    // Trigger animation
    setTimeout(() => notification.classList.add('show'), 10);

    // Remove after 3 seconds
    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}


// ADD THESE FUNCTIONS TO communication.js

// =====================================================
// FLOW BUILDER - USER FRIENDLY
// =====================================================

let flowActionCounter = 0;

function openFlowModal() {
    document.getElementById('flowModal').classList.add('show');
    document.getElementById('flowForm').reset();

    // Initialize with one action
    flowActionCounter = 0;
    document.getElementById('flowActionsBuilder').innerHTML = '';
    addFlowAction();
}

function addFlowAction() {
    flowActionCounter++;
    const builder = document.getElementById('flowActionsBuilder');

    const actionDiv = document.createElement('div');
    actionDiv.className = 'flow-action-item';
    actionDiv.id = `flow_action_${flowActionCounter}`;
    actionDiv.innerHTML = `
        <div class="flow-action-header">
            <span class="flow-action-number">Action ${flowActionCounter}</span>
            ${flowActionCounter > 1 ? `<button type="button" class="btn-remove" onclick="removeFlowAction(${flowActionCounter})"><i class="ti ti-trash"></i></button>` : ''}
        </div>
        <div class="form-row">
            <div class="form-group">
                <label>Action Type</label>
                <select class="flow-action-type" required>
                    <option value="send_email">Send Email</option>
                    <option value="send_whatsapp">Send WhatsApp</option>
                    <option value="send_sms">Send SMS</option>
                    <option value="wait">Wait/Delay</option>
                    <option value="add_tag">Add Tag</option>
                    <option value="notify_team">Notify Team</option>
                </select>
            </div>
            <div class="form-group">
                <label>Delay</label>
                <select class="flow-action-delay" required>
                    <option value="0">Immediate</option>
                    <option value="5_minutes">5 Minutes</option>
                    <option value="30_minutes">30 Minutes</option>
                    <option value="1_hour">1 Hour</option>
                    <option value="6_hours">6 Hours</option>
                    <option value="1_day">1 Day</option>
                    <option value="3_days">3 Days</option>
                    <option value="1_week">1 Week</option>
                    <option value="2_weeks">2 Weeks</option>
                    <option value="1_month">1 Month</option>
                </select>
            </div>
        </div>
        <div class="form-group">
            <label>Template/Message Name</label>
            <input type="text" class="flow-action-template" placeholder="e.g., welcome_email, followup_message" required>
        </div>
    `;

    builder.appendChild(actionDiv);
}

function removeFlowAction(id) {
    const actionDiv = document.getElementById(`flow_action_${id}`);
    if (actionDiv) {
        actionDiv.remove();
    }

    // Renumber remaining actions
    const actions = document.querySelectorAll('.flow-action-item');
    actions.forEach((action, index) => {
        action.querySelector('.flow-action-number').textContent = `Action ${index + 1}`;
    });
}

function buildFlowActionsJSON() {
    const actions = [];
    const actionItems = document.querySelectorAll('.flow-action-item');

    actionItems.forEach(item => {
        const actionType = item.querySelector('.flow-action-type').value;
        const delay = item.querySelector('.flow-action-delay').value;
        const template = item.querySelector('.flow-action-template').value;

        actions.push({
            action: actionType,
            delay: delay,
            template: template
        });
    });

    return actions;
}

// UPDATE the submitAutomationFlow function
async function submitAutomationFlow() {
    try {
        const flowActions = buildFlowActionsJSON();

        if (flowActions.length === 0) {
            showNotification('Please add at least one action', 'error');
            return;
        }

        const data = {
            client_id: parseInt(document.getElementById('flow_client_id').value),
            flow_name: document.getElementById('flow_name').value,
            trigger_type: document.getElementById('flow_trigger_type').value,
            channel: document.getElementById('flow_channel').value,
            trigger_conditions: {},
            flow_actions: flowActions,
            is_active: document.getElementById('flow_active').checked
        };

        const token = localStorage.getItem('access_token');
        const response = await fetch(`${API_BASE}/flows/create`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify(data)
        });

        const result = await response.json();

        if (result.success) {
            showNotification('Automation flow created successfully!', 'success');
            closeModal('flowModal');
            loadAutomationFlows();
            loadAnalytics();
        } else {
            showNotification(result.detail || 'Failed to create flow', 'error');
        }
    } catch (error) {
        console.error('Error creating automation flow:', error);
        showNotification('An error occurred', 'error');
    }
}

// =====================================================
// SEGMENT MANAGEMENT - DELETE & VIEW
// =====================================================

// Handle Quick Segment Form Submission
document.addEventListener('DOMContentLoaded', function () {
    const quickSegmentForm = document.getElementById('quickSegmentForm');
    if (quickSegmentForm) {
        quickSegmentForm.addEventListener('submit', async function (e) {
            e.preventDefault();
            await submitQuickSegment();
        });
    }
});


async function viewSegment(segmentId) {
    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`${API_BASE}/segments/${segmentId}`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        const data = await response.json();

        if (data.success) {
            const segment = data.segment;

            // Show segment details in a modal or alert
            const details = `
Segment: ${segment.segment_name}
Platform: ${segment.platform}
Estimated Size: ${segment.estimated_size || 0} contacts
Description: ${segment.description || 'No description'}
Created: ${new Date(segment.created_at).toLocaleDateString()}
Client: ${segment.client_name}
            `;

            alert(details);
        }
    } catch (error) {
        console.error('Error viewing segment:', error);
        showNotification('Failed to load segment details', 'error');
    }
}

async function deleteSegment(segmentId, segmentName) {
    if (!confirm(`Are you sure you want to delete "${segmentName}"? This action cannot be undone.`)) {
        return;
    }

    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`${API_BASE}/segments/${segmentId}`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        const data = await response.json();

        if (data.success) {
            showNotification('Segment deleted successfully', 'success');
            loadAudienceSegments();
            loadAnalytics();
        } else {
            showNotification(data.detail || 'Failed to delete segment', 'error');
        }
    } catch (error) {
        console.error('Error deleting segment:', error);
        showNotification('An error occurred', 'error');
    }
}

function openModal(modalId) {
    document.getElementById(modalId).classList.add('active');
}



// Quick Segment Creation
function openQuickCreateSegment(returnTo) {
    document.getElementById('quick_return_to').value = returnTo;

    // Populate client dropdown
    const clientSelect = document.getElementById('quick_client_id');
    clientSelect.innerHTML = '<option value="">Choose client...</option>';
    clientsList.forEach(client => {
        const option = document.createElement('option');
        option.value = client.user_id;
        option.textContent = `${client.full_name}${client.business_name ? ' - ' + client.business_name : ''}`;
        clientSelect.appendChild(option);
    });

    // Set platform based on return destination
    if (returnTo === 'wa') {
        document.getElementById('quick_platform').value = 'whatsapp';
    } else if (returnTo === 'email') {
        document.getElementById('quick_platform').value = 'email';
    }

    openModal('quickSegmentModal');
}

async function submitQuickSegment() {
    try {
        const contactsText = document.getElementById('quick_contacts').value.trim();
        const contactsList = contactsText.split('\n').map(c => c.trim()).filter(c => c);

        if (contactsList.length === 0) {
            showNotification('Please add at least one contact', 'error');
            return;
        }

        // Parse contacts into structured data
        const contactsData = contactsList.map(contact => {
            if (contact.includes('@')) {
                return { type: 'email', value: contact };
            } else {
                return { type: 'phone', value: contact };
            }
        });

        const data = {
            client_id: parseInt(document.getElementById('quick_client_id').value),
            segment_name: document.getElementById('quick_segment_name').value,
            platform: document.getElementById('quick_platform').value,
            description: `Quick-created segment with ${contactsList.length} contacts`,
            segment_criteria: { source: 'manual_upload' },
            estimated_size: contactsList.length,
            contacts_data: contactsData
        };

        const token = localStorage.getItem('access_token');
        const response = await fetch(`${API_BASE}/segments/create`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify(data)
        });

        const result = await response.json();

        if (result.success) {
            showNotification('Audience segment created successfully!', 'success');
            closeModal('quickSegmentModal');

            // Reload segments list
            await loadSegmentsForDropdown();

            // Auto-select the newly created segment
            const returnTo = document.getElementById('quick_return_to').value;
            if (returnTo) {
                const selectElement = document.getElementById(`${returnTo}_audience_segment`);
                if (selectElement && result.segment_id) {
                    selectElement.value = result.segment_id;
                    loadAudienceRecipients(returnTo);
                }
            }
        } else {
            showNotification(result.detail || 'Failed to create segment', 'error');
        }
    } catch (error) {
        console.error('Error creating quick segment:', error);
        showNotification('An error occurred', 'error');
    }
}
// UPDATE the loadAudienceSegments function to remove Edit button and add Delete
async function loadAudienceSegments() {
    const container = document.getElementById('segmentsList');
    container.innerHTML = '<div class="loading-state"><div class="loader-spinner"></div><p>Loading segments...</p></div>';

    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`${API_BASE}/segments/list`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        const data = await response.json();

        if (data.success && data.segments.length > 0) {
            container.innerHTML = data.segments.map(segment => `
                <div class="segment-card">
                    <div class="segment-header">
                        <div class="segment-icon">
                            <i class="ti ti-users"></i>
                        </div>
                        <div class="segment-info">
                            <h3>${segment.segment_name}</h3>
                            <p class="segment-description">${segment.description || 'No description'}</p>
                            <p class="segment-meta">
                                <span class="platform-badge platform-${segment.platform}">
                                    <i class="ti ti-device-mobile"></i> ${segment.platform}
                                </span>
                                <span class="separator">•</span>
                                <i class="ti ti-user"></i> ${segment.client_name}
                            </p>
                        </div>
                    </div>
                    <div class="segment-stats">
                        <div class="stat-item">
                            <div class="stat-value">${segment.estimated_size || 0}</div>
                            <div class="stat-label">Contacts</div>
                        </div>
                    </div>
                    <div class="segment-actions">
                        <button class="btn-action btn-action-view" onclick="viewSegment(${segment.segment_id})">
                            <i class="ti ti-eye"></i> View
                        </button>
                        <button class="btn-action btn-action-delete" onclick="deleteSegment(${segment.segment_id}, '${segment.segment_name}')">
                            <i class="ti ti-trash"></i> Delete
                        </button>
                    </div>
                </div>
            `).join('');
        } else {
            container.innerHTML = `
                <div class="empty-state">
                    <i class="ti ti-users"></i>
                    <h3>No Audience Segments Yet</h3>
                    <p>Create targeted segments to personalize your campaigns</p>
                </div>
            `;
        }
    } catch (error) {
        console.error('Error loading segments:', error);
        container.innerHTML = '<div class="error-state">Failed to load segments</div>';
    }
}