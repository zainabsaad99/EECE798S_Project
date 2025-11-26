const BACKEND_URL = window.location.protocol + '//' + window.location.hostname + ':5000';

const chatState = {
    openaiKey: window.ENV_CONFIG?.openai_api_key || '',
    phantomKey: window.ENV_CONFIG?.phantombuster_api_key || '',
    firecrawlKey: window.ENV_CONFIG?.firecrawl_api_key || '',
    sessionCookie: '', // Always ask user for cookie instead of using env variable
    userAgent: window.ENV_CONFIG?.user_agent || '',
    sheetUrl: window.ENV_CONFIG?.google_sheet_url || '',
    userLinkedinUrl: window.ENV_CONFIG?.user_linkedin_url || '',
    userId: window.ENV_CONFIG?.user_id || '',
    serviceAccountJson: null,
    availableKeywords: [],
    selectedKeywords: [],
    styleNotes: '',
    styleUrlProcessed: false,
    trends: [],
    selectedTrend: '',
    manualTopic: '',
    postContent: '',
    savedPostArgs: null,
    step: 'keywords',
    awaitingResponse: null, // What we're waiting for: 'keywords', 'tone', 'trend', etc.
    pendingSaveIntent: null // Store save/post intent when waiting for cookie: { saveToSheet: bool, autopost: bool }
};

const elements = {};

document.addEventListener('DOMContentLoaded', async () => {
    cacheDomReferences();
    hydrateFromUserData();
    bindEventListeners();
    await loadDefaultServiceAccount();
    loadLinkedInPostCount();
    initChat();
});

function cacheDomReferences() {
    elements.chatMessages = document.getElementById('chatMessages');
    elements.userInputForm = document.getElementById('userInputForm');
    elements.userInput = document.getElementById('userInput');
    elements.statusMessages = document.getElementById('statusMessages');
}

function hydrateFromUserData() {
    if (window.USER_LINKEDIN_DATA && window.USER_LINKEDIN_DATA.success) {
        const formattedKeywords = formatKeywords(window.USER_LINKEDIN_DATA.keywords || []);
        chatState.availableKeywords = [...formattedKeywords];
        chatState.selectedKeywords = [...formattedKeywords];
        chatState.styleNotes = formatToneText(window.USER_LINKEDIN_DATA.tone_of_writing || '');
    }
}

function bindEventListeners() {
    elements.userInputForm?.addEventListener('submit', handleUserMessage);
    elements.userInput?.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            elements.userInputForm?.dispatchEvent(new Event('submit'));
        }
    });
    // Keep click handlers for optional shortcuts
    elements.chatMessages?.addEventListener('click', handleChatClick);
}

function initChat() {
    if (!chatState.availableKeywords.length) {
        showStatus('No keywords available. Please regenerate from the classic LinkedIn agent page.', 'error');
        addAgentMessage('I couldn\'t find any keywords. Please set up your LinkedIn profile data first.');
        return;
    }

    // Start conversation naturally
    addAgentMessage('Hi! I\'m here to help you create a LinkedIn post. Let me start by checking what I know about your interests.');
    
    // Show keywords as a visual reference, but ask user to confirm or regenerate
    addAgentMessage(`I found these keywords from your profile:\n\n${chatState.availableKeywords.map((k, i) => `${i + 1}. ${k}`).join('\n')}\n\nWould you like to:\n• Type "confirm" or "yes" to use these keywords\n• Type "regenerate" to regenerate keywords from your LinkedIn profile`);
    
    chatState.awaitingResponse = 'keywords';
    updateInputPlaceholder('Type "confirm" or "regenerate"...');
}

function addAgentMessage(content, isInteractive = false) {
    if (!elements.chatMessages) return;
    const msg = document.createElement('div');
    msg.className = `chat-message agent ${isInteractive ? 'interactive' : ''}`;
    
    // Support basic markdown-like formatting
    const formatted = content
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\n/g, '<br>');
    
    msg.innerHTML = formatted;
    elements.chatMessages.appendChild(msg);
    elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
    return msg;
}

