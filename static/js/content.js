/**
 * Content Intelligence Hub - Frontend JavaScript
 * File: static/js/content.js
 */

const API_BASE = `/api/v1/content`;
let selectedPlatform = '';
let selectedContentType = '';
let generatedContent = null;
let currentClientId = null;

// =====================================================
// INITIALIZATION
// =====================================================

document.addEventListener('DOMContentLoaded', function() {
    initializePlatformSelector();
    initializeContentTypeSelector();
    loadClients();
    loadContentLibrary();
});

// =====================================================
// PLATFORM & CONTENT TYPE SELECTION
// =====================================================

function initializePlatformSelector() {
    const platforms = document.querySelectorAll('.platform-option');
    
    platforms.forEach(platform => {
        platform.addEventListener('click', function() {
            // Remove active class from all
            platforms.forEach(p => p.classList.remove('active'));
            
            // Add active class to selected
            this.classList.add('active');
            selectedPlatform = this.dataset.platform;
            
            // Show platform guidelines
            showPlatformGuidelines(selectedPlatform);
        });
    });
}

function initializeContentTypeSelector() {
    const types = document.querySelectorAll('.type-chip');
    
    types.forEach(type => {
        type.addEventListener('click', function() {
            // Remove active class from all
            types.forEach(t => t.classList.remove('active'));
            
            // Add active class to selected
            this.classList.add('active');
            selectedContentType = this.dataset.type;
        });
    });
}

// =====================================================
// LOAD CLIENTS
// =====================================================

async function loadClients() {
    const clientSelect = document.getElementById('clientSelect');
    
    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch('/api/v1/clients/list', {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (!response.ok) {
            throw new Error('Failed to fetch clients');
        }
        
        const data = await response.json();
        
        clientSelect.innerHTML = '<option value="">Select a client...</option>';
        
        if (data.clients && data.clients.length > 0) {
            data.clients.forEach(client => {
                const option = document.createElement('option');
                option.value = client.user_id;
                option.textContent = client.full_name;
                clientSelect.appendChild(option);
            });
        }
        
    } catch (error) {
        console.error('Error loading clients:', error);
        clientSelect.innerHTML = '<option value="">Error loading clients</option>';
    }
}

// =====================================================
// PLATFORM GUIDELINES
// =====================================================

async function showPlatformGuidelines(platform) {
    const guidelinesSection = document.getElementById('guidelinesSection');
    const guidelinesContent = document.getElementById('guidelinesContent');
    
    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`${API_BASE}/platforms/guidelines`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        const result = await response.json();
        
        if (result.success && result.data[platform]) {
            const guidelines = result.data[platform];
            
            guidelinesContent.innerHTML = `
                <div class="guideline-box">
                    <h4><i class="ti ti-ruler"></i> Character Limits</h4>
                    <p style="font-size: 0.875rem; color: #64748b; margin: 0.5rem 0;">
                        <strong>Optimal:</strong> ${guidelines.optimal_chars} characters | 
                        <strong>Maximum:</strong> ${guidelines.max_chars} characters
                    </p>
                </div>
                
                <div class="guideline-box">
                    <h4><i class="ti ti-hash"></i> Hashtag Guidelines</h4>
                    <p style="font-size: 0.875rem; color: #64748b; margin: 0.5rem 0;">
                        <strong>Optimal:</strong> ${guidelines.optimal_hashtags} hashtags | 
                        <strong>Maximum:</strong> ${guidelines.hashtag_limit} hashtags
                    </p>
                </div>
                
                ${guidelines.best_practices && guidelines.best_practices.length > 0 ? `
                    <div class="guideline-box">
                        <h4><i class="ti ti-bulb"></i> Best Practices</h4>
                        <ul class="guideline-list">
                            ${guidelines.best_practices.map(practice => 
                                `<li>${practice}</li>`
                            ).join('')}
                        </ul>
                    </div>
                ` : ''}
            `;
            
            guidelinesSection.style.display = 'block';
        }
        
    } catch (error) {
        console.error('Error loading guidelines:', error);
    }
}

// =====================================================
// GENERATE CONTENT
// =====================================================

