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
    service_account_json: null,  // Will be loaded from backend
    keywords: [],
    style_notes: '',
    trends: [],
    current_post: '',
    current_topic: '', // Store current topic for regeneration
    current_manual_topic: '' // Store manual topic if used
};

// DOM Elements
const runAgentBtn = document.getElementById('runAgentBtn');
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
    
    // Set up post content editor listener
    const postContent = document.getElementById('postContent');
    if (postContent) {
        postContent.addEventListener('input', function() {
            agentState.current_post = this.value;
        });
    }
});

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
    runAgentBtn.addEventListener('click', handleRunAgent);
    generatePostBtn.addEventListener('click', handleGeneratePost);
    saveAndPostBtn.addEventListener('click', handleSaveAndPost);
    copyPostBtn.addEventListener('click', handleCopyPost);
    regeneratePostBtn.addEventListener('click', handleRegeneratePost);
    
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

async function handleRunAgent() {
    const form = document.getElementById('configForm');
    const formData = new FormData(form);
    
    // Get style profile URL from form (optional)
    let style_profile_url = formData.get('style_profile_url') || '';
    
    // Get user profile URL from agentState (from .env/user profile)
    const user_profile_url = agentState.user_linkedin_url;
    
    // Validate required fields
    if (!user_profile_url) {
        showStatus('User LinkedIn URL is missing. Please set it in your account profile or .env file', 'error');
        return;
    }
    
    // If style profile URL is not provided, use user's profile URL as default
    if (!style_profile_url || style_profile_url.trim() === '') {
        style_profile_url = user_profile_url;
        showStatus('No style profile URL provided. Using your own profile as style reference.', 'info');
    }
    
    // Validate session cookie is present (from .env)
    if (!agentState.session_cookie) {
        showStatus('LinkedIn session cookie is missing. Please set LINKEDIN_SESSION_COOKIE in .env file', 'error');
        return;
    }
    
    // Validate API keys are present (from .env)
    if (!agentState.openai_key || !agentState.phantom_key || !agentState.firecrawl_key || 
        !agentState.user_agent) {
        showStatus('API keys are missing. Please configure them in .env file', 'error');
        return;
    }
    
    // Show loading state
    setButtonLoading(runAgentBtn, true);
    showStatus('Running agent... This may take a few minutes.', 'info');
    
    try {
        const payload = {
            openai_api_key: agentState.openai_key,
            phantom_api_key: agentState.phantom_key,
            firecrawl_api_key: agentState.firecrawl_key,
            session_cookie: agentState.session_cookie,
            user_agent: agentState.user_agent,
            user_profile_url: user_profile_url,
            style_profile_url: style_profile_url,
            sheet_url: agentState.sheet_url
        };
        
        if (agentState.service_account_json) {
            payload.service_account_json = agentState.service_account_json;
        }
        
        const response = await fetch(`${BACKEND_URL}/api/linkedin/run-agent`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });
        
        const result = await response.json();
        
        if (result.success) {
            agentState.keywords = result.keywords || [];
            agentState.style_notes = result.style_notes || '';
            agentState.trends = result.trends || [];
            
            displayResults();
            showStatus('Agent completed successfully!', 'success');
        } else {
            showStatus(`Error: ${result.message || 'Unknown error'}`, 'error');
        }
    } catch (error) {
        showStatus(`Error: ${error.message}`, 'error');
    } finally {
        setButtonLoading(runAgentBtn, false);
    }
}

function displayResults() {
    // Display keywords
    const keywordsDisplay = document.getElementById('keywordsDisplay');
    if (agentState.keywords.length > 0) {
        keywordsDisplay.innerHTML = '<ul class="keyword-list">' + 
            agentState.keywords.map(k => `<li>${k}</li>`).join('') + 
            '</ul>';
    } else {
        keywordsDisplay.textContent = 'No keywords extracted';
    }
    
    // Display style notes
    const styleDisplay = document.getElementById('styleDisplay');
    styleDisplay.textContent = agentState.style_notes || 'No style notes available';
    
    // Display trends
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
    
    // Show results section
    document.getElementById('resultsSection').style.display = 'block';
    document.getElementById('generateSection').style.display = 'block';
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
    const buttonToDisable = isRegenerate ? regeneratePostBtn : generatePostBtn;
    setButtonLoading(buttonToDisable, true);
    showStatus('Generating post...', 'info');
    
    // Clear previous post and show textarea
    const postContent = document.getElementById('postContent');
    postContent.value = '';
    document.getElementById('postDisplay').style.display = 'block';
    
    try {
        const payload = {
            openai_api_key: agentState.openai_key,
            topic: selectedTrend || topic,
            manual_topic: manualTopic || '',
            style_notes: agentState.style_notes,
            keywords: agentState.keywords,
            firecrawl_api_key: agentState.firecrawl_key,
            stream: true  // Enable streaming
        };
        
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
        
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            
            const chunk = decoder.decode(value);
            const lines = chunk.split('\n');
            
            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.slice(6));
                        if (data.chunk) {
                            fullPost += data.chunk;
                            postContent.value = fullPost;
                            // Auto-scroll to bottom
                            postContent.scrollTop = postContent.scrollHeight;
                        }
                        if (data.done) {
                            agentState.current_post = fullPost;
                            document.getElementById('saveSection').style.display = 'block';
                            showStatus('Post generated successfully!', 'success');
                            setButtonLoading(buttonToDisable, false);
                            return;
                        }
                        if (data.error) {
                            throw new Error(data.error);
                        }
                    } catch (e) {
                        // Skip invalid JSON lines
                        if (e.message !== 'Unexpected end of JSON input') {
                            console.error('Error parsing stream:', e);
                        }
                    }
                }
            }
        }
        
        // Finalize
        agentState.current_post = fullPost;
        document.getElementById('saveSection').style.display = 'block';
        showStatus('Post generated successfully!', 'success');
    } catch (error) {
        showStatus(`Error: ${error.message}`, 'error');
    } finally {
        setButtonLoading(buttonToDisable, false);
    }
}

async function handleRegeneratePost() {
    if (!agentState.current_topic && !agentState.current_manual_topic) {
        showStatus('No previous topic found. Please generate a post first.', 'error');
        return;
    }
    
    // Use stored topic - determine which one was used
    let topic = '';
    let manualTopic = '';
    let selectedTrend = '';
    
    if (agentState.current_manual_topic) {
        // Manual topic was used
        topic = agentState.current_manual_topic;
        manualTopic = agentState.current_manual_topic;
        selectedTrend = '';
    } else if (agentState.current_topic) {
        // Trend was selected
        topic = agentState.current_topic;
        manualTopic = '';
        selectedTrend = agentState.current_topic;
    } else {
        showStatus('No previous topic found. Please generate a post first.', 'error');
        return;
    }
    
    await generatePostWithTopic(topic, manualTopic, selectedTrend, true);
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
                saveResults.innerHTML += `<div class="result-message success">Autopost triggered successfully!${clearSheetAfterPost ? ' Sheet cleared after posting.' : ''}</div>`;
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
    const btnText = button.querySelector('.btn-text');
    const btnLoader = button.querySelector('.btn-loader');
    
    if (loading) {
        button.disabled = true;
        btnText.style.display = 'none';
        btnLoader.style.display = 'inline';
    } else {
        button.disabled = false;
        btnText.style.display = 'inline';
        btnLoader.style.display = 'none';
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

