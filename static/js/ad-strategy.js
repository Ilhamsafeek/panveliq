/**
 * Ad Strategy & Suggestion Engine - Frontend JavaScript (FIXED)
 * File: static/js/ad-strategy.js
 * 
 * FIXES:
 * - Real modals instead of alerts
 * - Proper JSON parsing and display
 * - No dummy data
 */

const API_BASE = `/api/v1/ad-strategy`;
let selectedPlatform = '';
let selectedContentType = '';
let generatedContent = null;
let currentClientId = null;
let selectedAdCopy = null;

// =====================================================
// INITIALIZATION
// =====================================================

document.addEventListener('DOMContentLoaded', function() {
    loadClients();
    loadDashboard();
});

// =====================================================
// UTILITY FUNCTIONS
// =====================================================

function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 1rem 1.5rem;
        background: ${type === 'error' ? '#ef4444' : type === 'success' ? '#10b981' : '#3b82f6'};
        color: white;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        z-index: 10000;
        animation: slideIn 0.3s ease-out;
    `;
    notification.textContent = message;
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease-out';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

// =====================================================
// TAB SWITCHING
// =====================================================

function switchTab(tabName) {
    document.querySelectorAll('.tab').forEach(tab => tab.classList.remove('active'));
    event.target.closest('.tab').classList.add('active');
    
    document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
    document.getElementById(`${tabName}-tab`).classList.add('active');
    
    if (tabName === 'campaigns') {
        loadCampaigns();
    } else if (tabName === 'audience') {
        loadAudienceSegments();
    }
}

// =====================================================
// LOAD CLIENTS
// =====================================================

const token = localStorage.getItem('access_token');

async function loadClients() {
    try {
        const response = await fetch('/api/v1/clients/list', {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (!response.ok) throw new Error('Failed to fetch clients');
        
        const data = await response.json();
        
        const selectors = ['filterClientCampaign', 'filterClientAudience'];
        selectors.forEach(id => {
            const select = document.getElementById(id);
            if (select) {
                select.innerHTML = '<option value="">All Clients</option>';
                if (data.clients && data.clients.length > 0) {
                    data.clients.forEach(client => {
                        select.innerHTML += `<option value="${client.user_id}">${client.full_name}</option>`;
                    });
                }
            }
        });
        
        if (data.clients && data.clients.length === 1) {
            currentClientId = data.clients[0].user_id;
        }
        
    } catch (error) {
        console.error('Error loading clients:', error);
        showNotification('Failed to load clients', 'error');
    }
}

// =====================================================
// DASHBOARD
// =====================================================

async function loadDashboard() {
    const clientId = currentClientId || (await getFirstClientId());
    if (!clientId) {
        showEmptyDashboard();
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/dashboard/${clientId}`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (!response.ok) throw new Error('Failed to load dashboard');
        
        const data = await response.json();
        
        displayDashboardStats(data.campaign_stats);
        displayPlatformPerformance(data.platform_performance);
        displayRecentCampaigns(data.recent_campaigns);
        
    } catch (error) {
        console.error('Error loading dashboard:', error);
        showNotification('Failed to load dashboard data', 'error');
    }
}

