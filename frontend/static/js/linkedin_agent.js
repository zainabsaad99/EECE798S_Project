// LinkedIn Agent JavaScript
// Use relative URL for same-origin requests, or configure based on environment
// In Docker, frontend can call backend via http://backend:5000, but from browser we need to use the exposed port
const BACKEND_URL = window.location.protocol + '//' + window.location.hostname + ':5000';

// Initialize agentState with API keys from .env (via window.ENV_CONFIG)
let agentState = {
    openai_key: window.ENV_CONFIG?.openai_api_key || '',
    phantom_key: window.ENV_CONFIG?.phantombuster_api_key || '',
    firecrawl_key: window.ENV_CONFIG?.firecrawl_api_key || '',
    session_cookie: window.ENV_CONFIG?.linkedin_session_cookie || '',  // From .env
    user_agent: window.ENV_CONFIG?.user_agent || '',
    sheet_url: window.ENV_CONFIG?.google_sheet_url || '',  // From .env
    user_linkedin_url: window.ENV_CONFIG?.user_linkedin_url || '',  // From user profile
    user_id: window.ENV_CONFIG?.user_id || '',  // User ID
    service_account_json: null,  // Will be loaded from backend
    keywords: [],
    style_notes: '',
    trends: [],
    current_post: '',
    // Post generation arguments saved for regeneration
    saved_post_args: {
        topic: '',
        manual_topic: '',
        selected_trend: '',
        style_notes: '',
        keywords: []
    },
    has_saved_data: false,  // Whether user has saved keywords/tone
    style_url_processed: false  // Whether a style URL was processed
};

// Initialize with saved data if available
if (window.USER_LINKEDIN_DATA && window.USER_LINKEDIN_DATA.success) {
    agentState.keywords = window.USER_LINKEDIN_DATA.keywords || [];
    agentState.style_notes = window.USER_LINKEDIN_DATA.tone_of_writing || '';
    agentState.has_saved_data = agentState.keywords.length > 0 || agentState.style_notes.length > 0;
}

// Formatting utility functions
function formatToneText(toneText) {
    if (!toneText) return '';
    
    // Remove markdown formatting
    let formatted = toneText
        .replace(/\*\*/g, '')  // Remove bold markers
        .replace(/\*/g, '')    // Remove italic markers
        .replace(/^-\s+/gm, '') // Remove bullet points at start of lines
        .replace(/^\d+\.\s+/gm, '') // Remove numbered lists
        .replace(/^•\s+/gm, '') // Remove bullet points (•)
        .trim();
    
    // Split by common separators and clean up
    const lines = formatted.split(/\n+/).filter(line => line.trim().length > 0);
    
    // Format each line nicely
    return lines.map(line => {
        line = line.trim();
        // Remove any remaining markdown-like patterns
        line = line.replace(/^[-•*]\s*/, ''); // Remove any remaining bullet markers
        // Capitalize first letter
        if (line.length > 0) {
            line = line.charAt(0).toUpperCase() + line.slice(1);
        }
        // Ensure proper sentence ending
        if (line.length > 0 && !line.match(/[.!?]$/)) {
            line += '.';
        }
        return line;
    }).join('\n\n');
}

function formatKeyword(keyword) {
    if (!keyword) return '';
    // Capitalize first letter of each word
    return keyword
        .split(/\s+/)
        .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
        .join(' ');
}

function formatKeywords(keywords) {
    if (!keywords || !Array.isArray(keywords)) return [];
    return keywords.map(formatKeyword);
}

// DOM Elements
const regenerateProfileBtn = document.getElementById('regenerateProfileBtn');
const skipProfileBtn = document.getElementById('skipProfileBtn');
const skipStyleUrlBtn = document.getElementById('skipStyleUrlBtn');
const processStyleUrlBtn = document.getElementById('processStyleUrlBtn');
const generatePostBtn = document.getElementById('generatePostBtn');
const saveAndPostBtn = document.getElementById('saveAndPostBtn');
const copyPostBtn = document.getElementById('copyPostBtn');
const regeneratePostBtn = document.getElementById('regeneratePostBtn');

