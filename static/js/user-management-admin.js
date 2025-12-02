/**
 * User Management & Access Control
 * File: static/js/user-management.js
 */

const API_BASE = '/api/v1/user-management';
let currentPage = 1;
let allPermissions = {};
let selectedUserId = null;

// ==============================================
// INITIALIZATION
// ==============================================

document.addEventListener('DOMContentLoaded', () => {
    const token = localStorage.getItem('access_token');
    if (!token) {
        window.location.href = '/auth/login';
        return;
    }

    loadStatistics();
    loadUsers();

    // Search with debounce
    const searchInput = document.getElementById('searchUsers');
    let searchTimeout;
    searchInput.addEventListener('input', () => {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => loadUsers(), 500);
    });
});

// ==============================================
// TAB SWITCHING
// ==============================================

function switchTab(tabName) {
    // Update tab buttons
    document.querySelectorAll('.tab').forEach(tab => tab.classList.remove('active'));
    event.target.classList.add('active');

    // Update tab content
    document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
    document.getElementById(`${tabName}-tab`).classList.add('active');

    // Load data for active tab
    if (tabName === 'permissions') {
        loadPermissions();
    } else if (tabName === 'audit') {
        loadAuditLog();
    }
}

// ==============================================
// LOAD STATISTICS
// ==============================================

async function loadStatistics() {
    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`${API_BASE}/statistics`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (response.ok) {
            const data = await response.json();
            const stats = data.statistics;

            // Calculate totals
            let totalUsers = 0;
            let adminCount = 0;
            let employeeCount = 0;
            let clientCount = 0;

            stats.users_by_role.forEach(role => {
                totalUsers += role.count;
                if (role.role === 'admin') adminCount = role.count;
                if (role.role === 'employee') employeeCount = role.count;
                if (role.role === 'client') clientCount = role.count;
            });

            document.getElementById('totalUsers').textContent = totalUsers;
            document.getElementById('adminCount').textContent = adminCount;
            document.getElementById('employeeCount').textContent = employeeCount;
            document.getElementById('clientCount').textContent = clientCount;
        }
    } catch (error) {
        console.error('Error loading statistics:', error);
    }
}

// ==============================================
// USER MANAGEMENT
// ==============================================

