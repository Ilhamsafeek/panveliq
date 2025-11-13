/**
 * Project Planner JavaScript
 * Handles proposal creation and management
 */

// API Base URL
const API_BASE = '/api/v1';

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    loadProposals();
});

/**
 * Switch between tabs
 */
window.switchTab = function(tabName) {
    // Update tab buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');
    
    // Update tab content
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });
    document.getElementById(`tab-${tabName}`).classList.add('active');
    
    // Reload proposals if switching to proposals tab
    if (tabName === 'proposals') {
        loadProposals();
    }
}

/**
 * Show create tab
 */
function showCreateTab() {
    switchTab('create');
}

/**
 * Handle form submission
 */
async function handleSubmit(event) {
    event.preventDefault();
    
    const form = event.target;
    const formData = new FormData(form);
    
    // Get existing presence checkboxes
    const existingPresence = {};
    document.querySelectorAll('input[type="checkbox"][name^="presence_"]').forEach(checkbox => {
        if (checkbox.checked) {
            const platform = checkbox.value;
            existingPresence[platform] = true;
        }
    });
    
    // Prepare request data
    const requestData = {
        lead_name: formData.get('lead_name'),
        lead_email: formData.get('lead_email'),
        company_name: formData.get('company_name'),
        business_type: formData.get('business_type'),
        budget: parseFloat(formData.get('budget')),
        challenges: formData.get('challenges'),
        target_audience: formData.get('target_audience'),
        existing_presence: existingPresence
    };
    
    // Show loading overlay
    showLoading(true);
    
    try {
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
            body: JSON.stringify(requestData)
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.detail || 'Failed to generate proposal');
        }
        
        // Hide loading
        showLoading(false);
        
        // Show success message
        showFlashMessage('Proposal generated successfully!', 'success');
        
        // Reset form
        form.reset();
        
        // Switch to proposals tab
        switchTab('proposals');
        
        // Reload proposals
        loadProposals();
        
    } catch (error) {
        showLoading(false);
        console.error('Error generating proposal:', error);
        showFlashMessage(error.message || 'Failed to generate proposal', 'error');
    }
}

/**
 * Load all proposals
 */
async function loadProposals() {
    const container = document.getElementById('proposalsContainer');
    
    // Show loading state
    container.innerHTML = `
        <div style="text-align: center; padding: 3rem;">
            <div class="spinner" style="margin: 0 auto 1rem;"></div>
            <p style="color: var(--color-gray-600);">Loading proposals...</p>
        </div>
    `;
    
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
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.detail || 'Failed to load proposals');
        }
        
        // Display proposals
        if (data.proposals && data.proposals.length > 0) {
            displayProposals(data.proposals);
        } else {
            displayEmptyState();
        }
        
    } catch (error) {
        console.error('Error loading proposals:', error);
        container.innerHTML = `
            <div class="empty-state">
                <i class="ti ti-alert-circle"></i>
                <h3>Error Loading Proposals</h3>
                <p>${error.message}</p>
                <button class="btn btn-primary" onclick="loadProposals()">
                    <i class="ti ti-refresh"></i>
                    Retry
                </button>
            </div>
        `;
    }
}

/**
 * Display proposals in grid
 */