// Initialize
document.addEventListener('DOMContentLoaded', async () => {
    setupEventListeners();
    // Initialize agentState from pre-filled form values (from .env)
    initializeFromForm();
    
    // Load service account JSON immediately
    await loadDefaultServiceAccount();
    
    // Format keywords and tone on page load
    formatPageContent();
    
    // Set up post content editor listener
    const postContent = document.getElementById('postContent');
    if (postContent) {
        postContent.addEventListener('input', function() {
            agentState.current_post = this.value;
        });
    }
});

// Format keywords and tone displayed on page load
function formatPageContent() {
    // Format keywords in the initial display
    const keywordItems = document.querySelectorAll('.keyword-item');
    keywordItems.forEach(item => {
        item.textContent = formatKeyword(item.textContent);
    });
    
    // Format tone in the initial display
    const savedToneDisplay = document.getElementById('savedToneDisplay');
    if (savedToneDisplay && savedToneDisplay.textContent && savedToneDisplay.textContent !== 'No tone data available') {
        const formattedTone = formatToneText(savedToneDisplay.textContent);
        savedToneDisplay.textContent = formattedTone;
    }
}

function initializeFromForm() {
    // Validate that required API keys are present (from .env)
    const missingKeys = [];
    if (!agentState.openai_key) missingKeys.push('OPENAI_API_KEY');
    if (!agentState.phantom_key) missingKeys.push('PHANTOMBUSTER_API_KEY');
    if (!agentState.firecrawl_key) missingKeys.push('FIRECRAWL_API_KEY');
    if (!agentState.user_agent) missingKeys.push('USER_AGENT');
    if (!agentState.session_cookie) missingKeys.push('LINKEDIN_SESSION_COOKIE');
    if (!agentState.user_linkedin_url) missingKeys.push('User LinkedIn URL (set in account profile)');
    
    if (missingKeys.length > 0) {
        showStatus(`Missing required configuration: ${missingKeys.join(', ')}. Please configure them in .env or account profile`, 'error');
    }
}

function setupEventListeners() {
    if (regenerateProfileBtn) {
        regenerateProfileBtn.addEventListener('click', handleRegenerateProfile);
    }
    if (skipProfileBtn) {
        skipProfileBtn.addEventListener('click', handleSkipProfile);
    }
    if (skipStyleUrlBtn) {
        skipStyleUrlBtn.addEventListener('click', handleSkipStyleUrl);
    }
    if (processStyleUrlBtn) {
        processStyleUrlBtn.addEventListener('click', handleProcessStyleUrl);
    }
    if (generatePostBtn) {
        generatePostBtn.addEventListener('click', handleGeneratePost);
    }
    if (saveAndPostBtn) {
        saveAndPostBtn.addEventListener('click', handleSaveAndPost);
    }
    if (copyPostBtn) {
        copyPostBtn.addEventListener('click', handleCopyPost);
    }
    if (regeneratePostBtn) {
        regeneratePostBtn.addEventListener('click', handleRegeneratePost);
    }
    
    // Show/hide session cookie field when autopost checkbox is toggled
    const autopostCheckbox = document.getElementById('autopost');
    const sessionCookieGroup = document.getElementById('sessionCookieGroup');
    if (autopostCheckbox && sessionCookieGroup) {
        autopostCheckbox.addEventListener('change', function() {
            sessionCookieGroup.style.display = this.checked ? 'block' : 'none';
        });
    }
}

async function loadDefaultServiceAccount() {
    try {
        // Try to load from backend endpoint that serves the file
        const response = await fetch(`${BACKEND_URL}/api/linkedin/service-account-file`);
        if (response.ok) {
            const text = await response.text();
            agentState.service_account_json = text;
            console.log('Service account JSON loaded successfully');
        } else {
            console.warn('Could not load default service account file:', response.status, response.statusText);
        }
    } catch (error) {
        console.warn('Error loading default service account:', error);
    }
}

// Handle skip profile section
function handleSkipProfile() {
    // Show style URL section
    document.getElementById('styleUrlSection').style.display = 'block';
}

// Handle skip style URL - fetch trends directly
async function handleSkipStyleUrl() {
    await fetchTrendsOnly();
}