async function loadUsers(page = 1) {
    try {
        const token = localStorage.getItem('access_token');
        const role = document.getElementById('filterRole').value;
        const status = document.getElementById('filterStatus').value;
        const search = document.getElementById('searchUsers').value;

        const params = new URLSearchParams({
            page: page,
            limit: 20
        });

        if (role) params.append('role', role);
        if (status) params.append('status', status);
        if (search) params.append('search', search);

        const response = await fetch(`${API_BASE}/users?${params}`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (response.ok) {
            const data = await response.json();
            displayUsers(data.users);
            displayPagination(data.pagination, 'usersPagination', loadUsers);
            currentPage = page;
        }
    } catch (error) {
        console.error('Error loading users:', error);
        showError('Failed to load users');
    }
}

function displayUsers(users) {
    const tbody = document.getElementById('usersTableBody');

    if (users.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="6">
                    <div class="empty-state">
                        <i class="ti ti-users"></i>
                        <p>No users found</p>
                    </div>
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = users.map(user => {
        const initials = user.full_name.split(' ').map(n => n[0]).join('').toUpperCase().substring(0, 2);
        const lastLogin = user.last_login ? new Date(user.last_login).toLocaleDateString() : 'Never';
        const created = new Date(user.created_at).toLocaleDateString();

        return `
            <tr>
                <td>
                    <div class="user-info">
                        <div class="user-avatar">${initials}</div>
                        <div class="user-details">
                            <h4>${user.full_name}</h4>
                            <p>${user.email}</p>
                        </div>
                    </div>
                </td>
                <td><span class="badge badge-${user.role}">${user.role}</span></td>
                <td><span class="badge badge-${user.status}">${user.status}</span></td>
                <td>${lastLogin}</td>
                <td>${created}</td>
                <td>
                    <div class="actions">
                        <button class="btn-icon" onclick="viewUserDetails(${user.user_id})" title="View Details">
                         <i class="ti ti-eye"></i>
                        </button>
                        <button class="btn-icon" onclick="editUser(${user.user_id})" title="Edit">
                            <i class="ti ti-edit"></i>
                        </button>
                        <button class="btn-icon" onclick="managePermissions(${user.user_id})" title="Permissions">
                            <i class="ti ti-shield-lock"></i>
                        </button>
                        <button class="btn-icon" onclick="openChangePassword(${user.user_id})" title="Change Password">
                            <i class="ti ti-key"></i>
                        </button>
                        <button class="btn-icon" onclick="toggleSuspend(${user.user_id}, '${user.status}')" title="${user.status === 'suspended' ? 'Activate' : 'Suspend'}">
                            <i class="ti ti-${user.status === 'suspended' ? 'lock-open' : 'lock'}"></i>
                        </button>
                        <button class="btn-icon" onclick="deleteUser(${user.user_id})" title="Delete" style="color: #dc2626;">
                            <i class="ti ti-trash"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `;
    }).join('');
}

function displayPagination(pagination, containerId, loadFunction) {
    const container = document.getElementById(containerId);
    if (!pagination || pagination.pages <= 1) {
        container.innerHTML = '';
        return;
    }

    const pages = [];
    for (let i = 1; i <= pagination.pages; i++) {
        pages.push(i);
    }

    container.innerHTML = `
        <button class="page-btn" onclick="${loadFunction.name}(${pagination.page - 1})" ${pagination.page === 1 ? 'disabled' : ''}>
            <i class="ti ti-chevron-left"></i>
        </button>
        ${pages.map(p => `
            <button class="page-btn ${p === pagination.page ? 'active' : ''}" onclick="${loadFunction.name}(${p})">
                ${p}
            </button>
        `).join('')}
        <button class="page-btn" onclick="${loadFunction.name}(${pagination.page + 1})" ${pagination.page === pagination.pages ? 'disabled' : ''}>
            <i class="ti ti-chevron-right"></i>
        </button>
    `;
}

// ==============================================
// CREATE/EDIT USER
// ==============================================

function openCreateUserModal() {
    document.getElementById('userModalTitle').textContent = 'Add New User';
    document.getElementById('userForm').reset();
    document.getElementById('userId').value = '';
    document.getElementById('passwordGroup').style.display = 'block';
    document.getElementById('userPassword').required = true;
    openModal('userModal');
}

async function editUser(userId) {
    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`${API_BASE}/users/${userId}`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (response.ok) {
            const data = await response.json();
            const user = data.user;

            document.getElementById('userModalTitle').textContent = 'Edit User';
            document.getElementById('userId').value = user.user_id;
            document.getElementById('userEmail').value = user.email;
            document.getElementById('userFullName').value = user.full_name;
            document.getElementById('userPhone').value = user.phone || '';
            document.getElementById('userRole').value = user.role;
            document.getElementById('userStatus').value = user.status;
            document.getElementById('passwordGroup').style.display = 'none';
            document.getElementById('userPassword').required = false;

            openModal('userModal');
        }
    } catch (error) {
        console.error('Error loading user:', error);
        showError('Failed to load user');
    }
}

async function saveUser() {
    try {
        const userId = document.getElementById('userId').value;
        const token = localStorage.getItem('access_token');

        const userData = {
            email: document.getElementById('userEmail').value,
            full_name: document.getElementById('userFullName').value,
            phone: document.getElementById('userPhone').value || null,
            role: document.getElementById('userRole').value,
            status: document.getElementById('userStatus').value
        };

        if (!userId) {
            // Create new user
            const password = document.getElementById('userPassword').value;
            if (!password || password.length < 8) {
                showError('Password must be at least 8 characters');
                return;
            }
            userData.password = password;

            const response = await fetch(`${API_BASE}/users`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(userData)
            });

            if (response.ok) {
                showSuccess('User created successfully');
                closeModal('userModal');
                loadUsers();
                loadStatistics();
            } else {
                const error = await response.json();
                showError(error.detail || 'Failed to create user');
            }
        } else {
            // Update existing user
            const response = await fetch(`${API_BASE}/users/${userId}`, {
                method: 'PUT',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(userData)
            });

            if (response.ok) {
                showSuccess('User updated successfully');
                closeModal('userModal');
                loadUsers();
            } else {
                const error = await response.json();
                showError(error.detail || 'Failed to update user');
            }
        }
    } catch (error) {
        console.error('Error saving user:', error);
        showError('Failed to save user');
    }
}

