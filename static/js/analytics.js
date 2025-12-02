// =====================================================
// ENHANCED ANALYTICS DASHBOARD - JAVASCRIPT
// File: static/js/analytics.js
// =====================================================

const API_BASE = '/api/v1/analytics';
let currentClientId = null;
let currentView = 'daily'; // daily, weekly, campaign
let selectedDateRange = {
    start: null,
    end: null
};

// Chart instances
let trendChart = null;
let channelChart = null;
let heatmapInstance = null;

// =====================================================
// INITIALIZATION
// =====================================================

document.addEventListener('DOMContentLoaded', function () {
    // Check authentication first
    const token = localStorage.getItem('access_token');
    if (!token) {
        window.location.href = '/auth/login';
        return;
    }

    initializeDateRange();
    loadClients();
});

function initializeDateRange() {
    const endDate = new Date();
    const startDate = new Date();
    startDate.setDate(startDate.getDate() - 30);

    const startInput = document.getElementById('startDate');
    const endInput = document.getElementById('endDate');

    if (startInput && endInput) {
        startInput.valueAsDate = startDate;
        endInput.valueAsDate = endDate;
    }

    selectedDateRange = {
        start: startDate.toISOString().split('T')[0],
        end: endDate.toISOString().split('T')[0]
    };
}

// =====================================================
// VIEW SWITCHING
// =====================================================

function switchView(view) {
    currentView = view;

    // Update tab buttons
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    document.getElementById(`${view}Tab`).classList.add('active');

    // Show/hide sections based on view
    const campaignSection = document.getElementById('campaignSection');
    if (view === 'campaign') {
        campaignSection.style.display = 'block';
        loadCampaignAnalytics();
    } else {
        campaignSection.style.display = 'none';
    }

    // Reload data for the selected view
    if (currentClientId) {
        if (view === 'weekly') {
            loadWeeklyAnalytics();
        } else if (view === 'daily') {
            loadAnalytics();
        }
    }
}

// =====================================================
// LOAD CLIENTS
// =====================================================

