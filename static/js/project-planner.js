// =====================================================
// GLOBAL VARIABLES
// =====================================================
let currentStep = 1;
let proposalData = {};
let quillEditor = null;
let currentProposalId = null;

const API_BASE = '/api/v1';
// =====================================================
// INITIALIZATION
// =====================================================
document.addEventListener('DOMContentLoaded', function() {
    console.log('Project Planner initialized');
    loadProposals();
    initializeEventListeners();
});

// =====================================================
// EVENT LISTENERS
// =====================================================
function initializeEventListeners() {
    // Step 1 Form Submit
    const clientForm = document.getElementById('clientDetailsForm');
    if (clientForm) {
        clientForm.addEventListener('submit', handleClientFormSubmit);
    }
}

// =====================================================
// TAB SWITCHING
// =====================================================
function switchTab(tabName) {
    // Update tab buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    document.querySelector(`.tab-btn[data-tab="${tabName}"]`).classList.add('active');
    
    // Update tab content
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });
    document.getElementById(`tab-${tabName}`).classList.add('active');
    
    // Reset wizard if switching to create tab
    if (tabName === 'create' && currentStep !== 1) {
        resetWizard();
    }
    
    // Load proposals if switching to proposals tab
    if (tabName === 'proposals') {
        loadProposals();
    }
}

function showCreateTab() {
    switchTab('create');
    resetWizard();
}

// =====================================================
// WIZARD NAVIGATION
// =====================================================
function goToStep(stepNumber) {
    // Validate current step before proceeding
    if (stepNumber > currentStep) {
        if (!validateCurrentStep()) {
            return;
        }
    }
    
    // Hide current step
    document.querySelectorAll('.step-content').forEach(content => {
        content.classList.remove('active');
    });
    
    // Update stepper items
    document.querySelectorAll('.stepper-item').forEach((item, index) => {
        const step = index + 1;
        item.classList.remove('active', 'completed');
        
        if (step < stepNumber) {
            item.classList.add('completed');
        } else if (step === stepNumber) {
            item.classList.add('active');
        }
    });
    
    // Show new step
    document.getElementById(`step${stepNumber}`).classList.add('active');
    currentStep = stepNumber;
    
    // Update progress bar
    updateProgressBar();
    
    // Initialize step-specific features
    if (stepNumber === 2) {
        initializeEditor();
    } else if (stepNumber === 3) {
        populateProposalSummary();
    }
    
    // Scroll to top
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function updateProgressBar() {
    const progress = document.getElementById('stepperProgress');
    if (progress) {
        const percentage = ((currentStep - 1) / 2) * 70; // 0%, 35%, 70%
        progress.style.width = `${percentage}%`;
    }
}

function validateCurrentStep() {
    if (currentStep === 1) {
        const form = document.getElementById('clientDetailsForm');
        return form.checkValidity();
    }
    return true;
}

function resetWizard() {
    currentStep = 1;
    proposalData = {};
    currentProposalId = null;
    
    // Reset form
    const form = document.getElementById('clientDetailsForm');
    if (form) {
        form.reset();
    }
    
    // Reset editor
    if (quillEditor) {
        quillEditor.setContents([]);
    }
    
    // Show step 1
    goToStep(1);
}

// =====================================================
// STEP 1: CLIENT FORM HANDLING
// =====================================================
async function handleClientFormSubmit(e) {
    e.preventDefault();
    
    // Show loading
    showLoading();
    
    try {
        // Collect form data
        const formData = new FormData(e.target);
        const existingPresence = {};
        
        // Collect checkboxes
        document.querySelectorAll('input[type="checkbox"][name^="existing_"]').forEach(checkbox => {
            const key = checkbox.name.replace('existing_', '');
            existingPresence[key] = checkbox.checked;
        });
        
        // Build request payload
        const payload = {
            lead_name: formData.get('lead_name'),
            lead_email: formData.get('lead_email'),
            company_name: formData.get('company_name'),
            business_type: formData.get('business_type'),
            budget: parseFloat(formData.get('budget')),
            target_audience: formData.get('target_audience'),
            challenges: formData.get('challenges'),
            existing_presence: existingPresence
        };
        
        console.log('Submitting proposal request:', payload);
        
        // Call API to generate proposal
        const token = localStorage.getItem('access_token');
        if (!token) {
            window.location.href = '/auth/login';
            return;
        }
        
        const response = await fetch(`${API_BASE}/project-planner/generate-proposal`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify(payload)
        });

        
        
        const result = await response.json();
        
        if (result.success) {
            // Store proposal data
            proposalData = result.proposal;
            currentProposalId = result.proposal_id;
            
            console.log('Proposal generated successfully:', result);
            
            // Show success notification
            showNotification('AI Strategy generated successfully!', 'success');
            
            // Move to step 2 after short delay
            setTimeout(() => {
                hideLoading();
                goToStep(2);
                loadGeneratedContent(result.proposal);
            }, 1000);
        } else {
            hideLoading();
            showNotification(result.message || 'Failed to generate proposal', 'error');
        }
    } catch (error) {
        console.error('Error generating proposal:', error);
        hideLoading();
        showNotification('Failed to generate proposal. Please try again.', 'error');
    }
}