function addUserMessage(content) {
    if (!elements.chatMessages) return;
    const msg = document.createElement('div');
    msg.className = 'chat-message user';
    msg.textContent = content;
    elements.chatMessages.appendChild(msg);
    elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
}

function updateInputPlaceholder(text) {
    if (elements.userInput) {
        elements.userInput.placeholder = text;
    }
}

function handleUserMessage(event) {
    event.preventDefault();
    const message = elements.userInput.value.trim();
    if (!message) return;
    
    addUserMessage(message);
    elements.userInput.value = '';
    
    // Process based on what we're waiting for
    if (chatState.awaitingResponse === 'keywords') {
        processKeywordsResponse(message);
    } else if (chatState.awaitingResponse === 'tone') {
        processToneResponse(message);
    } else if (chatState.awaitingResponse === 'trend') {
        processTrendResponse(message);
    } else if (chatState.awaitingResponse === 'save') {
        processSaveResponse(message);
    } else if (chatState.awaitingResponse === 'cookie') {
        processCookieResponse(message);
    } else {
        // General response - try to understand intent
        processGeneralMessage(message);
    }
}

function processKeywordsResponse(message) {
    const lower = message.toLowerCase().trim();
    
    // Check for confirmation
    if (lower.match(/^(yes|yep|yeah|ok|okay|confirm|use these|keep|proceed|continue)$/)) {
        chatState.selectedKeywords = [...chatState.availableKeywords];
        addAgentMessage('Great! I\'ll use these keywords. Moving on to the writing tone...');
        proceedToToneStep();
        return;
    }
    
    // Check for regenerate
    if (lower.match(/^(regenerate|regenerate keywords|new keywords|refresh keywords)$/)) {
        handleRegenerateKeywords();
        return;
    }
    
    // If they type something else, remind them of options
    addAgentMessage('Please type either:\n• "confirm" or "yes" to use the current keywords\n• "regenerate" to regenerate keywords from your LinkedIn profile');
}

async function handleRegenerateKeywords() {
    addUserMessage('regenerate');
    addAgentMessage('Regenerating keywords from your LinkedIn profile... This may take a few minutes.');
    
    try {
        const payload = {
            user_id: chatState.userId,
            openai_api_key: chatState.openaiKey,
            phantom_api_key: chatState.phantomKey,
            session_cookie: chatState.sessionCookie,
            user_agent: chatState.userAgent,
            stream: true
        };
        
        const response = await fetch(`${BACKEND_URL}/api/linkedin/regenerate-user-data`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error ${response.status}`);
        }
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let finalResult = null;
        let progressMsg = null;
        
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';
            
            for (const line of lines) {
                if (!line.startsWith('data: ')) continue;
                try {
                    const data = JSON.parse(line.slice(6));
                    
                    if (data.progress) {
                        if (!progressMsg) {
                            progressMsg = addAgentMessage('Processing...');
                        } else {
                            progressMsg.innerHTML = `Processing: ${data.progress}`;
                        }
                    }
                    
                    if (data.done) {
                        finalResult = data;
                    }
                    
                    if (data.error) {
                        throw new Error(data.error);
                    }
                } catch (err) {
                    console.warn('Stream parse error', err);
                }
            }
        }
        
        if (progressMsg) progressMsg.remove();
        
        if (finalResult && finalResult.keywords) {
            const formattedKeywords = formatKeywords(finalResult.keywords || []);
            chatState.availableKeywords = [...formattedKeywords];
            chatState.selectedKeywords = [...formattedKeywords];
            
            if (finalResult.tone_of_writing) {
                chatState.styleNotes = formatToneText(finalResult.tone_of_writing);
            }
            
            addAgentMessage(`Great! I've regenerated your keywords:\n\n${chatState.availableKeywords.map((k, i) => `${i + 1}. ${k}`).join('\n')}\n\nType "confirm" to use these keywords, or "regenerate" to try again.`);
        } else {
            throw new Error('No keywords received from regeneration');
        }
    } catch (error) {
        addAgentMessage(`Sorry, I couldn't regenerate keywords: ${error.message}. Please try again or type "confirm" to use the current keywords.`);
    }
}