async function loadClients() {
    try {
        const token = localStorage.getItem('access_token');
        if (!token) {
            window.location.href = '/auth/login';
            return;
        }

        const response = await fetch('/api/v1/clients/list', {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();

        console.log('Clients data:', data); // Debug log

        if (data.success && data.clients && data.clients.length > 0) {
            const selector = document.getElementById('clientSelector');
            selector.innerHTML = '<option value="">Select Client...</option>';

            data.clients.forEach(client => {
                const option = document.createElement('option');
                // FIX: Use user_id instead of client_id
                option.value = client.user_id || client.client_id;
                option.textContent = client.business_name || client.full_name;
                selector.appendChild(option);
            });

            // Auto-select first client and load data
            currentClientId = data.clients[0].user_id || data.clients[0].client_id;
            selector.value = currentClientId;

            console.log('Selected client ID:', currentClientId); // Debug log

            // Hide loading and show content
            hideLoading();
            document.getElementById('analyticsContent').style.display = 'block';

            // Now load analytics data
            loadAnalytics();
        } else {
            hideLoading();
            showError('No clients found. Please create a client first.');
        }
    } catch (error) {
        console.error('Error loading clients:', error);
        hideLoading();
        showError('Failed to load clients. Please try refreshing the page.');
    }
}

function handleClientChange() {
    const selector = document.getElementById('clientSelector');
    const selectedValue = selector.value;

    console.log('Client changed, selected value:', selectedValue); // Debug log

    currentClientId = selectedValue ? parseInt(selectedValue) : null;

    console.log('Current client ID after change:', currentClientId); // Debug log

    if (currentClientId) {
        // Show loading
        showLoading();
        // Load analytics for selected client
        loadAnalytics();
    } else {
        // Hide content if no client selected
        document.getElementById('analyticsContent').style.display = 'none';
        document.getElementById('loadingState').style.display = 'none';
    }
}


// =====================================================
// LOAD DAILY ANALYTICS DATA
// =====================================================

async function loadAnalytics() {
    console.log('loadAnalytics called, currentClientId:', currentClientId); // Debug log

    if (!currentClientId) {
        console.warn('No client selected');
        hideLoading();
        return;
    }

    showLoading();

    try {
        const token = localStorage.getItem('access_token');
        if (!token) {
            window.location.href = '/auth/login';
            return;
        }

        const url = `${API_BASE}/overview/${currentClientId}?start_date=${selectedDateRange.start}&end_date=${selectedDateRange.end}`;

        console.log('Fetching analytics from:', url); // Debug log

        const response = await fetch(url, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        console.log('Analytics response status:', response.status); // Debug log

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            console.error('Analytics API error:', errorData);
            throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();

        console.log('Analytics data received:', data); // Debug log

        if (data.success) {
            // Show content area
            document.getElementById('analyticsContent').style.display = 'block';

            displayOverviewMetrics(data.overview_metrics || {});
            displayDailyTrends(data.daily_metrics || []);

            if (data.ai_insights) {
                displayAIInsights(data.ai_insights);
            }

            hideLoading();

            // Load additional data in background
            setTimeout(() => {
                if (typeof loadAlerts === 'function') loadAlerts();
                if (typeof loadFunnels === 'function') loadFunnels();
                if (typeof loadKeywordMovement === 'function') loadKeywordMovement();
                if (typeof loadGA4Data === 'function') loadGA4Data();
                loadContentEngagement();
            }, 500);
        } else {
            throw new Error(data.detail || 'Failed to load analytics');
        }
    } catch (error) {
        console.error('Error loading analytics:', error);
        hideLoading();

        // Show error message
        showError(`Failed to load analytics: ${error.message}`);

        // Show empty state instead of error for better UX
        displayEmptyState();
        document.getElementById('analyticsContent').style.display = 'block';
    }
}

function displayEmptyState() {
    document.getElementById('totalImpressions').textContent = '0';
    document.getElementById('totalClicks').textContent = '0';
    document.getElementById('ctr').textContent = '0%';
    document.getElementById('totalConversions').textContent = '0';
    document.getElementById('conversionRate').textContent = '0%';
    document.getElementById('totalSpend').textContent = '₹0';
    document.getElementById('roas').textContent = '0.00';
    document.getElementById('websiteVisits').textContent = '0';
    document.getElementById('socialEngagement').textContent = '0';
    document.getElementById('bounceRate').textContent = '0%';

    // Show message in insights
    const insightsGrid = document.getElementById('insightsGrid');
    if (insightsGrid) {
        insightsGrid.innerHTML = `
            <div class="empty-state">
                <i class="ti ti-info-circle"></i>
                <p>No analytics data available yet. Sync your data to get started.</p>
            </div>
        `;
    }
}

// =====================================================
// LOAD WEEKLY ANALYTICS
// =====================================================

async function loadWeeklyAnalytics() {
    if (!currentClientId) return;

    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`${API_BASE}/overview/weekly/${currentClientId}?weeks=8`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        const data = await response.json();

        if (data.success) {
            displayWeeklyTrends(data.weekly_data);
        }
    } catch (error) {
        console.error('Error loading weekly analytics:', error);
    }
}

function displayWeeklyTrends(weeklyData) {
    const labels = weeklyData.map(w => {
        const start = new Date(w.week_start_date);
        return start.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    }).reverse();

    const impressionsData = weeklyData.map(w => w.total_impressions || 0).reverse();
    const clicksData = weeklyData.map(w => w.total_clicks || 0).reverse();

    // Update trend chart
    if (trendChart) {
        trendChart.data.labels = labels;
        trendChart.data.datasets[0].data = impressionsData;
        trendChart.data.datasets[0].label = 'Weekly Impressions';
        trendChart.update();
    }
}

// =====================================================
// LOAD CAMPAIGN ANALYTICS
// =====================================================

async function loadCampaignAnalytics() {
    if (!currentClientId) return;

    try {
        const token = localStorage.getItem('access_token');
        const filter = document.getElementById('campaignTypeFilter')?.value || '';

        let url = `${API_BASE}/campaigns/${currentClientId}?start_date=${selectedDateRange.start}&end_date=${selectedDateRange.end}`;
        if (filter) {
            url += `&campaign_type=${filter}`;
        }

        const response = await fetch(url, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        const data = await response.json();

        if (data.success) {
            displayCampaignTable(data.campaigns);
        }
    } catch (error) {
        console.error('Error loading campaign analytics:', error);
    }
}

function displayCampaignTable(campaigns) {
    const tbody = document.getElementById('campaignTableBody');

    if (!campaigns || campaigns.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; padding: 2rem;">No campaign data available</td></tr>';
        return;
    }

    tbody.innerHTML = campaigns.map(campaign => `
        <tr>
            <td>${campaign.campaign_name || 'Untitled Campaign'}</td>
            <td><span class="campaign-type-badge ${campaign.campaign_type}">${campaign.campaign_type.toUpperCase()}</span></td>
            <td>${(campaign.impressions || 0).toLocaleString()}</td>
            <td>${(campaign.clicks || 0).toLocaleString()}</td>
            <td>${campaign.ctr ? campaign.ctr.toFixed(2) + '%' : '0%'}</td>
            <td>${campaign.conversions || 0}</td>
            <td>₹${(campaign.spend || 0).toLocaleString()}</td>
            <td>${campaign.roas ? campaign.roas.toFixed(2) : '0.00'}</td>
        </tr>
    `).join('');
}

function filterCampaigns() {
    loadCampaignAnalytics();
}

// =====================================================
// DISPLAY OVERVIEW METRICS
// =====================================================

function displayOverviewMetrics(metrics) {
    document.getElementById('totalImpressions').textContent = metrics.total_impressions.toLocaleString();
    document.getElementById('totalClicks').textContent = metrics.total_clicks.toLocaleString();
    document.getElementById('ctr').textContent = `${metrics.ctr}%`;
    document.getElementById('totalConversions').textContent = metrics.total_conversions.toLocaleString();
    document.getElementById('conversionRate').textContent = `${metrics.conversion_rate}%`;
    document.getElementById('totalSpend').textContent = `₹${metrics.total_ad_spend.toLocaleString()}`;
    document.getElementById('roas').textContent = metrics.avg_roas.toFixed(2);
    document.getElementById('websiteVisits').textContent = metrics.total_website_visits.toLocaleString();
    document.getElementById('socialEngagement').textContent = metrics.total_social_engagement.toLocaleString();
}

// =====================================================
// DISPLAY DAILY TRENDS CHART
// ===================================================== 

function displayDailyTrends(dailyMetrics) {
    const labels = dailyMetrics.map(m => {
        const date = new Date(m.metric_date);
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    });

    const impressionsData = dailyMetrics.map(m => m.total_impressions || 0);
    const clicksData = dailyMetrics.map(m => m.total_clicks || 0);
    const conversionsData = dailyMetrics.map(m => m.total_conversions || 0);
    const spendData = dailyMetrics.map(m => m.total_ad_spend || 0);

    // Create trend chart
    const trendCtx = document.getElementById('trendChart');
    if (trendChart) {
        trendChart.destroy();
    }

    trendChart = new Chart(trendCtx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Impressions',
                data: impressionsData,
                borderColor: '#9926F3',
                backgroundColor: 'rgba(153, 38, 243, 0.1)',
                tension: 0.4,
                fill: true
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: true,
                    position: 'top'
                },
                tooltip: {
                    mode: 'index',
                    intersect: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        callback: function (value) {
                            return value.toLocaleString();
                        }
                    }
                }
            }
        }
    });

    // Create channel distribution chart
    const channelCtx = document.getElementById('channelChart');
    if (channelChart) {
        channelChart.destroy();
    }

    const totalImpressions = impressionsData.reduce((a, b) => a + b, 0);
    const totalClicks = clicksData.reduce((a, b) => a + b, 0);
    const totalConversions = conversionsData.reduce((a, b) => a + b, 0);

    channelChart = new Chart(channelCtx, {
        type: 'doughnut',
        data: {
            labels: ['Impressions', 'Clicks', 'Conversions'],
            datasets: [{
                data: [totalImpressions, totalClicks, totalConversions],
                backgroundColor: [
                    'rgba(153, 38, 243, 0.8)',
                    'rgba(29, 216, 252, 0.8)',
                    'rgba(16, 185, 129, 0.8)'
                ],
                borderWidth: 2,
                borderColor: '#fff'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom'
                }
            }
        }
    });

    // Store data for metric switching
    window.chartData = {
        labels,
        impressions: impressionsData,
        clicks: clicksData,
        conversions: conversionsData,
        spend: spendData
    };
}