// =====================================================
// STEP 2: RICH TEXT EDITOR
// =====================================================
function initializeEditor() {
    // Check if editor is already initialized
    if (quillEditor) {
        return;
    }
    
    // Show loading state
    document.getElementById('aiLoadingState').style.display = 'block';
    document.getElementById('editorContainer').style.display = 'none';
    
    // Initialize Quill editor after delay (simulating AI generation)
    setTimeout(() => {
        const toolbarOptions = [
            [{ 'font': [] }, { 'size': [] }],
            ['bold', 'italic', 'underline', 'strike'],
            [{ 'color': [] }, { 'background': [] }],
            [{ 'align': [] }],
            [{ 'list': 'ordered'}, { 'list': 'bullet' }],
            [{ 'indent': '-1'}, { 'indent': '+1' }],
            [{ 'header': [1, 2, false] }],
            ['blockquote'],
            ['link', 'image'],
            ['clean']
        ];
        
        quillEditor = new Quill('#editor', {
            theme: 'snow',
            modules: {
                toolbar: '#toolbar'
            },
            placeholder: 'AI-generated content will appear here...'
        });
        
        // Hide loading and show editor
        document.getElementById('aiLoadingState').style.display = 'none';
        document.getElementById('editorContainer').style.display = 'block';
        document.getElementById('step2Navigation').style.display = 'flex';
        
        console.log('Quill editor initialized');
    }, 500);
}

function loadGeneratedContent(proposal) {
    if (!quillEditor) {
        console.error('Editor not initialized');
        return;
    }
    
    // Generate comprehensive proposal content
    const strategy = proposal.ai_generated_strategy || {};
    const differentiators = proposal.competitive_differentiators || {};
    const timeline = proposal.suggested_timeline || {};
    
    const content = generateProposalHTML(proposal, strategy, differentiators, timeline);
    
    // Set content in editor
    quillEditor.clipboard.dangerouslyPasteHTML(content);
    
    // Populate AI Insights
    populateAIInsights(strategy, differentiators);
    
    console.log('Content loaded into editor');
}