async function generateContent() {
    // Validation
    if (!selectedPlatform) {
        showNotification('Please select a platform', 'error');
        return;
    }
    
    if (!selectedContentType) {
        showNotification('Please select a content type', 'error');
        return;
    }
    
    const topic = document.getElementById('topicInput').value.trim();
    if (!topic) {
        showNotification('Please enter a topic or brief', 'error');
        return;
    }
    
    const clientId = document.getElementById('clientSelect').value;
    if (!clientId) {
        showNotification('Please select a client', 'error');
        return;
    }
    
    currentClientId = parseInt(clientId);
    
    const generateBtn = document.getElementById('generateBtn');
    const previewContainer = document.getElementById('previewContainer');
    
    // Show loading state
    generateBtn.disabled = true;
    generateBtn.innerHTML = '<i class="ti ti-loader"></i> Generating...';
    
    previewContainer.innerHTML = `
        <div class="loading-state">
            <div class="loader-spinner"></div>
            <p>AI is generating your content...</p>
        </div>
    `;
    
    try {
        const token = localStorage.getItem('access_token');
        
        // Get optional fields
        const tone = document.getElementById('toneSelect').value;
        const targetAudience = document.getElementById('audienceInput').value.trim();
        const keywordsInput = document.getElementById('keywordsInput').value.trim();
        const keywords = keywordsInput ? keywordsInput.split(',').map(k => k.trim()) : [];
        
        const response = await fetch(`${API_BASE}/generate`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                platform: selectedPlatform,
                content_type: selectedContentType,
                topic: topic,
                tone: tone,
                target_audience: targetAudience || null,
                keywords: keywords,
                client_id: currentClientId
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to generate content');
        }
        
        const result = await response.json();
        
        if (result.success) {
            generatedContent = result.data;
            displayGeneratedContent(result.data);
            showNotification('Content generated successfully!', 'success');
        }
        
    } catch (error) {
        console.error('Error generating content:', error);
        showNotification(error.message || 'Failed to generate content', 'error');
        
        previewContainer.innerHTML = `
            <div class="empty-state">
                <i class="ti ti-alert-circle"></i>
                <h3>Generation Failed</h3>
                <p>${error.message}</p>
            </div>
        `;
    } finally {
        generateBtn.disabled = false;
        generateBtn.innerHTML = '<i class="ti ti-sparkles"></i> Generate Content';
    }
}

// =====================================================
// DISPLAY GENERATED CONTENT
// =====================================================

function displayGeneratedContent(data) {
    const previewContainer = document.getElementById('previewContainer');
    
    const scoreColor = data.optimization_score >= 80 ? '#16a34a' : 
                      data.optimization_score >= 60 ? '#eab308' : '#ef4444';
    
    previewContainer.innerHTML = `
        <!-- Optimization Score -->
        <div class="optimization-score">
            <div class="score-circle" style="background: ${scoreColor};">
                ${Math.round(data.optimization_score)}
            </div>
            <div class="score-details">
                <h4>Optimization Score</h4>
                <p>${data.optimization_score >= 80 ? 'Excellent!' : 
                     data.optimization_score >= 60 ? 'Good, but could be better' : 
                     'Needs improvement'}</p>
            </div>
        </div>

        <!-- Main Content -->
        <div class="content-preview">
            ${data.headline ? `
                <div style="margin-bottom: 1rem;">
                    <label style="font-size: 0.75rem; font-weight: 600; color: #64748b; text-transform: uppercase; margin-bottom: 0.5rem; display: block;">Headline</label>
                    <div style="font-size: 1.1rem; font-weight: 600; color: #1e293b;" id="headlineText">${data.headline}</div>
                </div>
            ` : ''}
            
            <div style="margin-bottom: 1rem;">
                <label style="font-size: 0.75rem; font-weight: 600; color: #64748b; text-transform: uppercase; margin-bottom: 0.5rem; display: block;">Content</label>
                <div style="font-size: 0.95rem; line-height: 1.6; color: #334155; white-space: pre-wrap;" id="contentText">${data.content}</div>
                
                <div class="character-counter">
                    <span>${data.character_count} / ${data.guidelines.max_chars} characters</span>
                    <span style="color: ${data.character_count <= data.guidelines.optimal_chars ? '#16a34a' : '#eab308'};">
                        ${data.character_count <= data.guidelines.optimal_chars ? 'Optimal length ✓' : 'Consider shortening'}
                    </span>
                </div>
                <div class="counter-bar">
                    <div class="counter-fill" style="width: ${(data.character_count / data.guidelines.max_chars) * 100}%;"></div>
                </div>
            </div>

            ${data.cta ? `
                <div style="margin-bottom: 1rem;">
                    <label style="font-size: 0.75rem; font-weight: 600; color: #64748b; text-transform: uppercase; margin-bottom: 0.5rem; display: block;">Call to Action</label>
                    <div style="font-size: 0.95rem; font-weight: 500; color: #9926F3;" id="ctaText">${data.cta}</div>
                </div>
            ` : ''}
        </div>

        <!-- Hashtags -->
        ${data.hashtags && data.hashtags.length > 0 ? `
            <div style="margin-bottom: 1.5rem;">
                <label style="font-size: 0.875rem; font-weight: 600; color: #334155; margin-bottom: 0.75rem; display: block;">
                    <i class="ti ti-hash"></i> Suggested Hashtags (${data.hashtags.length})
                </label>
                <div class="hashtag-container" id="hashtagsContainer">
                    ${data.hashtags.map((tag, index) => 
                        `<span class="hashtag-tag" id="hashtag-${index}">#${tag}</span>`
                    ).join('')}
                </div>
            </div>
        ` : ''}

        <!-- Action Buttons -->
        <div style="display: flex; gap: 0.75rem; margin-top: 1.5rem;">
            <button class="btn-primary" onclick="saveContent()">
                <i class="ti ti-device-floppy"></i>
                Save to Library
            </button>
            <button class="btn-secondary" onclick="copyToClipboard()">
                <i class="ti ti-copy"></i>
                Copy All
            </button>
            <button class="btn-secondary" onclick="regenerateContent()">
                <i class="ti ti-refresh"></i>
                Regenerate
            </button>
        </div>
    `;
}