function proceedToToneStep() {
    chatState.step = 'tone';
    chatState.awaitingResponse = 'tone';
    
    if (chatState.styleNotes) {
        addAgentMessage(`I have your current writing tone saved. Would you like to:\n• Keep using your current tone (type "use my tone" or "keep")\n• Use a different LinkedIn profile's style (type the LinkedIn profile URL)\n• Skip and use default (type "skip")`);
    } else {
        addAgentMessage(`I don't have a saved writing tone yet. Would you like to:\n• Provide a LinkedIn profile URL to extract a writing style (just paste the URL)\n• Skip and use default (type "skip")`);
    }
    updateInputPlaceholder('Type your choice about tone...');
}

function processToneResponse(message) {
    const lower = message.toLowerCase().trim();
    
    // Check for "use my tone" or "keep"
    if (lower.match(/^(use my tone|keep|use saved|use current|yes|ok)$/)) {
        if (!chatState.styleNotes) {
            addAgentMessage('I don\'t have a saved tone. Please provide a LinkedIn profile URL or type "skip".');
            return;
        }
        addAgentMessage('Perfect! I\'ll use your saved tone. Let me fetch some trending topics for you...');
        chatState.step = 'trends';
        fetchTrendsOnly();
        return;
    }
    
    // Check for "skip"
    if (lower.match(/^(skip|no|none|default)$/)) {
        addAgentMessage('Got it! I\'ll proceed without a specific tone. Let me fetch some trending topics...');
        chatState.step = 'trends';
        fetchTrendsOnly();
        return;
    }
    
    // Check if it's a URL
    if (message.match(/^https?:\/\/(www\.)?linkedin\.com\/in\//i)) {
        addAgentMessage('Great! I\'ll extract the writing style from that profile. This may take a minute...');
        handleProcessToneUrl(message);
        return;
    }
    
    // If it looks like they're trying to provide a URL but it's incomplete
    if (lower.includes('linkedin') || lower.includes('url') || lower.includes('profile')) {
        addAgentMessage('Please paste the full LinkedIn profile URL (e.g., https://www.linkedin.com/in/username) or type "skip" to proceed.');
        return;
    }
    
    addAgentMessage('I didn\'t understand that. Please type:\n• "use my tone" to keep your saved tone\n• A LinkedIn profile URL to extract a different style\n• "skip" to proceed without a specific tone');
}

async function handleProcessToneUrl(url) {
    const styleProfileUrl = url.trim();
    
    const payload = {
        openai_api_key: chatState.openaiKey,
        phantom_api_key: chatState.phantomKey,
        session_cookie: chatState.sessionCookie,
        user_agent: chatState.userAgent,
        style_profile_url: styleProfileUrl,
        user_id: chatState.userId,
        use_saved_data: true,
        firecrawl_api_key: chatState.firecrawlKey,
        stream: true
    };
    
    try {
        const response = await fetch(`${BACKEND_URL}/api/linkedin/run-agent`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error ${response.status}`);
        }
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let finalResult = null;
        let progressMsg = null;
        
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';
            
            for (const line of lines) {
                if (!line.startsWith('data: ')) continue;
                try {
                    const data = JSON.parse(line.slice(6));
                    
                    if (data.progress) {
                        if (!progressMsg) {
                            progressMsg = addAgentMessage('Processing...');
                        } else {
                            progressMsg.innerHTML = `Processing: ${data.progress}`;
                        }
                    }
                    if (data.style_notes) {
                        chatState.styleNotes = formatToneText(data.style_notes);
                    }
                    if (data.trends) {
                        finalResult = data;
                    }
                    if (data.done) {
                        finalResult = data;
                    }
                    if (data.error) {
                        throw new Error(data.error);
                    }
                } catch (err) {
                    console.warn('Stream parse error', err);
                }
            }
        }
        
        if (progressMsg) progressMsg.remove();
        addAgentMessage('Great! I\'ve extracted the writing style. Now let me fetch some trending topics...');
        chatState.step = 'trends';
        
        if (finalResult && finalResult.trends) {
            chatState.trends = finalResult.trends;
            showTrendsAndAsk();
        } else {
            await fetchTrendsOnly();
        }
    } catch (error) {
        addAgentMessage(`Sorry, I couldn't extract the tone: ${error.message}. Would you like to try another URL or type "skip"?`);
    }
}

async function fetchTrendsOnly() {
    if (!chatState.selectedKeywords.length) {
        addAgentMessage('I need your keywords first. Let me go back to that step.');
        chatState.step = 'keywords';
        chatState.awaitingResponse = 'keywords';
        return;
    }
    
    addAgentMessage('Searching for the latest trends based on your keywords...');
    
    try {
        const response = await fetch(`${BACKEND_URL}/api/linkedin/fetch-trends-only`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                firecrawl_api_key: chatState.firecrawlKey,
                openai_api_key: chatState.openaiKey,
                keywords: chatState.selectedKeywords
            })
        });
        
        const result = await response.json();
        if (!result.success) {
            throw new Error(result.message || 'Unknown error');
        }
        
        chatState.trends = result.trends || [];
        showTrendsAndAsk();
    } catch (error) {
        addAgentMessage(`Sorry, I couldn't fetch trends: ${error.message}. Would you like to provide a custom topic instead?`);
        chatState.awaitingResponse = 'trend';
        updateInputPlaceholder('Type a custom topic for your post...');
    }
}