function updateTrendChart() {
    const metric = document.getElementById('trendMetric').value;

    if (!window.chartData || !trendChart) return;

    const datasetConfig = {
        impressions: {
            label: 'Impressions',
            data: window.chartData.impressions,
            borderColor: '#9926F3',
            backgroundColor: 'rgba(153, 38, 243, 0.1)'
        },
        clicks: {
            label: 'Clicks',
            data: window.chartData.clicks,
            borderColor: '#1DD8FC',
            backgroundColor: 'rgba(29, 216, 252, 0.1)'
        },
        conversions: {
            label: 'Conversions',
            data: window.chartData.conversions,
            borderColor: '#10B981',
            backgroundColor: 'rgba(16, 185, 129, 0.1)'
        },
        spend: {
            label: 'Ad Spend',
            data: window.chartData.spend,
            borderColor: '#F59E0B',
            backgroundColor: 'rgba(245, 158, 11, 0.1)'
        }
    };

    const config = datasetConfig[metric];
    trendChart.data.datasets[0] = {
        ...config,
        tension: 0.4,
        fill: true
    };

    trendChart.update();
}

// =====================================================
// KEYWORD MOVEMENT
// =====================================================

async function loadKeywordMovement() {
    if (!currentClientId) return;

    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`${API_BASE}/seo/keyword-movement/${currentClientId}?days=30`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        const data = await response.json();

        if (data.success) {
            displayKeywordMovement(data.keyword_movements);
        }
    } catch (error) {
        console.error('Error loading keyword movement:', error);
    }
}