async function deleteUser(userId) {
    if (!confirm('Are you sure you want to delete this user? This action cannot be undone.')) {
        return;
    }

    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`${API_BASE}/users/${userId}`, {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (response.ok) {
            showSuccess('User deleted successfully');
            loadUsers();
            loadStatistics();
        } else {
            const error = await response.json();
            showError(error.detail || 'Failed to delete user');
        }
    } catch (error) {
        console.error('Error deleting user:', error);
        showError('Failed to delete user');
    }
}

async function toggleSuspend(userId, currentStatus) {
    const suspend = currentStatus !== 'suspended';
    const action = suspend ? 'suspend' : 'activate';

    if (!confirm(`Are you sure you want to ${action} this user?`)) {
        return;
    }

    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`${API_BASE}/users/${userId}/suspend`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ suspend })
        });

        if (response.ok) {
            showSuccess(`User ${action}d successfully`);
            loadUsers();
        } else {
            const error = await response.json();
            showError(error.detail || `Failed to ${action} user`);
        }
    } catch (error) {
        console.error(`Error ${action}ing user:`, error);
        showError(`Failed to ${action} user`);
    }
}

// ==============================================
// PASSWORD MANAGEMENT
// ==============================================

function openChangePassword(userId) {
    document.getElementById('pwdUserId').value = userId;
    document.getElementById('newPassword').value = '';
    openModal('passwordModal');
}

async function changePassword() {
    try {
        const userId = document.getElementById('pwdUserId').value;
        const newPassword = document.getElementById('newPassword').value;

        if (!newPassword || newPassword.length < 8) {
            showError('Password must be at least 8 characters');
            return;
        }

        const token = localStorage.getItem('access_token');
        const response = await fetch(`${API_BASE}/users/${userId}/change-password`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ new_password: newPassword })
        });

        if (response.ok) {
            showSuccess('Password changed successfully');
            closeModal('passwordModal');
        } else {
            const error = await response.json();
            showError(error.detail || 'Failed to change password');
        }
    } catch (error) {
        console.error('Error changing password:', error);
        showError('Failed to change password');
    }
}