function generateProposalHTML(proposal, strategy, differentiators, timeline) {
    const campaigns = strategy.campaigns || [];
    const tools = strategy.automation_tools || [];
    const diffItems = differentiators.differentiators || [];
    const phases = timeline.phases || [];
    
    return `
        <h1 style="text-align: center; color: #9926F3;">Digital Marketing Proposal</h1>
        <h2 style="text-align: center; color: #1DD8FC;">for ${proposal.company_name || 'Your Company'}</h2>
        <p style="text-align: center; margin-bottom: 2rem;"><em>Prepared by PanvelIQ</em></p>
        
        <hr style="margin: 2rem 0;">
        
        <h2><strong>Executive Summary</strong></h2>
        <p>This comprehensive digital marketing proposal has been specifically designed for <strong>${proposal.company_name || 'your organization'}</strong>, a ${proposal.business_type} looking to enhance their digital presence and drive measurable growth.</p>
        <p>Our AI-powered approach combines cutting-edge marketing technology with proven strategies to deliver exceptional results within your investment budget of <strong>$${(proposal.budget || 0).toLocaleString()}</strong>.</p>
        
        <h2><strong>Current Challenges</strong></h2>
        <p>${proposal.challenges || 'No specific challenges mentioned.'}</p>
        
        <h2><strong>Target Audience Analysis</strong></h2>
        <p>${proposal.target_audience || 'Target audience not specified.'}</p>
        
        <h2><strong>Recommended Marketing Strategy</strong></h2>
        <p>Based on our AI analysis, we recommend the following comprehensive marketing approach:</p>
        
        <h3><strong>Recommended Campaigns</strong></h3>
        <ul>
            ${campaigns.map(camp => `<li><strong>${camp.name || 'Campaign'}:</strong> ${camp.description || ''}</li>`).join('')}
        </ul>
        
        <h3><strong>Automation Tools & Technologies</strong></h3>
        <ul>
            ${tools.map(tool => `<li>${tool.name || tool}: ${tool.purpose || ''}</li>`).join('')}
        </ul>
        
        <h2><strong>Competitive Differentiators</strong></h2>
        <p>What sets our approach apart:</p>
        <ul>
            ${diffItems.map(diff => `
                <li>
                    <strong>${diff.title || 'Differentiator'}:</strong> ${diff.description || ''}<br>
                    <em>Impact: ${diff.impact || 'Significant improvement expected'}</em>
                </li>
            `).join('')}
        </ul>
        
        <h2><strong>Project Timeline</strong></h2>
        ${phases.map((phase, idx) => `
            <h3><strong>Phase ${idx + 1}: ${phase.name || 'Phase ' + (idx + 1)}</strong></h3>
            <p><strong>Duration:</strong> ${phase.duration || 'TBD'}</p>
            <p><strong>Key Deliverables:</strong></p>
            <ul>
                ${(phase.deliverables || []).map(del => `<li>${del}</li>`).join('')}
            </ul>
        `).join('')}
        
        <hr style="margin: 2rem 0;">
        
        <h2><strong>Investment & ROI</strong></h2>
        <p><strong>Total Investment:</strong> $${(proposal.budget || 0).toLocaleString()}</p>
        <p>Our data-driven approach ensures maximum return on investment through:</p>
        <ul>
            <li>Continuous performance optimization</li>
            <li>AI-powered audience targeting</li>
            <li>Real-time analytics and reporting</li>
            <li>Agile campaign management</li>
        </ul>
        
        <h2><strong>Next Steps</strong></h2>
        <ol>
            <li>Review this proposal and provide feedback</li>
            <li>Schedule a strategy session to discuss implementation</li>
            <li>Finalize project scope and timeline</li>
            <li>Begin Phase 1 execution</li>
        </ol>
        
        <hr style="margin: 2rem 0;">
        
        <p style="text-align: center;"><strong>We look forward to partnering with you to achieve exceptional marketing results!</strong></p>
        <p style="text-align: center;"><em>Contact: info@panveliq.com | www.panveliq.com</em></p>
    `;
}

function populateAIInsights(strategy, differentiators) {
    const insightsContainer = document.getElementById('aiInsightsContent');
    if (!insightsContainer) return;
    
    const insights = [
        {
            title: 'Budget Optimization',
            icon: 'currency-dollar',
            content: 'AI recommends allocating 40% to paid advertising, 30% to content creation, 20% to SEO, and 10% to analytics tools for optimal ROI.'
        },
        {
            title: 'Platform Priority',
            icon: 'chart-line',
            content: `Focus on ${strategy.platforms ? strategy.platforms.join(', ') : 'social media, search, and email marketing'} based on your target audience demographics and behavior patterns.`
        },
        {
            title: 'Timeline Recommendation',
            icon: 'clock',
            content: 'Expected to see initial results in 30-45 days, with full campaign optimization achieved by month 3.'
        },
        {
            title: 'Key Success Metrics',
            icon: 'target',
            content: 'Track: Website traffic (+50%), Lead generation (+40%), Conversion rate (+25%), Social engagement (+60%).'
        }
    ];
    
    insightsContainer.innerHTML = insights.map(insight => `
        <div class="ai-insight-item">
            <div class="insight-title">
                <i class="ti ti-${insight.icon}"></i>
                ${insight.title}
            </div>
            <div class="insight-content">${insight.content}</div>
        </div>
    `).join('');
}

// =====================================================
// STEP 3: EXPORT & SHARE
// =====================================================
function populateProposalSummary() {
    const container = document.getElementById('proposalSummaryContent');
    if (!container || !proposalData) return;
    
    const summary = [
        { label: 'Company', value: proposalData.company_name || 'N/A', icon: 'building' },
        { label: 'Business Type', value: proposalData.business_type || 'N/A', icon: 'briefcase' },
        { label: 'Budget', value: `$${(proposalData.budget || 0).toLocaleString()}`, icon: 'currency-dollar' },
        { label: 'Contact', value: proposalData.lead_name || 'N/A', icon: 'user' },
        { label: 'Email', value: proposalData.lead_email || 'N/A', icon: 'mail' },
        { label: 'Status', value: 'Draft', icon: 'file' }
    ];
    
    container.innerHTML = summary.map(item => `
        <div class="summary-item">
            <span class="summary-label">
                <i class="ti ti-${item.icon}"></i> ${item.label}
            </span>
            <span class="summary-value">${item.value}</span>
        </div>
    `).join('');
}