function displayKeywordMovement(movements) {
    const grid = document.getElementById('keywordMovementGrid');

    if (!movements || movements.length === 0) {
        grid.innerHTML = `
            <div class="empty-state">
                <i class="ti ti-trending-down"></i>
                <p>No keyword tracking data available</p>
            </div>
        `;
        return;
    }

    grid.innerHTML = movements.slice(0, 6).map(kw => `
        <div class="keyword-card ${kw.trend}">
            <div class="keyword-header">
                <div class="keyword-name">${kw.keyword}</div>
                <div class="keyword-trend ${kw.trend}">
                    ${kw.trend === 'up' ? '<i class="ti ti-trending-up"></i>' :
            kw.trend === 'down' ? '<i class="ti ti-trending-down"></i>' :
                '<i class="ti ti-minus"></i>'}
                    ${kw.trend_label}
                </div>
            </div>
            <div class="keyword-stats">
                <div class="keyword-stat">
                    <div class="keyword-stat-value">#${kw.current_position}</div>
                    <div class="keyword-stat-label">Current Rank</div>
                </div>
                <div class="keyword-stat">
                    <div class="keyword-stat-value">${(kw.search_volume || 0).toLocaleString()}</div>
                    <div class="keyword-stat-label">Search Volume</div>
                </div>
            </div>
        </div>
    `).join('');
}

// =====================================================
// GOOGLE ANALYTICS 4 DATA
// =====================================================

async function loadGA4Data() {
    if (!currentClientId) return;

    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`${API_BASE}/ga4/${currentClientId}?start_date=${selectedDateRange.start}&end_date=${selectedDateRange.end}`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        const data = await response.json();

        if (data.success && data.summary) {
            // Update bounce rate in metrics
            document.getElementById('bounceRate').textContent = `${data.summary.avg_bounce_rate}%`;
        }
    } catch (error) {
        console.error('Error loading GA4 data:', error);
    }
}

// =====================================================
// HEATMAP
// =====================================================