async function viewUserDetails(userId) {
    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`${API_BASE}/users/${userId}`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (response.ok) {
            const data = await response.json();
            const user = data.user;

            // Basic Information
            document.getElementById('viewUserEmail').textContent = user.email;
            document.getElementById('viewUserName').textContent = user.full_name;
            document.getElementById('viewUserPhone').textContent = user.phone || 'Not provided';
            document.getElementById('viewUserRole').innerHTML = `<span class="badge badge-${user.role}">${user.role}</span>`;
            document.getElementById('viewUserStatus').innerHTML = `<span class="badge badge-${user.status}">${user.status}</span>`;
            document.getElementById('viewUserCreated').textContent = new Date(user.created_at).toLocaleString();
            document.getElementById('viewUserUpdated').textContent = new Date(user.updated_at).toLocaleString();
            document.getElementById('viewUserLastLogin').textContent = user.last_login ? new Date(user.last_login).toLocaleString() : 'Never';

            // Role-specific information
            const roleSpecificSection = document.getElementById('roleSpecificInfo');

            if (user.role === 'client') {
                roleSpecificSection.innerHTML = `
                    <div class="section-divider"></div>
                    <h4 class="section-title">Client Information</h4>
                    
                    ${user.client_profile ? `
                        <div class="detail-group">
                            <label class="detail-label">Business Name</label>
                            <p class="detail-value">${user.client_profile.business_name || 'Not provided'}</p>
                        </div>
                        <div class="detail-group">
                            <label class="detail-label">Business Type</label>
                            <p class="detail-value">${user.client_profile.business_type || 'Not provided'}</p>
                        </div>
                        <div class="detail-group">
                            <label class="detail-label">Website</label>
                            <p class="detail-value">${user.client_profile.website_url || 'Not provided'}</p>
                        </div>
                        <div class="detail-group">
                            <label class="detail-label">Budget</label>
                            <p class="detail-value">${user.client_profile.current_budget ? '₹' + parseFloat(user.client_profile.current_budget).toLocaleString() : 'Not set'}</p>
                        </div>
                    ` : '<p class="detail-value text-muted">No business profile created</p>'}
                    
                    ${user.subscription ? `
                        <div class="section-divider"></div>
                        <h4 class="section-title">Active Subscription</h4>
                        <div class="detail-group">
                            <label class="detail-label">Package</label>
                            <p class="detail-value">
                                <span class="package-badge ${user.subscription.package_tier}">${user.subscription.package_name}</span>
                            </p>
                        </div>
                        <div class="detail-group">
                            <label class="detail-label">Price</label>
                            <p class="detail-value">₹${parseFloat(user.subscription.price).toLocaleString()} / ${user.subscription.billing_cycle}</p>
                        </div>
                        <div class="detail-group">
                            <label class="detail-label">Subscription Period</label>
                            <p class="detail-value">${new Date(user.subscription.start_date).toLocaleDateString()} - ${new Date(user.subscription.end_date).toLocaleDateString()}</p>
                        </div>
                    ` : '<p class="detail-value text-muted">No active subscription</p>'}
                    
                    ${user.assigned_employee ? `
                        <div class="section-divider"></div>
                        <h4 class="section-title">Assigned Employee</h4>
                        <div class="detail-group">
                            <label class="detail-label">Employee</label>
                            <p class="detail-value">${user.assigned_employee.employee_name} (${user.assigned_employee.employee_email})</p>
                        </div>
                        <div class="detail-group">
                            <label class="detail-label">Assigned Since</label>
                            <p class="detail-value">${new Date(user.assigned_employee.assigned_at).toLocaleDateString()}</p>
                        </div>
                    ` : ''}
                `;
            } else if (user.role === 'employee') {
                roleSpecificSection.innerHTML = `
                    <div class="section-divider"></div>
                    <h4 class="section-title">Employee Information</h4>
                    <div class="detail-group">
                        <label class="detail-label">Assigned Clients</label>
                        <p class="detail-value">${user.assigned_clients_count || 0} clients</p>
                    </div>
                `;
            } else {
                roleSpecificSection.innerHTML = '';
            }

            // Tasks Summary
            if (user.tasks_summary && user.tasks_summary.total > 0) {
                document.getElementById('tasksSection').innerHTML = `
                    <div class="section-divider"></div>
                    <h4 class="section-title">Tasks Summary</h4>
                    <div class="stats-grid">
                        <div class="stat-box">
                            <div class="stat-value">${user.tasks_summary.total || 0}</div>
                            <div class="stat-label">Total Tasks</div>
                        </div>
                        <div class="stat-box">
                            <div class="stat-value" style="color: #F59E0B;">${user.tasks_summary.pending || 0}</div>
                            <div class="stat-label">Pending</div>
                        </div>
                        <div class="stat-box">
                            <div class="stat-value" style="color: #3B82F6;">${user.tasks_summary.in_progress || 0}</div>
                            <div class="stat-label">In Progress</div>
                        </div>
                        <div class="stat-box">
                            <div class="stat-value" style="color: #10B981;">${user.tasks_summary.completed || 0}</div>
                            <div class="stat-label">Completed</div>
                        </div>
                    </div>
                `;
            } else {
                document.getElementById('tasksSection').innerHTML = '';
            }

            // Permissions Summary
            const permissionsCount = (user.custom_permissions?.length || 0) + (user.role_permissions?.length || 0);
            document.getElementById('permissionsSection').innerHTML = `
                <div class="section-divider"></div>
                <h4 class="section-title">Permissions</h4>
                <div class="detail-group">
                    <label class="detail-label">Role Permissions</label>
                    <p class="detail-value">${user.role_permissions?.length || 0} permissions from role</p>
                </div>
                <div class="detail-group">
                    <label class="detail-label">Custom Permissions</label>
                    <p class="detail-value">${user.custom_permissions?.length || 0} custom permissions</p>
                </div>
                <div class="detail-group">
                    <label class="detail-label">Total Permissions</label>
                    <p class="detail-value"><strong>${permissionsCount} total permissions</strong></p>
                </div>
            `;

            // Activity Summary
            document.getElementById('activitySection').innerHTML = `
                <div class="section-divider"></div>
                <h4 class="section-title">Activity</h4>
                <div class="detail-group">
                    <label class="detail-label">Recent Activity (30 days)</label>
                    <p class="detail-value">${user.recent_activity_count || 0} activities logged</p>
                </div>
            `;

            openModal('viewUserModal');
        } else {
            const error = await response.json();
            showError(error.detail || 'Failed to load user details');
        }
    } catch (error) {
        console.error('Error loading user details:', error);
        showError('Failed to load user details');
    }
}