// =====================================================
// EXPORT FUNCTIONS
// =====================================================
async function exportProposal(format) {
    if (!currentProposalId) {
        showNotification('Please generate a proposal first', 'error');
        return;
    }
    
    showLoading();
    
    try {
        const response = await fetch(`${API_BASE}/project-planner/proposals/${currentProposalId}/export/pdf`);
        
        if (response.ok) {
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `proposal_${currentProposalId}.pdf`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
            
            showNotification('Proposal exported successfully!', 'success');
        } else {
            throw new Error('Export failed');
        }
    } catch (error) {
        console.error('Export error:', error);
        showNotification('Failed to export proposal', 'error');
    } finally {
        hideLoading();
    }
}

async function generateShareLink() {
    if (!currentProposalId) {
        showNotification('Please generate a proposal first', 'error');
        return;
    }
    
    showLoading();
    
    try {
        const response = await fetch(`${API_BASE}/project-planner/proposals/${currentProposalId}/share-link`, {
            method: 'POST'
        });
        
        const result = await response.json();
        
        if (result.success) {
            document.getElementById('generatedLink').value = result.share_link;
            document.getElementById('shareLinkResult').style.display = 'block';
            showNotification('Share link generated!', 'success');
        } else {
            throw new Error(result.message || 'Failed to generate link');
        }
    } catch (error) {
        console.error('Share link error:', error);
        showNotification('Failed to generate share link', 'error');
    } finally {
        hideLoading();
    }
}

function copyShareLink() {
    const input = document.getElementById('generatedLink');
    input.select();
    document.execCommand('copy');
    showNotification('Link copied to clipboard!', 'success');
}

function openEmailModal() {
    if (!currentProposalId) {
        showNotification('Please generate a proposal first', 'error');
        return;
    }
    
    // Pre-fill recipient email
    const emailInput = document.getElementById('recipientEmail');
    if (emailInput && proposalData.lead_email) {
        emailInput.value = proposalData.lead_email;
    }
    
    document.getElementById('emailModal').classList.add('active');
}

function closeModal(modalId) {
    document.getElementById(modalId).classList.remove('active');
}

async function sendEmail() {
    const recipientEmail = document.getElementById('recipientEmail').value;
    const subject = document.getElementById('emailSubject').value;
    const message = document.getElementById('emailMessage').value;
    
    if (!recipientEmail || !subject || !message) {
        showNotification('Please fill in all fields', 'error');
        return;
    }
    
    showLoading();
    closeModal('emailModal');
    
    try {
        const response = await fetch(`${API_BASE}/project-planner/proposals/${currentProposalId}/send-email`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                recipient_email: recipientEmail,
                subject: subject,
                message: message
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            showNotification('Proposal sent via email successfully!', 'success');
        } else {
            throw new Error(result.message || 'Failed to send email');
        }
    } catch (error) {
        console.error('Email error:', error);
        showNotification('Failed to send email', 'error');
    } finally {
        hideLoading();
    }
}

async function sendToDashboard() {
    if (!currentProposalId) {
        showNotification('Please generate a proposal first', 'error');
        return;
    }
    
    showLoading();
    
    try {
        const response = await fetch(`${API_BASE}/project-planner/proposals/${currentProposalId}/send-to-dashboard`, {
            method: 'POST'
        });
        
        const result = await response.json();
        
        if (result.success) {
            showNotification('Proposal added to client dashboard!', 'success');
        } else {
            throw new Error(result.message || 'Failed to send to dashboard');
        }
    } catch (error) {
        console.error('Dashboard error:', error);
        showNotification('Failed to send to dashboard', 'error');
    } finally {
        hideLoading();
    }
}

function finishProposal() {
    showNotification('Proposal completed successfully!', 'success');
    
    // Reload proposals list
    setTimeout(() => {
        switchTab('proposals');
        resetWizard();
    }, 1500);
}