async function loadHeatmapData() {
    if (!currentClientId) return;

    const pageUrl = document.getElementById('heatmapPageSelect').value;
    if (!pageUrl) return;

    try {
        const token = localStorage.getItem('access_token');
        let url = `${API_BASE}/heatmap/${currentClientId}?days=7`;
        if (pageUrl) {
            url += `&page_url=${encodeURIComponent(pageUrl)}`;
        }

        const response = await fetch(url, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        const data = await response.json();

        if (data.success) {
            displayHeatmap(data.heatmap_data);
        }
    } catch (error) {
        console.error('Error loading heatmap data:', error);
    }
}

function displayHeatmap(heatmapData) {
    const container = document.getElementById('heatmapContainer');

    if (!heatmapData || heatmapData.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <i class="ti ti-map-off"></i>
                <p>No heatmap data available for this page</p>
            </div>
        `;
        return;
    }

    // Create heatmap visualization
    container.innerHTML = '<div class="heatmap-canvas" id="heatmapCanvas"></div>';

    const canvas = document.getElementById('heatmapCanvas');
    const config = {
        container: canvas,
        radius: 25,
        maxOpacity: 0.6,
        minOpacity: 0,
        blur: 0.75
    };

    heatmapInstance = h337.create(config);

    const points = heatmapData.map(point => ({
        x: point.click_x,
        y: point.click_y,
        value: point.interaction_count
    }));

    const max = Math.max(...points.map(p => p.value));

    heatmapInstance.setData({
        max: max,
        data: points
    });
}

// =====================================================
// ANOMALY DETECTION
// =====================================================

async function detectAnomalies() {
    if (!currentClientId) {
        showError('Please select a client');
        return;
    }

    const btn = event.target.closest('button');
    const originalHTML = btn.innerHTML;
    btn.innerHTML = '<i class="ti ti-loader"></i> Detecting...';
    btn.disabled = true;

    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`${API_BASE}/detect-anomalies/${currentClientId}`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        const data = await response.json();

        if (data.success) {
            showSuccess(`Detected ${data.anomalies_detected} anomalies`);
            loadAnomalies();
        }
    } catch (error) {
        console.error('Error detecting anomalies:', error);
        showError('Anomaly detection failed');
    } finally {
        btn.innerHTML = originalHTML;
        btn.disabled = false;
    }
}

async function loadAnomalies() {
    if (!currentClientId) return;

    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`${API_BASE}/anomalies/${currentClientId}?unresolved_only=true`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        const data = await response.json();

        if (data.success) {
            displayAnomalies(data.anomalies);
        }
    } catch (error) {
        console.error('Error loading anomalies:', error);
    }
}

function displayAnomalies(anomalies) {
    const grid = document.getElementById('anomalyGrid');

    if (!anomalies || anomalies.length === 0) {
        grid.innerHTML = `
            <div class="empty-state">
                <i class="ti ti-check-circle"></i>
                <p>No anomalies detected. Performance is normal!</p>
            </div>
        `;
        return;
    }

    grid.innerHTML = anomalies.map(anomaly => `
        <div class="anomaly-card ${anomaly.severity}">
            <div class="anomaly-header">
                <div class="anomaly-metric">${anomaly.metric_name.replace(/_/g, ' ').toUpperCase()}</div>
                <div class="anomaly-severity ${anomaly.severity}">${anomaly.severity}</div>
            </div>
            <div class="anomaly-values">
                <div class="anomaly-value-item">
                    <div class="anomaly-value-label">Expected</div>
                    <div class="anomaly-value-number">${parseFloat(anomaly.expected_value).toLocaleString()}</div>
                </div>
                <div class="anomaly-value-item">
                    <div class="anomaly-value-label">Actual</div>
                    <div class="anomaly-value-number">${parseFloat(anomaly.actual_value).toLocaleString()}</div>
                </div>
            </div>
            <div class="anomaly-deviation">${anomaly.deviation_percentage.toFixed(1)}% Deviation</div>
            <div class="anomaly-date">${formatDate(anomaly.detected_date)}</div>
        </div>
    `).join('');
}

// =====================================================
// AI INSIGHTS
// =====================================================

function displayAIInsights(insights) {
    const grid = document.getElementById('insightsGrid');

    if (!insights || insights.length === 0) {
        grid.innerHTML = `
            <div class="empty-state">
                <i class="ti ti-bulb-off"></i>
                <p>No AI insights available at this time</p>
            </div>
        `;
        return;
    }

    grid.innerHTML = insights.map(insight => `
        <div class="insight-card ${insight.type}">
            <div class="insight-icon">
                <i class="ti ti-bulb"></i>
            </div>
            <div class="insight-message">${insight.message}</div>
        </div>
    `).join('');
}

// =====================================================
// ALERTS
// =====================================================

async function loadAlerts() {
    if (!currentClientId) return;

    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`${API_BASE}/alerts/${currentClientId}`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        const data = await response.json();

        if (data.success) {
            displayAlerts(data.alerts);
        }
    } catch (error) {
        console.error('Error loading alerts:', error);
    }
}

function displayAlerts(alerts) {
    const container = document.getElementById('alertsList');

    if (!alerts || alerts.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <i class="ti ti-bell-off"></i>
                <p>No alerts at this time</p>
            </div>
        `;
        return;
    }

    container.innerHTML = alerts.map(alert => `
        <div class="alert-item ${!alert.is_read ? 'unread' : ''}">
            <div class="alert-icon">
                <i class="ti ti-alert-triangle"></i>
            </div>
            <div class="alert-content">
                <div class="alert-title">${alert.title}</div>
                <div class="alert-description">${alert.description}</div>
                <div class="alert-meta">${formatDate(alert.created_at)}</div>
            </div>
            ${!alert.is_read ? `
                <div class="alert-actions">
                    <button class="btn-secondary" onclick="markAlertRead(${alert.alert_id})">
                        <i class="ti ti-check"></i> Mark Read
                    </button>
                </div>
            ` : ''}
        </div>
    `).join('');
}

async function markAlertRead(alertId) {
    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`${API_BASE}/alerts/${alertId}/mark-read`, {
            method: 'PUT',
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        const data = await response.json();

        if (data.success) {
            loadAlerts();
        }
    } catch (error) {
        console.error('Error marking alert as read:', error);
    }
}

// =====================================================
// FUNNELS
// =====================================================

async function loadFunnels() {
    if (!currentClientId) return;

    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`${API_BASE}/funnels/${currentClientId}`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        const data = await response.json();

        if (data.success) {
            displayFunnels(data.funnels);
        }
    } catch (error) {
        console.error('Error loading funnels:', error);
    }
}

function displayFunnels(funnels) {
    const grid = document.getElementById('funnelsGrid');

    if (!funnels || funnels.length === 0) {
        grid.innerHTML = `
            <div class="empty-state">
                <i class="ti ti-funnel-off"></i>
                <p>No conversion funnels created yet</p>
            </div>
        `;
        return;
    }

    grid.innerHTML = funnels.map(funnel => `
        <div class="funnel-card">
            <div class="funnel-header">
                <div class="funnel-name">${funnel.funnel_name}</div>
            </div>
            <div class="funnel-stages">
                ${funnel.funnel_stages.map((stage, index) => {
        const nextStage = funnel.funnel_stages[index + 1];
        const dropOffRate = nextStage ?
            ((stage.count - nextStage.count) / stage.count * 100).toFixed(1) : 0;

        return `
                        <div class="funnel-stage-item">
                            <div class="funnel-stage-name">${stage.name}</div>
                            <div class="funnel-stage-stats">
                                <div class="funnel-stage-count">${stage.count || 0}</div>
                                ${nextStage ? `<div class="funnel-stage-drop">-${dropOffRate}% drop-off</div>` : ''}
                            </div>
                        </div>
                    `;
    }).join('')}
            </div>
        </div>
    `).join('');
}