function displayProposals(proposals) {
    const container = document.getElementById('proposalsContainer');
    
    const proposalsHTML = proposals.map(proposal => `
        <div class="proposal-card">
            <div class="proposal-header">
                <div class="proposal-client">
                    <h3>${escapeHtml(proposal.company_name || 'N/A')}</h3>
                    <p>${escapeHtml(proposal.client_name || 'N/A')} • ${escapeHtml(proposal.client_email || 'N/A')}</p>
                </div>
                <span class="status-badge status-${proposal.status}">${proposal.status}</span>
            </div>
            
            <div class="proposal-details">
                <div class="detail-item">
                    <span class="detail-label">
                        <i class="ti ti-category"></i>
                        Business Type
                    </span>
                    <span class="detail-value">${escapeHtml(proposal.business_type || 'N/A')}</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">
                        <i class="ti ti-cash"></i>
                        Budget
                    </span>
                    <span class="detail-value">$${formatNumber(proposal.budget)}</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">
                        <i class="ti ti-calendar"></i>
                        Created
                    </span>
                    <span class="detail-value">${formatDate(proposal.created_at)}</span>
                </div>
            </div>
            
            <div class="proposal-actions">
                <button class="btn btn-sm btn-view" onclick="viewProposal(${proposal.proposal_id})">
                    <i class="ti ti-eye"></i>
                    View
                </button>
                <button class="btn btn-sm btn-edit" onclick="editProposal(${proposal.proposal_id})">
                    <i class="ti ti-edit"></i>
                    Edit
                </button>
                ${proposal.status === 'draft' ? `
                <button class="btn btn-sm btn-primary" onclick="sendProposal(${proposal.proposal_id})" title="Send to client">
                    <i class="ti ti-send"></i>
                </button>
                <button class="btn btn-sm" style="background: var(--secondary-cyan); color: white;" onclick="generateShareLink(${proposal.proposal_id})" title="Generate shareable link">
                    <i class="ti ti-link"></i>
                </button>
                <button class="btn btn-sm btn-primary" onclick="downloadProposal(${proposal.proposal_id})" title="Download PDF">
                    <i class="ti ti-download"></i>
                </button>
                ` : `
                <button class="btn btn-sm btn-primary" onclick="downloadProposal(${proposal.proposal_id})">
                    <i class="ti ti-download"></i>
                    PDF
                </button>
                <button class="btn btn-sm" style="background: var(--secondary-cyan); color: white;" onclick="generateShareLink(${proposal.proposal_id})">
                    <i class="ti ti-link"></i>
                    Link
                </button>
                `}
                <button class="btn btn-sm btn-delete" onclick="deleteProposal(${proposal.proposal_id})" title="Delete">
                    <i class="ti ti-trash"></i>
                </button>
            </div>
        </div>
    `).join('');
    
    container.innerHTML = `<div class="proposals-grid">${proposalsHTML}</div>`;
}

/**
 * Display empty state
 */
function displayEmptyState() {
    const container = document.getElementById('proposalsContainer');
    container.innerHTML = `
        <div class="empty-state">
            <i class="ti ti-file-off"></i>
            <h3>No Proposals Yet</h3>
            <p>Create your first AI-powered proposal to get started</p>
            <button class="btn btn-primary" onclick="showCreateTab()">
                <i class="ti ti-plus"></i>
                Create New Proposal
            </button>
        </div>
    `;
}

/**
 * View proposal details
 */
async function viewProposal(proposalId) {
    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`${API_BASE}/project-planner/proposals/${proposalId}`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.detail || 'Failed to load proposal');
        }
        
        // Display proposal in modal or new page
        displayProposalModal(data);
        
    } catch (error) {
        console.error('Error viewing proposal:', error);
        showFlashMessage(error.message || 'Failed to load proposal', 'error');
    }
}

/**
 * Display proposal in modal
 */