function showTrendsAndAsk() {
    if (!chatState.trends.length) {
        addAgentMessage('I couldn\'t find any trends. Please provide a custom topic for your post.');
        chatState.awaitingResponse = 'trend';
        updateInputPlaceholder('Type a topic for your post...');
        return;
    }
    
    addAgentMessage(`Here are some trending topics I found:\n\n${chatState.trends.map((t, i) => `${i + 1}. ${t.title}`).join('\n')}\n\nYou can:\n• Type the number (1-${chatState.trends.length}) to select a trend\n• Type the trend name\n• Type a custom topic of your own`);
    
    chatState.awaitingResponse = 'trend';
    updateInputPlaceholder('Type the number, trend name, or your custom topic...');
}

function processTrendResponse(message) {
    const lower = message.toLowerCase().trim();
    
    // Check if it's a number
    const num = parseInt(message.trim());
    if (!isNaN(num) && num >= 1 && num <= chatState.trends.length) {
        const selectedTrend = chatState.trends[num - 1];
        chatState.selectedTrend = selectedTrend.title;
        chatState.manualTopic = '';
        addUserMessage(message);
        addAgentMessage(`Perfect! I'll create a post about "${selectedTrend.title}". Let me generate it for you...`);
        chatState.step = 'generate';
        handleGeneratePost(false);
        return;
    }
    
    // Check if it matches a trend title
    const matchingTrend = chatState.trends.find(t => 
        t.title.toLowerCase() === lower || 
        lower.includes(t.title.toLowerCase()) ||
        t.title.toLowerCase().includes(lower)
    );
    
    if (matchingTrend) {
        chatState.selectedTrend = matchingTrend.title;
        chatState.manualTopic = '';
        addUserMessage(message);
        addAgentMessage(`Great! I'll create a post about "${matchingTrend.title}". Let me generate it for you...`);
        chatState.step = 'generate';
        handleGeneratePost(false);
        return;
    }
    
    // Otherwise, treat as custom topic
    chatState.manualTopic = message;
    chatState.selectedTrend = '';
    addUserMessage(message);
    addAgentMessage(`Got it! I'll create a post about "${message}". Let me generate it for you...`);
    chatState.step = 'generate';
    handleGeneratePost(false);
}