// =====================================================
// SAVE CONTENT
// =====================================================

async function saveContent() {
    if (!generatedContent || !currentClientId) {
        showNotification('No content to save', 'error');
        return;
    }
    
    try {
        const token = localStorage.getItem('access_token');
        
        const response = await fetch(`${API_BASE}/save`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                client_id: currentClientId,
                platform: selectedPlatform,
                content_type: selectedContentType,
                title: generatedContent.headline || `${selectedPlatform} ${selectedContentType}`,
                content_text: generatedContent.content,
                hashtags: generatedContent.hashtags || [],
                cta_text: generatedContent.cta,
                optimization_score: generatedContent.optimization_score,
                status: 'draft'
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to save content');
        }
        
        const result = await response.json();
        
        if (result.success) {
            showNotification('Content saved to library!', 'success');
            loadContentLibrary();
            
            // Reset form
            document.getElementById('topicInput').value = '';
            document.getElementById('audienceInput').value = '';
            document.getElementById('keywordsInput').value = '';
            
            const previewContainer = document.getElementById('previewContainer');
            previewContainer.innerHTML = `
                <div class="empty-state">
                    <i class="ti ti-check-circle" style="color: #16a34a;"></i>
                    <h3>Content Saved!</h3>
                    <p>Your content has been saved to the library</p>
                </div>
            `;
            
            generatedContent = null;
        }
        
    } catch (error) {
        console.error('Error saving content:', error);
        showNotification(error.message || 'Failed to save content', 'error');
    }
}

// =====================================================
// COPY TO CLIPBOARD
// =====================================================

function copyToClipboard() {
    if (!generatedContent) {
        showNotification('No content to copy', 'error');
        return;
    }
    
    let textToCopy = '';
    
    if (generatedContent.headline) {
        textToCopy += generatedContent.headline + '\n\n';
    }
    
    textToCopy += generatedContent.content + '\n\n';
    
    if (generatedContent.cta) {
        textToCopy += generatedContent.cta + '\n\n';
    }
    
    if (generatedContent.hashtags && generatedContent.hashtags.length > 0) {
        textToCopy += generatedContent.hashtags.map(tag => `#${tag}`).join(' ');
    }
    
    navigator.clipboard.writeText(textToCopy).then(() => {
        showNotification('Content copied to clipboard!', 'success');
    }).catch(err => {
        console.error('Failed to copy:', err);
        showNotification('Failed to copy content', 'error');
    });
}

// =====================================================
// REGENERATE CONTENT
// =====================================================

function regenerateContent() {
    generateContent();
}

// =====================================================
// LOAD CONTENT LIBRARY
// =====================================================