// Handle process style URL - fetch new tone and trends
async function handleProcessStyleUrl() {
    const styleUrlInput = document.getElementById('style_profile_url');
    const style_profile_url = styleUrlInput ? styleUrlInput.value.trim() : '';
    
    if (!style_profile_url) {
        showStatus('Please enter a style profile URL', 'error');
        return;
    }
    
    setButtonLoading(processStyleUrlBtn, true);
    
    try {
        // First, scrape style profile and get tone with streaming progress
        // IMPORTANT: We only scrape the style_profile_url, NOT the user_profile_url
        // Keywords are already saved in database, so we use those directly
        // DO NOT send user_profile_url - it's not needed and might cause the backend to scrape it
        const scrapePayload = {
            openai_api_key: agentState.openai_key,
            phantom_api_key: agentState.phantom_key,
            session_cookie: agentState.session_cookie,
            user_agent: agentState.user_agent,
            style_profile_url: style_profile_url,  // Only scrape this URL for style
            user_id: agentState.user_id,  // Required to get saved keywords from DB
            use_saved_data: true,  // Use saved keywords - don't scrape user profile
            firecrawl_api_key: agentState.firecrawl_key,
            stream: true  // Enable streaming
        };
        
        console.log('Processing style URL - payload:', {
            has_style_url: !!style_profile_url,
            has_user_id: !!agentState.user_id,
            use_saved_data: true,
            note: 'NOT sending user_profile_url to avoid scraping user profile'
        });
        
        // Use streaming endpoint for progress updates
        const scrapeResponse = await fetch(`${BACKEND_URL}/api/linkedin/run-agent`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(scrapePayload)
        });
        
        if (!scrapeResponse.ok) {
            throw new Error(`HTTP error! status: ${scrapeResponse.status}`);
        }
        
        const reader = scrapeResponse.body.getReader();
        const decoder = new TextDecoder();
        let finalResult = null;
        let buffer = ''; // Buffer for incomplete lines
        let streamEnded = false;
        
        try {
            while (true) {
                const { done, value } = await reader.read();
                
                if (done) {
                    streamEnded = true;
                    // Stream ended - process any remaining buffer
                    if (buffer.trim()) {
                        const lines = buffer.split('\n');
                        for (const line of lines) {
                            if (line.trim() && line.startsWith('data: ')) {
                                try {
                                    const data = JSON.parse(line.slice(6));
                                    if (data.done) {
                                        finalResult = data;
                                    }
                                } catch (e) {
                                    // Skip invalid JSON
                                }
                            }
                        }
                    }
                    break;
                }
                
                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop() || ''; // Keep incomplete line in buffer
                
                for (const line of lines) {
                    if (line.trim() && line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.slice(6));
                            
                            // Handle progress updates
                            if (data.progress) {
                                showStatus(data.progress, 'info');
                            }
                            
                            // Handle style notes update (can come during streaming or in final result)
                            if (data.style_notes) {
                                agentState.style_notes = data.style_notes;
                                agentState.style_url_processed = true;
                                
                                // Show tone section with the extracted tone
                                const toneSection = document.getElementById('toneSection');
                                const styleDisplay = document.getElementById('styleDisplay');
                                
                                if (styleDisplay) {
                                    const formattedTone = formatToneText(agentState.style_notes);
                                    styleDisplay.style.whiteSpace = 'pre-line';
                                    styleDisplay.textContent = formattedTone;
                                }
                                
                                if (toneSection) {
                                    toneSection.style.display = 'block';
                                    // Scroll to tone section to make it visible
                                    toneSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                                }
                            }
                            
                            // Handle final result
                            if (data.done) {
                                finalResult = data;
                                
                                // If tone is in final result but wasn't shown yet, show it now
                                if (finalResult.style_notes && !agentState.style_url_processed) {
                                    agentState.style_notes = finalResult.style_notes;
                                    agentState.style_url_processed = true;
                                    
                                    const toneSection = document.getElementById('toneSection');
                                    const styleDisplay = document.getElementById('styleDisplay');
                                    
                                    if (styleDisplay) {
                                        const formattedTone = formatToneText(agentState.style_notes);
                                        styleDisplay.style.whiteSpace = 'pre-line';
                                        styleDisplay.textContent = formattedTone;
                                    }
                                    
                                    if (toneSection) {
                                        toneSection.style.display = 'block';
                                        toneSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                                    }
                                }
                                
                                break;
                            }
                            
                            // Handle errors
                            if (data.error) {
                                throw new Error(data.error);
                            }
                        } catch (e) {
                            // Skip invalid JSON lines
                            if (e.message !== 'Unexpected end of JSON input' && !e.message.includes('JSON')) {
                                console.error('Error parsing stream:', e, 'Line:', line);
                            }
                        }
                    }
                }
                
                if (finalResult) break;
            }
        } finally {
            // Ensure reader is released
            try {
                reader.releaseLock();
            } catch (e) {
                // Already released
            }
        }
        
        // Process final result
        if (finalResult && finalResult.trends) {
            // Update trends from stream
            agentState.trends = finalResult.trends || [];
            displayTrends();
            document.getElementById('generateSection').style.display = 'block';
            showStatus('Style processed and trends fetched successfully!', 'success');
        } else if (finalResult) {
            // Fallback: fetch trends if not in result
            await fetchTrendsOnly();
        } else if (streamEnded) {
            // Stream ended but no final result - try to fetch trends anyway
            console.warn('Stream ended without final result, fetching trends separately');
            await fetchTrendsOnly();
        } else {
            showStatus('Error: Stream connection lost', 'error');
        }
    } catch (error) {
        showStatus(`Error: ${error.message}`, 'error');
    } finally {
        setButtonLoading(processStyleUrlBtn, false);
    }
}