function openFunnelModal() {
    document.getElementById('funnelModal').classList.add('active');
}

function closeFunnelModal() {
    document.getElementById('funnelModal').classList.remove('active');
    document.getElementById('funnelForm').reset();
}

function addFunnelStage() {
    const container = document.getElementById('funnelStages');
    const stageNumber = container.children.length + 1;

    const stageDiv = document.createElement('div');
    stageDiv.className = 'funnel-stage';
    stageDiv.innerHTML = `
        <input type="text" placeholder="Stage ${stageNumber}" required>
        <input type="number" placeholder="Count" min="0">
    `;

    container.appendChild(stageDiv);
}

async function handleCreateFunnel(event) {
    event.preventDefault();

    if (!currentClientId) {
        showError('Please select a client');
        return;
    }

    const funnelName = document.getElementById('funnelName').value;
    const stageInputs = document.querySelectorAll('#funnelStages .funnel-stage');

    const stages = Array.from(stageInputs).map(stage => {
        const inputs = stage.querySelectorAll('input');
        return {
            name: inputs[0].value,
            count: parseInt(inputs[1].value) || 0
        };
    });

    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`${API_BASE}/funnels`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                client_id: currentClientId,
                funnel_name: funnelName,
                funnel_stages: stages
            })
        });

        const data = await response.json();

        if (data.success) {
            showSuccess('Funnel created successfully!');
            closeFunnelModal();
            loadFunnels();
        } else {
            throw new Error(data.detail || 'Failed to create funnel');
        }
    } catch (error) {
        console.error('Error creating funnel:', error);
        showError('Failed to create funnel');
    }
}

// =====================================================
// SYNC & EXPORT
// =====================================================
async function syncAnalytics() {
    if (!currentClientId) {
        showError('Please select a client');
        return;
    }

    const btn = event.target.closest('button');
    const originalHTML = btn.innerHTML;
    btn.innerHTML = '<i class="ti ti-refresh"></i> Syncing from APIs...';
    btn.disabled = true;

    try {
        const token = localStorage.getItem('access_token');

        const response = await fetch(`${API_BASE}/sync-all-platforms`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                client_id: currentClientId,
                start_date: selectedDateRange.start,
                end_date: selectedDateRange.end
            })
        });

        const data = await response.json();
        console.log('Sync response:', data);

        if (data.success) {
            showSuccess('✓ Analytics synced successfully!');
            loadAnalytics();
        } else {
            throw new Error(data.detail || 'Sync failed');
        }
    } catch (error) {
        console.error('Sync error:', error);
        showError(`Sync failed: ${error.message}`);
    } finally {
        btn.innerHTML = originalHTML;
        btn.disabled = false;
    }
}

function applyDateRange() {
    const startInput = document.getElementById('startDate');
    const endInput = document.getElementById('endDate');

    selectedDateRange = {
        start: startInput.value,
        end: endInput.value
    };

    loadAnalytics();
}

async function exportReport() {
    if (!currentClientId) {
        showError('Please select a client');
        return;
    }

    try {
        const token = localStorage.getItem('access_token');
        const url = `${API_BASE}/export/${currentClientId}?start_date=${selectedDateRange.start}&end_date=${selectedDateRange.end}&format=json`;

        const response = await fetch(url, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        const data = await response.json();

        if (data.success) {
            const dataStr = JSON.stringify(data.data, null, 2);
            const dataBlob = new Blob([dataStr], { type: 'application/json' });
            const url = URL.createObjectURL(dataBlob);
            const link = document.createElement('a');
            link.href = url;
            link.download = `analytics_report_${selectedDateRange.start}_to_${selectedDateRange.end}.json`;
            link.click();

            showSuccess('Report exported successfully!');
        }
    } catch (error) {
        console.error('Error exporting report:', error);
        showError('Failed to export report');
    }
}

// =====================================================
// UTILITY FUNCTIONS
// =====================================================
function showLoading() {
    const loadingState = document.getElementById('loadingState');
    const analyticsContent = document.getElementById('analyticsContent');

    if (loadingState) {
        loadingState.style.display = 'flex';
    }
    if (analyticsContent) {
        analyticsContent.style.display = 'none';
    }
}

function hideLoading() {
    const loadingState = document.getElementById('loadingState');

    if (loadingState) {
        loadingState.style.display = 'none';
    }
}
function showError(message) {
    // Simple error notification
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error-notification';
    errorDiv.innerHTML = `
        <i class="ti ti-alert-circle"></i>
        <span>${message}</span>
    `;
    errorDiv.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: #ff4444;
        color: white;
        padding: 15px 20px;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        z-index: 10000;
        display: flex;
        align-items: center;
        gap: 10px;
        animation: slideIn 0.3s ease;
    `;

    document.body.appendChild(errorDiv);

    setTimeout(() => {
        errorDiv.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => errorDiv.remove(), 300);
    }, 5000);
}

function showSuccess(message) {
    // Simple success notification
    const successDiv = document.createElement('div');
    successDiv.className = 'success-notification';
    successDiv.innerHTML = `
        <i class="ti ti-check-circle"></i>
        <span>${message}</span>
    `;
    successDiv.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: #00c851;
        color: white;
        padding: 15px 20px;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        z-index: 10000;
        display: flex;
        align-items: center;
        gap: 10px;
        animation: slideIn 0.3s ease;
    `;

    document.body.appendChild(successDiv);

    setTimeout(() => {
        successDiv.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => successDiv.remove(), 300);
    }, 3000);
}