// =====================================================
// LOAD PROPOSALS (ALL TAB)
// =====================================================
async function loadProposals() {
    const container = document.getElementById('proposalsContainer');
    if (!container) return;
    
    container.innerHTML = '<div class="loading-state"><div class="loader-spinner"></div><p>Loading proposals...</p></div>';
    
    try {

         const token = localStorage.getItem('access_token');
        if (!token) {
            window.location.href = '/auth/login';
            return;
        }

        const response = await fetch(`${API_BASE}/project-planner/proposals/list`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        const result = await response.json();
        
        if (result.success && result.proposals.length > 0) {
            container.innerHTML = `
                <div class="proposals-grid">
                    ${result.proposals.map(proposal => createProposalCard(proposal)).join('')}
                </div>
            `;
        } else {
            container.innerHTML = `
                <div class="empty-state">
                    <i class="ti ti-file-off"></i>
                    <h3>No Proposals Yet</h3>
                    <p>Create your first AI-powered marketing proposal</p>
                    <button class="btn btn-primary" onclick="showCreateTab()">
                        <i class="ti ti-plus"></i>
                        Create New Proposal
                    </button>
                </div>
            `;
        }
    } catch (error) {
        console.error('Error loading proposals:', error);
        container.innerHTML = `
            <div class="empty-state">
                <i class="ti ti-alert-circle"></i>
                <h3>Error Loading Proposals</h3>
                <p>Please try again later</p>
            </div>
        `;
    }
}

function createProposalCard(proposal) {
    const statusClass = `status-${proposal.status.toLowerCase()}`;
    const createdDate = new Date(proposal.created_at).toLocaleDateString();
    
    return `
        <div class="proposal-card">
            <div class="proposal-header">
                <div class="proposal-client">
                    <h3>${proposal.company_name || 'Untitled'}</h3>
                    <p>${proposal.business_type}</p>
                </div>
                <span class="status-badge ${statusClass}">${proposal.status}</span>
            </div>
            
            <div class="proposal-details">
                <div class="detail-item">
                    <span class="detail-label">
                        <i class="ti ti-currency-dollar"></i>
                        Budget
                    </span>
                    <span class="detail-value">$${(proposal.budget || 0).toLocaleString()}</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">
                        <i class="ti ti-user"></i>
                        Contact
                    </span>
                    <span class="detail-value">${proposal.lead_name || 'N/A'}</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">
                        <i class="ti ti-calendar"></i>
                        Created
                    </span>
                    <span class="detail-value">${createdDate}</span>
                </div>
            </div>
            
            <div class="proposal-actions">
                <button class="btn btn-sm btn-primary" onclick="viewProposal(${proposal.proposal_id})">
                    <i class="ti ti-eye"></i>
                    View
                </button>
                <button class="btn btn-sm btn-outline" onclick="editProposal(${proposal.proposal_id})">
                    <i class="ti ti-edit"></i>
                    Edit
                </button>
                <button class="btn btn-sm btn-outline" onclick="deleteProposal(${proposal.proposal_id})" style="color: #EF4444; border-color: #EF4444;">
                    <i class="ti ti-trash"></i>
                </button>
            </div>
        </div>
    `;
}

// =====================================================
// PROPOSAL ACTIONS
// =====================================================
function viewProposal(proposalId) {
    window.location.href = `/project-planner/view/${proposalId}`;
}

function editProposal(proposalId) {
    showNotification('Edit functionality coming soon!', 'info');
}

async function deleteProposal(proposalId) {
    if (!confirm('Are you sure you want to delete this proposal?')) {
        return;
    }
    
    showLoading();
    
    try {
        const response = await fetch(`${API_BASE}/project-planner/proposals/${proposalId}`, {
            method: 'DELETE'
        });
        
        const result = await response.json();
        
        if (result.success) {
            showNotification('Proposal deleted successfully', 'success');
            loadProposals();
        } else {
            throw new Error(result.message || 'Failed to delete');
        }
    } catch (error) {
        console.error('Delete error:', error);
        showNotification('Failed to delete proposal', 'error');
    } finally {
        hideLoading();
    }
}

// =====================================================
// UTILITY FUNCTIONS
// =====================================================
function showLoading() {
    document.getElementById('loadingOverlay').classList.add('active');
}

function hideLoading() {
    document.getElementById('loadingOverlay').classList.remove('active');
}

function showNotification(message, type = 'info') {
    const colors = {
        success: '#10B981',
        error: '#EF4444',
        info: '#3B82F6',
        warning: '#F59E0B'
    };
    
    const icons = {
        success: 'check-circle',
        error: 'alert-circle',
        info: 'info-circle',
        warning: 'alert-triangle'
    };
    
    const notification = document.createElement('div');
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: ${colors[type]};
        color: white;
        padding: 1rem 1.5rem;
        border-radius: 12px;
        box-shadow: 0 10px 25px rgba(0, 0, 0, 0.2);
        z-index: 10000;
        animation: slideIn 0.3s ease;
        max-width: 400px;
        display: flex;
        align-items: center;
        gap: 0.75rem;
    `;
    
    notification.innerHTML = `
        <i class="ti ti-${icons[type]}" style="font-size: 1.5rem;"></i>
        <span>${message}</span>
    `;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

// =====================================================
// ANIMATIONS
// =====================================================
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(400px);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(400px);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);