// Fetch trends only (using saved keywords)
async function fetchTrendsOnly() {
    showStatus('Fetching trends...', 'info');
    
    try {
        const payload = {
            firecrawl_api_key: agentState.firecrawl_key,
            openai_api_key: agentState.openai_key,
            keywords: agentState.keywords
        };
        
        const response = await fetch(`${BACKEND_URL}/api/linkedin/fetch-trends-only`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });
        
        const result = await response.json();
        
        if (result.success) {
            agentState.trends = result.trends || [];
            displayTrends();
            document.getElementById('generateSection').style.display = 'block';
            showStatus('Trends fetched successfully!', 'success');
        } else {
            showStatus(`Error: ${result.message || 'Unknown error'}`, 'error');
        }
    } catch (error) {
        showStatus(`Error: ${error.message}`, 'error');
    }
}
    
    // Display trends
function displayTrends() {
    const trendsDisplay = document.getElementById('trendsDisplay');
    const trendSelect = document.getElementById('trendSelect');
    
    if (agentState.trends.length > 0) {
        const trendsHTML = agentState.trends.map((trend, index) => 
            `<div class="trend-item">
                <strong>${trend.title}</strong>
                ${trend.url ? `<a href="${trend.url}" target="_blank" class="trend-link">View source</a>` : ''}
            </div>`
        ).join('');
        trendsDisplay.innerHTML = trendsHTML;
        
        // Populate dropdown
        trendSelect.innerHTML = '<option value="">-- Select a trend --</option>' +
            agentState.trends.map(t => `<option value="${t.title}">${t.title}</option>`).join('');
    } else {
        trendsDisplay.textContent = 'No trends found';
    }
    
    // Show trends section
    document.getElementById('trendsSection').style.display = 'block';
}


async function handleGeneratePost() {
    const trendSelect = document.getElementById('trendSelect');
    const manualTopicInput = document.getElementById('manualTopic');
    const manualTopic = manualTopicInput ? manualTopicInput.value.trim() : '';
    const selectedTrend = trendSelect ? trendSelect.value : '';
    
    let topic = '';
    if (manualTopic) {
        topic = manualTopic;
        agentState.current_manual_topic = manualTopic;
        agentState.current_topic = '';
    } else if (selectedTrend) {
        topic = selectedTrend;
        agentState.current_topic = selectedTrend;
        agentState.current_manual_topic = '';
    } else {
        showStatus('Please select a trend or enter a custom topic', 'error');
        return;
    }
    
    await generatePostWithTopic(topic, manualTopic || '', selectedTrend || '', false);
}