async function handleGeneratePost(isRegenerate) {
    const topic = chatState.selectedTrend || chatState.manualTopic;
    if (!topic) {
        addAgentMessage('I need a topic first. Please select a trend or provide a custom topic.');
        return;
    }
    
    const isManual = Boolean(chatState.manualTopic);
    const payload = {
        openai_api_key: chatState.openaiKey,
        topic: chatState.selectedTrend || chatState.manualTopic,
        manual_topic: chatState.manualTopic,
        style_notes: chatState.styleNotes,
        keywords: chatState.selectedKeywords,
        stream: true
    };
    
    if (!isManual && chatState.selectedTrend) {
        payload.firecrawl_api_key = chatState.firecrawlKey;
    }
    
    chatState.savedPostArgs = { ...payload };
    
    try {
        const response = await fetch(`${BACKEND_URL}/api/linkedin/generate-post`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error ${response.status}`);
        }
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let fullPost = '';
        
        // Show streaming message
        const streamingMsg = addAgentMessage('Generating your post...');
        
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';
            
            for (const line of lines) {
                if (!line.startsWith('data: ')) continue;
                try {
                    const data = JSON.parse(line.slice(6));
                    if (data.chunk) {
                        fullPost += data.chunk;
                        streamingMsg.innerHTML = `Generating your post...<br><br><div style="opacity: 0.7; margin-top: 0.5rem;">${fullPost.replace(/\n/g, '<br>')}</div>`;
                        elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
                    }
                    if (data.done) {
                        break;
                    }
                    if (data.error) {
                        throw new Error(data.error);
                    }
                } catch (err) {
                    console.warn('Stream parse error', err);
                }
            }
        }
        
        if (!fullPost) {
            throw new Error('No content received.');
        }
        
        chatState.postContent = fullPost;
        streamingMsg.remove();
        
        // Show the final post
        addAgentMessage('Here\'s your generated post:');
        const postMsg = addAgentMessage('', true);
        const postDiv = document.createElement('div');
        postDiv.className = 'chat-post-content';
        postDiv.textContent = fullPost;
        postMsg.appendChild(postDiv);
        
        addAgentMessage('What would you like to do next?\n• Type "regenerate" to create a new version\n• Type "copy" to copy it to clipboard\n• Type "save" or "post" to save and/or publish it\n• Or just tell me what you\'d like to change');
        
        chatState.step = 'post';
        chatState.awaitingResponse = null;
        updateInputPlaceholder('What would you like to do with this post?');
    } catch (error) {
        addAgentMessage(`Sorry, I couldn't generate the post: ${error.message}. Would you like to try again?`);
    }
}

function processGeneralMessage(message) {
    const lower = message.toLowerCase().trim();
    
    if (chatState.step === 'post') {
        if (lower.match(/^(regenerate|new|again|redo)$/)) {
            addUserMessage(message);
            addAgentMessage('Regenerating the post...');
            handleGeneratePost(true);
            return;
        }
        
        if (lower.match(/^(copy|clipboard)$/)) {
            handleCopyPost();
            return;
        }
        
        if (lower.match(/^(save|post|publish|autopost)$/)) {
            addUserMessage(message);
            askSaveOptions();
            return;
        }
        
        // Otherwise, treat as feedback for regeneration
        addUserMessage(message);
        addAgentMessage('I\'ll regenerate the post with your feedback in mind...');
        // Could enhance this to pass feedback to regeneration
        handleGeneratePost(true);
    } else {
        addAgentMessage('I\'m not sure what you mean. Could you clarify?');
    }
}

function askSaveOptions() {
    addAgentMessage('How would you like to save/publish this post?\n\nType:\n• "save" to save to Google Sheet\n• "post" to autopost via PhantomBuster (requires LinkedIn session cookie)\n• "both" to do both\n• Or describe what you want');
    
    chatState.awaitingResponse = 'save';
    updateInputPlaceholder('Type your save/post preferences...');
}

function processSaveResponse(message) {
    const lower = message.toLowerCase().trim();
    
    const saveToSheet = lower.includes('save') || lower.includes('sheet') || lower.includes('both');
    const autopost = lower.includes('post') || lower.includes('publish') || lower.includes('autopost') || lower.includes('both');
    
    if (!saveToSheet && !autopost) {
        addAgentMessage('I didn\'t understand. Please type "save", "post", or "both".');
        return;
    }
    
    handleSaveAndPost(saveToSheet, autopost, message);
}

function processCookieResponse(message) {
    // User provided session cookie
    const cookie = message.trim();
    if (!cookie) {
        addAgentMessage('Please paste your LinkedIn session cookie (the "li_at" value).');
        return;
    }
    
    chatState.sessionCookie = cookie;
    // Show a masked version in chat instead of full cookie
    const maskedCookie = cookie.length > 20 ? cookie.substring(0, 10) + '...' + cookie.substring(cookie.length - 10) : '***';
    addUserMessage(`Cookie provided (${maskedCookie})`);
    
    // If we have a pending save intent, proceed with it
    if (chatState.pendingSaveIntent) {
        addAgentMessage('Perfect! Now I can proceed with your request.');
        const { saveToSheet, autopost } = chatState.pendingSaveIntent;
        chatState.pendingSaveIntent = null;
        chatState.awaitingResponse = null;
        // Proceed with the original request, skip cookie check since we just got it
        handleSaveAndPost(saveToSheet, autopost, '', true);
    } else {
        addAgentMessage('Got it! Now I can proceed with autoposting. Should I save to sheet, autopost, or both?');
        chatState.awaitingResponse = 'save';
        updateInputPlaceholder('Type "save", "post", or "both"...');
    }
}

async function loadLinkedInPostCount() {
    if (!chatState.userId) return;
    
    try {
        const BACKEND_URL = window.location.protocol + '//' + window.location.hostname + ':5000';
        const response = await fetch(`${BACKEND_URL}/api/dashboard/stats?user_id=${chatState.userId}`);
        const data = await response.json();
        
        if (data.success && data.stats) {
            const count = data.stats.activity?.linkedin_posts_count || 0;
            const countElement = document.getElementById('linkedinPostCount');
            if (countElement) {
                countElement.textContent = count;
            }
        }
    } catch (error) {
        console.error('Error loading LinkedIn post count:', error);
    }
}

async function handleSaveAndPost(saveToSheet, autopost, userMessage, skipCookieCheck = false) {
    if (!chatState.postContent) {
        addAgentMessage('I need a post to save. Please generate one first.');
        return;
    }
    
    if (saveToSheet && (!chatState.sheetUrl)) {
        addAgentMessage('Google Sheet URL is missing in configuration. I can only autopost.');
        if (!autopost) return;
    }
    
    if (saveToSheet && !chatState.serviceAccountJson) {
        await loadDefaultServiceAccount();
        if (!chatState.serviceAccountJson) {
            addAgentMessage('Service account file is required to save to sheet. I can only autopost.');
            if (!autopost) return;
        }
    }
    
    // Always ask for session cookie when autoposting (don't use env variable)
    // Skip check if cookie was just provided (skipCookieCheck = true)
    if (autopost && !skipCookieCheck && (!chatState.sessionCookie || chatState.sessionCookie.trim() === '')) {
        addAgentMessage('I need your LinkedIn session cookie to autopost. Please paste it (the "li_at" value from your browser cookies).\n\nTo get it:\n1. Open LinkedIn in your browser\n2. Press F12 to open Developer Tools\n3. Go to Application → Cookies → linkedin.com\n4. Copy the "li_at" value\n5. Paste it here');
        chatState.awaitingResponse = 'cookie';
        chatState.pendingSaveIntent = { saveToSheet, autopost };
        updateInputPlaceholder('Paste your LinkedIn session cookie (li_at)...');
        return;
    }
    
    addAgentMessage('Processing your request...');
    
    try {
        if (saveToSheet) {
            const saveResponse = await fetch(`${BACKEND_URL}/api/linkedin/save-to-sheet`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    sheet_url: chatState.sheetUrl,
                    content: chatState.postContent,
                    service_account_json: chatState.serviceAccountJson
                })
            });
            const saveResult = await saveResponse.json();
            if (saveResult.success) {
                addAgentMessage(`✓ Saved to Google Sheet successfully!`);
            } else {
                addAgentMessage(`✗ Save failed: ${saveResult.message}`);
            }
        }
        
        if (autopost) {
            const autopostPayload = {
                phantom_api_key: chatState.phantomKey,
                session_cookie: chatState.sessionCookie,
                user_agent: chatState.userAgent,
                sheet_url: chatState.sheetUrl,
                clear_sheet_after_post: false,
                user_id: chatState.userId  // Add user_id for tracking
            };
            
            const autopostResponse = await fetch(`${BACKEND_URL}/api/linkedin/autopost`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(autopostPayload)
            });
            
            const autopostResult = await autopostResponse.json();
            if (autopostResult.success) {
                addAgentMessage('✓ Post scheduled via PhantomBuster! It will be posted within 3 minutes.');
                // Update post count after successful post
                await loadLinkedInPostCount();
            } else {
                addAgentMessage(`✗ Autopost failed: ${autopostResult.message}`);
            }
        }
        
        addAgentMessage('All done! Would you like to create another post? Just tell me what you need.');
        chatState.step = 'complete';
        chatState.awaitingResponse = null;
        updateInputPlaceholder('Type to start a new post or ask a question...');
    } catch (error) {
        addAgentMessage(`Sorry, something went wrong: ${error.message}`);
    }
}