function displayProposalModal(proposal) {
    // Create modal overlay
    const modal = document.createElement('div');
    modal.className = 'loading-overlay active';
    modal.style.overflowY = 'auto';
    
    const aiStrategy = proposal.ai_generated_strategy || {};
    const differentiators = proposal.competitive_differentiators || {};
    const timeline = proposal.suggested_timeline || {};
    
    modal.innerHTML = `
        <div class="loading-content" style="max-width: 800px; max-height: 90vh; overflow-y: auto; text-align: left;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem;">
                <h2 style="font-size: 24px; font-weight: 700;">${escapeHtml(proposal.company_name)}</h2>
                <button onclick="closeModal()" style="background: none; border: none; font-size: 24px; cursor: pointer; color: var(--color-gray-600);">
                    <i class="ti ti-x"></i>
                </button>
            </div>
            
            <div style="margin-bottom: 1.5rem;">
                <h3 style="font-size: 18px; font-weight: 700; margin-bottom: 0.5rem; color: var(--primary-purple);">Client Information</h3>
                <p><strong>Name:</strong> ${escapeHtml(proposal.client_name)}</p>
                <p><strong>Email:</strong> ${escapeHtml(proposal.client_email)}</p>
                <p><strong>Business Type:</strong> ${escapeHtml(proposal.business_type)}</p>
                <p><strong>Budget:</strong> $${formatNumber(proposal.budget)}</p>
            </div>
            
            <div style="margin-bottom: 1.5rem;">
                <h3 style="font-size: 18px; font-weight: 700; margin-bottom: 0.5rem; color: var(--primary-purple);">Challenges</h3>
                <p style="white-space: pre-wrap;">${escapeHtml(proposal.challenges)}</p>
            </div>
            
            <div style="margin-bottom: 1.5rem;">
                <h3 style="font-size: 18px; font-weight: 700; margin-bottom: 0.5rem; color: var(--primary-purple);">Target Audience</h3>
                <p style="white-space: pre-wrap;">${escapeHtml(proposal.target_audience)}</p>
            </div>
            
            ${aiStrategy.campaigns ? `
            <div style="margin-bottom: 1.5rem;">
                <h3 style="font-size: 18px; font-weight: 700; margin-bottom: 0.5rem; color: var(--primary-purple);">Recommended Campaigns</h3>
                <ul style="list-style: none; padding: 0;">
                    ${aiStrategy.campaigns.map(campaign => `
                        <li style="padding: 0.5rem 0; border-bottom: 1px solid var(--color-gray-200);">
                            <strong>${escapeHtml(campaign.name || campaign.type || 'Campaign')}</strong>
                            ${campaign.description ? `<br><span style="color: var(--color-gray-600); font-size: 14px;">${escapeHtml(campaign.description)}</span>` : ''}
                        </li>
                    `).join('')}
                </ul>
            </div>
            ` : ''}
            
            ${differentiators.differentiators ? `
            <div style="margin-bottom: 1.5rem;">
                <h3 style="font-size: 18px; font-weight: 700; margin-bottom: 0.5rem; color: var(--primary-purple);">Competitive Differentiators</h3>
                <ul style="list-style: none; padding: 0;">
                    ${differentiators.differentiators.map(diff => `
                        <li style="padding: 0.5rem 0; border-bottom: 1px solid var(--color-gray-200);">
                            <strong>${escapeHtml(diff.title)}</strong>
                            ${diff.description ? `<br><span style="color: var(--color-gray-600); font-size: 14px;">${escapeHtml(diff.description)}</span>` : ''}
                        </li>
                    `).join('')}
                </ul>
            </div>
            ` : ''}
            
            <div style="display: flex; gap: 1rem; margin-top: 2rem;">
                <button class="btn btn-primary" onclick="downloadProposal(${proposal.proposal_id})">
                    <i class="ti ti-download"></i>
                    Download PDF
                </button>
                <button class="btn btn-outline" onclick="closeModal()">Close</button>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    window.currentModal = modal;
}

/**
 * Close modal
 */
window.closeModal = function() {
    if (window.currentModal) {
        window.currentModal.remove();
        window.currentModal = null;
    }
}

/**
 * Show edit modal
 */
function showEditModal(proposal) {
    const modal = document.createElement('div');
    modal.className = 'loading-overlay active';
    modal.style.overflowY = 'auto';
    
    const aiStrategy = proposal.ai_generated_strategy || {};
    const differentiators = proposal.competitive_differentiators || {};
    const timeline = proposal.suggested_timeline || {};
    
    modal.innerHTML = `
        <div class="loading-content" style="max-width: 900px; max-height: 90vh; overflow-y: auto; text-align: left;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; border-bottom: 2px solid var(--primary-purple); padding-bottom: 1rem;">
                <h2 style="font-size: 24px; font-weight: 700; color: var(--primary-purple);">
                    <i class="ti ti-edit"></i> Edit Proposal
                </h2>
                <button onclick="closeModal()" style="background: none; border: none; font-size: 24px; cursor: pointer; color: var(--color-gray-600);">
                    <i class="ti ti-x"></i>
                </button>
            </div>
            
            <form id="editProposalForm" onsubmit="submitEditProposal(event, ${proposal.proposal_id})">
                <!-- Basic Information -->
                <div style="margin-bottom: 1.5rem;">
                    <h3 style="font-size: 18px; font-weight: 700; margin-bottom: 1rem; color: var(--color-gray-900); display: flex; align-items: center; gap: 0.5rem;">
                        <i class="ti ti-info-circle" style="color: var(--primary-purple);"></i>
                        Basic Information
                    </h3>
                    <div style="display: grid; gap: 1rem;">
                        <div>
                            <label style="display: block; font-weight: 600; margin-bottom: 0.5rem;">Company Name</label>
                            <input type="text" name="company_name" value="${escapeHtml(proposal.company_name || '')}" 
                                   style="width: 100%; padding: 0.75rem; border: 1px solid var(--color-gray-300); border-radius: 8px;">
                        </div>
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
                            <div>
                                <label style="display: block; font-weight: 600; margin-bottom: 0.5rem;">Business Type</label>
                                <input type="text" name="business_type" value="${escapeHtml(proposal.business_type || '')}" 
                                       style="width: 100%; padding: 0.75rem; border: 1px solid var(--color-gray-300); border-radius: 8px;">
                            </div>
                            <div>
                                <label style="display: block; font-weight: 600; margin-bottom: 0.5rem;">Budget</label>
                                <input type="number" name="budget" value="${proposal.budget || 0}" 
                                       style="width: 100%; padding: 0.75rem; border: 1px solid var(--color-gray-300); border-radius: 8px;">
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Challenges -->
                <div style="margin-bottom: 1.5rem;">
                    <label style="display: block; font-weight: 600; margin-bottom: 0.5rem;">
                        <i class="ti ti-alert-triangle" style="color: var(--primary-purple);"></i> Challenges
                    </label>
                    <textarea name="challenges" rows="3" style="width: 100%; padding: 0.75rem; border: 1px solid var(--color-gray-300); border-radius: 8px; font-family: inherit;">${escapeHtml(proposal.challenges || '')}</textarea>
                </div>
                
                <!-- Target Audience -->
                <div style="margin-bottom: 1.5rem;">
                    <label style="display: block; font-weight: 600; margin-bottom: 0.5rem;">
                        <i class="ti ti-users" style="color: var(--primary-purple);"></i> Target Audience
                    </label>
                    <textarea name="target_audience" rows="3" style="width: 100%; padding: 0.75rem; border: 1px solid var(--color-gray-300); border-radius: 8px; font-family: inherit;">${escapeHtml(proposal.target_audience || '')}</textarea>
                </div>
                
                <!-- AI Strategy Notes -->
                <div style="margin-bottom: 1.5rem;">
                    <label style="display: block; font-weight: 600; margin-bottom: 0.5rem;">
                        <i class="ti ti-bulb" style="color: var(--primary-purple);"></i> Custom Strategy Notes
                    </label>
                    <textarea name="custom_notes" rows="4" placeholder="Add any custom notes or modifications to the AI-generated strategy..." 
                              style="width: 100%; padding: 0.75rem; border: 1px solid var(--color-gray-300); border-radius: 8px; font-family: inherit;">${escapeHtml(proposal.custom_notes || '')}</textarea>
                    <p style="font-size: 12px; color: var(--color-gray-600); margin-top: 0.5rem;">
                        <i class="ti ti-info-circle"></i> These notes will be included in the final proposal document
                    </p>
                </div>
                
                <!-- Tone Selection -->
                <div style="margin-bottom: 2rem;">
                    <label style="display: block; font-weight: 600; margin-bottom: 0.5rem;">
                        <i class="ti ti-mood-smile" style="color: var(--primary-purple);"></i> Proposal Tone
                    </label>
                    <select name="tone" style="width: 100%; padding: 0.75rem; border: 1px solid var(--color-gray-300); border-radius: 8px;">
                        <option value="professional">Professional & Formal</option>
                        <option value="friendly">Friendly & Approachable</option>
                        <option value="innovative">Innovative & Tech-Forward</option>
                        <option value="concise">Concise & Direct</option>
                    </select>
                </div>
                
                <div style="display: flex; gap: 1rem; justify-content: flex-end; padding-top: 1rem; border-top: 1px solid var(--color-gray-200);">
                    <button type="button" class="btn btn-outline" onclick="closeModal()">Cancel</button>
                    <button type="submit" class="btn btn-primary">
                        <i class="ti ti-device-floppy"></i> Save Changes
                    </button>
                </div>
            </form>
        </div>
    `;
    
    document.body.appendChild(modal);
    window.currentModal = modal;
}

/**
 * Submit edit proposal
 */
window.submitEditProposal = async function(event, proposalId) {
    event.preventDefault();
    
    const form = event.target;
    const formData = new FormData(form);
    
    const editData = {
        company_name: formData.get('company_name'),
        business_type: formData.get('business_type'),
        budget: parseFloat(formData.get('budget')),
        challenges: formData.get('challenges'),
        target_audience: formData.get('target_audience'),
        custom_notes: formData.get('custom_notes'),
        tone: formData.get('tone')
    };
    
    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`${API_BASE}/project-planner/proposals/${proposalId}/edit`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify(editData)
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.detail || 'Failed to update proposal');
        }
        
        showFlashMessage('Proposal updated successfully!', 'success');
        closeModal();
        loadProposals();
        
    } catch (error) {
        console.error('Error updating proposal:', error);
        showFlashMessage(error.message || 'Failed to update proposal', 'error');
    }
}

/**
 * Send proposal to client
 */
window.sendProposal = async function(proposalId) {
    const modal = document.createElement('div');
    modal.className = 'loading-overlay active';
    
    modal.innerHTML = `
        <div class="loading-content" style="max-width: 500px; text-align: left;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem;">
                <h2 style="font-size: 20px; font-weight: 700;">
                    <i class="ti ti-send"></i> Send Proposal
                </h2>
                <button onclick="closeModal()" style="background: none; border: none; font-size: 24px; cursor: pointer; color: var(--color-gray-600);">
                    <i class="ti ti-x"></i>
                </button>
            </div>
            
            <form id="sendProposalForm" onsubmit="submitSendProposal(event, ${proposalId})">
                <div style="margin-bottom: 1.5rem;">
                    <label style="display: block; font-weight: 600; margin-bottom: 0.5rem;">Send Option</label>
                    <div style="display: flex; flex-direction: column; gap: 0.75rem;">
                        <label style="display: flex; align-items: center; gap: 0.5rem; padding: 1rem; border: 2px solid var(--color-gray-200); border-radius: 8px; cursor: pointer;" onclick="toggleSchedule(false)">
                            <input type="radio" name="send_option" value="instant" checked style="width: 18px; height: 18px;">
                            <div>
                                <strong>Send Immediately</strong>
                                <p style="font-size: 13px; color: var(--color-gray-600); margin: 0;">Proposal will be sent right away</p>
                            </div>
                        </label>
                        <label style="display: flex; align-items: center; gap: 0.5rem; padding: 1rem; border: 2px solid var(--color-gray-200); border-radius: 8px; cursor: pointer;" onclick="toggleSchedule(true)">
                            <input type="radio" name="send_option" value="schedule" style="width: 18px; height: 18px;">
                            <div>
                                <strong>Schedule for Later</strong>
                                <p style="font-size: 13px; color: var(--color-gray-600); margin: 0;">Choose a specific date and time</p>
                            </div>
                        </label>
                    </div>
                </div>
                
                <div id="scheduleSection" style="display: none; margin-bottom: 1.5rem;">
                    <label style="display: block; font-weight: 600; margin-bottom: 0.5rem;">Schedule Date & Time</label>
                    <input type="datetime-local" name="scheduled_time" 
                           style="width: 100%; padding: 0.75rem; border: 1px solid var(--color-gray-300); border-radius: 8px;">
                </div>
                
                <div style="margin-bottom: 1.5rem;">
                    <label style="display: block; font-weight: 600; margin-bottom: 0.5rem;">Custom Message (Optional)</label>
                    <textarea name="custom_message" rows="3" placeholder="Add a personal message to accompany the proposal..." 
                              style="width: 100%; padding: 0.75rem; border: 1px solid var(--color-gray-300); border-radius: 8px; font-family: inherit;"></textarea>
                </div>
                
                <div style="display: flex; gap: 1rem; justify-content: flex-end;">
                    <button type="button" class="btn btn-outline" onclick="closeModal()">Cancel</button>
                    <button type="submit" class="btn btn-primary">
                        <i class="ti ti-send"></i> Send Proposal
                    </button>
                </div>
            </form>
        </div>
    `;
    
    document.body.appendChild(modal);
    window.currentModal = modal;
}

/**
 * Toggle schedule section
 */
window.toggleSchedule = function(show) {
    const scheduleSection = document.getElementById('scheduleSection');
    if (scheduleSection) {
        scheduleSection.style.display = show ? 'block' : 'none';
    }
}

/**
 * Submit send proposal
 */
window.submitSendProposal = async function(event, proposalId) {
    event.preventDefault();
    
    const form = event.target;
    const formData = new FormData(form);
    const sendOption = formData.get('send_option');
    
    const sendData = {
        send_immediately: sendOption === 'instant',
        scheduled_time: sendOption === 'schedule' ? formData.get('scheduled_time') : null,
        custom_message: formData.get('custom_message')
    };
    
    try {
        const token = localStorage.getItem('access_token');
        
        // First, get proposal details for email
        const proposalResponse = await fetch(`${API_BASE}/project-planner/proposals/${proposalId}`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        const proposalData = await proposalResponse.json();
        
        sendData.lead_email = proposalData.client_email;
        sendData.lead_name = proposalData.client_name;
        
        const response = await fetch(`${API_BASE}/project-planner/proposals/${proposalId}/send`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify(sendData)
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.detail || 'Failed to send proposal');
        }
        
        showFlashMessage(data.message || 'Proposal sent successfully!', 'success');
        closeModal();
        loadProposals();
        
    } catch (error) {
        console.error('Error sending proposal:', error);
        showFlashMessage(error.message || 'Failed to send proposal', 'error');
    }
}

/**
 * Generate shareable link
 */
window.generateShareLink = async function(proposalId) {
    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`${API_BASE}/project-planner/proposals/${proposalId}/generate-link`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.detail || 'Failed to generate link');
        }
        
        // Show link modal
        showShareLinkModal(data.share_link, data.expires_in);
        
    } catch (error) {
        console.error('Error generating link:', error);
        showFlashMessage(error.message || 'Failed to generate link', 'error');
    }
}

/**
 * Show share link modal
 */
function showShareLinkModal(shareLink, expiresIn) {
    const modal = document.createElement('div');
    modal.className = 'loading-overlay active';
    
    modal.innerHTML = `
        <div class="loading-content" style="max-width: 600px; text-align: left;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem;">
                <h2 style="font-size: 20px; font-weight: 700;">
                    <i class="ti ti-link"></i> Shareable Link Generated
                </h2>
                <button onclick="closeModal()" style="background: none; border: none; font-size: 24px; cursor: pointer; color: var(--color-gray-600);">
                    <i class="ti ti-x"></i>
                </button>
            </div>
            
            <div style="background: var(--color-gray-50); padding: 1rem; border-radius: 8px; margin-bottom: 1rem;">
                <p style="font-size: 14px; color: var(--color-gray-700; margin-bottom: 0.5rem;">
                    <i class="ti ti-info-circle"></i> Share this link with your client. It will expire in ${expiresIn}.
                </p>
            </div>
            
            <div style="display: flex; gap: 0.5rem; margin-bottom: 1.5rem;">
                <input type="text" value="${shareLink}" readonly id="shareLinkInput"
                       style="flex: 1; padding: 0.875rem; border: 2px solid var(--primary-purple); border-radius: 8px; font-family: monospace; font-size: 13px;">
                <button onclick="copyShareLink()" class="btn btn-primary" style="padding: 0.875rem 1.5rem;">
                    <i class="ti ti-copy"></i> Copy
                </button>
            </div>
            
            <div style="display: flex; gap: 1rem; justify-content: flex-end;">
                <button class="btn btn-outline" onclick="closeModal()">Close</button>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    window.currentModal = modal;
}