async function generatePostWithTopic(topic, manualTopic, selectedTrend, isRegenerate = false) {
    // Disable both buttons during generation
    if (generatePostBtn) setButtonLoading(generatePostBtn, true);
    if (regeneratePostBtn) setButtonLoading(regeneratePostBtn, true);
    showStatus('Generating post...', 'info');
    
    // Save post generation arguments for regeneration
    agentState.saved_post_args = {
        topic: selectedTrend || topic,
        manual_topic: manualTopic || '',
        selected_trend: selectedTrend || '',
        style_notes: agentState.style_notes,
        keywords: [...agentState.keywords]
    };
    
    // Clear previous post and show chat box
    const postContent = document.getElementById('postContent');
    const streamingChatBox = document.getElementById('streamingChatBox');
    const chatMessages = document.getElementById('chatMessages');
    
    postContent.value = '';
    agentState.current_post = ''; // Clear the state as well
    document.getElementById('postDisplay').style.display = 'block';
    
    // Show streaming chat box, hide textarea initially
    streamingChatBox.style.display = 'block';
    postContent.style.display = 'none';
    chatMessages.innerHTML = '<div class="chat-message ai-message">Generating post...</div>';
    
    try {
        // For manual topics, don't send firecrawl_api_key to prevent trend fetching
        const payload = {
            openai_api_key: agentState.openai_key,
            topic: selectedTrend || topic,
            manual_topic: manualTopic || '',
            style_notes: agentState.style_notes,
            keywords: agentState.keywords,
            stream: true  // Enable streaming
        };
        
        // Only include firecrawl_api_key if using a trend (not manual topic)
        if (!manualTopic && selectedTrend) {
            payload.firecrawl_api_key = agentState.firecrawl_key;
        }
        
        const response = await fetch(`${BACKEND_URL}/api/linkedin/generate-post`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let fullPost = '';
        let buffer = ''; // Buffer for incomplete lines
        
        while (true) {
            const { done, value } = await reader.read();
            
            if (done) {
                // Stream ended - finalize
                if (fullPost) {
                    postContent.value = fullPost;
                    agentState.current_post = fullPost;
                    // Switch to textarea view
                    streamingChatBox.style.display = 'none';
                    postContent.style.display = 'block';
                    document.getElementById('saveSection').style.display = 'block';
                    showStatus('Post generated successfully!', 'success');
                }
                break;
            }
            
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || ''; // Keep incomplete line in buffer
            
            for (const line of lines) {
                if (line.trim() && line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.slice(6));
                        if (data.chunk) {
                            fullPost += data.chunk;
                            // Update chat box with streaming content
                            const lastMessage = chatMessages.querySelector('.ai-message:last-child');
                            if (lastMessage) {
                                lastMessage.textContent = fullPost;
                            } else {
                                const messageDiv = document.createElement('div');
                                messageDiv.className = 'chat-message ai-message';
                                messageDiv.textContent = fullPost;
                                chatMessages.appendChild(messageDiv);
                            }
                            // Auto-scroll to bottom
                            chatMessages.scrollTop = chatMessages.scrollHeight;
                        }
                        if (data.done) {
                            // Stream complete
                            postContent.value = fullPost;
                            agentState.current_post = fullPost;
                            // Switch to textarea view
                            streamingChatBox.style.display = 'none';
                            postContent.style.display = 'block';
                            document.getElementById('saveSection').style.display = 'block';
                            showStatus('Post generated successfully!', 'success');
                            // Re-enable both buttons
                            if (generatePostBtn) setButtonLoading(generatePostBtn, false);
                            if (regeneratePostBtn) setButtonLoading(regeneratePostBtn, false);
                            return;
                        }
                        if (data.error) {
                            throw new Error(data.error);
                        }
                    } catch (e) {
                        // Skip invalid JSON lines
                        if (e.message !== 'Unexpected end of JSON input' && !e.message.includes('JSON')) {
                            console.error('Error parsing stream:', e, 'Line:', line);
                        }
                    }
                }
            }
        }
        
        // Finalize if we got here
        if (fullPost) {
            postContent.value = fullPost;
        agentState.current_post = fullPost;
            streamingChatBox.style.display = 'none';
            postContent.style.display = 'block';
        document.getElementById('saveSection').style.display = 'block';
        showStatus('Post generated successfully!', 'success');
        }
    } catch (error) {
        showStatus(`Error: ${error.message}`, 'error');
    } finally {
        // Re-enable both buttons
        if (generatePostBtn) setButtonLoading(generatePostBtn, false);
        if (regeneratePostBtn) setButtonLoading(regeneratePostBtn, false);
    }
}

