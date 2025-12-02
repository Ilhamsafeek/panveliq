/**
 * Social Media Command Center - Module 6
 * File: static/js/social-media.js
 * 
 * FULLY CORRECTED VERSION
 */

const API_BASE = '/api/v1/social-media';
let currentMonth = new Date().getMonth();
let currentYear = new Date().getFullYear();
let selectedContentId = null;
let selectedMediaUrls = [];
let selectedPlatforms = [];
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
    loadStats();
    
    const filterClient = document.getElementById('filterClient');
    if (filterClient) {
        filterClient.addEventListener('change', function() {
            loadStats();
            loadCalendar();
            loadPosts();
        });
    }

    const captionInput = document.getElementById('postCaption');
    const charCount = document.getElementById('captionCharCount');
    
    if (captionInput && charCount) {
        captionInput.addEventListener('input', function() {
            charCount.textContent = this.value.length;
        });
    }
});

// =====================================================
// PLATFORM SELECTOR - MULTI-SELECT SUPPORT
// =====================================================

function initializePlatformSelector() {
    const platforms = document.querySelectorAll('.platform-option');
    platforms.forEach(platform => {
        platform.addEventListener('click', function(e) {
            e.preventDefault();
            const platformName = this.dataset.platform;
            
            if (this.classList.contains('selected')) {
                this.classList.remove('selected');
                selectedPlatforms = selectedPlatforms.filter(p => p !== platformName);
            } else {
                this.classList.add('selected');
                selectedPlatforms.push(platformName);
            }
            
            document.getElementById('postPlatform').value = selectedPlatforms.join(',');
            updatePlatformCount();
        });
    });
}

function updatePlatformCount() {
    const countEl = document.getElementById('selectedPlatformCount');
    if (countEl) {
        if (selectedPlatforms.length > 0) {
            countEl.textContent = `${selectedPlatforms.length} platform${selectedPlatforms.length > 1 ? 's' : ''} selected`;
            countEl.style.display = 'block';
        } else {
            countEl.style.display = 'none';
        }
    }
}

// =====================================================
// LOAD CLIENTS
// =====================================================

