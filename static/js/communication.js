/**
 * Communication Hub - JavaScript Implementation
 * File: static/js/communication.js
 */

const API_BASE = '/api/v1/communication';
let emailEditor = null;
let currentTab = 'whatsapp';
let clientsList = [];
let segmentsList = [];
let currentUser = null;
let csvData = null;

// =====================================================
// INITIALIZATION
// =====================================================

document.addEventListener('DOMContentLoaded', async function() {
    await initializePage();
    initializeEmailEditor();
    initializeFileUpload();
});

// =====================================================
// GET CURRENT USER
// =====================================================

async function getCurrentUser() {
    if (currentUser) return currentUser;
    
    try {
        const token = localStorage.getItem('access_token');
        if (!token) {
            window.location.href = '/login';
            return null;
        }
        
        // Decode JWT to get user info (simple decode, not validation)
        const payload = JSON.parse(atob(token.split('.')[1]));
        currentUser = {
            user_id: payload.sub,
            email: payload.email,
            role: payload.role,
            full_name: payload.full_name
        };
        
        return currentUser;
    } catch (error) {
        console.error('Error getting current user:', error);
        window.location.href = '/login';
        return null;
    }
}

async function initializePage() {
    try {
        // Get current user
        await getCurrentUser();
        
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
        const response = await fetch('/api/v1/clients/list', {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
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
            
            // Filter segments by platform
            const filteredSegments = segmentsList.filter(seg => 
                seg.platform === platform || seg.platform === 'all'
            );
            
            filteredSegments.forEach(segment => {
                const option = document.createElement('option');
                option.value = segment.segment_id;
                option.textContent = `${segment.segment_name} (${segment.estimated_size || 0} contacts)`;
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
            const count = type === 'wa' ? data.phones.length : data.emails.length;
            countElement.textContent = `${count} recipients selected`;
            
            // Store recipients for form submission
            if (type === 'wa') {
                window.waRecipients = data.phones;
            } else {
                window.emailRecipients = data.emails;
            }
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
    
    // Show file name
    document.getElementById('fileName').textContent = `Selected: ${file.name}`;
    
    // Parse CSV
    Papa.parse(file, {
        header: true,
        skipEmptyLines: true,
        complete: function(results) {
            csvData = results.data;
            displayCSVPreview(results.data);
        },
        error: function(error) {
            showNotification('Error parsing CSV file', 'error');
            console.error('CSV Parse Error:', error);
        }
    });
}

function displayCSVPreview(data) {
    const previewDiv = document.getElementById('csvPreview');
    const tableDiv = document.getElementById('previewTable');
    const statsDiv = document.getElementById('previewStats');
    
    if (!previewDiv || !tableDiv || !statsDiv) return;
    
    // Show preview section
    previewDiv.style.display = 'block';
    
    // Get first 5 rows
    const previewData = data.slice(0, 5);
    const headers = Object.keys(previewData[0] || {});
    
    // Create table
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
    
    tableDiv.innerHTML = tableHTML;
    
    // Calculate stats
    const totalContacts = data.length;
    const emailCount = data.filter(row => row.email).length;
    const phoneCount = data.filter(row => row.phone).length;
    
    statsDiv.innerHTML = `
        <div>Total Contacts: <span>${totalContacts}</span></div>
        <div>With Email: <span>${emailCount}</span></div>
        <div>With Phone: <span>${phoneCount}</span></div>
    `;
}

function downloadCSVTemplate() {
    const csvContent = "name,email,phone\nJohn Doe,john@example.com,+1234567890\nJane Smith,jane@example.com,+0987654321\n";
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    
    link.setAttribute('href', url);
    link.setAttribute('download', 'audience_template.csv');
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
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
            
            // Update WhatsApp stats
            document.getElementById('whatsappCampaigns').textContent = analytics.whatsapp.total_campaigns;
            document.getElementById('whatsappDeliveryRate').textContent = `${analytics.whatsapp.delivery_rate}% delivery rate`;
            
            // Update Email stats
            document.getElementById('emailCampaigns').textContent = analytics.email.total_campaigns;
            document.getElementById('emailOpenRate').textContent = `${analytics.email.open_rate}% open rate`;
            
            // Update Flows stats
            document.getElementById('activeFlows').textContent = analytics.flows.active_flows;
            document.getElementById('totalFlows').textContent = `${analytics.flows.total_flows} total automation flows`;
        }
    } catch (error) {
        console.error('Error loading analytics:', error);
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
    switch(tabName) {
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
}

function openCreateCampaignModal() {
    // Show selection modal or default to email
    openEmailModal();
}

function closeModal(modalId) {
    document.getElementById(modalId).classList.remove('show');
}

// Close modal on backdrop click
document.addEventListener('click', function(e) {
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
                    [{ 'list': 'ordered'}, { 'list': 'bullet' }],
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
    document.getElementById('whatsappForm').addEventListener('submit', async function(e) {
        e.preventDefault();
        await submitWhatsAppCampaign();
    });
    
    // Email Form
    document.getElementById('emailForm').addEventListener('submit', async function(e) {
        e.preventDefault();
        await submitEmailCampaign();
    });
    
    // Flow Form
    document.getElementById('flowForm').addEventListener('submit', async function(e) {
        e.preventDefault();
        await submitAutomationFlow();
    });
    
    // Segment Form
    document.getElementById('segmentForm').addEventListener('submit', async function(e) {
        e.preventDefault();
        await submitAudienceSegment();
    });
    
    // AI Email Form
    document.getElementById('aiEmailForm').addEventListener('submit', async function(e) {
        e.preventDefault();
        await submitAIEmailGeneration();
    });
}

async function submitWhatsAppCampaign() {
    try {
        const recipients = window.waRecipients || [];
        
        if (recipients.length === 0) {
            showNotification('Please select an audience segment', 'error');
            return;
        }
        
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
        const response = await fetch(`${API_BASE}/whatsapp/campaigns/create`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify(data)
        });
        
        const result = await response.json();
        
        if (result.success) {
            showNotification('WhatsApp campaign created successfully!', 'success');
            closeModal('whatsappModal');
            loadWhatsAppCampaigns();
            loadAnalytics();
        } else {
            showNotification(result.detail || 'Failed to create campaign', 'error');
        }
    } catch (error) {
        console.error('Error creating WhatsApp campaign:', error);
        showNotification('An error occurred', 'error');
    }
}

async function submitEmailCampaign() {
    try {
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
        const data = {
            client_id: parseInt(document.getElementById('segment_client_id').value),
            segment_name: document.getElementById('segment_name').value,
            description: document.getElementById('segment_description').value,
            platform: document.getElementById('segment_platform').value,
            segment_criteria: JSON.parse(document.getElementById('segment_criteria').value)
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
            closeModal('segmentModal');
            loadAudienceSegments();
        } else {
            showNotification(result.detail || 'Failed to create segment', 'error');
        }
    } catch (error) {
        console.error('Error creating segment:', error);
        showNotification('Invalid JSON or error occurred', 'error');
    }
}

async function submitAIEmailGeneration() {
    try {
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

function editCampaign(type, id) {
    showNotification(`Editing ${type} campaign ${id}`, 'info');
    // Implement edit functionality
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