async function handleRegeneratePost() {
    // Regenerate works exactly like generate - use current form values
    // Simply call handleGeneratePost to reuse the same logic
    await handleGeneratePost();
}

async function handleRegenerateProfile() {
    if (!regenerateProfileBtn) return;
    
    setButtonLoading(regenerateProfileBtn, true);
    showStatus('Regenerating keywords and tone from your LinkedIn profile... This may take a few minutes.', 'info');
    
    try {
        const payload = {
            user_id: agentState.user_id,
            openai_api_key: agentState.openai_key,
            phantom_api_key: agentState.phantom_key,
            session_cookie: agentState.session_cookie,
            user_agent: agentState.user_agent,
            stream: true  // Enable streaming
        };
        
        const response = await fetch(`${BACKEND_URL}/api/linkedin/regenerate-user-data`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let finalResult = null;
        let streamEnded = false;
        
        try {
            while (true) {
                const { done, value } = await reader.read();
                
                if (done) {
                    streamEnded = true;
                    // Process any remaining buffer
                    if (buffer.trim()) {
                        const lines = buffer.split('\n');
                        for (const line of lines) {
                            if (line.trim() && line.startsWith('data: ')) {
                                try {
                                    const data = JSON.parse(line.slice(6));
                                    if (data.done) {
                                        finalResult = data;
                                    }
                                } catch (e) {
                                    // Skip invalid JSON
                                }
                            }
                        }
                    }
                    break;
                }
                
                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop() || '';
                
                for (const line of lines) {
                    if (line.trim() && line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.slice(6));
                            
                            // Handle progress updates
                            if (data.progress) {
                                showStatus(data.progress, 'info');
                            }
                            
                            // Handle final result
                            if (data.done) {
                                finalResult = data;
                                break;
                            }
                            
                            // Handle errors
                            if (data.error) {
                                throw new Error(data.error);
                            }
                        } catch (e) {
                            if (e.message !== 'Unexpected end of JSON input' && !e.message.includes('JSON')) {
                                console.error('Error parsing stream:', e, 'Line:', line);
                            }
                        }
                    }
                }
                
                if (finalResult) break;
            }
        } finally {
            try {
                reader.releaseLock();
            } catch (e) {
                // Already released
            }
        }
        
        if (finalResult && finalResult.keywords !== undefined) {
            const result = finalResult;
            // Update agentState
            agentState.keywords = result.keywords || [];
            agentState.style_notes = result.tone_of_writing || '';
            agentState.has_saved_data = agentState.keywords.length > 0 || agentState.style_notes.length > 0;
            
            showStatus('Keywords and tone regenerated successfully!', 'success');
            
            // Update global window object for consistency
            if (window.USER_LINKEDIN_DATA) {
                window.USER_LINKEDIN_DATA.keywords = agentState.keywords;
                window.USER_LINKEDIN_DATA.tone_of_writing = agentState.style_notes;
                window.USER_LINKEDIN_DATA.success = true;
            } else {
                window.USER_LINKEDIN_DATA = {
                    success: true,
                    keywords: agentState.keywords,
                    tone_of_writing: agentState.style_notes
                };
            }
            
            // Update UI - check if profile section exists or needs to be created
            const profileSection = document.getElementById('profileDataSection');
            const savedKeywordsDisplay = document.getElementById('savedKeywordsDisplay');
            const savedToneDisplay = document.getElementById('savedToneDisplay');
            
            // If profile section doesn't exist (was showing error), update it
            if (profileSection && profileSection.style.background.includes('239, 68, 68')) {
                // Change from error state to success state
                profileSection.style.background = 'rgba(59, 130, 246, 0.05)';
                profileSection.style.border = '1px solid rgba(59, 130, 246, 0.2)';
                const title = profileSection.querySelector('.section-title');
                const desc = profileSection.querySelector('.section-description');
                if (title) {
                    title.textContent = 'Step 1: Your Profile Data';
                    title.style.color = '';
                }
                if (desc) {
                    desc.textContent = 'Your saved keywords of interest and writing tone extracted from your LinkedIn profile';
                    desc.style.color = '';
                }
                
                // Add results grid if it doesn't exist
                if (!profileSection.querySelector('.results-grid')) {
                    const formActions = profileSection.querySelector('.form-actions');
                    const resultsGrid = document.createElement('div');
                    resultsGrid.className = 'results-grid';
                    resultsGrid.innerHTML = `
                        <div class="result-card">
                            <h3 class="result-title">Keywords of Interest</h3>
                            <div id="savedKeywordsDisplay" class="result-content"></div>
                        </div>
                        <div class="result-card">
                            <h3 class="result-title">Writing Tone</h3>
                            <div id="savedToneDisplay" class="result-content"></div>
                        </div>
                    `;
                    profileSection.insertBefore(resultsGrid, formActions);
                    
                    // Add skip button if it doesn't exist
                    if (!document.getElementById('skipProfileBtn')) {
                        const skipBtn = document.createElement('button');
                        skipBtn.type = 'button';
                        skipBtn.id = 'skipProfileBtn';
                        skipBtn.className = 'btn btn-primary';
                        skipBtn.innerHTML = '<span class="btn-text">Skip</span>';
                        skipBtn.addEventListener('click', handleSkipProfile);
                        formActions.appendChild(skipBtn);
                    }
                }
            }
            
            // Update keywords and tone displays
            if (savedKeywordsDisplay) {
                if (agentState.keywords.length > 0) {
                    const formattedKeywords = formatKeywords(agentState.keywords);
                    savedKeywordsDisplay.innerHTML = '<ul class="keyword-list">' + 
                        formattedKeywords.map(k => `<li>${k}</li>`).join('') + 
                        '</ul>';
    } else {
                    savedKeywordsDisplay.textContent = 'No keywords extracted';
                }
            }
            
            if (savedToneDisplay) {
                const formattedTone = formatToneText(agentState.style_notes);
                savedToneDisplay.style.whiteSpace = 'pre-line';
                savedToneDisplay.textContent = formattedTone || 'No tone data available';
            }
            
            showStatus('Keywords and tone regenerated successfully!', 'success');
            
            // Show style URL section after regeneration
            document.getElementById('styleUrlSection').style.display = 'block';
        } else if (streamEnded) {
            // Stream ended but no final result - might have been an error
            showStatus('Regeneration completed but no data was received. Please try again.', 'error');
        } else {
            showStatus('Error: No result received from stream', 'error');
        }
    } catch (error) {
        showStatus(`Error: ${error.message}`, 'error');
    } finally {
        setButtonLoading(regenerateProfileBtn, false);
    }
}