function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}


// =====================================================
// CONTENT ENGAGEMENT BY FORMAT & PLATFORM
// =====================================================

async function loadContentEngagement() {
    if (!currentClientId) return;

    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`${API_BASE}/content-engagement/${currentClientId}?start_date=${selectedDateRange.start}&end_date=${selectedDateRange.end}`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        const data = await response.json();

        if (data.success) {
            displayFormatEngagement(data.by_format);
            displayPlatformEngagement(data.by_platform);
            displayTopContent(data.top_performing_content);
            displayContentRecommendation(data.insights);
        }
    } catch (error) {
        console.error('Error loading content engagement:', error);
    }
}

function displayFormatEngagement(formatData) {
    const grid = document.getElementById('formatEngagementGrid');
    if (!grid) return;

    if (!formatData || formatData.length === 0) {
        grid.innerHTML = `
            <div class="empty-state">
                <i class="ti ti-photo-off"></i>
                <p>No content format data available</p>
            </div>
        `;
        return;
    }

    const formatIcons = {
        'image': 'ti-photo',
        'video': 'ti-video',
        'carousel': 'ti-carousel-horizontal',
        'text': 'ti-text-caption',
        'story': 'ti-circle-dashed',
        'reel': 'ti-movie',
        'article': 'ti-article'
    };

    const formatColors = {
        'image': '#9926F3',
        'video': '#1DD8FC',
        'carousel': '#10B981',
        'text': '#F59E0B',
        'story': '#EC4899',
        'reel': '#8B5CF6',
        'article': '#3B82F6'
    };

    grid.innerHTML = formatData.map((item, index) => `
        <div class="format-card ${index === 0 ? 'top-performer' : ''}">
            <div class="format-icon" style="background: ${formatColors[item.content_format] || '#6B7280'}20; color: ${formatColors[item.content_format] || '#6B7280'}">
                <i class="ti ${formatIcons[item.content_format] || 'ti-file'}"></i>
            </div>
            <div class="format-details">
                <div class="format-name">${(item.content_format || 'unknown').replace('_', ' ').toUpperCase()}</div>
                <div class="format-stats">
                    <div class="format-stat">
                        <span class="stat-value">${item.total_posts}</span>
                        <span class="stat-label">Posts</span>
                    </div>
                    <div class="format-stat">
                        <span class="stat-value">${(item.total_engagement || 0).toLocaleString()}</span>
                        <span class="stat-label">Engagement</span>
                    </div>
                    <div class="format-stat">
                        <span class="stat-value">${item.avg_engagement_rate}%</span>
                        <span class="stat-label">Eng. Rate</span>
                    </div>
                </div>
            </div>
            ${index === 0 ? '<div class="top-badge"><i class="ti ti-crown"></i> Best</div>' : ''}
        </div>
    `).join('');
}

