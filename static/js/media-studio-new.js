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
// MODAL FUNCTIONS
// =====================================================

function openImageGenerator() {
    document.getElementById('imageModal').classList.add('show');
}

function openVideoGenerator() {
    document.getElementById('videoModal').classList.add('show');
}

function openDesignStudio() {
    document.getElementById('designModal').classList.add('show');
}

function openAnimationGenerator() {
    document.getElementById('animationModal').classList.add('show');
}

function openImageToVideo() {
    document.getElementById('imageToVideoModal').classList.add('show');
}

function openImageToAnimation() {
    document.getElementById('imageToAnimationModal').classList.add('show');
}

function closeModal(modalId) {
    document.getElementById(modalId).classList.remove('show');
}

// =====================================================
// LOAD CLIENTS
// =====================================================

async function loadClients() {
    const clientSelects = [
        'imageClient', 
        'videoClient', 
        'designClient', 
        'filterClient',
        'animationClient',
        'imageToVideoClient',
        'imageToAnimationClient'
    ];
    
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
            if (select && data.clients) {
                data.clients.forEach(client => {
                    const option = document.createElement('option');
                    option.value = client.user_id;
                    option.textContent = client.company_name || client.email;
                    select.appendChild(option);
                });
            }
        });
        
    } catch (error) {
        console.error('Error loading clients:', error);
    }
}

// =====================================================
// NOTIFICATION HELPER
// =====================================================