function displayPost(post) {
    const postContent = document.getElementById('postContent');
    postContent.value = post;
    document.getElementById('postDisplay').style.display = 'block';
}

function handleCopyPost() {
    const postContent = document.getElementById('postContent');
    const text = postContent.value || postContent.textContent || '';
    navigator.clipboard.writeText(text).then(() => {
        showStatus('Post copied to clipboard!', 'success');
    }).catch(err => {
        showStatus('Failed to copy: ' + err.message, 'error');
    });
}

async function handleSaveAndPost() {
    if (!agentState.current_post) {
        showStatus('No post to save. Please generate a post first.', 'error');
        return;
    }
    
    const saveToSheet = document.getElementById('saveToSheet').checked;
    const autopost = document.getElementById('autopost').checked;
    
    if (!saveToSheet && !autopost) {
        showStatus('Please select at least one option (Save to Sheet or Autopost)', 'error');
        return;
    }
    
    // Ensure service account JSON is loaded
    if (saveToSheet && !agentState.service_account_json) {
        showStatus('Loading service account file...', 'info');
        await loadDefaultServiceAccount();
        if (!agentState.service_account_json) {
            showStatus('Service account JSON is required for saving. Please ensure the file exists.', 'error');
            return;
        }
    }
    
    // Ensure sheet URL is set
    if (saveToSheet && !agentState.sheet_url) {
        showStatus('Sheet URL is missing. Please set GOOGLE_SHEET_URL in .env file', 'error');
        return;
    }
    
    // Get session cookie from form if autoposting
    if (autopost) {
        const sessionCookieInput = document.getElementById('autopost_session_cookie');
        const sessionCookieFromForm = sessionCookieInput ? sessionCookieInput.value.trim() : '';
        
        // Use form input if provided, otherwise reuse from run agent step
        if (sessionCookieFromForm) {
            agentState.session_cookie = sessionCookieFromForm;
        } else if (!agentState.session_cookie) {
            showStatus('LinkedIn session cookie is required for autopost. Please set LINKEDIN_SESSION_COOKIE in .env file.', 'error');
            return;
        }
        // If agentState.session_cookie exists from run agent, reuse it
    }
    
    setButtonLoading(saveAndPostBtn, true);
    showStatus('Saving and posting...', 'info');
    
    const saveResults = document.getElementById('saveResults');
    saveResults.innerHTML = '';
    
    try {
        // Save to sheet if requested
        if (saveToSheet) {
            if (!agentState.sheet_url || !agentState.service_account_json) {
                showStatus('Sheet URL and service account JSON are required for saving', 'error');
                setButtonLoading(saveAndPostBtn, false);
                return;
            }
            
            const saveResponse = await fetch(`${BACKEND_URL}/api/linkedin/save-to-sheet`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    sheet_url: agentState.sheet_url,
                    content: agentState.current_post,
                    service_account_json: agentState.service_account_json
                })
            });
            
            const saveResult = await saveResponse.json();
            if (saveResult.success) {
                saveResults.innerHTML += `<div class="result-message success">${saveResult.message}</div>`;
            } else {
                saveResults.innerHTML += `<div class="result-message error">Save failed: ${saveResult.message}</div>`;
            }
        }
        
        // Autopost if requested
        if (autopost) {
            if (!agentState.session_cookie) {
                showStatus('Session cookie is required for autopost', 'error');
                setButtonLoading(saveAndPostBtn, false);
                return;
            }
            
            const clearSheetAfterPost = document.getElementById('clearSheetAfterPost').checked;
            
            const autopostPayload = {
                phantom_api_key: agentState.phantom_key,
                session_cookie: agentState.session_cookie,
                user_agent: agentState.user_agent,
                sheet_url: agentState.sheet_url,
                clear_sheet_after_post: clearSheetAfterPost
            };
            
            // Include service account JSON if clearing sheet
            if (clearSheetAfterPost && agentState.service_account_json) {
                autopostPayload.service_account_json = agentState.service_account_json;
            }
            
            const autopostResponse = await fetch(`${BACKEND_URL}/api/linkedin/autopost`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(autopostPayload)
            });
            
            const autopostResult = await autopostResponse.json();
            if (autopostResult.success) {
                saveResults.innerHTML += `<div class="result-message success">post will be posted within 3 minutes</div>`;
            } else {
                saveResults.innerHTML += `<div class="result-message error">Autopost failed: ${autopostResult.message}</div>`;
            }
        }
        
        showStatus('Save and post operations completed', 'success');
    } catch (error) {
        showStatus(`Error: ${error.message}`, 'error');
    } finally {
        setButtonLoading(saveAndPostBtn, false);
    }
}

function setButtonLoading(button, loading) {
    if (!button) return; // Guard against null buttons
    
    const btnText = button.querySelector('.btn-text');
    const btnLoader = button.querySelector('.btn-loader');
    
    if (!btnText || !btnLoader) return; // Guard against missing elements
    
    if (loading) {
        button.disabled = true;
        if (btnText) btnText.style.display = 'none';
        if (btnLoader) btnLoader.style.display = 'inline';
    } else {
        button.disabled = false;
        if (btnText) btnText.style.display = 'inline';
        if (btnLoader) btnLoader.style.display = 'none';
    }
}

function showStatus(message, type = 'info') {
    const statusMessages = document.getElementById('statusMessages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `status-message status-${type}`;
    messageDiv.textContent = message;
    
    statusMessages.appendChild(messageDiv);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        messageDiv.remove();
    }, 5000);
    
    // Scroll to message
    messageDiv.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}


