// Dashboard JavaScript
// Get backend URL from environment config (set by Flask template)
// Falls back to constructed URL for local development
const BACKEND_API_URL = (() => {
    // First try ENV_CONFIG (set by templates)
    if (window.ENV_CONFIG?.backend_url) {
        return window.ENV_CONFIG.backend_url;
    }
    // Check if we're in development (localhost) or production
    if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
        return 'http://localhost:5000';
    }
    // In Docker, use the backend service name
    return window.location.origin.replace(':3000', ':5000');
})();

// Get user ID from session or URL
function getUserId() {
    // Get from global variable set by template
    if (window.DASHBOARD_USER_ID) {
        return window.DASHBOARD_USER_ID;
    }
    
    // Try to get from data attribute
    const userId = document.body.getAttribute('data-user-id');
    if (userId) return userId;
    
    // Fallback: try to get from localStorage or session
    try {
        const userData = localStorage.getItem('user');
        if (userData) {
            const user = JSON.parse(userData);
            return user.user_id;
        }
    } catch (e) {
        console.error('Error getting user ID:', e);
    }
    return null;
}

// Format date relative to now (handles timezone correctly)
function formatRelativeTime(dateString) {
    if (!dateString) return 'Unknown';
    
    // Parse the date string - MySQL returns in format 'YYYY-MM-DD HH:MM:SS'
    // MySQL TIMESTAMP is stored in UTC but displayed in server timezone
    // We need to parse it correctly and convert to user's local timezone
    let date;
    if (dateString.includes('T') || dateString.includes('Z')) {
        // ISO format with timezone info
        date = new Date(dateString);
    } else {
        // MySQL format without timezone - assume it's UTC and let JavaScript convert to local
        // Add 'Z' to indicate UTC, or append timezone offset
        // If the string doesn't have timezone, MySQL typically returns it in server timezone
        // But to be safe, we'll treat it as UTC and let the browser convert
        const mysqlDate = dateString.replace(' ', 'T');
        // If no timezone indicator, assume UTC
        date = new Date(mysqlDate + (mysqlDate.includes('Z') || mysqlDate.includes('+') || mysqlDate.includes('-') && mysqlDate.match(/[+-]\d{2}:\d{2}$/) ? '' : 'Z'));
    }
    
    // Validate date
    if (isNaN(date.getTime())) {
        // Fallback: try parsing as local time
        date = new Date(dateString.replace(' ', 'T'));
    }
    
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);
    
    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins} min${diffMins > 1 ? 's' : ''} ago`;
    if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
    if (diffDays < 7) return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
    
    return date.toLocaleDateString();
}

// Format activity type for display
function formatActivityType(type, subtype) {
    if (type === 'content_generation') {
        const subtypes = {
            'social_content': 'Social Content',
            'proposal_content': 'Proposal Content',
            'linkedin_post': 'LinkedIn Post'
        };
        return subtypes[subtype] || 'Content Generated';
    }
    if (type === 'gap_analysis') {
        return 'Gap Analysis';
    }
    return type.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase());
}

// Load dashboard data
async function loadDashboard() {
    const userId = getUserId();
    if (!userId) {
        console.error('User ID not found');
        document.getElementById('dashboardLoading').innerHTML = 
            '<p style="color: #ef4444;">Error: User not authenticated</p>';
        return;
    }
    
    try {
        const response = await fetch(`${BACKEND_API_URL}/api/dashboard/stats?user_id=${userId}`);
        const data = await response.json();
        
        if (!data.success) {
            throw new Error(data.message || 'Failed to load dashboard');
        }
        
        renderDashboard(data.stats);
        document.getElementById('dashboardLoading').style.display = 'none';
        document.getElementById('dashboardContent').style.display = 'block';
    } catch (error) {
        console.error('Error loading dashboard:', error);
        document.getElementById('dashboardLoading').innerHTML = 
            `<p style="color: #ef4444;">Error loading dashboard: ${error.message}</p>`;
    }
}

// Render dashboard with data
function renderDashboard(stats) {
    // Update stat cards
    const profileCompletionEl = document.getElementById('profileCompletion');
    const totalActivitiesEl = document.getElementById('totalActivities');
    const contentGeneratedEl = document.getElementById('contentGenerated');
    const linkedinPostsCountEl = document.getElementById('linkedinPostsCount');
    
    if (profileCompletionEl) {
        profileCompletionEl.textContent = `${stats.profile.completion}%`;
    }
    if (totalActivitiesEl) {
        totalActivitiesEl.textContent = stats.activity.total_activities || 0;
    }
    if (contentGeneratedEl) {
        contentGeneratedEl.textContent = (stats.activity.by_type?.content_generation || 0);
    }
    if (linkedinPostsCountEl) {
        linkedinPostsCountEl.textContent = stats.activity.linkedin_posts_count || 0;
    }
    
    // Render charts
    renderActivityChart(stats.activity.daily_activity || []);
    renderPlatformChart(stats.activity.platform_usage || {});
    
    // Render LinkedIn insights
    renderLinkedInInsights(stats.profile);
    
    // Render keywords
    renderKeywords(stats.keywords || []);
}

// Render activity over time chart
function renderActivityChart(dailyData) {
    const ctx = document.getElementById('activityChart');
    if (!ctx) return;
    
    // Prepare data for last 7 days
    const last7Days = [];
    const today = new Date();
    for (let i = 6; i >= 0; i--) {
        const date = new Date(today);
        date.setDate(date.getDate() - i);
        const dateStr = date.toISOString().split('T')[0];
        const dayData = dailyData.find(d => d.date === dateStr);
        last7Days.push({
            date: dateStr,
            label: date.toLocaleDateString('en-US', { weekday: 'short' }),
            count: dayData ? dayData.count : 0
        });
    }
    
    new Chart(ctx, {
        type: 'line',
        data: {
            labels: last7Days.map(d => d.label),
            datasets: [{
                label: 'Activities',
                data: last7Days.map(d => d.count),
                borderColor: 'rgb(139, 92, 246)',
                backgroundColor: 'rgba(139, 92, 246, 0.1)',
                tension: 0.4,
                fill: true,
                pointRadius: 4,
                pointHoverRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        stepSize: 1,
                        color: 'rgba(163, 163, 163, 0.8)'
                    },
                    grid: {
                        color: 'rgba(38, 38, 38, 0.5)'
                    }
                },
                x: {
                    ticks: {
                        color: 'rgba(163, 163, 163, 0.8)'
                    },
                    grid: {
                        display: false
                    }
                }
            }
        }
    });
}

// Render platform usage chart
function renderPlatformChart(platformData) {
    const ctx = document.getElementById('platformChart');
    if (!ctx) return;
    
    const platforms = Object.keys(platformData);
    const counts = Object.values(platformData);
    
    if (platforms.length === 0) {
        ctx.parentElement.innerHTML = '<div class="empty-state"><p>No platform data available</p></div>';
        return;
    }
    
    // Format platform names
    const formattedPlatforms = platforms.map(p => {
        const names = {
            'linkedin': 'LinkedIn',
            'instagram_feed': 'Instagram Feed',
            'instagram_story': 'Instagram Story',
            'twitter': 'Twitter',
            'tiktok': 'TikTok'
        };
        return names[p] || p;
    });
    
    new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: formattedPlatforms,
            datasets: [{
                data: counts,
                backgroundColor: [
                    'rgba(139, 92, 246, 0.8)',
                    'rgba(34, 197, 94, 0.8)',
                    'rgba(251, 191, 36, 0.8)',
                    'rgba(59, 130, 246, 0.8)',
                    'rgba(239, 68, 68, 0.8)',
                    'rgba(168, 85, 247, 0.8)'
                ],
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        color: 'rgba(163, 163, 163, 0.8)',
                        padding: 15,
                        font: {
                            size: 12
                        }
                    }
                }
            }
        }
    });
}

// Removed renderContentTypeChart and renderRecentActivity functions as they are no longer used

// Render LinkedIn insights
function renderLinkedInInsights(profile) {
    const container = document.getElementById('linkedinInsights');
    if (!container) return;
    
    const insights = [
        {
            label: 'LinkedIn Profile',
            value: profile.linkedin_configured ? 'Connected' : 'Not Connected',
            badge: profile.linkedin_configured ? 'success' : 'warning'
        },
        {
            label: 'Keywords Extracted',
            value: `${profile.keywords_count || 0} keywords`
        },
        {
            label: 'Writing Style',
            value: profile.has_tone ? 'Analyzed' : 'Not Analyzed',
            badge: profile.has_tone ? 'success' : 'warning'
        },
        {
            label: 'Last Updated',
            value: profile.linkedin_updated_at 
                ? formatRelativeTime(profile.linkedin_updated_at)
                : 'Never'
        }
    ];
    
    container.innerHTML = insights.map(insight => `
        <div class="insight-item">
            <span class="insight-label">${insight.label}</span>
            <div style="display: flex; align-items: center; gap: 0.5rem;">
                <span class="insight-value">${insight.value}</span>
                ${insight.badge ? `<span class="insight-badge ${insight.badge}">${insight.badge}</span>` : ''}
            </div>
        </div>
    `).join('');
}

// Render keywords
function renderKeywords(keywords) {
    const container = document.getElementById('keywordsList');
    if (!container) return;
    
    if (keywords.length === 0) {
        container.innerHTML = '<div class="empty-state"><p>No keywords extracted yet</p></div>';
        return;
    }
    
    // Handle both string and object keywords
    const keywordList = keywords.map(k => {
        if (typeof k === 'string') return k;
        if (k.keyword) return k.keyword;
        return k;
    }).filter(k => k);
    
    container.innerHTML = keywordList.map(keyword => 
        `<span class="keyword-tag">${keyword}</span>`
    ).join('');
}

// Initialize dashboard when page loads
document.addEventListener('DOMContentLoaded', () => {
    loadDashboard();
});