function displayPlatformEngagement(platformData) {
    const grid = document.getElementById('platformEngagementGrid');
    if (!grid) return;

    if (!platformData || platformData.length === 0) {
        grid.innerHTML = `
            <div class="empty-state">
                <i class="ti ti-brand-instagram"></i>
                <p>No platform data available</p>
            </div>
        `;
        return;
    }

    const platformIcons = {
        'instagram': 'ti-brand-instagram',
        'facebook': 'ti-brand-facebook',
        'linkedin': 'ti-brand-linkedin',
        'twitter': 'ti-brand-twitter',
        'tiktok': 'ti-brand-tiktok'
    };

    const platformColors = {
        'instagram': '#E4405F',
        'facebook': '#1877F2',
        'linkedin': '#0A66C2',
        'twitter': '#1DA1F2',
        'tiktok': '#000000'
    };

    grid.innerHTML = platformData.map((item, index) => `
        <div class="platform-card ${index === 0 ? 'top-performer' : ''}">
            <div class="platform-icon" style="background: ${platformColors[item.platform] || '#6B7280'}; color: white;">
                <i class="ti ${platformIcons[item.platform] || 'ti-world'}"></i>
            </div>
            <div class="platform-details">
                <div class="platform-name">${(item.platform || 'unknown').charAt(0).toUpperCase() + (item.platform || 'unknown').slice(1)}</div>
                <div class="platform-metrics">
                    <div class="metric-row">
                        <span>Posts:</span>
                        <strong>${item.total_posts}</strong>
                    </div>
                    <div class="metric-row">
                        <span>Impressions:</span>
                        <strong>${(item.total_impressions || 0).toLocaleString()}</strong>
                    </div>
                    <div class="metric-row">
                        <span>Reach:</span>
                        <strong>${(item.total_reach || 0).toLocaleString()}</strong>
                    </div>
                    <div class="metric-row">
                        <span>Engagement:</span>
                        <strong>${(item.total_engagement || 0).toLocaleString()}</strong>
                    </div>
                    <div class="metric-row highlight">
                        <span>Eng. Rate:</span>
                        <strong>${item.avg_engagement_rate}%</strong>
                    </div>
                </div>
            </div>
            ${index === 0 ? '<div class="top-badge"><i class="ti ti-crown"></i> Best</div>' : ''}
        </div>
    `).join('');
}

function displayTopContent(topContent) {
    const list = document.getElementById('topContentList');
    if (!list) return;

    if (!topContent || topContent.length === 0) {
        list.innerHTML = `
            <div class="empty-state">
                <i class="ti ti-trophy-off"></i>
                <p>No top performing content yet</p>
            </div>
        `;
        return;
    }

    const platformIcons = {
        'instagram': 'ti-brand-instagram',
        'facebook': 'ti-brand-facebook',
        'linkedin': 'ti-brand-linkedin',
        'twitter': 'ti-brand-twitter',
        'tiktok': 'ti-brand-tiktok'
    };

    const formatIcons = {
        'image': 'ti-photo',
        'video': 'ti-video',
        'carousel': 'ti-carousel-horizontal',
        'text': 'ti-text-caption',
        'story': 'ti-circle-dashed',
        'reel': 'ti-movie'
    };

    list.innerHTML = topContent.map((item, index) => `
        <div class="top-content-item">
            <div class="content-rank">#${index + 1}</div>
            <div class="content-info">
                <div class="content-meta">
                    <span class="platform-badge">
                        <i class="ti ${platformIcons[item.platform] || 'ti-world'}"></i>
                        ${item.platform || 'unknown'}
                    </span>
                    <span class="format-badge">
                        <i class="ti ${formatIcons[item.content_format] || 'ti-file'}"></i>
                        ${item.content_format || 'unknown'}
                    </span>
                </div>
                <div class="content-caption">${item.caption ? (item.caption.length > 80 ? item.caption.substring(0, 80) + '...' : item.caption) : 'No caption'}</div>
                <div class="content-date">${item.published_at ? formatDate(item.published_at) : 'N/A'}</div>
            </div>
            <div class="content-stats">
                <div class="stat-item">
                    <span class="stat-number">${(item.impressions || 0).toLocaleString()}</span>
                    <span class="stat-label">Impressions</span>
                </div>
                <div class="stat-item">
                    <span class="stat-number">${(item.engagement || 0).toLocaleString()}</span>
                    <span class="stat-label">Engagement</span>
                </div>
                <div class="stat-item highlight">
                    <span class="stat-number">${item.engagement_rate || 0}%</span>
                    <span class="stat-label">Eng. Rate</span>
                </div>
            </div>
        </div>
    `).join('');
}

function displayContentRecommendation(insights) {
    const container = document.getElementById('contentRecommendation');
    const textEl = document.getElementById('recommendationText');
    if (!container || !textEl) return;

    if (!insights || !insights.recommendation) {
        container.style.display = 'none';
        return;
    }

    textEl.innerHTML = `
        <strong>Insight:</strong> ${insights.recommendation}
        ${insights.best_format ? `<br><small>Best performing format: <strong>${insights.best_format.toUpperCase()}</strong></small>` : ''}
        ${insights.best_platform ? `<br><small>Best performing platform: <strong>${insights.best_platform.charAt(0).toUpperCase() + insights.best_platform.slice(1)}</strong></small>` : ''}
    `;

    container.style.display = 'flex';
}

// ============================================
// UPDATE: Add this call inside loadAnalytics() setTimeout block
// Find the setTimeout block and add: loadContentEngagement();
// ============================================

// Also update displayOverviewMetrics to include CPC
// Add this line inside displayOverviewMetrics function:
// document.getElementById('avgCpc').textContent = `₹${(metrics.avg_cpc || 0).toFixed(2)}`;