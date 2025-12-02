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
    
    // Save editor content before leaving step 2
    if (currentStep === 2 && stepNumber !== 2 && quillEditor) {
        saveProposalContent();
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

// =====================================================
// SAVE PROPOSAL CONTENT
// =====================================================
async function saveProposalContent() {
    if (!currentProposalId || !quillEditor) {
        return;
    }
    
    try {
        const token = localStorage.getItem('access_token');
        if (!token) {
            return;
        }
        
        const content = quillEditor.root.innerHTML;
        
        const response = await fetch(`${API_BASE}/project-planner/proposals/${currentProposalId}/update-content`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                content: content
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            console.log('Proposal content saved');
        }
    } catch (error) {
        console.error('Error saving content:', error);
    }
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
        
        // Re-enable all form inputs
        document.querySelectorAll('#clientDetailsForm input, #clientDetailsForm select, #clientDetailsForm textarea').forEach(input => {
            input.disabled = false;
        });
    }
    
    // Reset editor
    if (quillEditor) {
        quillEditor.setContents([]);
        quillEditor.enable(true); // Re-enable editor
    }
    
    // Show step 1
    goToStep(1);
}



// Around line 150-200 in submitDiscoveryForm function
async function submitDiscoveryForm(e) {
    e.preventDefault();
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
            hideLoading();
            showNotification('Session expired. Please login again.', 'error');
            setTimeout(() => {
                window.location.href = '/auth/login';
            }, 2000);
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
        
        if (!response.ok) {
            throw new Error(result.detail || result.message || 'Failed to generate proposal');
        }
        
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
            throw new Error(result.message || 'Failed to generate proposal');
        }
    } catch (error) {
        console.error('Error generating proposal:', error);
        hideLoading();
        
        // Show error with retry option
        showRetryDialog(error.message || 'Failed to generate proposal. Please try again.');
    }
}

// Add this new function for retry functionality
function showRetryDialog(errorMessage) {
    const dialogHTML = `
        <div class="retry-dialog-overlay" id="retryDialog">
            <div class="retry-dialog">
                <div class="retry-dialog-icon">
                    <i class="ti ti-alert-circle" style="font-size: 48px; color: #EF4444;"></i>
                </div>
                <h3>Proposal Generation Failed</h3>
                <p>${errorMessage}</p>
                <div class="retry-dialog-actions">
                    <button class="btn btn-secondary" onclick="closeRetryDialog()">
                        Cancel
                    </button>
                    <button class="btn btn-primary" onclick="retryProposalGeneration()">
                        <i class="ti ti-refresh"></i>
                        Try Again
                    </button>
                </div>
            </div>
        </div>
    `;
    
    document.body.insertAdjacentHTML('beforeend', dialogHTML);
}

function closeRetryDialog() {
    const dialog = document.getElementById('retryDialog');
    if (dialog) {
        dialog.remove();
    }
}

function retryProposalGeneration() {
    closeRetryDialog();
    // Get the form and submit it again
    const form = document.getElementById('clientDetailsForm');
    if (form) {
        submitDiscoveryForm({ preventDefault: () => {}, target: form });
    }
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
        // Retry after a short delay if editor not ready
        setTimeout(() => loadGeneratedContent(proposal), 300);
        return;
    }
    
    console.log('=== LOADING GENERATED CONTENT ===');
    console.log('Raw proposal object:', proposal);

        // Check if there's edited content saved
    if (proposal.edited_content) {
        console.log('Loading previously edited content');
        quillEditor.clipboard.dangerouslyPasteHTML(proposal.edited_content);
        populateAIInsights(proposal.ai_generated_strategy || {}, proposal.competitive_differentiators || {});
        return;
    }
    
    // Parse JSON fields if they are strings
    let strategy = {};
    let differentiators = {};
    let timeline = {};
    
    try {
        strategy = typeof proposal.ai_generated_strategy === 'string' 
            ? JSON.parse(proposal.ai_generated_strategy) 
            : (proposal.ai_generated_strategy || {});
        console.log('Parsed strategy:', strategy);
        console.log('Strategy keys:', Object.keys(strategy));
    } catch (e) {
        console.error('Error parsing strategy:', e);
        strategy = {};
    }
    
    try {
        differentiators = typeof proposal.competitive_differentiators === 'string'
            ? JSON.parse(proposal.competitive_differentiators)
            : (proposal.competitive_differentiators || {});
        console.log('Parsed differentiators:', differentiators);
    } catch (e) {
        console.error('Error parsing differentiators:', e);
        differentiators = {};
    }
    
    try {
        timeline = typeof proposal.suggested_timeline === 'string'
            ? JSON.parse(proposal.suggested_timeline)
            : (proposal.suggested_timeline || {});
        console.log('Parsed timeline:', timeline);
    } catch (e) {
        console.error('Error parsing timeline:', e);
        timeline = {};
    }
    
    console.log('=== CHECKING DATA AVAILABILITY ===');
    console.log('Campaigns:', strategy.campaigns || strategy.Recommended_Campaigns);
    console.log('Tools:', strategy.automation_tools || strategy.Automation_Tools);
    console.log('Company:', proposal.company_name || proposal.Company || strategy.Company);
    
    const content = generateProposalHTML(proposal, strategy, differentiators, timeline);
    
    // Set content in editor
    quillEditor.clipboard.dangerouslyPasteHTML(content);
    
    // Populate AI Insights
    populateAIInsights(strategy, differentiators);
    
    console.log('=== CONTENT LOADED SUCCESSFULLY ===');
}