function handleCopyPost() {
    if (!chatState.postContent) {
        addAgentMessage('I need a post to copy. Please generate one first.');
        return;
    }
    
    navigator.clipboard.writeText(chatState.postContent)
        .then(() => {
            addUserMessage('copy');
            addAgentMessage('✓ Post copied to your clipboard!');
        })
        .catch(err => {
            addAgentMessage(`✗ Copy failed: ${err.message}`);
        });
}

// Handle optional click shortcuts
function handleChatClick(event) {
    const action = event.target.dataset.action || event.target.closest('[data-action]')?.dataset.action;
    if (!action) return;
    
    // These are optional shortcuts - main flow is through typing
    switch (action) {
        case 'select-trend':
            const trendItem = event.target.closest('.chat-trend-item');
            if (trendItem) {
                const index = Number(trendItem.dataset.trendIndex);
                const trend = chatState.trends[index];
                elements.userInput.value = trend.title;
                elements.userInputForm.dispatchEvent(new Event('submit'));
            }
            break;
    }
}

async function loadDefaultServiceAccount() {
    try {
        const response = await fetch(`${BACKEND_URL}/api/linkedin/service-account-file`);
        if (response.ok) {
            const text = await response.text();
            chatState.serviceAccountJson = text;
        }
    } catch (error) {
        console.warn('Could not load default service account JSON', error);
    }
}

function showStatus(message, type = 'info') {
    if (!elements.statusMessages) return;
    const div = document.createElement('div');
    div.className = `status-message status-${type}`;
    div.textContent = message;
    elements.statusMessages.appendChild(div);
    setTimeout(() => div.remove(), 6000);
}

function formatToneText(toneText) {
    if (!toneText) return '';
    let formatted = toneText
        .replace(/\*\*/g, '')
        .replace(/\*/g, '')
        .replace(/^[-•*]\s+/gm, '')
        .replace(/^\d+\.\s+/gm, '')
        .trim();
    const lines = formatted.split(/\n+/).filter(Boolean);
    return lines.map(line => {
        const trimmed = line.trim();
        if (!trimmed) return '';
        const sentence = trimmed.charAt(0).toUpperCase() + trimmed.slice(1);
        return sentence.endsWith('.') ? sentence : `${sentence}.`;
    }).join('\n\n');
}

function formatKeyword(keyword) {
    return keyword
        .split(/\s+/)
        .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
        .join(' ');
}

function formatKeywords(keywords) {
    if (!Array.isArray(keywords)) return [];
    return keywords.map(formatKeyword);
}