function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 1rem 1.5rem;
        background: ${type === 'success' ? '#10b981' : type === 'error' ? '#ef4444' : '#3b82f6'};
        color: white;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
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
            document.getElementById('imageForm').reset();
            loadMediaAssets();
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
            document.getElementById('videoForm').reset();
            
            // Start checking video status
            if (result.video_id) {
                checkVideoStatus(result.video_id);
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
// CHECK VIDEO STATUS
// =====================================================

async function checkVideoStatus(videoId) {
    let attempts = 0;
    const maxAttempts = 30; // 5 minutes
    
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
// GENERATE ANIMATION (TEXT-TO-ANIMATION)
// =====================================================

async function generateAnimation(event) {
    event.preventDefault();
    
    const generateBtn = document.getElementById('generateAnimationBtn');
    const originalBtnText = generateBtn.innerHTML;
    
    try {
        generateBtn.disabled = true;
        generateBtn.innerHTML = '<i class="ti ti-loader"></i> Generating...';
        
        const token = localStorage.getItem('access_token');
        const clientId = document.getElementById('animationClient').value;
        const title = document.getElementById('animationTitle').value;
        const prompt = document.getElementById('animationPrompt').value;
        const style = document.getElementById('animationStyle').value;
        const duration = document.getElementById('animationDuration').value;
        
        const response = await fetch(`${API_BASE}/generate/animation`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                client_id: parseInt(clientId),
                title: title,
                prompt: prompt,
                style: style,
                duration: parseInt(duration)
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to generate animation');
        }
        
        const result = await response.json();
        
        if (result.success) {
            showNotification('Animation generated successfully!', 'success');
            closeModal('animationModal');
            document.getElementById('animationForm').reset();
            loadMediaAssets();
        }
        
    } catch (error) {
        console.error('Error generating animation:', error);
        showNotification(error.message || 'Failed to generate animation', 'error');
    } finally {
        generateBtn.disabled = false;
        generateBtn.innerHTML = originalBtnText;
    }
}

// =====================================================
// CONVERT IMAGE TO VIDEO
// =====================================================

async function convertImageToVideo(event) {
    event.preventDefault();
    
    const convertBtn = document.getElementById('convertImageToVideoBtn');
    const originalBtnText = convertBtn.innerHTML;
    
    try {
        convertBtn.disabled = true;
        convertBtn.innerHTML = '<i class="ti ti-loader"></i> Converting...';
        
        const token = localStorage.getItem('access_token');
        const clientId = document.getElementById('imageToVideoClient').value;
        const imageFile = document.getElementById('sourceImage').files[0];
        const motionPrompt = document.getElementById('motionPrompt').value;
        const duration = document.getElementById('videoLength').value;
        
        if (!imageFile) {
            throw new Error('Please select an image');
        }
        
        // Convert image to base64
        const base64Image = await fileToBase64(imageFile);
        
        const response = await fetch(`${API_BASE}/convert/image-to-video`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                client_id: parseInt(clientId),
                image_data: base64Image,
                motion_prompt: motionPrompt,
                duration: parseInt(duration)
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to convert image to video');
        }
        
        const result = await response.json();
        
        if (result.success) {
            showNotification('Image converted to video successfully!', 'success');
            closeModal('imageToVideoModal');
            document.getElementById('imageToVideoForm').reset();
            loadMediaAssets();
        }
        
    } catch (error) {
        console.error('Error converting image to video:', error);
        showNotification(error.message || 'Failed to convert image to video', 'error');
    } finally {
        convertBtn.disabled = false;
        convertBtn.innerHTML = originalBtnText;
    }
}

// =====================================================
// CONVERT IMAGE TO ANIMATION
// =====================================================

async function convertImageToAnimation(event) {
    event.preventDefault();
    
    const convertBtn = document.getElementById('convertImageToAnimationBtn');
    const originalBtnText = convertBtn.innerHTML;
    
    try {
        convertBtn.disabled = true;
        convertBtn.innerHTML = '<i class="ti ti-loader"></i> Creating...';
        
        const token = localStorage.getItem('access_token');
        const clientId = document.getElementById('imageToAnimationClient').value;
        const imageFile = document.getElementById('animSourceImage').files[0];
        const animationEffect = document.getElementById('animationEffect').value;
        const animationType = document.getElementById('animationType').value;
        
        if (!imageFile) {
            throw new Error('Please select an image');
        }
        
        // Convert image to base64
        const base64Image = await fileToBase64(imageFile);
        
        const response = await fetch(`${API_BASE}/convert/image-to-animation`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                client_id: parseInt(clientId),
                image_data: base64Image,
                animation_effect: animationEffect,
                animation_type: animationType
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to create animation');
        }
        
        const result = await response.json();
        
        if (result.success) {
            showNotification('Animation created successfully!', 'success');
            closeModal('imageToAnimationModal');
            document.getElementById('imageToAnimationForm').reset();
            loadMediaAssets();
        }
        
    } catch (error) {
        console.error('Error creating animation:', error);
        showNotification(error.message || 'Failed to create animation', 'error');
    } finally {
        convertBtn.disabled = false;
        convertBtn.innerHTML = originalBtnText;
    }
}

// =====================================================
// FILE TO BASE64 HELPER
// =====================================================

function fileToBase64(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => {
            const base64 = reader.result.split(',')[1];
            resolve(base64);
        };
        reader.onerror = reject;
        reader.readAsDataURL(file);
    });
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
        'canva': 'Canva',
        'ideogram': 'Ideogram',
        'openai': 'OpenAI'
    };
    
    const icon = typeIcons[asset.asset_type] || 'ti-file';
    const genLabel = generationLabels[asset.generation_type] || asset.generation_type;
    
    const isImage = asset.asset_type === 'image' && asset.file_url;
    const previewContent = isImage 
        ? `<img src="${asset.file_url}" alt="${asset.asset_name}" onerror="this.style.display='none'; this.parentElement.innerHTML='<i class=\\'ti ${icon}\\'></i>';">`
        : `<i class="ti ${icon}"></i>`;
    
    const escapedUrl = (asset.file_url || '').replace(/'/g, "\\'");
    
    return `
        <div class="asset-card">
            <div class="asset-preview">
                ${previewContent}
                ${asset.ai_generated ? `<span class="asset-badge">${genLabel}</span>` : ''}
            </div>
            <div class="asset-info">
                <h3>${asset.asset_name || 'Untitled Asset'}</h3>
                <div class="asset-meta">
                    ${new Date(asset.created_at).toLocaleDateString()}
                </div>
                <div class="asset-actions">
                    <button class="btn-icon" onclick="downloadAsset(${asset.asset_id})" title="Download">
                        <i class="ti ti-download"></i>
                    </button>
                    <button class="btn-icon" onclick="viewAsset('${escapedUrl}')" title="View">
                        <i class="ti ti-eye"></i>
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
async function downloadAsset(assetId) {
    try {
        showNotification('Starting download...', 'info');
        
        const token = localStorage.getItem('access_token');
        
        // Use the new download endpoint
        const response = await fetch(`${API_BASE}/assets/${assetId}/download`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (!response.ok) {
            throw new Error('Download failed');
        }
        
        // Check if it's a redirect response
        const contentType = response.headers.get('content-type');
        if (contentType && contentType.includes('application/json')) {
            const data = await response.json();
            if (data.redirect_url) {
                window.open(data.redirect_url, '_blank');
                return;
            }
        }
        
        // Handle direct file download
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `asset_${assetId}`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
        
        showNotification('Download completed', 'success');
        
    } catch (error) {
        console.error('Download error:', error);
        showNotification('Failed to download asset', 'error');
    }
}

function viewAsset(url) {
    alert(url);
    if (url && (url.startsWith('http') || url.startsWith('/static'))) {
        window.open(url, '_blank');
    } else {
        showNotification('View URL not available', 'error');
    }
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
        showNotification(error.message || 'Failed to delete asset', 'error');
    }
}