function generateProposalHTML(proposal, strategy, differentiators, timeline) {
    console.log('=== GENERATING PROPOSAL HTML ===');
    console.log('Strategy:', strategy);
    
    // Extract data - checking capitalized keys first since that's what API returns
    const campaigns = strategy.Recommended_Campaigns || strategy.campaigns || [];
    const tools = strategy.Automation_Tools || strategy.automation_tools || [];
    const diffItems = differentiators.differentiators || [];
    const phases = timeline.phases || [];
    
    console.log('Campaigns found:', campaigns.length);
    console.log('Tools found:', tools.length);
    
    // Extract company name from multiple possible sources
    const companyName = proposal.company_name || strategy.Company || 'Your Company';
    
    // Build campaigns HTML
    const campaignsHTML = campaigns.length > 0 
        ? campaigns.map(camp => {
            const type = camp.Type || camp.type || 'Campaign';
            const platform = camp.Platform || camp.platform || '';
            const platformText = Array.isArray(platform) ? platform.join(', ') : platform;
            const topics = camp.Content_Topics || camp.content_topics || [];
            const topicsText = Array.isArray(topics) ? topics.join(', ') : '';
            const budget = camp.Budget_Allocation_Percentage || '';
            
            let html = `<li><strong>${type}</strong>`;
            if (platformText) html += ` (${platformText})`;
            html += `: ${topicsText}`;
            if (budget) html += ` <em>(${budget}% of budget)</em>`;
            html += `</li>`;
            
            return html;
          }).join('')
        : '<li>AI-powered digital marketing campaigns tailored to your business needs</li>';
    
    // Build tools HTML
    const toolsHTML = tools.length > 0
        ? tools.map(tool => {
            const name = tool.Tool || tool.tool || tool.name || 'Marketing Tool';
            const purpose = tool.Purpose || tool.purpose || 'Campaign enhancement';
            const budget = tool.Budget_Allocation_Percentage || '';
            
            let html = `<li><strong>${name}:</strong> ${purpose}`;
            if (budget) html += ` <em>(${budget}% of budget)</em>`;
            html += `</li>`;
            
            return html;
          }).join('')
        : '<li>Marketing automation and analytics tools</li>';
    
    // Build differentiators HTML
    const diffHTML = diffItems.length > 0
        ? diffItems.map(diff => `
            <li>
                <strong>${diff.title}:</strong> ${diff.description}<br>
                <em>Impact: ${diff.impact}</em>
            </li>
          `).join('')
        : `<li><strong>AI-Powered Approach:</strong> Leveraging cutting-edge technology for optimal results<br><em>Impact: Increased efficiency and ROI</em></li>`;
    
    // Build timeline HTML
    const timelineHTML = phases.length > 0
        ? phases.map((phase, idx) => `
            <h3><strong>Phase ${idx + 1}: ${phase.phase || phase.name || `Phase ${idx + 1}`}</strong></h3>
            <p><strong>Duration:</strong> ${phase.duration}</p>
            <p><strong>Key Deliverables:</strong></p>
            <ul>
                ${(phase.deliverables || []).map(del => `<li>${del}</li>`).join('')}
            </ul>
          `).join('')
        : `<h3><strong>Phase 1: Planning & Setup</strong></h3><p><strong>Duration:</strong> 2-4 weeks</p><ul><li>Initial strategy development</li></ul>`;
    
    const challenges = proposal.challenges || (strategy.Challenges ? strategy.Challenges.join(', ') : 'Enhancing digital presence');
    const targetAudience = proposal.target_audience || strategy.Target_Audience || 'Target market segments';
    const budget = proposal.budget || strategy.Budget || 0;
    const businessType = proposal.business_type || strategy.Business_Type || 'organization';
    
    return `
        <h1 style="text-align: center; color: #9926F3;">Digital Marketing Proposal</h1>
        <h2 style="text-align: center; color: #1DD8FC;">for ${companyName}</h2>
        <p style="text-align: center; margin-bottom: 2rem;"><em>Prepared by PanvelIQ</em></p>
        
        <hr style="margin: 2rem 0;">
        
        <h2><strong>Executive Summary</strong></h2>
        <p>This comprehensive digital marketing proposal has been specifically designed for <strong>${companyName}</strong>, a ${businessType} looking to enhance their digital presence and drive measurable growth.</p>
        <p>Our AI-powered approach combines cutting-edge marketing technology with proven strategies to deliver exceptional results within your investment budget of <strong>₹${budget.toLocaleString()}</strong>.</p>
        
        <h2><strong>Current Challenges</strong></h2>
        <p>${challenges}</p>
        
        <h2><strong>Target Audience Analysis</strong></h2>
        <p>${targetAudience}</p>
        
        <h2><strong>Recommended Marketing Strategy</strong></h2>
        <p>Based on our AI analysis, we recommend a comprehensive marketing approach across multiple channels.</p>
        
        <h3><strong>Recommended Campaigns</strong></h3>
        <ul>
            ${campaignsHTML}
        </ul>
        
        <h3><strong>Automation Tools & Technologies</strong></h3>
        <ul>
            ${toolsHTML}
        </ul>
        
        <h2><strong>Competitive Differentiators</strong></h2>
        <p>What sets our approach apart:</p>
        <ul>
            ${diffHTML}
        </ul>
        
        <h2><strong>Project Timeline</strong></h2>
        ${timelineHTML}
        
        <hr style="margin: 2rem 0;">
        
        <h2><strong>Investment & ROI</strong></h2>
        <p><strong>Total Investment:</strong> ₹${budget.toLocaleString()}</p>
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
        { label: 'Budget', value: `₹${(proposalData.budget || 0).toLocaleString()}`, icon: 'currency-dollar' },
        { label: 'Contact', value: proposalData.full_name || 'N/A', icon: 'user' },
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

        const token = localStorage.getItem('access_token');
        const response = await fetch(`${API_BASE}/project-planner/proposals/${currentProposalId}/export/pdf`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
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
       const token = localStorage.getItem('access_token');
        const response = await fetch(`${API_BASE}/project-planner/proposals/${currentProposalId}/generate-link`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`
            }
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