/**
 * Copy share link to clipboard
 */
window.copyShareLink = function() {
    const input = document.getElementById('shareLinkInput');
    input.select();
    document.execCommand('copy');
    showFlashMessage('Link copied to clipboard!', 'success');
}

/**
 * Edit proposal
 */
window.editProposal = async function(proposalId) {
    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`${API_BASE}/project-planner/proposals/${proposalId}`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.detail || 'Failed to load proposal');
        }
        
        // Show edit modal
        showEditModal(data);
        
    } catch (error) {
        console.error('Error loading proposal for edit:', error);
        showFlashMessage(error.message || 'Failed to load proposal', 'error');
    }
}

/**
 * Download proposal as PDF
 */
async function downloadProposal(proposalId) {
    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`${API_BASE}/project-planner/proposals/${proposalId}/pdf`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (!response.ok) {
            throw new Error('Failed to download proposal');
        }
        
        // Get filename from header or use default
        const contentDisposition = response.headers.get('Content-Disposition');
        let filename = 'proposal.pdf';
        if (contentDisposition) {
            const filenameMatch = contentDisposition.match(/filename="?(.+)"?/);
            if (filenameMatch) {
                filename = filenameMatch[1];
            }
        }
        
        // Download file
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        a.remove();
        
        showFlashMessage('Proposal downloaded successfully!', 'success');
        
    } catch (error) {
        console.error('Error downloading proposal:', error);
        showFlashMessage(error.message || 'Failed to download proposal', 'error');
    }
}

/**
 * Delete proposal
 */
async function deleteProposal(proposalId) {
    if (!confirm('Are you sure you want to delete this proposal? This action cannot be undone.')) {
        return;
    }
    
    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`${API_BASE}/project-planner/proposals/${proposalId}`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.detail || 'Failed to delete proposal');
        }
        
        showFlashMessage('Proposal deleted successfully!', 'success');
        loadProposals();
        
    } catch (error) {
        console.error('Error deleting proposal:', error);
        showFlashMessage(error.message || 'Failed to delete proposal', 'error');
    }
}

/**
 * Show/hide loading overlay
 */
function showLoading(show) {
    const overlay = document.getElementById('loadingOverlay');
    if (show) {
        overlay.classList.add('active');
    } else {
        overlay.classList.remove('active');
    }
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Format number with commas
 */
function formatNumber(number) {
    if (!number) return '0';
    return parseFloat(number).toLocaleString('en-US', { 
        minimumFractionDigits: 0,
        maximumFractionDigits: 2 
    });
}

/**
 * Format date
 */
function formatDate(dateString) {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', { 
        year: 'numeric', 
        month: 'short', 
        day: 'numeric' 
    });
}