async function loadClients() {
    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch('/api/v1/clients/list', {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (!response.ok) throw new Error('Failed to load clients');

        const data = await response.json();
        const clients = data.clients || [];
        
        const filterSelect = document.getElementById('filterClient');
        const formSelect = document.getElementById('postClient');
        
        if (filterSelect) filterSelect.innerHTML = '<option value="">All Clients</option>';
        if (formSelect) formSelect.innerHTML = '<option value="">Select client...</option>';
        
        clients.forEach(client => {
            const clientId = client.user_id || client.client_id;
            const clientName = client.full_name || client.name || `Client ${clientId}`;
            
            if (filterSelect) filterSelect.add(new Option(clientName, clientId));
            if (formSelect) formSelect.add(new Option(clientName, clientId));
        });
    } catch (error) {
        console.error('Error loading clients:', error);
        showNotification('Failed to load clients', 'error');
    }
}

// =====================================================
// LOAD STATS
// =====================================================

async function loadStats() {
    try {
        const token = localStorage.getItem('access_token');
        if (!token) return;
        
        const clientId = document.getElementById('filterClient')?.value || '';
        
        let url = `${API_BASE}/stats`;
        if (clientId) url += `?client_id=${clientId}`;
        
        let response = await fetch(url, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (response.ok) {
            const data = await response.json();
            const stats = data.stats || {};
            updateStatsDisplay(stats.total || 0, stats.scheduled || 0, stats.published || 0, stats.draft || 0);
            return;
        }
        
        url = `${API_BASE}/posts`;
        if (clientId) url += `?client_id=${clientId}`;
        
        response = await fetch(url, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (!response.ok) {
            updateStatsDisplay(0, 0, 0, 0);
            return;
        }
        
        const data = await response.json();
        const posts = data.posts || [];
        
        const total = posts.length;
        const scheduled = posts.filter(p => p.status === 'scheduled').length;
        const published = posts.filter(p => p.status === 'published').length;
        const draft = posts.filter(p => p.status === 'draft').length;
        
        updateStatsDisplay(total, scheduled, published, draft);
        
    } catch (error) {
        console.error('Error in loadStats:', error);
        updateStatsDisplay(0, 0, 0, 0);
    }
}

function updateStatsDisplay(total, scheduled, published, draft) {
    const totalEl = document.getElementById('totalPosts');
    const scheduledEl = document.getElementById('scheduledPosts');
    const publishedEl = document.getElementById('publishedPosts');
    const draftEl = document.getElementById('draftPosts');
    
    if (totalEl) totalEl.textContent = total;
    if (scheduledEl) scheduledEl.textContent = scheduled;
    if (publishedEl) publishedEl.textContent = published;
    if (draftEl) draftEl.textContent = draft;
}

function updateStats(posts) {
    if (!posts || !Array.isArray(posts)) posts = [];
    
    const total = posts.length;
    const scheduled = posts.filter(p => p.status === 'scheduled').length;
    const published = posts.filter(p => p.status === 'published').length;
    const draft = posts.filter(p => p.status === 'draft').length;
    
    updateStatsDisplay(total, scheduled, published, draft);
}

// =====================================================
// LOAD POSTS (LIST VIEW)
// =====================================================

async function loadPosts() {
    const postsList = document.getElementById('postsList');
    
    try {
        if (postsList) {
            postsList.innerHTML = `
                <div class="loading-state">
                    <div class="loader-spinner"></div>
                    <p>Loading posts...</p>
                </div>
            `;
        }
        
        const token = localStorage.getItem('access_token');
        const clientId = document.getElementById('filterClient')?.value || '';
        const platform = document.getElementById('filterPlatform')?.value || '';
        const status = document.getElementById('filterStatus')?.value || '';
        
        let url = `${API_BASE}/posts?`;
        if (clientId) url += `client_id=${clientId}&`;
        if (platform) url += `platform=${platform}&`;
        if (status) url += `status=${status}&`;
        
        const response = await fetch(url, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (!response.ok) throw new Error('Failed to load posts');

        const data = await response.json();
        const posts = data.posts || [];
        
        updateStats(posts);
        
        if (!posts || posts.length === 0) {
            if (postsList) {
                postsList.innerHTML = `
                    <div class="empty-state" style="padding: 3rem; text-align: center;">
                        <i class="ti ti-calendar-off" style="font-size: 3rem; color: #94a3b8;"></i>
                        <h3 style="margin-top: 1rem; color: #475569;">No Posts Found</h3>
                        <p style="color: #94a3b8;">Create your first social media post to get started</p>
                        <button class="btn btn-primary" onclick="openPostModal()" style="margin-top: 1rem;">
                            <i class="ti ti-plus"></i> Create Post
                        </button>
                    </div>
                `;
            }
            return;
        }
        
        let html = '';
        posts.forEach(post => {
            const platformClass = `platform-${post.platform}`;
            const statusClass = `status-${post.status}`;
            const scheduledDate = post.scheduled_at ? new Date(post.scheduled_at).toLocaleString() : 'Not scheduled';
            const hashtags = post.hashtags || [];
            const mediaCount = post.media_count || 0;
            
            html += `
                <div class="post-item">
                    <div class="post-platform-icon ${platformClass}">
                        <i class="ti ti-brand-${post.platform}"></i>
                    </div>
                    <div class="post-content">
                        <div class="post-header">
                            <div class="post-client">${post.client_name || 'Unknown Client'}</div>
                            <span class="post-status ${statusClass}">${post.status}</span>
                        </div>
                        <div class="post-caption">${(post.caption || '').substring(0, 200)}${(post.caption || '').length > 200 ? '...' : ''}</div>
                        <div class="post-meta">
                            <span><i class="ti ti-calendar"></i> ${scheduledDate}</span>
                            <span><i class="ti ti-photo"></i> ${mediaCount} media</span>
                            <span><i class="ti ti-hash"></i> ${hashtags.length} hashtags</span>
                        </div>
                    </div>
                    <div class="post-actions">
                        <button onclick="editPost(${post.post_id})" title="Edit">
                            <i class="ti ti-pencil"></i>
                        </button>
                        <button onclick="deletePost(${post.post_id})" title="Delete">
                            <i class="ti ti-trash"></i>
                        </button>
                    </div>
                </div>
            `;
        });
        
        if (postsList) postsList.innerHTML = html;
        
    } catch (error) {
        console.error('Error loading posts:', error);
        if (postsList) {
            postsList.innerHTML = `
                <div class="empty-state" style="padding: 3rem; text-align: center;">
                    <i class="ti ti-alert-circle" style="font-size: 3rem; color: #ef4444;"></i>
                    <h3 style="margin-top: 1rem; color: #475569;">Failed to Load Posts</h3>
                    <p style="color: #94a3b8;">${error.message}</p>
                </div>
            `;
        }
        updateStats([]);
    }
}

function truncateText(text, maxLength) {
    if (!text) return '';
    return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
}

// =====================================================
// CALENDAR VIEW
// =====================================================

function loadCalendar() {
    const monthNames = ['January', 'February', 'March', 'April', 'May', 'June',
        'July', 'August', 'September', 'October', 'November', 'December'];
    
    const calendarMonth = document.getElementById('calendarMonth');
    if (calendarMonth) {
        calendarMonth.textContent = `${monthNames[currentMonth]} ${currentYear}`;
    }
    
    fetchCalendarData();
}

async function fetchCalendarData() {
    const grid = document.getElementById('calendarGrid');
    const clientId = document.getElementById('filterClient')?.value || '';
    
    try {
        const token = localStorage.getItem('access_token');
        
        let url = `${API_BASE}/calendar?month=${currentMonth + 1}&year=${currentYear}`;
        if (clientId) {
            url += `&client_id=${clientId}`;
        }
        
        const response = await fetch(url, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (!response.ok) {
            renderCalendar({});
            return;
        }
        
        const data = await response.json();
        renderCalendar(data.calendar || {});
        
    } catch (error) {
        console.error('Error loading calendar:', error);
        renderCalendar({});
    }
}

function renderCalendar(calendarData) {
    const grid = document.getElementById('calendarGrid');
    if (!grid) return;
    
    const firstDay = new Date(currentYear, currentMonth, 1).getDay();
    const daysInMonth = new Date(currentYear, currentMonth + 1, 0).getDate();
    const today = new Date();
    
    let html = `
        <div class="calendar-grid">
            <div class="calendar-header-row">
                <div class="calendar-day-header">Sun</div>
                <div class="calendar-day-header">Mon</div>
                <div class="calendar-day-header">Tue</div>
                <div class="calendar-day-header">Wed</div>
                <div class="calendar-day-header">Thu</div>
                <div class="calendar-day-header">Fri</div>
                <div class="calendar-day-header">Sat</div>
            </div>
            <div class="calendar-days">
    `;
    
    for (let i = 0; i < firstDay; i++) {
        html += '<div class="calendar-day empty"></div>';
    }
    
    for (let day = 1; day <= daysInMonth; day++) {
        const dateStr = `${currentYear}-${String(currentMonth + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
        const isToday = today.getDate() === day && 
                        today.getMonth() === currentMonth && 
                        today.getFullYear() === currentYear;
        
        const dayPosts = calendarData[dateStr] || [];
        
        html += `
            <div class="calendar-day ${isToday ? 'today' : ''}" onclick="showDayPosts('${dateStr}')">
                <div class="day-number">${day}</div>
                <div class="day-posts">
                    ${dayPosts.slice(0, 3).map(post => `
                        <div class="calendar-post ${post.platform}" title="${post.caption || ''}">
                            <i class="ti ti-brand-${post.platform}"></i>
                            <span>${truncateText(post.caption, 20)}</span>
                        </div>
                    `).join('')}
                    ${dayPosts.length > 3 ? `<div class="more-posts">+${dayPosts.length - 3} more</div>` : ''}
                </div>
            </div>
        `;
    }
    
    html += '</div></div>';
    grid.innerHTML = html;
}

function changeMonth(delta) {
    if (delta === 0) {
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

function showDayPosts(dateStr) {
    showNotification(`Showing posts for ${dateStr}`, 'info');
}

// =====================================================
// VIEW SWITCHING
// =====================================================

function switchView(view) {
    document.querySelectorAll('.view-tab').forEach(tab => tab.classList.remove('active'));
    document.querySelectorAll('.calendar-view, .list-view').forEach(v => v.classList.remove('active'));
    
    if (view === 'calendar') {
        document.querySelector('.view-tab:first-child')?.classList.add('active');
        document.getElementById('calendarView')?.classList.add('active');
    } else {
        document.querySelector('.view-tab:last-child')?.classList.add('active');
        document.getElementById('listView')?.classList.add('active');
    }
}

// =====================================================
// CREATE/EDIT POST MODAL
// =====================================================

function openPostModal() {
    currentEditingPostId = null;
    selectedContentId = null;
    selectedMediaUrls = [];
    selectedPlatforms = [];
    
    document.getElementById('modalTitle').textContent = 'Create New Post';
    document.getElementById('postForm').reset();
    document.getElementById('postModal').classList.add('active');
    document.getElementById('submitPostBtn').innerHTML = '<i class="ti ti-check"></i> Create Post';
    
    document.querySelectorAll('.platform-option').forEach(p => p.classList.remove('selected'));
    document.getElementById('postPlatform').value = '';
    
    document.getElementById('contentLibraryPicker').style.display = 'none';
    document.getElementById('mediaLibraryPicker').style.display = 'none';
    document.getElementById('bestTimesPanel').style.display = 'none';
    
    const mediaPreview = document.getElementById('selectedMediaPreview');
    if (mediaPreview) mediaPreview.innerHTML = '';
    
    updatePlatformCount();
}

function openCreatePostModal() {
    openPostModal();
}

async function editPost(postId) {
    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`${API_BASE}/posts/${postId}`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (!response.ok) throw new Error('Failed to load post');

        const data = await response.json();
        const post = data.post;
        
        currentEditingPostId = postId;
        document.getElementById('modalTitle').textContent = 'Edit Post';
        document.getElementById('submitPostBtn').innerHTML = '<i class="ti ti-check"></i> Update Post';
        
        document.getElementById('postClient').value = post.client_id;
        document.getElementById('postCaption').value = post.caption || '';
        document.getElementById('postHashtags').value = (post.hashtags || []).join(', ');
        document.getElementById('postStatus').value = post.status || 'draft';
        
        if (post.scheduled_at) {
            const date = new Date(post.scheduled_at);
            const localDateTime = new Date(date.getTime() - (date.getTimezoneOffset() * 60000))
                .toISOString().slice(0, 16);
            document.getElementById('postScheduledAt').value = localDateTime;
        }
        
        selectedPlatforms = post.platform ? post.platform.split(',') : [];
        document.querySelectorAll('.platform-option').forEach(p => {
            if (selectedPlatforms.includes(p.dataset.platform)) {
                p.classList.add('selected');
            } else {
                p.classList.remove('selected');
            }
        });
        document.getElementById('postPlatform').value = selectedPlatforms.join(',');
        
        selectedMediaUrls = post.media_urls || [];
        selectedContentId = post.content_id;
        
        updatePlatformCount();
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
        const platforms = document.getElementById('postPlatform').value;
        const caption = document.getElementById('postCaption').value;
        const hashtagsInput = document.getElementById('postHashtags').value;
        const hashtags = hashtagsInput.split(',').map(h => h.trim()).filter(h => h);
        const status = document.getElementById('postStatus').value;
        const scheduledAt = document.getElementById('postScheduledAt').value;
        
        if (!clientId) {
            showNotification('Please select a client', 'error');
            throw new Error('Client required');
        }
        
        if (!platforms) {
            showNotification('Please select at least one platform', 'error');
            throw new Error('Platform required');
        }
        
        if (!caption.trim()) {
            showNotification('Please enter a caption', 'error');
            throw new Error('Caption required');
        }
        
        const platformList = platforms.split(',').filter(p => p.trim());
        let successCount = 0;
        
        for (const platform of platformList) {
            const postData = {
                client_id: parseInt(clientId),
                content_id: selectedContentId,
                platform: platform.trim(),
                caption: caption,
                media_urls: selectedMediaUrls,
                hashtags: hashtags,
                scheduled_at: scheduledAt || null,
                status: status
            };
            
            let url = `${API_BASE}/posts`;
            let method = 'POST';
            
            if (currentEditingPostId && platformList.length === 1) {
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
            
            if (response.ok) {
                successCount++;
            }
        }
        
        if (successCount > 0) {
            showNotification(`Successfully saved ${successCount} post(s)`, 'success');
            closePostModal();
            loadPosts();
            loadCalendar();
            loadStats();
        } else {
            throw new Error('Failed to save any posts');
        }
        
    } catch (error) {
        console.error('Error saving post:', error);
        if (!['Client required', 'Platform required', 'Caption required'].includes(error.message)) {
            showNotification(error.message || 'Failed to save post', 'error');
        }
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
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (!response.ok) throw new Error('Failed to delete post');
        
        showNotification('Post deleted successfully', 'success');
        loadPosts();
        loadCalendar();
        loadStats();
        
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
    const picker = document.getElementById('contentLibraryPicker');
    
    if (!clientId) {
        showNotification('Please select a client first', 'error');
        return;
    }
    
    picker.innerHTML = '<div class="loading-state"><div class="loader-spinner"></div><p>Loading content...</p></div>';
    picker.style.display = 'block';
    
    try {
        const token = localStorage.getItem('access_token');
        
        let response = await fetch(`/api/v1/content/list?client_id=${clientId}`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (!response.ok) {
            response = await fetch(`/api/v1/content?client_id=${clientId}`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
        }

        if (!response.ok) throw new Error('Failed to load content library');

        const data = await response.json();
        displayContentLibrary(data.content || data.data || []);
        
    } catch (error) {
        console.error('Error loading content library:', error);
        picker.innerHTML = `<div style="text-align: center; padding: 2rem; color: #64748b;">Failed to load content library</div>`;
    }
}

function displayContentLibrary(content) {
    const picker = document.getElementById('contentLibraryPicker');
    
    if (!content || content.length === 0) {
        picker.innerHTML = `<div style="text-align: center; padding: 2rem; color: #64748b;">No saved content found</div>`;
        return;
    }
    
    picker.innerHTML = content.map(item => `
        <div class="content-card" onclick="selectContent(${item.content_id || item.id}, this)">
            <div class="content-card-platform">${item.platform || 'General'}</div>
            <div class="content-card-text">${truncateText(item.content_text || item.text || '', 100)}</div>
        </div>
    `).join('');
}

function selectContent(contentId, element) {
    selectedContentId = contentId;
    
    document.querySelectorAll('.content-card').forEach(card => card.classList.remove('selected'));
    element.classList.add('selected');
    
    const contentText = element.querySelector('.content-card-text')?.textContent || '';
    document.getElementById('postCaption').value = contentText;
    
    showNotification('Content loaded successfully', 'success');
}

// =====================================================
// MEDIA LIBRARY INTEGRATION (MODULE 8)
// =====================================================

async function loadMediaLibrary() {
    const clientId = document.getElementById('postClient').value;
    const picker = document.getElementById('mediaLibraryPicker');
    
    if (!clientId) {
        showNotification('Please select a client first', 'error');
        return;
    }
    
    picker.innerHTML = '<div class="loading-state"><div class="loader-spinner"></div><p>Loading media...</p></div>';
    picker.style.display = 'grid';
    
    try {
        const token = localStorage.getItem('access_token');
        
        let response = await fetch(`/api/v1/media-studio/assets?client_id=${clientId}`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (!response.ok) {
            response = await fetch(`/api/v1/media/assets?client_id=${clientId}`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
        }

        if (!response.ok) throw new Error('Failed to load media library');

        const data = await response.json();
        displayMediaLibrary(data.assets || data.data || []);
        
    } catch (error) {
        console.error('Error loading media library:', error);
        picker.innerHTML = `<div style="text-align: center; padding: 2rem; color: #64748b; grid-column: 1/-1;">Failed to load media library</div>`;
    }
}

function displayMediaLibrary(assets) {
    const picker = document.getElementById('mediaLibraryPicker');
    
    if (!assets || assets.length === 0) {
        picker.innerHTML = `<div style="text-align: center; padding: 2rem; color: #64748b; grid-column: 1/-1;">No media assets found</div>`;
        return;
    }
    
    picker.innerHTML = assets.map(asset => {
        const fileUrl = asset.file_url || asset.url;
        const isSelected = selectedMediaUrls.includes(fileUrl);
        return `
            <div class="media-card ${isSelected ? 'selected' : ''}" onclick="toggleMedia('${fileUrl}')">
                <img src="${fileUrl}" alt="${asset.asset_name || 'Asset'}" onerror="this.src='/static/images/placeholder.png'">
                <div class="media-card-type">${asset.asset_type || 'image'}</div>
                <div class="checkmark"><i class="ti ti-check"></i></div>
            </div>
        `;
    }).join('');
}

function toggleMedia(url) {
    const index = selectedMediaUrls.indexOf(url);
    
    if (index > -1) {
        selectedMediaUrls.splice(index, 1);
    } else {
        selectedMediaUrls.push(url);
    }
    
    event.target.closest('.media-card')?.classList.toggle('selected');
    showNotification(`${selectedMediaUrls.length} media selected`, 'info');
    updateSelectedMediaPreview();
}

function updateSelectedMediaPreview() {
    const preview = document.getElementById('selectedMediaPreview');
    if (!preview) return;
    
    if (selectedMediaUrls.length === 0) {
        preview.innerHTML = '';
        return;
    }
    
    preview.innerHTML = `
        <div style="display: flex; gap: 0.5rem; flex-wrap: wrap; margin-top: 1rem;">
            ${selectedMediaUrls.map(url => `
                <div style="position: relative; width: 60px; height: 60px; border-radius: 8px; overflow: hidden;">
                    <img src="${url}" style="width: 100%; height: 100%; object-fit: cover;">
                    <button onclick="removeMedia('${url}')" style="position: absolute; top: 2px; right: 2px; width: 20px; height: 20px; border-radius: 50%; background: #ef4444; border: none; color: white; cursor: pointer;">×</button>
                </div>
            `).join('')}
        </div>
    `;
}

function removeMedia(url) {
    const index = selectedMediaUrls.indexOf(url);
    if (index > -1) selectedMediaUrls.splice(index, 1);
    updateSelectedMediaPreview();
}

// =====================================================
// AI BEST TIMES - COMPLETELY FIXED
// =====================================================

async function getBestTimes() {
    const clientId = document.getElementById('postClient').value;
    const platforms = document.getElementById('postPlatform').value;
    const panel = document.getElementById('bestTimesPanel');
    
    if (!clientId) {
        showNotification('Please select a client first', 'error');
        return;
    }
    
    if (!platforms) {
        showNotification('Please select at least one platform first', 'error');
        return;
    }
    
    panel.innerHTML = '<div class="loading-state"><div class="loader-spinner"></div><p>Analyzing best times...</p></div>';
    panel.style.display = 'block';
    
    try {
        const token = localStorage.getItem('access_token');
        const platformList = platforms.split(',');
        const firstPlatform = platformList[0].trim();
        
        const response = await fetch(`${API_BASE}/best-times`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                client_id: parseInt(clientId),
                platform: firstPlatform
            })
        });

        if (!response.ok) throw new Error('Failed to get best times');

        const data = await response.json();
        console.log('Best times API response:', data);
        
        const times = data.recommended_times || [];
        displayBestTimes(times);
        
    } catch (error) {
        console.error('Error getting best times:', error);
        panel.innerHTML = `<div style="text-align: center; padding: 2rem; color: #64748b;">Failed to analyze best times</div>`;
    }
}

function displayBestTimes(times) {
    const panel = document.getElementById('bestTimesPanel');
    
    if (!times || times.length === 0) {
        panel.innerHTML = `<div style="text-align: center; padding: 2rem; color: #64748b;">No best time recommendations available</div>`;
        return;
    }
    
    let html = '<div class="best-times-grid">';
    
    times.forEach(time => {
        // Parse values safely
        const day = time.day || 'Unknown';
        const hour = parseInt(time.hour) || 12;
        let score = parseFloat(time.engagement_score) || 0;
        
        // FIX: Normalize score - keep dividing by 100 until it's in 0-100 range
        while (score > 100) {
            score = score / 100;
        }
        
        // Format time for display (convert 24h to 12h format)
        const hour12 = hour % 12 || 12;
        const ampm = hour >= 12 ? 'PM' : 'AM';
        const timeDisplay = `${hour12}:00 ${ampm}`;
        
        html += `
            <div class="best-time-item" onclick="useBestTime('${day}', ${hour})" style="cursor: pointer;">
                <div class="best-time-info">
                    <div class="best-time-icon">
                        <i class="ti ti-clock"></i>
                    </div>
                    <div class="best-time-details">
                        <h4>${day}</h4>
                        <p>${timeDisplay}</p>
                    </div>
                </div>
                <div class="best-time-score">
                    <span class="score-badge">${score.toFixed(1)}%</span>
                </div>
            </div>
        `;
    });
    
    html += '</div>';
    panel.innerHTML = html;
    panel.style.display = 'block';
}

function useBestTime(day, hour) {
    console.log('useBestTime called with:', day, hour);
    
    // Get form elements
    const dateInput = document.getElementById('postScheduledAt');
    const statusSelect = document.getElementById('postStatus');
    
    if (!dateInput) {
        console.error('Date input not found');
        showNotification('Error: Date input not found', 'error');
        return;
    }
    
    if (!statusSelect) {
        console.error('Status select not found');
        showNotification('Error: Status select not found', 'error');
        return;
    }
    
    // FIXED: Day mapping aligned with JavaScript's getDay() where Sunday = 0
    // Backend uses Monday = 0, but we receive day NAME so we map to JS days
    const dayToJsIndex = {
        'Sunday': 0,
        'Monday': 1,
        'Tuesday': 2,
        'Wednesday': 3,
        'Thursday': 4,
        'Friday': 5,
        'Saturday': 6
    };
    
    const targetDayIndex = dayToJsIndex[day];
    
    if (targetDayIndex === undefined) {
        console.error('Invalid day:', day);
        showNotification('Invalid day selected', 'error');
        return;
    }
    
    // Ensure hour is a number
    const targetHour = parseInt(hour);
    if (isNaN(targetHour) || targetHour < 0 || targetHour > 23) {
        console.error('Invalid hour:', hour);
        showNotification('Invalid hour selected', 'error');
        return;
    }
    
    // Calculate next occurrence of this day
    const now = new Date();
    const currentDayIndex = now.getDay(); // JavaScript: Sunday = 0
    
    let daysUntil = targetDayIndex - currentDayIndex;
    if (daysUntil <= 0) {
        daysUntil += 7; // Next week
    }
    
    // Create target date
    const targetDate = new Date();
    targetDate.setDate(targetDate.getDate() + daysUntil);
    targetDate.setHours(targetHour, 0, 0, 0);
    
    // Format for datetime-local input: YYYY-MM-DDTHH:MM
    const year = targetDate.getFullYear();
    const month = String(targetDate.getMonth() + 1).padStart(2, '0');
    const dateNum = String(targetDate.getDate()).padStart(2, '0');
    const hourStr = String(targetHour).padStart(2, '0');
    
    const formattedDateTime = `${year}-${month}-${dateNum}T${hourStr}:00`;
    
    console.log('Setting datetime to:', formattedDateTime);
    console.log('Target date object:', targetDate);
    
    // SET THE VALUES DIRECTLY
    dateInput.value = formattedDateTime;
    statusSelect.value = 'scheduled';
    
    // Verify the values were set
    console.log('Date input value after set:', dateInput.value);
    console.log('Status select value after set:', statusSelect.value);
    
    // Visual feedback
    const hour12 = targetHour % 12 || 12;
    const ampm = targetHour >= 12 ? 'PM' : 'AM';
    
    showNotification(`Scheduled for ${day} at ${hour12}:00 ${ampm}`, 'success');
}

// =====================================================
// TRENDING TOPICS
// =====================================================

async function loadTrendingTopics() {
    const container = document.getElementById('trendingTopics');
    if (!container) return;
    
    try {
        const token = localStorage.getItem('access_token');
        const platform = document.getElementById('trendingPlatformFilter')?.value || '';
        
        let url = `${API_BASE}/trending`;
        if (platform) url += `?platform=${platform}`;
        
        const response = await fetch(url, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (!response.ok) throw new Error('Failed to load trends');

        const data = await response.json();
        displayTrendingTopics(data.topics || data.trending || data.trends || []);
        
    } catch (error) {
        console.error('Error loading trending topics:', error);
        container.innerHTML = '<p style="color: #94a3b8; text-align: center;">Unable to load trending topics</p>';
    }
}

function displayTrendingTopics(topics) {
    const container = document.getElementById('trendingTopics');
    
    if (!topics || topics.length === 0) {
        container.innerHTML = '<p style="color: #94a3b8; text-align: center;">No trending topics available</p>';
        return;
    }
    
    container.innerHTML = `
        <div class="trending-grid">
            ${topics.slice(0, 6).map(topic => `
                <div class="trending-card" onclick="useTrend('${(topic.topic || topic.name || '').replace(/'/g, "\\'")}')">
                    <div class="trending-header">
                        <span class="trending-platform">${topic.platform || 'All'}</span>
                        <span class="trending-volume">
                            <i class="ti ti-trending-up"></i> ${formatNumber(topic.volume || 0)}
                        </span>
                    </div>
                    <div class="trending-topic">${topic.topic || topic.name}</div>
                    <span class="trending-category">${topic.category || 'Trending'}</span>
                </div>
            `).join('')}
        </div>
    `;
}

function useTrend(topic) {
    const caption = document.getElementById('postCaption');
    if (caption) {
        caption.value += (caption.value ? ' ' : '') + topic;
        showNotification('Trend added to caption', 'success');
    }
}

function formatNumber(num) {
    if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
    if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
    return num.toString();
}

// =====================================================
// PERFORMANCE SUMMARIES
// =====================================================

async function loadPerformanceSummaries() {
    const container = document.getElementById('performanceSummaries');
    if (!container) return;
    
    try {
        const token = localStorage.getItem('access_token');
        const clientId = document.getElementById('filterClient')?.value || '';
        
        let url = `${API_BASE}/analytics/summary`;
        if (clientId) url += `?client_id=${clientId}`;
        
        const response = await fetch(url, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (!response.ok) throw new Error('Failed to load performance data');

        const data = await response.json();
        displayPerformanceSummaries(data.summaries || data.analytics || []);
        
    } catch (error) {
        console.error('Error loading performance summaries:', error);
        container.innerHTML = '<p style="color: #94a3b8; text-align: center;">Unable to load performance data</p>';
    }
}

function displayPerformanceSummaries(summaries) {
    const container = document.getElementById('performanceSummaries');
    if (!container) return;
    
    if (!summaries || summaries.length === 0) {
        container.innerHTML = '<p style="color: #94a3b8; text-align: center;">No performance data available</p>';
        return;
    }
    
    container.innerHTML = summaries.map(summary => {
        const platform = summary.platform || 'Unknown';
        return `
            <div class="performance-card">
                <div class="performance-header">
                    <div class="platform-badge platform-${platform.toLowerCase()}">
                        <i class="ti ti-brand-${platform.toLowerCase()}"></i>
                        ${platform}
                    </div>
                </div>
                <div class="metrics-row">
                    <div class="metric-item">
                        <span class="metric-label">Posts</span>
                        <span class="metric-value">${summary.total_posts || 0}</span>
                    </div>
                    <div class="metric-item">
                        <span class="metric-label">Engagement</span>
                        <span class="metric-value">${formatNumber(summary.engagement || 0)}</span>
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

// =====================================================
// NOTIFICATIONS
// =====================================================

function showNotification(message, type = 'info') {
    const existing = document.querySelector('.notification');
    if (existing) existing.remove();
    
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <i class="ti ti-${type === 'success' ? 'check' : type === 'error' ? 'x' : 'info-circle'}"></i>
        <span>${message}</span>
    `;
    
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 1rem 1.5rem;
        border-radius: 10px;
        background: ${type === 'success' ? '#10b981' : type === 'error' ? '#ef4444' : '#3b82f6'};
        color: white;
        display: flex;
        align-items: center;
        gap: 0.75rem;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        z-index: 10000;
        animation: slideIn 0.3s ease;
    `;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

// Animation styles
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    @keyframes slideOut {
        from { transform: translateX(0); opacity: 1; }
        to { transform: translateX(100%); opacity: 0; }
    }
`;
document.head.appendChild(style);

// =====================================================
// MEDIA UPLOAD HANDLER
// =====================================================

async function handleMediaUpload(event) {
    const files = event.target.files;
    if (!files || files.length === 0) return;
    
    const clientId = document.getElementById('postClient').value;
    if (!clientId) {
        showNotification('Please select a client first', 'error');
        event.target.value = '';
        return;
    }
    
    showNotification('Uploading media...', 'info');
    
    for (const file of files) {
        try {
            const formData = new FormData();
            formData.append('file', file);
            formData.append('client_id', clientId);
            formData.append('asset_type', file.type.startsWith('video/') ? 'video' : 'image');
            formData.append('asset_name', file.name);
            
            const token = localStorage.getItem('access_token');
            const response = await fetch('/api/v1/media-studio/upload', {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` },
                body: formData
            });
            
            if (response.ok) {
                const result = await response.json();
                if (result.file_url) {
                    selectedMediaUrls.push(result.file_url);
                }
            }
        } catch (error) {
            console.error('Error uploading file:', error);
        }
    }
    
    updateSelectedMediaPreview();
    showNotification(`${files.length} file(s) uploaded`, 'success');
    event.target.value = '';
}

// =====================================================
// EXPOSE FUNCTIONS GLOBALLY
// =====================================================

window.openPostModal = openPostModal;
window.openCreatePostModal = openCreatePostModal;
window.closePostModal = closePostModal;
window.editPost = editPost;
window.deletePost = deletePost;
window.savePost = savePost;
window.loadPosts = loadPosts;
window.loadCalendar = loadCalendar;
window.loadContentLibrary = loadContentLibrary;
window.loadMediaLibrary = loadMediaLibrary;
window.selectContent = selectContent;
window.toggleMedia = toggleMedia;
window.removeMedia = removeMedia;
window.getBestTimes = getBestTimes;
window.useBestTime = useBestTime;
window.useTrend = useTrend;
window.switchView = switchView;
window.changeMonth = changeMonth;
window.showDayPosts = showDayPosts;
window.handleMediaUpload = handleMediaUpload;
window.loadTrendingTopics = loadTrendingTopics;