// ============================================
// FIX: Replace the sendEmail() function in static/js/project-planner.js
// The issue is missing Authorization header
// ============================================


async function sendEmail() {
    const recipientEmail = document.getElementById('recipientEmail').value;
    const subject = document.getElementById('emailSubject').value;
    const message = document.getElementById('emailMessage').value;
    
    if (!recipientEmail || !subject || !message) {
        showNotification('Please fill in all fields', 'error');
        return;
    }
    
    const token = localStorage.getItem('access_token');
    if (!token) {
        showNotification('Session expired. Please login again.', 'error');
        window.location.href = '/auth/login';
        return;
    }
    
    showLoading();
    closeModal('emailModal');
    
    try {
        const response = await fetch(`${API_BASE}/project-planner/proposals/${currentProposalId}/send-email`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
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
            throw new Error(result.message || result.detail || 'Failed to send email');
        }
    } catch (error) {
        console.error('Email error:', error);
        showNotification('Failed to send email: ' + error.message, 'error');
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
        const token = localStorage.getItem('access_token');
        if (!token) {
            hideLoading();
            showNotification('Session expired. Please login again.', 'error');
            setTimeout(() => {
                window.location.href = '/auth/login';
            }, 2000);
            return;
        }
        
        const response = await fetch(`${API_BASE}/project-planner/proposals/${currentProposalId}/send-to-dashboard`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to send to dashboard');
        }
        
        const result = await response.json();
        
        if (result.success) {
            // Show success message
            showNotification('Proposal added to client dashboard!', 'success');
            
            // Update UI to show proposal was sent
            setTimeout(() => {
                hideLoading();
                showSuccessDialog();
            }, 500);
        } else {
            throw new Error(result.message || 'Failed to send to dashboard');
        }
    } catch (error) {
        console.error('Dashboard error:', error);
        hideLoading();
        showNotification(error.message || 'Failed to send to dashboard', 'error');
    }
}