async function loadContentLibrary() {
    const libraryContainer = document.getElementById('contentLibrary');
    
    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`${API_BASE}/list?limit=10`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (!response.ok) {
            throw new Error('Failed to fetch content library');
        }
        
        const result = await response.json();
        
        if (result.success && result.data.length > 0) {
            libraryContainer.innerHTML = result.data.map(content => `
                <div class="content-card">
                    <div class="content-card-header">
                        <div>
                            <h3 style="font-size: 1rem; font-weight: 600; color: #1e293b; margin-bottom: 0.5rem;">
                                ${content.title || 'Untitled Content'}
                            </h3>
                            <div class="content-meta">
                                <span><i class="ti ti-brand-${content.platform}"></i> ${capitalize(content.platform)}</span>
                                <span><i class="ti ti-file"></i> ${capitalize(content.content_type)}</span>
                                <span><i class="ti ti-user"></i> ${content.client_name}</span>
                                <span class="status-badge status-${content.status}">${capitalize(content.status)}</span>
                            </div>
                        </div>
                        <div class="content-actions">
                            <button class="btn-icon" onclick="viewContent(${content.content_id})" title="View">
                                <i class="ti ti-eye"></i>
                            </button>
                            <button class="btn-icon" onclick="editContent(${content.content_id})" title="Edit">
                                <i class="ti ti-edit"></i>
                            </button>
                            <button class="btn-icon" onclick="deleteContent(${content.content_id})" title="Delete">
                                <i class="ti ti-trash"></i>
                            </button>
                        </div>
                    </div>
                    
                    <p style="font-size: 0.9rem; color: #64748b; line-height: 1.6; margin-bottom: 1rem;">
                        ${truncateText(content.content_text, 150)}
                    </p>
                    
                    ${content.hashtags && content.hashtags.length > 0 ? `
                        <div class="hashtag-container">
                            ${content.hashtags.slice(0, 5).map(tag => 
                                `<span class="hashtag-tag">#${tag}</span>`
                            ).join('')}
                            ${content.hashtags.length > 5 ? 
                                `<span class="hashtag-tag">+${content.hashtags.length - 5} more</span>` : ''}
                        </div>
                    ` : ''}
                    
                    ${content.optimization_score ? `
                        <div style="margin-top: 1rem; padding-top: 1rem; border-top: 1px solid #e2e8f0;">
                            <span style="font-size: 0.875rem; color: #64748b;">
                                <i class="ti ti-chart-line"></i> Optimization Score: 
                                <strong style="color: #9926F3;">${Math.round(content.optimization_score)}%</strong>
                            </span>
                        </div>
                    ` : ''}
                </div>
            `).join('');
        } else {
            libraryContainer.innerHTML = `
                <div class="empty-state">
                    <i class="ti ti-folder-off"></i>
                    <h3>No Content Yet</h3>
                    <p>Start generating content to build your library</p>
                </div>
            `;
        }
        
    } catch (error) {
        console.error('Error loading content library:', error);
        libraryContainer.innerHTML = `
            <div class="empty-state">
                <i class="ti ti-alert-circle"></i>
                <h3>Failed to Load Content</h3>
                <p>${error.message}</p>
            </div>
        `;
    }
}

// =====================================================
// CONTENT ACTIONS
// =====================================================

async function viewContent(contentId) {
    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`${API_BASE}/${contentId}`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (!response.ok) {
            throw new Error('Failed to fetch content');
        }
        
        const result = await response.json();
        
        if (result.success) {
            // Display in preview panel
            generatedContent = {
                content: result.data.content_text,
                headline: result.data.title,
                cta: result.data.cta_text,
                hashtags: result.data.hashtags || [],
                optimization_score: result.data.optimization_score || 0,
                character_count: result.data.content_text.length,
                guidelines: {
                    max_chars: 2000,
                    optimal_chars: 200
                }
            };
            
            displayGeneratedContent(generatedContent);
            
            // Scroll to preview
            document.querySelector('.content-grid').scrollIntoView({ behavior: 'smooth' });
        }
        
    } catch (error) {
        console.error('Error viewing content:', error);
        showNotification('Failed to load content', 'error');
    }
}

function editContent(contentId) {
    viewContent(contentId);
    showNotification('Edit the content in the preview and save again', 'info');
}

async function deleteContent(contentId) {
    if (!confirm('Are you sure you want to delete this content?')) {
        return;
    }
    
    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`${API_BASE}/${contentId}`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (!response.ok) {
            throw new Error('Failed to delete content');
        }
        
        showNotification('Content deleted successfully', 'success');
        loadContentLibrary();
        
    } catch (error) {
        console.error('Error deleting content:', error);
        showNotification('Failed to delete content', 'error');
    }
}

// =====================================================
// UTILITY FUNCTIONS
// =====================================================

function capitalize(str) {
    return str.charAt(0).toUpperCase() + str.slice(1);
}

function truncateText(text, maxLength) {
    if (text.length <= maxLength) return text;
    return text.substring(0, maxLength) + '...';
}

function showNotification(message, type = 'info') {
    // Use existing notification system or create a simple one
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 1rem 1.5rem;
        background: ${type === 'success' ? '#dcfce7' : type === 'error' ? '#fee2e2' : '#dbeafe'};
        color: ${type === 'success' ? '#16a34a' : type === 'error' ? '#dc2626' : '#2563eb'};
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        z-index: 9999;
        animation: slideIn 0.3s ease;
    `;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}