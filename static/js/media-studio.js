/**
 * Creative Media Studio - Frontend JavaScript
 * File: static/js/media-studio.js
 */

const API_BASE = '/api/v1/media-studio';
let selectedImageSize = '1024x1024';

// =====================================================
// INITIALIZATION
// =====================================================

document.addEventListener('DOMContentLoaded', function() {
    initializeSizeSelector();
    loadClients();
    loadMediaAssets();
});

// =====================================================
// SIZE SELECTOR
// =====================================================

function initializeSizeSelector() {
    const sizeChips = document.querySelectorAll('.size-chip');
    
    sizeChips.forEach(chip => {
        chip.addEventListener('click', function() {
            sizeChips.forEach(c => c.classList.remove('active'));
            this.classList.add('active');
            selectedImageSize = this.dataset.size;
        });
    });
}

// =====================================================
// LOAD CLIENTS
// =====================================================

async function loadClients() {
    const clientSelects = ['imageClient', 'videoClient', 'designClient', 'filterClient'];
    
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
        
        clientSelects.forEach(selectId => {
            const select = document.getElementById(selectId);
            if (select) {
                const firstOption = select.querySelector('option:first-child');
                select.innerHTML = '';
                select.appendChild(firstOption.cloneNode(true));
                
                if (data.clients && data.clients.length > 0) {
                    data.clients.forEach(client => {
                        const option = document.createElement('option');
                        option.value = client.user_id;
                        option.textContent = client.full_name;
                        select.appendChild(option);
                    });
                }
            }
        });
        
    } catch (error) {
        console.error('Error loading clients:', error);
    }
}

// =====================================================
// MODAL FUNCTIONS
// =====================================================

function openImageGenerator() {
    document.getElementById('imageModal').classList.add('show');
    document.getElementById('imageForm').reset();
    selectedImageSize = '1024x1024';
}

function openVideoGenerator() {
    document.getElementById('videoModal').classList.add('show');
    document.getElementById('videoForm').reset();
}