// Add success dialog function
function showSuccessDialog() {
    const dialogHTML = `
        <div class="success-dialog-overlay" id="successDialog">
            <div class="success-dialog">
                <div class="success-dialog-icon">
                    <i class="ti ti-circle-check" style="font-size: 64px; color: #10B981;"></i>
                </div>
                <h3>Proposal Sent Successfully!</h3>
                <p>The proposal has been added to the client's dashboard. They will receive a notification to review it.</p>
                <div class="success-dialog-details">
                    <div class="detail-item">
                        <i class="ti ti-check"></i>
                        <span>Client notified</span>
                    </div>
                    <div class="detail-item">
                        <i class="ti ti-check"></i>
                        <span>Added to dashboard</span>
                    </div>
                    <div class="detail-item">
                        <i class="ti ti-check"></i>
                        <span>Ready for review</span>
                    </div>
                </div>
                <button class="btn btn-primary" onclick="closeSuccessDialog()">
                    Done
                </button>
            </div>
        </div>
    `;
    
    document.body.insertAdjacentHTML('beforeend', dialogHTML);
}

function closeSuccessDialog() {
    const dialog = document.getElementById('successDialog');
    if (dialog) {
        dialog.remove();
    }
    // Optionally redirect to proposals list
    setTimeout(() => {
        switchTab('proposals');
        loadProposals();
    }, 500);
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
                    <span class="detail-value">₹${(proposal.budget || 0).toLocaleString()}</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">
                        <i class="ti ti-user"></i>
                        Contact
                    </span>
                    <span class="detail-value">${proposal.client_name || 'N/A'}</span>
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
                    Delete
                </button>
            </div>
        </div>
    `;
}



// =====================================================
// PROPOSAL ACTIONS
// =====================================================
async function viewProposal(proposalId) {
    showLoading();
    
    try {
        const token = localStorage.getItem('access_token');
        if (!token) {
            window.location.href = '/auth/login';
            return;
        }
        
        // Fetch proposal details
        const response = await fetch(`${API_BASE}/project-planner/proposals/${proposalId}`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        const result = await response.json();
        
        if (result.success && result.proposal) {
            // Store proposal data
            proposalData = result.proposal;
            currentProposalId = proposalId;
            
            // Switch to create tab in view mode
            switchTab('create');
            
            // Populate form with existing data (read-only)
            populateEditForm(result.proposal);
            
            // Disable form inputs for view mode
            document.querySelectorAll('#clientDetailsForm input, #clientDetailsForm select, #clientDetailsForm textarea').forEach(input => {
                input.disabled = true;
            });
            
            // Go directly to step 2 to show content
            setTimeout(() => {
                goToStep(2);
                loadGeneratedContent(result.proposal);
                
                // Make editor read-only
                if (quillEditor) {
                    quillEditor.enable(false);
                }
                
                hideLoading();
                showNotification('Viewing proposal in read-only mode', 'info');
            }, 500);
        } else {
            throw new Error(result.message || 'Failed to load proposal');
        }
    } catch (error) {
        console.error('View error:', error);
        showNotification('Failed to load proposal details', 'error');
        hideLoading();
    }
}

async function editProposal(proposalId) {
    showLoading();
    
    try {
        const token = localStorage.getItem('access_token');
        if (!token) {
            window.location.href = '/auth/login';
            return;
        }
        
        // Fetch proposal details
        const response = await fetch(`${API_BASE}/project-planner/proposals/${proposalId}`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        const result = await response.json();
        
        if (result.success && result.proposal) {
            // Store proposal data
            proposalData = result.proposal;
            currentProposalId = proposalId;
            
            // Switch to create tab
            switchTab('create');
            
            // Populate form with existing data
            populateEditForm(result.proposal);
            
            // Go to step 2 with editor
            setTimeout(() => {
                goToStep(2);
                loadGeneratedContent(result.proposal);
                hideLoading();
            }, 500);
            
            showNotification('Proposal loaded for editing', 'success');
        } else {
            throw new Error(result.message || 'Failed to load proposal');
        }
    } catch (error) {
        console.error('Edit error:', error);
        showNotification('Failed to load proposal for editing', 'error');
        hideLoading();
    }
}

function populateEditForm(proposal) {
    // Populate form fields
    document.getElementById('leadName').value = proposal.lead_name || '';
    document.getElementById('leadEmail').value = proposal.lead_email || '';
    document.getElementById('companyName').value = proposal.company_name || '';
    document.getElementById('businessType').value = proposal.business_type || '';
    document.getElementById('budget').value = proposal.budget || '';
    document.getElementById('targetAudience').value = proposal.target_audience || '';
    document.getElementById('challenges').value = proposal.challenges || '';
    
    // Populate checkboxes for existing presence
    const existingPresence = proposal.existing_presence || {};
    Object.keys(existingPresence).forEach(key => {
        const checkbox = document.querySelector(`input[name="existing_${key}"]`);
        if (checkbox) {
            checkbox.checked = existingPresence[key];
        }
    });
}

async function deleteProposal(proposalId) {
    if (!confirm('Are you sure you want to delete this proposal?')) {
        return;
    }
    
    showLoading();
    
    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`${API_BASE}/project-planner/proposals/${proposalId}`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${token}`
            }
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