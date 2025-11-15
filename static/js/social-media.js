/**
 * Social Media Command Center - Module 6
 * File: static/js/social-media.js
 */

const API_BASE = '/api/v1/social-media';
let currentMonth = new Date().getMonth();
let currentYear = new Date().getFullYear();
let selectedContentId = null;
let selectedMediaUrls = [];
let currentEditingPostId = null;

// =====================================================
// INITIALIZATION
// =====================================================

document.addEventListener('DOMContentLoaded', function() {
    loadClients();
    loadPosts();
    loadCalendar();
    loadTrendingTopics();
    loadPerformanceSummaries();
    initializePlatformSelector();
});

function initializePlatformSelector() {
    const platforms = document.querySelectorAll('.platform-option');
    platforms.forEach(platform => {
        platform.addEventListener('click', function() {
            platforms.forEach(p => p.classList.remove('selected'));
            this.classList.add('selected');
            document.getElementById('postPlatform').value = this.dataset.platform;
        });
    });
}

// =====================================================
// LOAD CLIENTS
// =====================================================

async function loadClients() {
    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch('/api/v1/clients/list', {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (!response.ok) throw new Error('Failed to load clients');

        const data = await response.json();
        
        // Populate both filter and form dropdowns
        const filterSelect = document.getElementById('filterClient');
        const formSelect = document.getElementById('postClient');
        
        data.clients.forEach(client => {
            // FIXED: Use user_id instead of client_id
            const option1 = new Option(client.full_name, client.user_id);
            const option2 = new Option(client.full_name, client.user_id);
            filterSelect.add(option1);
            formSelect.add(option2);
        });
    } catch (error) {
        console.error('Error loading clients:', error);
    }
}



// =====================================================
// LOAD POSTS (LIST VIEW)
// =====================================================

async function loadPosts() {
    try {
        const token = localStorage.getItem('access_token');
        const clientId = document.getElementById('filterClient').value;
        const platform = document.getElementById('filterPlatform').value;
        const status = document.getElementById('filterStatus').value;
        
        let url = `${API_BASE}/posts?`;
        if (clientId) url += `client_id=${clientId}&`;
        if (platform) url += `platform=${platform}&`;
        if (status) url += `status=${status}&`;
        
        const response = await fetch(url, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (!response.ok) throw new Error('Failed to load posts');

        const data = await response.json();
        
        displayPosts(data.posts);
        updateStats(data.posts);
        
        // Also reload performance summaries when client changes
        if (clientId) {
            loadPerformanceSummaries();
        }
        
    } catch (error) {
        console.error('Error loading posts:', error);
        showNotification('Failed to load posts', 'error');
    }
}

function displayPosts(posts) {
    const postsList = document.getElementById('postsList');
    
    if (!posts || posts.length === 0) {
        postsList.innerHTML = `
            <div class="empty-state">
                <i class="ti ti-calendar-off"></i>
                <h3>No posts found</h3>
                <p>Start creating social media posts to see them here</p>
                <button class="btn btn-primary" onclick="openCreatePostModal()">
                    <i class="ti ti-plus"></i> Create Your First Post
                </button>
            </div>
        `;
        return;
    }
    
    let html = '';
    posts.forEach(post => {
        const platformClass = `platform-${post.platform}`;
        const statusClass = `status-${post.status}`;
        const scheduledDate = post.scheduled_at ? new Date(post.scheduled_at).toLocaleString() : 'Not scheduled';
        
        html += `
            <div class="post-item">
                <div class="post-platform-icon ${platformClass}">
                    <i class="ti ti-brand-${post.platform}"></i>
                </div>
                <div class="post-content">
                    <div class="post-header">
                        <div class="post-client">${post.client_name}</div>
                        <span class="post-status ${statusClass}">${post.status.charAt(0).toUpperCase() + post.status.slice(1)}</span>
                    </div>
                    <div class="post-caption">${post.caption.substring(0, 200)}${post.caption.length > 200 ? '...' : ''}</div>
                    <div class="post-meta">
                        <span><i class="ti ti-calendar"></i> ${scheduledDate}</span>
                        <span><i class="ti ti-photo"></i> ${post.media_count} media</span>
                        <span><i class="ti ti-hash"></i> ${post.hashtags.length} hashtags</span>
                    </div>
                </div>
                <div class="post-actions">
                    <button onclick="editPost(${post.post_id})" title="Edit">
                        <i class="ti ti-edit"></i>
                    </button>
                    <button onclick="deletePost(${post.post_id})" title="Delete">
                        <i class="ti ti-trash"></i>
                    </button>
                </div>
            </div>
        `;
    });
    
    postsList.innerHTML = html;
}

function updateStats(posts) {
    const total = posts.length;
    const scheduled = posts.filter(p => p.status === 'scheduled').length;
    const published = posts.filter(p => p.status === 'published').length;
    const draft = posts.filter(p => p.status === 'draft').length;
    
    document.getElementById('totalPosts').textContent = total;
    document.getElementById('scheduledPosts').textContent = scheduled;
    document.getElementById('publishedPosts').textContent = published;
    document.getElementById('draftPosts').textContent = draft;
}

// =====================================================
// CALENDAR VIEW
// =====================================================

async function loadCalendar() {
    try {
        const token = localStorage.getItem('access_token');
        const clientId = document.getElementById('filterClient').value;
        
        if (!clientId) {
            displayCalendarGrid({});
            return;
        }
        
        const response = await fetch(`${API_BASE}/calendar?client_id=${clientId}&month=${currentMonth + 1}&year=${currentYear}`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (!response.ok) throw new Error('Failed to load calendar');

        const data = await response.json();
        displayCalendarGrid(data.calendar);
        
    } catch (error) {
        console.error('Error loading calendar:', error);
    }
}

function displayCalendarGrid(calendarData) {
    const monthNames = ['January', 'February', 'March', 'April', 'May', 'June', 
                       'July', 'August', 'September', 'October', 'November', 'December'];
    
    document.getElementById('calendarMonth').textContent = `${monthNames[currentMonth]} ${currentYear}`;
    
    const firstDay = new Date(currentYear, currentMonth, 1);
    const lastDay = new Date(currentYear, currentMonth + 1, 0);
    const startingDayOfWeek = firstDay.getDay();
    const numberOfDays = lastDay.getDate();
    
    let html = `
        <div class="calendar-grid">
            <div class="calendar-day-header">Sun</div>
            <div class="calendar-day-header">Mon</div>
            <div class="calendar-day-header">Tue</div>
            <div class="calendar-day-header">Wed</div>
            <div class="calendar-day-header">Thu</div>
            <div class="calendar-day-header">Fri</div>
            <div class="calendar-day-header">Sat</div>
    `;
    
    // Empty cells before first day
    for (let i = 0; i < startingDayOfWeek; i++) {
        html += '<div class="calendar-day other-month"></div>';
    }
    
    // Days of month
    const today = new Date();
    for (let day = 1; day <= numberOfDays; day++) {
        const dateKey = `${currentYear}-${String(currentMonth + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
        const isToday = day === today.getDate() && currentMonth === today.getMonth() && currentYear === today.getFullYear();
        
        const posts = calendarData[dateKey] || [];
        
        html += `
            <div class="calendar-day ${isToday ? 'today' : ''}">
                <div class="day-number">${day}</div>
        `;
        
        posts.forEach(post => {
            html += `
                <div class="calendar-post ${post.platform}" onclick="editPost(${post.post_id})" title="${post.caption}">
                    <i class="ti ti-brand-${post.platform}"></i> ${post.caption.substring(0, 30)}...
                </div>
            `;
        });
        
        html += '</div>';
    }
    
    html += '</div>';
    
    document.getElementById('calendarGrid').innerHTML = html;
}

function changeMonth(delta) {
    if (delta === 0) {
        // Today
        const today = new Date();
        currentMonth = today.getMonth();
        currentYear = today.getFullYear();
    } else {
        currentMonth += delta;
        if (currentMonth > 11) {
            currentMonth = 0;
            currentYear++;
        } else if (currentMonth < 0) {
            currentMonth = 11;
            currentYear--;
        }
    }
    loadCalendar();
}

// =====================================================
// VIEW SWITCHING
// =====================================================

function switchView(view) {
    const tabs = document.querySelectorAll('.view-tab');
    tabs.forEach(tab => tab.classList.remove('active'));
    event.target.closest('.view-tab').classList.add('active');
    
    document.getElementById('calendarView').classList.remove('active');
    document.getElementById('listView').classList.remove('active');
    
    if (view === 'calendar') {
        document.getElementById('calendarView').classList.add('active');
        loadCalendar();
    } else {
        document.getElementById('listView').classList.add('active');
        loadPosts();
    }
}

// =====================================================
// CREATE/EDIT POST MODAL
// =====================================================

function openCreatePostModal() {
    currentEditingPostId = null;
    selectedContentId = null;
    selectedMediaUrls = [];
    
    document.getElementById('modalTitle').textContent = 'Create New Post';
    document.getElementById('postForm').reset();
    document.getElementById('postModal').classList.add('active');
    document.getElementById('submitPostBtn').innerHTML = '<i class="ti ti-check"></i> Create Post';
    
    // Reset platform selection
    document.querySelectorAll('.platform-option').forEach(p => p.classList.remove('selected'));
    document.getElementById('postPlatform').value = '';
    
    // Hide pickers
    document.getElementById('contentLibraryPicker').style.display = 'none';
    document.getElementById('mediaLibraryPicker').style.display = 'none';
    document.getElementById('bestTimesPanel').style.display = 'none';
}

async function editPost(postId) {
    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`${API_BASE}/posts/${postId}`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (!response.ok) throw new Error('Failed to load post');

        const data = await response.json();
        const post = data.post;
        
        currentEditingPostId = postId;
        document.getElementById('modalTitle').textContent = 'Edit Post';
        document.getElementById('submitPostBtn').innerHTML = '<i class="ti ti-check"></i> Update Post';
        
        // Populate form
        document.getElementById('postClient').value = post.client_id;
        document.getElementById('postCaption').value = post.caption;
        document.getElementById('postHashtags').value = post.hashtags.join(', ');
        document.getElementById('postStatus').value = post.status;
        
        if (post.scheduled_at) {
            const date = new Date(post.scheduled_at);
            const localDateTime = new Date(date.getTime() - (date.getTimezoneOffset() * 60000)).toISOString().slice(0, 16);
            document.getElementById('postScheduledAt').value = localDateTime;
        }
        
        // Select platform
        document.querySelectorAll('.platform-option').forEach(p => p.classList.remove('selected'));
        const platformEl = document.querySelector(`[data-platform="${post.platform}"]`);
        if (platformEl) {
            platformEl.classList.add('selected');
            document.getElementById('postPlatform').value = post.platform;
        }
        
        selectedMediaUrls = post.media_urls || [];
        selectedContentId = post.content_id;
        
        document.getElementById('postModal').classList.add('active');
        
    } catch (error) {
        console.error('Error loading post:', error);
        showNotification('Failed to load post details', 'error');
    }
}

function closePostModal() {
    document.getElementById('postModal').classList.remove('active');
}

// =====================================================
// SAVE POST
// =====================================================

async function savePost(event) {
    event.preventDefault();
    
    const submitBtn = document.getElementById('submitPostBtn');
    const originalBtnText = submitBtn.innerHTML;
    
    try {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="ti ti-loader"></i> Saving...';
        
        const token = localStorage.getItem('access_token');
        const clientId = document.getElementById('postClient').value;
        const platform = document.getElementById('postPlatform').value;
        const caption = document.getElementById('postCaption').value;
        const hashtags = document.getElementById('postHashtags').value
            .split(',')
            .map(h => h.trim())
            .filter(h => h);
        const status = document.getElementById('postStatus').value;
        const scheduledAt = document.getElementById('postScheduledAt').value;
        
        if (!platform) {
            showNotification('Please select a platform', 'error');
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalBtnText;
            return;
        }
        
        const postData = {
            client_id: parseInt(clientId),
            content_id: selectedContentId,
            platform: platform,
            caption: caption,
            media_urls: selectedMediaUrls,
            hashtags: hashtags,
            scheduled_at: scheduledAt || null,
            status: status
        };
        
        let url = `${API_BASE}/posts`;
        let method = 'POST';
        
        if (currentEditingPostId) {
            url += `/${currentEditingPostId}`;
            method = 'PUT';
        }
        
        const response = await fetch(url, {
            method: method,
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify(postData)
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to save post');
        }
        
        const result = await response.json();
        
        showNotification(result.message, 'success');
        closePostModal();
        loadPosts();
        loadCalendar();
        
    } catch (error) {
        console.error('Error saving post:', error);
        showNotification(error.message, 'error');
    } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalBtnText;
    }
}

// =====================================================
// DELETE POST
// =====================================================

async function deletePost(postId) {
    if (!confirm('Are you sure you want to delete this post?')) return;
    
    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`${API_BASE}/posts/${postId}`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (!response.ok) throw new Error('Failed to delete post');
        
        showNotification('Post deleted successfully', 'success');
        loadPosts();
        loadCalendar();
        
    } catch (error) {
        console.error('Error deleting post:', error);
        showNotification('Failed to delete post', 'error');
    }
}

// =====================================================
// CONTENT LIBRARY INTEGRATION (MODULE 5)
// =====================================================

async function loadContentLibrary() {
    const clientId = document.getElementById('postClient').value;
    
    if (!clientId) {
        showNotification('Please select a client first', 'error');
        return;
    }
    
    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`/api/v1/content/list?client_id=${clientId}`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (!response.ok) throw new Error('Failed to load content library');

        const data = await response.json();
        displayContentLibrary(data.content || []);
        
    } catch (error) {
        console.error('Error loading content library:', error);
        showNotification('Failed to load content library', 'error');
    }
}

function displayContentLibrary(content) {
    const picker = document.getElementById('contentLibraryPicker');
    
    if (content.length === 0) {
        picker.innerHTML = '<p style="text-align: center; color: #64748b;">No saved content found</p>';
        picker.style.display = 'block';
        return;
    }
    
    let html = '';
    content.forEach(item => {
        const isSelected = selectedContentId === item.content_id;
        html += `
            <div class="content-card ${isSelected ? 'selected' : ''}" onclick="selectContent(${item.content_id}, '${item.content_text.replace(/'/g, "\\'")}', ${JSON.stringify(item.hashtags || [])})">
                <div class="content-card-platform">${item.platform || 'General'}</div>
                <div class="content-card-text">${item.content_text}</div>
            </div>
        `;
    });
    
    picker.innerHTML = html;
    picker.style.display = 'grid';
}

function selectContent(contentId, text, hashtags) {
    selectedContentId = contentId;
    document.getElementById('postCaption').value = text;
    
    if (hashtags && hashtags.length > 0) {
        document.getElementById('postHashtags').value = hashtags.join(', ');
    }
    
    // Update selected state
    document.querySelectorAll('.content-card').forEach(card => {
        card.classList.remove('selected');
    });
    event.target.closest('.content-card').classList.add('selected');
    
    showNotification('Content loaded successfully', 'success');
}

// =====================================================
// MEDIA LIBRARY INTEGRATION (MODULE 8)
// =====================================================

async function loadMediaLibrary() {
    const clientId = document.getElementById('postClient').value;
    
    if (!clientId) {
        showNotification('Please select a client first', 'error');
        return;
    }
    
    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`/api/v1/media-studio/assets?client_id=${clientId}`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (!response.ok) throw new Error('Failed to load media library');

        const data = await response.json();
        displayMediaLibrary(data.assets || []);
        
    } catch (error) {
        console.error('Error loading media library:', error);
        showNotification('Failed to load media library', 'error');
    }
}

function displayMediaLibrary(assets) {
    const picker = document.getElementById('mediaLibraryPicker');
    
    if (assets.length === 0) {
        picker.innerHTML = '<p style="text-align: center; color: #64748b;">No media assets found</p>';
        picker.style.display = 'block';
        return;
    }
    
    let html = '';
    assets.forEach(asset => {
        const isSelected = selectedMediaUrls.includes(asset.file_url);
        html += `
            <div class="media-card ${isSelected ? 'selected' : ''}" onclick="toggleMedia('${asset.file_url}', '${asset.asset_type}')">
                <img src="${asset.file_url}" alt="${asset.asset_name}">
                <div class="media-card-type">${asset.asset_type}</div>
                <div class="checkmark"><i class="ti ti-check"></i></div>
            </div>
        `;
    });
    
    picker.innerHTML = html;
    picker.style.display = 'grid';
}

function toggleMedia(url, type) {
    const index = selectedMediaUrls.indexOf(url);
    
    if (index > -1) {
        selectedMediaUrls.splice(index, 1);
    } else {
        selectedMediaUrls.push(url);
    }
    
    // Update UI
    event.target.closest('.media-card').classList.toggle('selected');
    
    showNotification(`${selectedMediaUrls.length} media selected`, 'info');
}

// =====================================================
// AI BEST TIMES
// =====================================================

async function getBestTimes() {
    const clientId = document.getElementById('postClient').value;
    const platform = document.getElementById('postPlatform').value;
    
    if (!clientId || !platform) {
        showNotification('Please select client and platform first', 'error');
        return;
    }
    
    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`${API_BASE}/best-times`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                client_id: parseInt(clientId),
                platform: platform
            })
        });

        if (!response.ok) throw new Error('Failed to get best times');

        const data = await response.json();
        displayBestTimes(data.recommended_times);
        
    } catch (error) {
        console.error('Error getting best times:', error);
        showNotification('Failed to get best times', 'error');
    }
}

function displayBestTimes(times) {
    const panel = document.getElementById('bestTimesPanel');
    
    let html = '<div class="best-times-grid">';
    times.forEach(time => {
        html += `
            <div class="best-time-item" onclick="useBestTime('${time.day}', ${time.hour})">
                <div class="best-time-info">
                    <div class="best-time-icon">
                        <i class="ti ti-clock"></i>
                    </div>
                    <div class="best-time-details">
                        <h4>${time.day} at ${time.time_formatted}</h4>
                        <p>Click to use this time</p>
                    </div>
                </div>
                <div class="best-time-score">
                    <div class="score-value">${time.engagement_score.toFixed(1)}</div>
                    <div class="score-label">Engagement Score</div>
                </div>
            </div>
        `;
    });
    html += '</div>';
    
    panel.innerHTML = html;
    panel.style.display = 'block';
}

function useBestTime(day, hour) {
    const dayMap = {
        'Monday': 1, 'Tuesday': 2, 'Wednesday': 3, 'Thursday': 4,
        'Friday': 5, 'Saturday': 6, 'Sunday': 0
    };
    
    const today = new Date();
    const targetDay = dayMap[day];
    const daysUntilTarget = (targetDay + 7 - today.getDay()) % 7 || 7;
    
    const targetDate = new Date(today);
    targetDate.setDate(today.getDate() + daysUntilTarget);
    targetDate.setHours(hour, 0, 0, 0);
    
    const localDateTime = new Date(targetDate.getTime() - (targetDate.getTimezoneOffset() * 60000)).toISOString().slice(0, 16);
    document.getElementById('postScheduledAt').value = localDateTime;
    document.getElementById('postStatus').value = 'scheduled';
    
    showNotification(`Scheduled for ${day} at ${hour}:00`, 'success');
}

// =====================================================
// TRENDING TOPICS
// =====================================================

async function loadTrendingTopics() {
    try {
        const token = localStorage.getItem('access_token');
        const platform = document.getElementById('trendingPlatformFilter').value;
        
        let url = `${API_BASE}/trending`;
        if (platform) {
            url += `?platform=${platform}`;
        }
        
        const response = await fetch(url, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (!response.ok) throw new Error('Failed to load trending topics');

        const data = await response.json();
        displayTrendingTopics(data.trends);
        
    } catch (error) {
        console.error('Error loading trending topics:', error);
    }
}

function displayTrendingTopics(trends) {
    const container = document.getElementById('trendingTopics');
    
    if (!trends || trends.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <i class="ti ti-trending-down"></i>
                <h3>No trending topics</h3>
                <p>Check back later for trending topics</p>
            </div>
        `;
        return;
    }
    
    let html = '<div class="trending-grid">';
    
    trends.forEach(trend => {
        const volumeFormatted = (trend.volume / 1000).toFixed(1) + 'K';
        html += `
            <div class="trending-card" onclick="useTrendingTopic('${trend.topic.replace(/'/g, "\\'")}')">
                <div class="trending-header">
                    <span class="trending-platform">${trend.platform}</span>
                    <span class="trending-volume">
                        <i class="ti ti-eye"></i> ${volumeFormatted}
                    </span>
                </div>
                <div class="trending-topic">#${trend.topic}</div>
                <div class="trending-category">${trend.category}</div>
            </div>
        `;
    });
    
    html += '</div>';
    container.innerHTML = html;
}

function useTrendingTopic(topic) {
    const caption = document.getElementById('postCaption');
    if (caption) {
        const currentCaption = caption.value;
        const newCaption = currentCaption ? `${currentCaption}\n\n#${topic}` : `#${topic}`;
        caption.value = newCaption;
        
        // Open modal if not already open
        const modal = document.getElementById('postModal');
        if (!modal.classList.contains('active')) {
            openCreatePostModal();
            // Wait a bit then set caption
            setTimeout(() => {
                document.getElementById('postCaption').value = newCaption;
            }, 100);
        }
        
        showNotification(`Added trending topic: ${topic}`, 'success');
    }
}

// =====================================================
// PERFORMANCE SUMMARIES
// =====================================================

async function loadPerformanceSummaries() {
    const clientId = document.getElementById('filterClient').value;
    
    if (!clientId) {
        document.getElementById('performanceSummaries').innerHTML = `
            <p style="text-align: center; color: #64748b; grid-column: 1/-1;">Select a client to view performance summaries</p>
        `;
        return;
    }
    
    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`${API_BASE}/performance-summary/${clientId}`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (!response.ok) throw new Error('Failed to load performance summaries');

        const data = await response.json();
        displayPerformanceSummaries(data.summaries);
        
    } catch (error) {
        console.error('Error loading performance summaries:', error);
    }
}

function displayPerformanceSummaries(summaries) {
    const container = document.getElementById('performanceSummaries');
    
    if (!summaries || summaries.length === 0) {
        container.innerHTML = `
            <div class="empty-state" style="grid-column: 1/-1;">
                <i class="ti ti-chart-line"></i>
                <h3>No performance data yet</h3>
                <p>Start posting to see performance summaries</p>
            </div>
        `;
        return;
    }
    
    let html = '';
    
    summaries.forEach(summary => {
        const metrics = summary.metrics;
        const platformClass = summary.platform.toLowerCase();
        const statusClass = `status-${summary.status}`;
        const statusText = summary.status.replace('_', ' ').toUpperCase();
        
        html += `
            <div class="performance-card">
                <div class="performance-header">
                    <div class="platform-badge ${platformClass}">
                        <i class="ti ti-brand-${summary.platform}"></i>
                        ${summary.platform.charAt(0).toUpperCase() + summary.platform.slice(1)}
                    </div>
                    <span class="status-indicator ${statusClass}">${statusText}</span>
                </div>
                
                <div class="metrics-row">
                    <div class="metric-item">
                        <div class="metric-label">Total Posts</div>
                        <div class="metric-value">${metrics.total_posts}</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-label">Engagement Rate</div>
                        <div class="metric-value">${metrics.engagement_rate}%</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-label">Impressions</div>
                        <div class="metric-value">${formatNumber(metrics.impressions)}</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-label">Reach</div>
                        <div class="metric-value">${formatNumber(metrics.reach)}</div>
                    </div>
                </div>
                
                <div class="performance-insight">
                    <i class="ti ti-bulb"></i> ${summary.insight}
                </div>
            </div>
        `;
    });
    
    container.innerHTML = html;
}

function formatNumber(num) {
    if (num >= 1000000) {
        return (num / 1000000).toFixed(1) + 'M';
    } else if (num >= 1000) {
        return (num / 1000).toFixed(1) + 'K';
    }
    return num.toString();
}

// =====================================================
// NOTIFICATIONS
// =====================================================

function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.style.cssText = `
        position: fixed;
        top: 2rem;
        right: 2rem;
        background: ${type === 'success' ? '#10b981' : type === 'error' ? '#ef4444' : '#3b82f6'};
        color: white;
        padding: 1rem 1.5rem;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        z-index: 10000;
        animation: slideIn 0.3s ease;
    `;
    notification.textContent = message;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}