function openDesignStudio() {
    document.getElementById('designModal').classList.add('show');
    document.getElementById('designForm').reset();
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
// GENERATE IMAGE (DALL-E)
// =====================================================

async function generateImage(event) {
    event.preventDefault();
    
    const generateBtn = document.getElementById('generateImageBtn');
    const originalBtnText = generateBtn.innerHTML;
    
    try {
        generateBtn.disabled = true;
        generateBtn.innerHTML = '<i class="ti ti-loader"></i> Generating...';
        
        const token = localStorage.getItem('access_token');
        const clientId = document.getElementById('imageClient').value;
        const prompt = document.getElementById('imagePrompt').value;
        const quality = document.getElementById('imageQuality').value;
        const style = document.getElementById('imageStyle').value;
        
        const response = await fetch(`${API_BASE}/generate/image`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                client_id: parseInt(clientId),
                prompt: prompt,
                size: selectedImageSize,
                quality: quality,
                style: style,
                n: 1
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to generate image');
        }
        
        const result = await response.json();
        
        if (result.success) {
            showNotification('Image generated successfully!', 'success');
            closeModal('imageModal');
            loadMediaAssets();
            
            // Show the generated image
            if (result.assets && result.assets.length > 0) {
                const imageUrl = result.assets[0].url;
                showImagePreview(imageUrl);
            }
        }
        
    } catch (error) {
        console.error('Error generating image:', error);
        showNotification(error.message || 'Failed to generate image', 'error');
    } finally {
        generateBtn.disabled = false;
        generateBtn.innerHTML = originalBtnText;
    }
}

// =====================================================
// GENERATE VIDEO (SYNTHESIA)
// =====================================================

async function generateVideo(event) {
    event.preventDefault();
    
    const generateBtn = document.getElementById('generateVideoBtn');
    const originalBtnText = generateBtn.innerHTML;
    
    try {
        generateBtn.disabled = true;
        generateBtn.innerHTML = '<i class="ti ti-loader"></i> Generating...';
        
        const token = localStorage.getItem('access_token');
        const clientId = document.getElementById('videoClient').value;
        const title = document.getElementById('videoTitle').value;
        const script = document.getElementById('videoScript').value;
        const background = document.getElementById('videoBackground').value;
        
        const response = await fetch(`${API_BASE}/generate/video`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                client_id: parseInt(clientId),
                script: script,
                title: title,
                background: background
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to generate video');
        }
        
        const result = await response.json();
        
        if (result.success) {
            showNotification('Video generation started! This may take a few minutes.', 'success');
            closeModal('videoModal');
            loadMediaAssets();
            
            // Poll for video status
            if (result.video_id) {
                pollVideoStatus(result.video_id, result.asset_id);
            }
        }
        
    } catch (error) {
        console.error('Error generating video:', error);
        showNotification(error.message || 'Failed to generate video', 'error');
    } finally {
        generateBtn.disabled = false;
        generateBtn.innerHTML = originalBtnText;
    }
}

// =====================================================
// POLL VIDEO STATUS
// =====================================================

async function pollVideoStatus(videoId, assetId) {
    const maxAttempts = 60; // Poll for up to 10 minutes (60 * 10 seconds)
    let attempts = 0;
    
    const checkStatus = async () => {
        try {
            const token = localStorage.getItem('access_token');
            const response = await fetch(`${API_BASE}/video/status/${videoId}`, {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });
            
            if (response.ok) {
                const result = await response.json();
                
                if (result.status === 'complete') {
                    showNotification('Video is ready!', 'success');
                    loadMediaAssets();
                    return true;
                } else if (result.status === 'failed') {
                    showNotification('Video generation failed', 'error');
                    return true;
                } else if (attempts >= maxAttempts) {
                    showNotification('Video is still processing. Please check back later.', 'info');
                    return true;
                }
            }
            
            attempts++;
            setTimeout(checkStatus, 10000); // Check again in 10 seconds
            
        } catch (error) {
            console.error('Error checking video status:', error);
        }
    };
    
    setTimeout(checkStatus, 10000); // Start checking after 10 seconds
}

// =====================================================
// CREATE DESIGN (CANVA)
// =====================================================

async function createDesign(event) {
    event.preventDefault();
    
    const createBtn = document.getElementById('createDesignBtn');
    const originalBtnText = createBtn.innerHTML;
    
    try {
        createBtn.disabled = true;
        createBtn.innerHTML = '<i class="ti ti-loader"></i> Creating...';
        
        const token = localStorage.getItem('access_token');
        const clientId = document.getElementById('designClient').value;
        const title = document.getElementById('designTitle').value;
        const designType = document.getElementById('designType').value;
        
        const response = await fetch(`${API_BASE}/generate/design`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                client_id: parseInt(clientId),
                title: title,
                design_type: designType,
                content_elements: {}
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to create design');
        }
        
        const result = await response.json();
        
        if (result.success) {
            showNotification('Design created successfully!', 'success');
            closeModal('designModal');
            loadMediaAssets();
            
            // Open Canva editor in new tab
            if (result.edit_url) {
                window.open(result.edit_url, '_blank');
            }
        }
        
    } catch (error) {
        console.error('Error creating design:', error);
        showNotification(error.message || 'Failed to create design', 'error');
    } finally {
        createBtn.disabled = false;
        createBtn.innerHTML = originalBtnText;
    }
}

// =====================================================
// LOAD MEDIA ASSETS
// =====================================================

async function loadMediaAssets() {
    const libraryContainer = document.getElementById('mediaLibrary');
    
    try {
        libraryContainer.innerHTML = `
            <div class="loading-state">
                <div class="loader-spinner"></div>
                <p>Loading media library...</p>
            </div>
        `;
        
        const token = localStorage.getItem('access_token');
        const filterType = document.getElementById('filterType').value;
        const filterClient = document.getElementById('filterClient').value;
        
        let url = `${API_BASE}/assets?limit=50`;
        if (filterType) url += `&asset_type=${filterType}`;
        if (filterClient) url += `&client_id=${filterClient}`;
        
        const response = await fetch(url, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (!response.ok) {
            throw new Error('Failed to fetch assets');
        }
        
        const result = await response.json();
        
        if (result.success && result.data.length > 0) {
            libraryContainer.innerHTML = `
                <div class="asset-grid">
                    ${result.data.map(asset => createAssetCard(asset)).join('')}
                </div>
            `;
        } else {
            libraryContainer.innerHTML = `
                <div class="empty-state">
                    <i class="ti ti-folder-off"></i>
                    <h3>No Media Assets Yet</h3>
                    <p>Start creating images, videos, or designs to build your library</p>
                </div>
            `;
        }
        
    } catch (error) {
        console.error('Error loading assets:', error);
        libraryContainer.innerHTML = `
            <div class="empty-state">
                <i class="ti ti-alert-circle"></i>
                <h3>Failed to Load Assets</h3>
                <p>${error.message}</p>
            </div>
        `;
    }
}

// =====================================================
// CREATE ASSET CARD
// =====================================================

function createAssetCard(asset) {
    const typeIcons = {
        'image': 'ti-photo',
        'video': 'ti-video',
        'animation': 'ti-gif',
        'presentation': 'ti-presentation'
    };
    
    const generationLabels = {
        'dall-e-3': 'DALL-E',
        'synthesia': 'Synthesia',
        'canva': 'Canva'
    };
    
    const icon = typeIcons[asset.asset_type] || 'ti-file';
    const genLabel = generationLabels[asset.generation_type] || asset.generation_type;
    
    const isImage = asset.asset_type === 'image' && asset.file_url.startsWith('http');
    const previewContent = isImage 
        ? `<img src="${asset.file_url}" alt="${asset.asset_name}">`
        : `<i class="ti ${icon}"></i>`;
    
    return `
        <div class="asset-card">
            <div class="asset-preview">
                ${previewContent}
                ${asset.ai_generated ? `<div class="asset-badge">${genLabel}</div>` : ''}
            </div>
            <div class="asset-info">
                <h3>${asset.asset_name}</h3>
                <div class="asset-meta">
                    <div><i class="ti ti-user"></i> ${asset.client_name}</div>
                    <div><i class="ti ti-calendar"></i> ${formatDate(asset.created_at)}</div>
                </div>
                <div class="asset-actions">
                    <button class="btn-icon" onclick="viewAsset(${asset.asset_id})" title="View">
                        <i class="ti ti-eye"></i>
                    </button>
                    <button class="btn-icon" onclick="downloadAsset('${asset.file_url}', '${asset.asset_name}')" title="Download">
                        <i class="ti ti-download"></i>
                    </button>
                    <button class="btn-icon" onclick="deleteAsset(${asset.asset_id})" title="Delete">
                        <i class="ti ti-trash"></i>
                    </button>
                </div>
            </div>
        </div>
    `;
}

// =====================================================
// ASSET ACTIONS
// =====================================================

function viewAsset(assetId) {
    window.open(`/modules/media-studio/asset/${assetId}`, '_blank');
}

function downloadAsset(url, filename) {
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    link.target = '_blank';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

async function deleteAsset(assetId) {
    if (!confirm('Are you sure you want to delete this asset?')) {
        return;
    }
    
    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`${API_BASE}/assets/${assetId}`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (!response.ok) {
            throw new Error('Failed to delete asset');
        }
        
        showNotification('Asset deleted successfully', 'success');
        loadMediaAssets();
        
    } catch (error) {
        console.error('Error deleting asset:', error);
        showNotification('Failed to delete asset', 'error');
    }
}

// =====================================================
// SHOW IMAGE PREVIEW
// =====================================================

function showImagePreview(imageUrl) {
    const previewHtml = `
        <div class="modal show" id="imagePreviewModal" onclick="closeModal('imagePreviewModal')">
            <div class="modal-content" style="max-width: 90%; max-height: 90vh;" onclick="event.stopPropagation()">
                <div class="modal-header">
                    <h2><i class="ti ti-photo"></i> Generated Image</h2>
                    <button class="modal-close" onclick="closeModal('imagePreviewModal')">
                        <i class="ti ti-x"></i>
                    </button>
                </div>
                <div class="modal-body" style="text-align: center;">
                    <img src="${imageUrl}" style="max-width: 100%; max-height: 70vh; border-radius: 8px;">
                    <div style="margin-top: 1rem;">
                        <a href="${imageUrl}" download class="btn-primary" style="text-decoration: none;">
                            <i class="ti ti-download"></i> Download Image
                        </a>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    document.body.insertAdjacentHTML('beforeend', previewHtml);
}

// =====================================================
// UTILITY FUNCTIONS
// =====================================================

function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', { 
        month: 'short', 
        day: 'numeric', 
        year: 'numeric' 
    });
}

function showNotification(message, type = 'info') {
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