async function getFirstClientId() {
    try {
        const response = await fetch('/api/v1/clients/list', {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        const data = await response.json();
        return data.clients && data.clients.length > 0 ? data.clients[0].user_id : null;
    } catch {
        return null;
    }
}

function displayDashboardStats(stats) {
    const container = document.getElementById('dashboardStats');
    if (!stats) {
        container.innerHTML = '<div class="empty-state"><p>No campaign data available</p></div>';
        return;
    }
    
    container.innerHTML = `
        <div class="stat-card">
            <div class="stat-icon"><i class="ti ti-badge-ad"></i></div>
            <div class="stat-value">${stats.total_campaigns || 0}</div>
            <div class="stat-label">Total Campaigns</div>
        </div>
        <div class="stat-card">
            <div class="stat-icon"><i class="ti ti-bolt"></i></div>
            <div class="stat-value">${stats.active_campaigns || 0}</div>
            <div class="stat-label">Active Campaigns</div>
        </div>
        <div class="stat-card">
            <div class="stat-icon"><i class="ti ti-player-pause"></i></div>
            <div class="stat-value">${stats.paused_campaigns || 0}</div>
            <div class="stat-label">Paused</div>
        </div>
        <div class="stat-card">
            <div class="stat-icon"><i class="ti ti-currency-dollar"></i></div>
            <div class="stat-value">₹${Number(stats.total_budget || 0).toLocaleString()}</div>
            <div class="stat-label">Total Budget</div>
        </div>
    `;
}

function displayPlatformPerformance(platforms) {
    const container = document.getElementById('platformPerformance');
    
    if (!platforms || platforms.length === 0) {
        container.innerHTML = '<div class="empty-state"><i class="ti ti-chart-bar"></i><p>No performance data yet</p></div>';
        return;
    }
    
    container.innerHTML = platforms.map(platform => `
        <div class="campaign-card">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
                <h3 style="margin: 0; text-transform: capitalize;">${platform.platform}</h3>
                <span class="platform-badge">${platform.campaigns} Campaigns</span>
            </div>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 1rem;">
                <div>
                    <div style="font-size: 0.875rem; color: #64748b;">Impressions</div>
                    <div style="font-size: 1.25rem; font-weight: 600;">${Number(platform.impressions || 0).toLocaleString()}</div>
                </div>
                <div>
                    <div style="font-size: 0.875rem; color: #64748b;">Clicks</div>
                    <div style="font-size: 1.25rem; font-weight: 600;">${Number(platform.clicks || 0).toLocaleString()}</div>
                </div>
                <div>
                    <div style="font-size: 0.875rem; color: #64748b;">Spend</div>
                    <div style="font-size: 1.25rem; font-weight: 600;">₹${Number(platform.spend || 0).toLocaleString()}</div>
                </div>
                <div>
                    <div style="font-size: 0.875rem; color: #64748b;">Conversions</div>
                    <div style="font-size: 1.25rem; font-weight: 600;">${platform.conversions || 0}</div>
                </div>
            </div>
        </div>
    `).join('');
}

function displayRecentCampaigns(campaigns) {
    const container = document.getElementById('recentCampaigns');
    
    if (!campaigns || campaigns.length === 0) {
        container.innerHTML = '<div class="empty-state"><i class="ti ti-badge-ad"></i><p>No campaigns yet</p></div>';
        return;
    }
    
    container.innerHTML = campaigns.map(campaign => `
        <div class="campaign-card" onclick="viewCampaign(${campaign.campaign_id})">
            <div class="campaign-header">
                <div>
                    <div class="campaign-title">${campaign.campaign_name}</div>
                    <div class="campaign-meta">
                        <span><i class="ti ti-calendar"></i> ${new Date(campaign.created_at).toLocaleDateString()}</span>
                        <span><i class="ti ti-user"></i> ${campaign.creator_name}</span>
                    </div>
                </div>
                <div style="display: flex; gap: 0.5rem; align-items: start;">
                    <span class="status-badge ${campaign.status}">${campaign.status}</span>
                    <span class="platform-badge">${campaign.platform}</span>
                </div>
            </div>
            <div style="font-size: 0.875rem; color: #64748b;">
                Budget: ₹${Number(campaign.budget).toLocaleString()}
            </div>
        </div>
    `).join('');
}

function showEmptyDashboard() {
    document.getElementById('dashboardStats').innerHTML = '<div class="empty-state"><i class="ti ti-chart-bar"></i><p>No data available. Create your first campaign to get started.</p></div>';
}

// =====================================================
// CAMPAIGNS
// =====================================================

async function loadCampaigns() {
    const clientId = document.getElementById('filterClientCampaign').value;
    const platform = document.getElementById('filterPlatformCampaign').value;
    
    const container = document.getElementById('campaignsList');
    container.innerHTML = '<div style="text-align: center; padding: 2rem;"><div class="loading-spinner"></div><p>Loading campaigns...</p></div>';
    
    try {
        let url = `${API_BASE}/campaigns/list/${clientId || (await getFirstClientId())}`;
        if (platform) url += `?platform=${platform}`;
        
        const response = await fetch(url, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (!response.ok) throw new Error('Failed to load campaigns');
        
        const data = await response.json();
        
        if (!data.campaigns || data.campaigns.length === 0) {
            container.innerHTML = '<div class="empty-state"><i class="ti ti-badge-ad"></i><h3>No campaigns yet</h3><p>Create your first ad campaign to get started</p></div>';
            return;
        }
        
        container.innerHTML = data.campaigns.map(campaign => `
            <div class="campaign-card">
                <div class="campaign-header">
                    <div>
                        <div class="campaign-title">${campaign.campaign_name}</div>
                        <div class="campaign-meta">
                            <span><i class="ti ti-target"></i> ${campaign.objective}</span>
                            <span><i class="ti ti-calendar"></i> ${new Date(campaign.start_date).toLocaleDateString()}</span>
                            <span><i class="ti ti-user"></i> ${campaign.creator_name}</span>
                        </div>
                    </div>
                    <div style="display: flex; gap: 0.5rem; align-items: start; flex-direction: column;">
                        <span class="status-badge ${campaign.status}">${campaign.status}</span>
                        <span class="platform-badge">${campaign.platform}</span>
                    </div>
                </div>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 1rem; margin-top: 1rem;">
                    <div>
                        <div style="font-size: 0.875rem; color: #64748b;">Budget</div>
                        <div style="font-size: 1.1rem; font-weight: 600;">₹${Number(campaign.budget).toLocaleString()}</div>
                    </div>
                    <div>
                        <div style="font-size: 0.875rem; color: #64748b;">Total Ads</div>
                        <div style="font-size: 1.1rem; font-weight: 600;">${campaign.total_ads || 0}</div>
                    </div>
                    <div>
                        <div style="font-size: 0.875rem; color: #64748b;">Bidding</div>
                        <div style="font-size: 0.875rem; font-weight: 500;">${campaign.bidding_strategy || 'Auto'}</div>
                    </div>
                </div>
                <div style="display: flex; gap: 0.75rem; margin-top: 1rem; padding-top: 1rem; border-top: 1px solid #e2e8f0;">
                    <button class="btn btn-secondary" onclick="viewCampaign(${campaign.campaign_id})">
                        <i class="ti ti-eye"></i> View Details
                    </button>
                    ${campaign.status === 'draft' ? `
                        <button class="btn btn-primary" onclick="publishCampaign(${campaign.campaign_id})">
                            <i class="ti ti-send"></i> Publish
                        </button>
                    ` : ''}
                </div>
            </div>
        `).join('');
        
    } catch (error) {
        console.error('Error loading campaigns:', error);
        container.innerHTML = '<div class="empty-state"><i class="ti ti-alert-circle"></i><p>Failed to load campaigns</p></div>';
        showNotification('Failed to load campaigns', 'error');
    }
}

function openCreateCampaignModal() {
    // Load clients into modal dropdown
    loadClientsForModal('campaignClient');
    
    // Set default start date to today
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('campaignStartDate').value = today;
    
    // Show modal
    document.getElementById('campaignModal').style.display = 'flex';
}

function closeCampaignModal() {
    document.getElementById('campaignModal').style.display = 'none';
    document.getElementById('campaignForm').reset();
}

async function submitCampaign() {
    const btn = document.getElementById('submitCampaignBtn');
    btn.disabled = true;
    btn.innerHTML = '<i class="ti ti-loader"></i> Creating...';
    
    try {
        const formData = {
            client_id: parseInt(document.getElementById('campaignClient').value),
            campaign_name: document.getElementById('campaignName').value,
            platform: document.getElementById('campaignPlatform').value,
            objective: document.getElementById('campaignObjective').value,
            budget: parseFloat(document.getElementById('campaignBudget').value),
            start_date: document.getElementById('campaignStartDate').value,
            end_date: document.getElementById('campaignEndDate').value || null,
            bidding_strategy: document.getElementById('campaignBidding').value || null,
            target_audience: {},
            placement_settings: {},
            ab_test_config: document.getElementById('enableABTest').checked ? {} : null
        };
        
        const response = await fetch(`${API_BASE}/campaigns/create`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify(formData)
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to create campaign');
        }
        
        const data = await response.json();
        showNotification('Campaign created successfully!', 'success');
        closeCampaignModal();
        loadCampaigns();
        
    } catch (error) {
        console.error('Error creating campaign:', error);
        showNotification(error.message, 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="ti ti-check"></i> Create Campaign';
    }
}

async function publishCampaign(campaignId) {
    if (!confirm('Publish this campaign to the ad platform?')) return;
    
    try {
        const response = await fetch(`${API_BASE}/campaigns/${campaignId}/publish`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to publish campaign');
        }
        
        const data = await response.json();
        showNotification(data.message, 'success');
        loadCampaigns();
        
    } catch (error) {
        console.error('Error publishing campaign:', error);
        showNotification(error.message, 'error');
    }
}
async function viewCampaign(campaignId) {
    try {
        // Fetch campaign details
        const campaignResponse = await fetch(`${API_BASE}/campaigns/list/${currentClientId || (await getFirstClientId())}`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (!campaignResponse.ok) throw new Error('Failed to fetch campaign');
        
        const campaignData = await campaignResponse.json();
        const campaign = campaignData.campaigns.find(c => c.campaign_id === campaignId);
        
        if (!campaign) {
            showNotification('Campaign not found', 'error');
            return;
        }
        
        // Fetch campaign ads
        const adsResponse = await fetch(`${API_BASE}/campaigns/${campaignId}/ads`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        let ads = [];
        if (adsResponse.ok) {
            const adsData = await adsResponse.json();
            ads = adsData.ads || [];
        }
        
        // Fetch performance data
        const perfResponse = await fetch(`${API_BASE}/performance/${campaignId}`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        let performance = null;
        if (perfResponse.ok) {
            const perfData = await perfResponse.json();
            performance = perfData.performance || null;
        }
        
        // Display campaign details modal
        displayCampaignDetailsModal(campaign, ads, performance);
        
    } catch (error) {
        console.error('Error loading campaign details:', error);
        showNotification('Failed to load campaign details', 'error');
    }
}

function displayCampaignDetailsModal(campaign, ads, performance) {
    const modal = document.getElementById('campaignDetailsModal');
    if (!modal) {
        createCampaignDetailsModal();
    }
    
    const detailsContainer = document.getElementById('campaignDetailsContent');
    
    // Campaign header
    let html = `
        <div style="margin-bottom: 2rem;">
            <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 1rem;">
                <div>
                    <h2 style="margin: 0 0 0.5rem 0; font-size: 1.5rem;">${campaign.campaign_name}</h2>
                    <div style="display: flex; gap: 0.75rem; align-items: center;">
                        <span class="status-badge ${campaign.status}">${campaign.status}</span>
                        <span class="platform-badge">${campaign.platform}</span>
                        <span style="color: #64748b; font-size: 0.875rem;">
                            <i class="ti ti-target"></i> ${campaign.objective}
                        </span>
                    </div>
                </div>
                <div style="display: flex; gap: 0.75rem;">
                    ${campaign.status === 'draft' ? `
                        <button class="btn btn-primary" onclick="publishCampaign(${campaign.campaign_id})">
                            <i class="ti ti-send"></i> Publish
                        </button>
                    ` : ''}
                    ${campaign.status === 'active' ? `
                        <button class="btn btn-secondary" onclick="pauseCampaign(${campaign.campaign_id})">
                            <i class="ti ti-player-pause"></i> Pause
                        </button>
                    ` : ''}
                    ${campaign.status === 'paused' ? `
                        <button class="btn btn-primary" onclick="resumeCampaign(${campaign.campaign_id})">
                            <i class="ti ti-player-play"></i> Resume
                        </button>
                    ` : ''}
                </div>
            </div>
            
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; background: #f8fafc; padding: 1.5rem; border-radius: 8px;">
                <div>
                    <div style="font-size: 0.875rem; color: #64748b; margin-bottom: 0.25rem;">Budget</div>
                    <div style="font-size: 1.25rem; font-weight: 600;">₹${Number(campaign.budget).toLocaleString()}</div>
                </div>
                <div>
                    <div style="font-size: 0.875rem; color: #64748b; margin-bottom: 0.25rem;">Start Date</div>
                    <div style="font-size: 1rem; font-weight: 500;">${new Date(campaign.start_date).toLocaleDateString()}</div>
                </div>
                ${campaign.end_date ? `
                <div>
                    <div style="font-size: 0.875rem; color: #64748b; margin-bottom: 0.25rem;">End Date</div>
                    <div style="font-size: 1rem; font-weight: 500;">${new Date(campaign.end_date).toLocaleDateString()}</div>
                </div>
                ` : ''}
                <div>
                    <div style="font-size: 0.875rem; color: #64748b; margin-bottom: 0.25rem;">Bidding Strategy</div>
                    <div style="font-size: 0.875rem; font-weight: 500;">${campaign.bidding_strategy || 'Automatic'}</div>
                </div>
                <div>
                    <div style="font-size: 0.875rem; color: #64748b; margin-bottom: 0.25rem;">Total Ads</div>
                    <div style="font-size: 1.25rem; font-weight: 600;">${ads.length}</div>
                </div>
            </div>
        </div>
    `;
    
    // Performance metrics
    if (performance) {
        html += `
            <div style="margin-bottom: 2rem;">
                <h3 style="margin: 0 0 1rem 0; font-size: 1.125rem;">
                    <i class="ti ti-chart-line"></i> Performance Metrics
                </h3>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1rem;">
                    <div class="stat-card">
                        <div class="stat-label">Impressions</div>
                        <div class="stat-value">${Number(performance.impressions || 0).toLocaleString()}</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Clicks</div>
                        <div class="stat-value">${Number(performance.clicks || 0).toLocaleString()}</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">CTR</div>
                        <div class="stat-value">${(performance.ctr || 0).toFixed(2)}%</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">CPC</div>
                        <div class="stat-value">₹${(performance.cpc || 0).toFixed(2)}</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Conversions</div>
                        <div class="stat-value">${Number(performance.conversions || 0).toLocaleString()}</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Spent</div>
                        <div class="stat-value">₹${Number(performance.amount_spent || 0).toLocaleString()}</div>
                    </div>
                </div>
            </div>
        `;
    }
    
    // Campaign ads
    html += `
        <div>
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
                <h3 style="margin: 0; font-size: 1.125rem;">
                    <i class="ti ti-ad"></i> Campaign Ads (${ads.length})
                </h3>
                <button class="btn btn-primary" onclick="openCreateAdModal(${campaign.campaign_id})">
                    <i class="ti ti-plus"></i> Create Ad
                </button>
            </div>
            
            ${ads.length === 0 ? `
                <div class="empty-state" style="padding: 2rem;">
                    <i class="ti ti-ad"></i>
                    <p>No ads created yet</p>
                </div>
            ` : `
                <div style="display: grid; gap: 1rem;">
                    ${ads.map(ad => `
                        <div style="border: 1px solid #e2e8f0; border-radius: 8px; padding: 1rem;">
                            <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 0.75rem;">
                                <div>
                                    <div style="font-weight: 600; margin-bottom: 0.25rem;">${ad.ad_name}</div>
                                    <div style="font-size: 0.875rem; color: #64748b;">${ad.ad_format}</div>
                                </div>
                                <span class="status-badge ${ad.status}">${ad.status}</span>
                            </div>
                            
                            <div style="margin-bottom: 0.75rem;">
                                <div style="font-size: 0.875rem; font-weight: 500; margin-bottom: 0.25rem;">Headline:</div>
                                <div style="font-size: 0.875rem;">${ad.headline}</div>
                            </div>
                            
                            <div style="margin-bottom: 0.75rem;">
                                <div style="font-size: 0.875rem; font-weight: 500; margin-bottom: 0.25rem;">Primary Text:</div>
                                <div style="font-size: 0.875rem; color: #64748b;">${ad.primary_text}</div>
                            </div>
                            
                            ${ad.total_impressions ? `
                                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(100px, 1fr)); gap: 1rem; padding-top: 0.75rem; border-top: 1px solid #e2e8f0;">
                                    <div>
                                        <div style="font-size: 0.75rem; color: #64748b;">Impressions</div>
                                        <div style="font-size: 0.875rem; font-weight: 600;">${Number(ad.total_impressions).toLocaleString()}</div>
                                    </div>
                                    <div>
                                        <div style="font-size: 0.75rem; color: #64748b;">Clicks</div>
                                        <div style="font-size: 0.875rem; font-weight: 600;">${Number(ad.total_clicks).toLocaleString()}</div>
                                    </div>
                                    <div>
                                        <div style="font-size: 0.75rem; color: #64748b;">CTR</div>
                                        <div style="font-size: 0.875rem; font-weight: 600;">${(ad.avg_ctr || 0).toFixed(2)}%</div>
                                    </div>
                                    <div>
                                        <div style="font-size: 0.75rem; color: #64748b;">CPC</div>
                                        <div style="font-size: 0.875rem; font-weight: 600;">₹${(ad.avg_cpc || 0).toFixed(2)}</div>
                                    </div>
                                </div>
                            ` : ''}
                        </div>
                    `).join('')}
                </div>
            `}
        </div>
    `;
    
    detailsContainer.innerHTML = html;
    document.getElementById('campaignDetailsModal').style.display = 'flex';
}

function createCampaignDetailsModal() {
    const modal = document.createElement('div');
    modal.id = 'campaignDetailsModal';
    modal.className = 'modal';
    modal.style.display = 'none';
    
    modal.innerHTML = `
        <div class="modal-overlay" onclick="closeCampaignDetailsModal()"></div>
        <div class="modal-container" style="max-width: 1200px; max-height: 90vh; overflow-y: auto;">
            <div class="modal-header">
                <h2><i class="ti ti-badge-ad"></i> Campaign Details</h2>
                <button class="modal-close" onclick="closeCampaignDetailsModal()">
                    <i class="ti ti-x"></i>
                </button>
            </div>
            <div class="modal-body" id="campaignDetailsContent">
                <div style="text-align: center; padding: 2rem;">
                    <div class="loading-spinner"></div>
                    <p>Loading campaign details...</p>
                </div>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
}

function closeCampaignDetailsModal() {
    const modal = document.getElementById('campaignDetailsModal');
    if (modal) {
        modal.style.display = 'none';
    }
}

async function pauseCampaign(campaignId) {
    if (!confirm('Are you sure you want to pause this campaign?')) return;
    
    try {
        const response = await fetch(`${API_BASE}/campaigns/${campaignId}/control`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ action: 'pause' })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to pause campaign');
        }
        
        showNotification('Campaign paused successfully', 'success');
        closeCampaignDetailsModal();
        loadCampaigns();
        
    } catch (error) {
        console.error('Error pausing campaign:', error);
        showNotification(error.message, 'error');
    }
}

async function resumeCampaign(campaignId) {
    if (!confirm('Resume this campaign?')) return;
    
    try {
        const response = await fetch(`${API_BASE}/campaigns/${campaignId}/control`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ action: 'resume' })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to resume campaign');
        }
        
        showNotification('Campaign resumed successfully', 'success');
        closeCampaignDetailsModal();
        loadCampaigns();
        
    } catch (error) {
        console.error('Error resuming campaign:', error);
        showNotification(error.message, 'error');
    }
}

async function openCreateAdModal(campaignId) {
    currentCampaignId = campaignId;
    
    // Create modal if it doesn't exist
    if (!document.getElementById('createAdModal')) {
        createAdModal();
    }
    
    // Reset form
    document.getElementById('createAdForm').reset();
    document.getElementById('adCampaignId').value = campaignId;
    
    // Show modal
    document.getElementById('createAdModal').style.display = 'flex';
}

function createAdModal() {
    const modal = document.createElement('div');
    modal.id = 'createAdModal';
    modal.className = 'modal';
    modal.style.display = 'none';
    
    modal.innerHTML = `
        <div class="modal-overlay" onclick="closeCreateAdModal()"></div>
        <div class="modal-container" style="max-width: 900px;">
            <div class="modal-header">
                <h2><i class="ti ti-ad"></i> Create New Ad</h2>
                <button class="modal-close" onclick="closeCreateAdModal()">
                    <i class="ti ti-x"></i>
                </button>
            </div>
            <div class="modal-body">
                <form id="createAdForm" onsubmit="event.preventDefault(); submitCreateAd();">
                    <input type="hidden" id="adCampaignId">
                    
                    <div class="form-group">
                        <label>Ad Name *</label>
                        <input type="text" class="form-control" id="adName" required placeholder="e.g., Summer Sale - Variant A">
                    </div>
                    
                    <div class="form-grid">
                        <div class="form-group">
                            <label>Ad Format *</label>
                            <select class="form-control" id="adFormat" required>
                                <option value="">Select format...</option>
                                <option value="feed">Feed Post</option>
                                <option value="story">Story</option>
                                <option value="reel">Reel</option>
                                <option value="carousel">Carousel</option>
                                <option value="video">Video</option>
                                <option value="collection">Collection</option>
                            </select>
                        </div>
                        
                        <div class="form-group">
                            <label>
                                <input type="checkbox" id="isABTest" style="margin-right: 0.5rem;">
                                A/B Test Variant
                            </label>
                        </div>
                    </div>
                    
                    <div id="abTestGroup" style="display: none;">
                        <div class="form-group">
                            <label>A/B Test Group</label>
                            <select class="form-control" id="abGroup">
                                <option value="A">Variant A</option>
                                <option value="B">Variant B</option>
                            </select>
                        </div>
                    </div>
                    
                    <div class="form-group">
                        <label>Headline *</label>
                        <input type="text" class="form-control" id="adHeadline" required placeholder="Catchy headline (max 40 characters)" maxlength="40">
                        <small style="color: #64748b; font-size: 0.875rem;">Character count: <span id="headlineCount">0</span>/40</small>
                    </div>
                    
                    <div class="form-group">
                        <label>Primary Text *</label>
                        <textarea class="form-control" id="adPrimaryText" required rows="4" placeholder="Main ad copy (max 125 characters)" maxlength="125"></textarea>
                        <small style="color: #64748b; font-size: 0.875rem;">Character count: <span id="primaryTextCount">0</span>/125</small>
                    </div>
                    
                    <div class="form-group">
                        <label>Description</label>
                        <textarea class="form-control" id="adDescription" rows="3" placeholder="Additional description (optional)" maxlength="30"></textarea>
                        <small style="color: #64748b; font-size: 0.875rem;">Character count: <span id="descriptionCount">0</span>/30</small>
                    </div>
                    
                    <div class="form-group">
                        <label>Media URLs</label>
                        <div id="mediaUrlsContainer">
                            <input type="url" class="form-control" id="mediaUrl1" placeholder="https://example.com/image1.jpg" style="margin-bottom: 0.5rem;">
                            <input type="url" class="form-control" id="mediaUrl2" placeholder="https://example.com/image2.jpg" style="margin-bottom: 0.5rem;">
                            <input type="url" class="form-control" id="mediaUrl3" placeholder="https://example.com/image3.jpg">
                        </div>
                        <small style="color: #64748b; font-size: 0.875rem;">Add image or video URLs for your ad creative</small>
                    </div>
                    
                    <div style="display: flex; gap: 1rem; justify-content: flex-end; margin-top: 2rem;">
                        <button type="button" class="btn btn-secondary" onclick="closeCreateAdModal()">Cancel</button>
                        <button type="submit" class="btn btn-primary" id="submitAdBtn">
                            <i class="ti ti-check"></i> Create Ad
                        </button>
                    </div>
                </form>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    // Add character counters
    document.getElementById('adHeadline').addEventListener('input', function(e) {
        document.getElementById('headlineCount').textContent = e.target.value.length;
    });
    
    document.getElementById('adPrimaryText').addEventListener('input', function(e) {
        document.getElementById('primaryTextCount').textContent = e.target.value.length;
    });
    
    document.getElementById('adDescription').addEventListener('input', function(e) {
        document.getElementById('descriptionCount').textContent = e.target.value.length;
    });
    
    // Show/hide A/B test group
    document.getElementById('isABTest').addEventListener('change', function(e) {
        document.getElementById('abTestGroup').style.display = e.target.checked ? 'block' : 'none';
    });
}

function closeCreateAdModal() {
    document.getElementById('createAdModal').style.display = 'none';
}

async function submitCreateAd() {
    const btn = document.getElementById('submitAdBtn');
    btn.disabled = true;
    btn.innerHTML = '<i class="ti ti-loader"></i> Creating...';
    
    try {
        // Collect media URLs
        const mediaUrls = [];
        for (let i = 1; i <= 3; i++) {
            const url = document.getElementById(`mediaUrl${i}`).value.trim();
            if (url) mediaUrls.push(url);
        }
        
        const isABTest = document.getElementById('isABTest').checked;
        
        const adData = {
            campaign_id: parseInt(document.getElementById('adCampaignId').value),
            ad_name: document.getElementById('adName').value,
            ad_format: document.getElementById('adFormat').value,
            headline: document.getElementById('adHeadline').value,
            primary_text: document.getElementById('adPrimaryText').value,
            description: document.getElementById('adDescription').value || null,
            media_urls: mediaUrls,
            is_ab_test_variant: isABTest,
            ab_test_group: isABTest ? document.getElementById('abGroup').value : null
        };
        
        const response = await fetch(`${API_BASE}/ads/create`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify(adData)
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to create ad');
        }
        
        const data = await response.json();
        showNotification('Ad created successfully!', 'success');
        closeCreateAdModal();
        
        // Reload campaign details to show new ad
        viewCampaign(adData.campaign_id);
        
    } catch (error) {
        console.error('Error creating ad:', error);
        showNotification(error.message, 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="ti ti-check"></i> Create Ad';
    }
}


// =====================================================
// AUDIENCE SEGMENTS
// =====================================================

async function loadAudienceSegments() {
    const clientId = document.getElementById('filterClientAudience').value;
    if (!clientId) {
        document.getElementById('audienceSegmentsList').innerHTML = '<div class="empty-state"><i class="ti ti-users"></i><p>Please select a client</p></div>';
        return;
    }
    
    const container = document.getElementById('audienceSegmentsList');
    container.innerHTML = '<div style="text-align: center; padding: 2rem;"><div class="loading-spinner"></div><p>Loading segments...</p></div>';
    
    try {
        const response = await fetch(`${API_BASE}/audience/list/${clientId}`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (!response.ok) throw new Error('Failed to load segments');
        
        const data = await response.json();
        
        if (!data.segments || data.segments.length === 0) {
            container.innerHTML = '<div class="empty-state"><i class="ti ti-users"></i><h3>No audience segments yet</h3><p>Create a segment to target specific audiences</p></div>';
            return;
        }
        
        container.innerHTML = data.segments.map(segment => `
            <div class="campaign-card">
                <div class="campaign-header">
                    <div>
                        <div class="campaign-title">${segment.segment_name}</div>
                        <div class="campaign-meta">
                            <span><i class="ti ti-calendar"></i> ${new Date(segment.created_at).toLocaleDateString()}</span>
                            <span><i class="ti ti-user"></i> ${segment.creator_name}</span>
                        </div>
                    </div>
                    <span class="platform-badge">${segment.platform}</span>
                </div>
                <div style="margin-top: 1rem;">
                    <div style="font-size: 0.875rem; color: #64748b; margin-bottom: 0.5rem;">Estimated Reach</div>
                    <div style="font-size: 1.25rem; font-weight: 600;">${Number(segment.estimated_size || 0).toLocaleString()} people</div>
                </div>
            </div>
        `).join('');
        
    } catch (error) {
        console.error('Error loading segments:', error);
        container.innerHTML = '<div class="empty-state"><i class="ti ti-alert-circle"></i><p>Failed to load segments</p></div>';
        showNotification('Failed to load audience segments', 'error');
    }
}

function openCreateAudienceModal() {
    // Load clients into modal dropdown
    loadClientsForModal('audienceClient');
    
    // Show modal
    document.getElementById('audienceModal').style.display = 'flex';
}

function closeAudienceModal() {
    document.getElementById('audienceModal').style.display = 'none';
    document.getElementById('audienceForm').reset();
}

async function submitAudience() {
    const btn = document.getElementById('submitAudienceBtn');
    btn.disabled = true;
    btn.innerHTML = '<i class="ti ti-loader"></i> Creating...';
    
    try {
        // Get device targeting
        const deviceCheckboxes = document.querySelectorAll('#audienceModal input[type="checkbox"]:checked');
        const devices = Array.from(deviceCheckboxes).map(cb => cb.value).filter(v => v);
        
        const formData = {
            client_id: parseInt(document.getElementById('audienceClient').value),
            platform: document.getElementById('audiencePlatform').value,
            segment_name: document.getElementById('audienceName').value,
            demographics: {
                age: document.getElementById('audienceAge').value || null,
                gender: document.getElementById('audienceGender').value,
                location: document.getElementById('audienceLocation').value || null
            },
            interests: document.getElementById('audienceInterests').value
                .split(',')
                .map(i => i.trim())
                .filter(i => i),
            behaviors: document.getElementById('audienceBehaviors').value
                .split(',')
                .map(b => b.trim())
                .filter(b => b),
            device_targeting: devices.length > 0 ? { devices: devices } : null,
            lookalike_source: document.getElementById('audienceLookalike').value || null
        };
        
        const response = await fetch(`${API_BASE}/audience/create`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify(formData)
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to create audience segment');
        }
        
        const data = await response.json();
        showNotification('Audience segment created successfully!', 'success');
        closeAudienceModal();
        
        // Switch to audience tab and reload
        document.getElementById('filterClientAudience').value = formData.client_id;
        loadAudienceSegments();
        
    } catch (error) {
        console.error('Error creating audience:', error);
        showNotification(error.message, 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="ti ti-check"></i> Create Audience';
    }
}

async function loadClientsForModal(selectId) {
    try {
        const response = await fetch('/api/v1/clients/list', {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (!response.ok) throw new Error('Failed to fetch clients');
        
        const data = await response.json();
        const select = document.getElementById(selectId);
        
        select.innerHTML = '<option value="">Select client...</option>';
        if (data.clients && data.clients.length > 0) {
            data.clients.forEach(client => {
                select.innerHTML += `<option value="${client.user_id}">${client.full_name}</option>`;
            });
        }
        
    } catch (error) {
        console.error('Error loading clients:', error);
    }
}

// =====================================================
// AI PLATFORM RECOMMENDATIONS
// =====================================================

async function getPlatformRecommendations() {
    const btn = document.getElementById('recommendBtn');
    const objective = document.getElementById('recObjective').value;
    const budget = parseFloat(document.getElementById('recBudget').value);
    const industry = document.getElementById('recIndustry').value;
    
    if (!objective || !budget) {
        showNotification('Please fill in all required fields', 'error');
        return;
    }
    
    btn.disabled = true;
    btn.innerHTML = '<i class="ti ti-wand"></i> Analyzing...<span class="loading-spinner"></span>';
    
    try {
        const response = await fetch(`${API_BASE}/platform/recommend`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                client_id: 1,
                campaign_objective: objective,
                budget: budget,
                target_audience: {},
                industry: industry || null
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to get recommendations');
        }
        
        const data = await response.json();
        displayPlatformRecommendations(data.recommendations);
        
    } catch (error) {
        console.error('Error getting recommendations:', error);
        showNotification(error.message, 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="ti ti-wand"></i> Get Recommendations';
    }
}

function displayPlatformRecommendations(recommendations) {
    const container = document.getElementById('platformRecommendations');
    
    if (!recommendations || !recommendations.recommendations) {
        container.innerHTML = '<p>No recommendations available</p>';
        return;
    }
    
    container.innerHTML = recommendations.recommendations.map((rec, index) => {
        // Properly handle formats array
        const formatsHtml = rec.formats && Array.isArray(rec.formats) 
            ? rec.formats.map(fmt => `
                <div style="margin-bottom: 0.75rem; padding: 0.75rem; background: white; border-radius: 6px;">
                    <strong>${fmt.format_name}</strong> (${fmt.budget_allocation}% of platform budget)<br>
                    <small style="color: #64748b;">${fmt.reason}</small><br>
                    <small style="color: #64748b;">Specs: ${fmt.creative_specs}</small>
                </div>
            `).join('')
            : '<p>No format details available</p>';
        
        return `
            <div class="recommendation-card">
                <h4>${index + 1}. ${rec.platform} - ${rec.budget_percent}% of budget</h4>
                <p style="margin-bottom: 1rem; color: #475569;">${rec.reasoning}</p>
                
                <h5 style="margin-top: 1rem; margin-bottom: 0.5rem;">Recommended Formats:</h5>
                ${formatsHtml}
                
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 1rem; margin-top: 1rem;">
                    <div>
                        <div style="font-size: 0.875rem; color: #64748b;">Expected CTR</div>
                        <div style="font-weight: 500;">${rec.expected_ctr}%</div>
                    </div>
                    <div>
                        <div style="font-size: 0.875rem; color: #64748b;">Expected CPC</div>
                        <div style="font-weight: 500;">₹${rec.expected_cpc}</div>
                    </div>
                    <div>
                        <div style="font-size: 0.875rem; color: #64748b;">Placement</div>
                        <div style="font-weight: 500;">${rec.recommended_placement || 'Automatic'}</div>
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

// =====================================================
// AI AD COPY GENERATOR
// =====================================================

async function generateAdCopy() {
    const btn = document.getElementById('generateCopyBtn');
    const product = document.getElementById('copyProduct').value;
    const audience = document.getElementById('copyAudience').value;
    const platform = document.getElementById('copyPlatform').value;
    const benefits = document.getElementById('copyBenefits').value.split(',').map(b => b.trim()).filter(b => b);
    
    if (!product || !audience) {
        showNotification('Please fill in all required fields', 'error');
        return;
    }
    
    btn.disabled = true;
    btn.innerHTML = '<i class="ti ti-sparkles"></i> Generating...<span class="loading-spinner"></span>';
    
    try {
        const response = await fetch(`${API_BASE}/adcopy/generate`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                campaign_objective: 'conversions',
                product_service: product,
                target_audience: audience,
                platform: platform,
                key_benefits: benefits,
                tone: 'professional',
                cta_type: 'Learn More'
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to generate ad copy');
        }
        
        const data = await response.json();
        displayAdCopyResults(data.ad_copy);
        
    } catch (error) {
        console.error('Error generating ad copy:', error);
        showNotification(error.message, 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="ti ti-sparkles"></i> Generate Ad Copy';
    }
}

function displayAdCopyResults(adCopy) {
    const container = document.getElementById('adCopyResults');
    
    if (!adCopy || !adCopy.variations) {
        container.innerHTML = '<p>No ad copy generated</p>';
        return;
    }
    
    container.innerHTML = `
        <h3 style="margin-bottom: 1rem;">Generated Ad Copy Variations</h3>
        ${adCopy.variations.map((variation, index) => `
            <div class="ad-copy-variation" onclick="selectAdCopy(${index}, this)">
                <h4 style="margin-bottom: 1rem; color: #9926F3;">Variation ${index + 1}</h4>
                <div style="margin-bottom: 0.75rem;">
                    <strong>Headline:</strong><br>
                    ${variation.headline}
                </div>
                <div style="margin-bottom: 0.75rem;">
                    <strong>Primary Text:</strong><br>
                    ${variation.primary_text}
                </div>
                ${variation.description ? `
                    <div style="margin-bottom: 0.75rem;">
                        <strong>Description:</strong><br>
                        ${variation.description}
                    </div>
                ` : ''}
                ${variation.hashtags && variation.hashtags.length > 0 ? `
                    <div>
                        <strong>Hashtags:</strong><br>
                        ${variation.hashtags.map(tag => `#${tag}`).join(' ')}
                    </div>
                ` : ''}
            </div>
        `).join('')}
    `;
}

function selectAdCopy(index, element) {
    document.querySelectorAll('.ad-copy-variation').forEach(v => v.classList.remove('selected'));
    element.classList.add('selected');
    selectedAdCopy = index;
    showNotification(`Variation ${index + 1} selected!`, 'success');
}

// =====================================================
// PERFORMANCE FORECASTER
// =====================================================

async function forecastPerformance() {
    const btn = document.getElementById('forecastBtn');
    const platform = document.getElementById('forecastPlatform').value;
    const budget = parseFloat(document.getElementById('forecastBudget').value);
    const duration = parseInt(document.getElementById('forecastDuration').value);
    const audience = parseInt(document.getElementById('forecastAudience').value);
    
    if (!budget || !duration || !audience) {
        showNotification('Please fill in all required fields', 'error');
        return;
    }
    
    btn.disabled = true;
    btn.innerHTML = '<i class="ti ti-calculator"></i> Calculating...<span class="loading-spinner"></span>';
    
    try {
        const response = await fetch(`${API_BASE}/forecast`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                platform: platform,
                objective: 'conversions',
                budget: budget,
                duration_days: duration,
                target_audience_size: audience,
                include_breakeven: true,
                average_order_value: 75,
                run_simulations: true
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to generate forecast');
        }
        
        const data = await response.json();
        displayForecastResults(data.forecast);
        
    } catch (error) {
        console.error('Error generating forecast:', error);
        showNotification(error.message, 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="ti ti-calculator"></i> Calculate Forecast';
    }
}

function displayForecastResults(forecast) {
    const container = document.getElementById('forecastResults');
    
    if (!forecast || !forecast.total_metrics) {
        container.innerHTML = '<p>No forecast available</p>';
        return;
    }
    
    const metrics = forecast.total_metrics;
    
    let breakEvenHtml = '';
    if (forecast.breakeven_analysis) {
        const ba = forecast.breakeven_analysis;
        breakEvenHtml = `
            <div style="margin-top: 1.5rem; padding: 1rem; background: #f8fafc; border-radius: 8px;">
                <h4 style="margin-bottom: 0.75rem;">Break-Even Analysis</h4>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem;">
                    <div>
                        <div style="font-size: 0.875rem; color: #64748b;">Break-Even Conversions</div>
                        <div style="font-size: 1.25rem; font-weight: 600;">${ba.breakeven_conversions}</div>
                    </div>
                    <div>
                        <div style="font-size: 0.875rem; color: #64748b;">Projected Conversions</div>
                        <div style="font-size: 1.25rem; font-weight: 600;">${ba.projected_conversions}</div>
                    </div>
                    <div>
                        <div style="font-size: 0.875rem; color: #64748b;">Status</div>
                        <div style="font-size: 1.25rem; font-weight: 600; color: ${ba.profitability_status === 'Profitable' ? '#10b981' : '#ef4444'};">
                            ${ba.profitability_status}
                        </div>
                    </div>
                </div>
            </div>
        `;
    }
    
    container.innerHTML = `
        <h3 style="margin-bottom: 1rem;">Performance Forecast</h3>
        <div class="forecast-grid">
            <div class="forecast-metric">
                <div class="forecast-metric-label">Total Impressions</div>
                <div class="forecast-metric-value">${Number(metrics.impressions).toLocaleString()}</div>
            </div>
            <div class="forecast-metric">
                <div class="forecast-metric-label">Total Clicks</div>
                <div class="forecast-metric-value">${Number(metrics.clicks).toLocaleString()}</div>
            </div>
            <div class="forecast-metric">
                <div class="forecast-metric-label">Est. Conversions</div>
                <div class="forecast-metric-value">${metrics.conversions}</div>
            </div>
            <div class="forecast-metric">
                <div class="forecast-metric-label">Engagements</div>
                <div class="forecast-metric-value">${Number(metrics.engagements).toLocaleString()}</div>
            </div>
            <div class="forecast-metric">
                <div class="forecast-metric-label">CTR</div>
                <div class="forecast-metric-value">${metrics.ctr}%</div>
            </div>
            <div class="forecast-metric">
                <div class="forecast-metric-label">CPC</div>
                <div class="forecast-metric-value">₹${metrics.cpc}</div>
            </div>
            <div class="forecast-metric">
                <div class="forecast-metric-label">Est. ROAS</div>
                <div class="forecast-metric-value">${metrics.roas}x</div>
            </div>
            <div class="forecast-metric">
                <div class="forecast-metric-label">Engagement Rate</div>
                <div class="forecast-metric-value">${metrics.engagement_rate}%</div>
            </div>
        </div>
        
        ${breakEvenHtml}
        
        ${forecast.optimization_tips && forecast.optimization_tips.length > 0 ? `
            <div style="margin-top: 1.5rem; padding: 1rem; background: #f8fafc; border-radius: 8px;">
                <h4 style="margin-bottom: 0.75rem;">Optimization Tips</h4>
                <ul style="margin: 0; padding-left: 1.5rem;">
                    ${forecast.optimization_tips.map(tip => `<li style="margin-bottom: 0.5rem;">${tip}</li>`).join('')}
                </ul>
            </div>
        ` : ''}
        
        <p style="margin-top: 1rem; font-size: 0.875rem; color: #64748b;">
            ${forecast.confidence_level}
        </p>
    `;
}