// ==============================================
// PERMISSIONS MANAGEMENT
// ==============================================

async function loadPermissions() {
    try {
        const token = localStorage.getItem('access_token');
        const module = document.getElementById('filterModule').value;

        const params = module ? `?module=${module}` : '';
        const response = await fetch(`${API_BASE}/permissions${params}`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (response.ok) {
            const data = await response.json();
            allPermissions = data.grouped_by_module;
            displayPermissionsOverview(data.grouped_by_module);
        }
    } catch (error) {
        console.error('Error loading permissions:', error);
        showError('Failed to load permissions');
    }
}

function displayPermissionsOverview(groupedPermissions) {
    const container = document.getElementById('permissionsContent');

    const html = Object.entries(groupedPermissions).map(([module, perms]) => `
        <div class="permission-card" style="margin-bottom: 1.5rem;">
            <h5>${formatModuleName(module)}</h5>
            ${perms.map(p => `
                <div class="permission-item">
                    <input type="checkbox" disabled>
                    <label>
                        <strong>${p.permission_name}</strong>
                        <br>
                        <small style="color: #6b7280;">${p.description}</small>
                    </label>
                </div>
            `).join('')}
        </div>
    `).join('');

    container.innerHTML = html || '<p style="text-align: center; color: #6b7280;">No permissions found</p>';
}

async function managePermissions(userId) {
    selectedUserId = userId;

    try {
        const token = localStorage.getItem('access_token');

        // Load all permissions
        const permResponse = await fetch(`${API_BASE}/permissions`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        // Load user details
        const userResponse = await fetch(`${API_BASE}/users/${userId}`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (permResponse.ok && userResponse.ok) {
            const permData = await permResponse.json();
            const userData = await userResponse.json();

            document.getElementById('permUserId').value = userId;

            // Get user's current custom permissions
            const userPermIds = new Set(
                userData.user.custom_permissions
                    .filter(p => p.granted)
                    .map(p => p.permission_id)
            );

            // Get role permissions
            const rolePermIds = new Set(
                userData.user.role_permissions.map(p => p.permission_id)
            );

            displayPermissionsGrid(permData.grouped_by_module, userPermIds, rolePermIds);
            openModal('permissionsModal');
        }
    } catch (error) {
        console.error('Error loading permissions:', error);
        showError('Failed to load permissions');
    }
}

function displayPermissionsGrid(groupedPerms, userPermIds, rolePermIds) {
    const grid = document.getElementById('permissionsGrid');

    const html = Object.entries(groupedPerms).map(([module, perms]) => `
        <div class="permission-card">
            <h5>${formatModuleName(module)}</h5>
            ${perms.map(p => {
        const hasRole = rolePermIds.has(p.permission_id);
        const hasCustom = userPermIds.has(p.permission_id);
        const checked = hasCustom ? 'checked' : '';
        const disabled = hasRole ? 'disabled title="Granted by role"' : '';

        return `
                    <div class="permission-item">
                        <input type="checkbox" 
                               id="perm-${p.permission_id}" 
                               value="${p.permission_id}"
                               ${checked} 
                               ${disabled}>
                        <label for="perm-${p.permission_id}">
                            ${p.permission_name}
                            ${hasRole ? '<small style="color: #10b981;">(Role)</small>' : ''}
                        </label>
                    </div>
                `;
    }).join('')}
        </div>
    `).join('');

    grid.innerHTML = html;
}

async function savePermissions() {
    try {
        const userId = document.getElementById('permUserId').value;
        const token = localStorage.getItem('access_token');

        // Get all checked permissions
        const checkboxes = document.querySelectorAll('#permissionsGrid input[type="checkbox"]:not(:disabled)');
        const selectedPermissions = [];

        checkboxes.forEach(cb => {
            if (cb.checked) {
                selectedPermissions.push(parseInt(cb.value));
            }
        });

        // Assign permissions
        const response = await fetch(`${API_BASE}/users/assign-permissions`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                user_id: parseInt(userId),
                permission_ids: selectedPermissions
            })
        });

        if (response.ok) {
            showSuccess('Permissions updated successfully');
            closeModal('permissionsModal');
        } else {
            const error = await response.json();
            showError(error.detail || 'Failed to update permissions');
        }
    } catch (error) {
        console.error('Error saving permissions:', error);
        showError('Failed to save permissions');
    }
}

// ==============================================
// AUDIT LOG
// ==============================================

async function loadAuditLog(page = 1) {
    try {
        const token = localStorage.getItem('access_token');
        const action = document.getElementById('filterAuditAction').value;

        const params = new URLSearchParams({
            page: page,
            limit: 20
        });

        if (action) params.append('action', action);

        const response = await fetch(`${API_BASE}/audit-log?${params}`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (response.ok) {
            const data = await response.json();
            displayAuditLog(data.logs);
            displayPagination(data.pagination, 'auditPagination', loadAuditLog);
        }
    } catch (error) {
        console.error('Error loading audit log:', error);
        showError('Failed to load audit log');
    }
}

function displayAuditLog(logs) {
    const container = document.getElementById('auditLogContent');

    if (logs.length === 0) {
        container.innerHTML = '<p style="text-align: center; color: #6b7280;">No audit logs found</p>';
        return;
    }

    container.innerHTML = logs.map(log => {
        const time = new Date(log.created_at).toLocaleString();
        const details = log.details ? JSON.parse(log.details) : {};

        return `
            <div class="audit-log-item">
                <div class="audit-header">
                    <div>
                        <div class="audit-action">${formatAuditAction(log.action)}</div>
                        <div class="audit-details">
                            By: ${log.user_name || 'System'} (${log.user_email || 'N/A'})
                            ${log.target_user_name ? ` → Target: ${log.target_user_name}` : ''}
                            ${log.permission_name ? ` → Permission: ${log.permission_name}` : ''}
                        </div>
                    </div>
                    <div class="audit-time">${time}</div>
                </div>
                ${Object.keys(details).length > 0 ? `
                    <div class="audit-details" style="margin-top: 0.5rem;">
                        Details: ${JSON.stringify(details)}
                    </div>
                ` : ''}
            </div>
        `;
    }).join('');
}

// ==============================================
// UTILITY FUNCTIONS
// ==============================================

function formatModuleName(module) {
    return module.split('_').map(word =>
        word.charAt(0).toUpperCase() + word.slice(1)
    ).join(' ');
}

function formatAuditAction(action) {
    return action.split('_').map(word =>
        word.charAt(0).toUpperCase() + word.slice(1)
    ).join(' ');
}

function openModal(modalId) {
    document.getElementById(modalId).classList.add('active');
}

function closeModal(modalId) {
    document.getElementById(modalId).classList.remove('active');
}

function showSuccess(message) {
    // You can implement a toast notification here
    alert(message);
}

function showError(message) {
    // You can implement a toast notification here
    alert('Error: ' + message);
}