const BACKEND_URL = window.location.protocol + '//' + window.location.hostname + ':5000';
const CONTENT_API = window.CONTENT_API || `${BACKEND_URL}/api/content/generate`;

const chatState = {
    brandSummary: '',
    campaignGoal: '',
    targetAudience: '',
    platform: '',
    outputs: [],
    adText: '',
    tone: 'professional',
    logoPosition: 'bottom-right',
    logoScale: '0.18',
    logoFile: null,
    referenceImageFile: null,
    step: 'brand',
    awaitingResponse: 'brand',
    generatedPlan: null
};

const elements = {};

// Status update interval for streaming messages
let statusUpdateInterval = null;

const PLATFORMS = [
    { value: 'instagram_feed', label: 'Instagram Feed' },
    { value: 'instagram_story', label: 'Instagram Story' },
    { value: 'linkedin', label: 'LinkedIn' },
    { value: 'twitter', label: 'Twitter' },
    { value: 'tiktok', label: 'TikTok' }
];

const OUTPUTS = [
    { value: 'text', label: 'Rewritten Text' },
    { value: 'poster', label: 'Poster Image' },
    { value: 'video', label: 'Video Reel' }
];

document.addEventListener('DOMContentLoaded', () => {
    cacheDomReferences();
    bindEventListeners();
    initChat();
});

function cacheDomReferences() {
    elements.chatMessages = document.getElementById('chatMessages');
    elements.userInputForm = document.getElementById('userInputForm');
    elements.userInput = document.getElementById('userInput');
    elements.statusMessages = document.getElementById('statusMessages');
}

function bindEventListeners() {
    elements.userInputForm?.addEventListener('submit', handleUserMessage);
    elements.userInput?.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            elements.userInputForm?.dispatchEvent(new Event('submit'));
        }
    });
}

function initChat() {
    addAgentMessage('Hi! I\'m here to help you create amazing social media content. Let\'s start by learning about your brand.');
    addAgentMessage('First, tell me about your brand or what you\'re offering. Describe your brand, product, or service.');
    chatState.step = 'brand';
    chatState.awaitingResponse = 'brand';
    updateInputPlaceholder('Describe your brand or offering...');
}

function addAgentMessage(content, isInteractive = false) {
    if (!elements.chatMessages) return;
    const msg = document.createElement('div');
    msg.className = `chat-message agent ${isInteractive ? 'interactive' : ''}`;
    
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

function startImageStatusUpdates() {
    // Clear any existing interval
    if (statusUpdateInterval) {
        clearInterval(statusUpdateInterval);
    }
    
    const statusMessages = [
        'Analyzing brand requirements...',
        'Generating visual concepts...',
        'Creating design elements...',
        'Composing final image...',
        'Applying logo and branding...',
        'Finalizing image details...',
        'Almost ready...'
    ];
    
    let statusIndex = 0;
    
    // Show first status immediately
    if (statusMessages.length > 0) {
        addAgentMessage(statusMessages[0]);
        statusIndex = 1;
    }
    
    // Update status every 10 seconds
    statusUpdateInterval = setInterval(() => {
        if (statusIndex < statusMessages.length) {
            addAgentMessage(statusMessages[statusIndex]);
            statusIndex++;
        } else {
            // Loop back or stop
            clearInterval(statusUpdateInterval);
            statusUpdateInterval = null;
        }
    }, 10000);
}

function startVideoStatusUpdates() {
    // Clear any existing interval
    if (statusUpdateInterval) {
        clearInterval(statusUpdateInterval);
    }
    
    const statusMessages = [
        'Initializing video generation...',
        'Creating video concept...',
        'Generating video frames...',
        'Processing video sequence...',
        'Rendering video content...',
        'Finalizing video details...',
        'Video generation in progress...'
    ];
    
    let statusIndex = 0;
    
    // Show first status immediately
    if (statusMessages.length > 0) {
        addAgentMessage(statusMessages[0]);
        statusIndex = 1;
    }
    
    // Update status every 10 seconds
    statusUpdateInterval = setInterval(() => {
        if (statusIndex < statusMessages.length) {
            addAgentMessage(statusMessages[statusIndex]);
            statusIndex++;
        } else {
            // Loop back or stop
            clearInterval(statusUpdateInterval);
            statusUpdateInterval = null;
        }
    }, 10000);
}

function stopStatusUpdates() {
    if (statusUpdateInterval) {
        clearInterval(statusUpdateInterval);
        statusUpdateInterval = null;
    }
}

function handleUserMessage(event) {
    event.preventDefault();
    const message = elements.userInput.value.trim();
    if (!message) return;
    
    addUserMessage(message);
    elements.userInput.value = '';
    
    if (chatState.awaitingResponse === 'brand') {
        processBrandResponse(message);
    } else if (chatState.awaitingResponse === 'goal') {
        processGoalResponse(message);
    } else if (chatState.awaitingResponse === 'audience') {
        processAudienceResponse(message);
    } else if (chatState.awaitingResponse === 'platform') {
        processPlatformResponse(message);
    } else if (chatState.awaitingResponse === 'outputs') {
        processOutputsResponse(message);
    } else if (chatState.awaitingResponse === 'optional') {
        processOptionalResponse(message);
    } else {
        processGeneralMessage(message);
    }
}

function processBrandResponse(message) {
    chatState.brandSummary = message;
    addAgentMessage(`Got it! Your brand: ${message}`);
    addAgentMessage('What\'s the goal of this campaign? (e.g., "Launch new service", "Increase brand awareness", "Promote a sale")');
    chatState.step = 'goal';
    chatState.awaitingResponse = 'goal';
    updateInputPlaceholder('Describe your campaign goal...');
}

function processGoalResponse(message) {
    chatState.campaignGoal = message;
    addAgentMessage(`Perfect! Campaign goal: ${message}`);
    addAgentMessage('Who is your target audience? (e.g., "SaaS marketing leads", "Young professionals", "Small business owners")');
    chatState.step = 'audience';
    chatState.awaitingResponse = 'audience';
    updateInputPlaceholder('Describe your target audience...');
}

function processAudienceResponse(message) {
    chatState.targetAudience = message;
    addAgentMessage(`Great! Target audience: ${message}`);
    addAgentMessage(`Which platform would you like to create content for?\n\n${PLATFORMS.map((p, i) => `${i + 1}. ${p.label}`).join('\n')}\n\nType the number or platform name.`);
    chatState.step = 'platform';
    chatState.awaitingResponse = 'platform';
    updateInputPlaceholder('Type the number or platform name...');
}

function processPlatformResponse(message) {
    const lower = message.toLowerCase().trim();
    
    // Check for number
    const numberMatch = message.match(/\b(\d+)\b/);
    if (numberMatch) {
        const num = parseInt(numberMatch[1]);
        if (num >= 1 && num <= PLATFORMS.length) {
            chatState.platform = PLATFORMS[num - 1].value;
            addAgentMessage(`Perfect! I'll create content for ${PLATFORMS[num - 1].label}.`);
            askForOutputs();
            return;
        }
    }
    
    // Check if it matches a platform name
    const matchingPlatform = PLATFORMS.find(p => 
        p.label.toLowerCase() === lower ||
        lower.includes(p.value) ||
        p.label.toLowerCase().includes(lower)
    );
    
    if (matchingPlatform) {
        chatState.platform = matchingPlatform.value;
        addAgentMessage(`Perfect! I'll create content for ${matchingPlatform.label}.`);
        askForOutputs();
        return;
    }
    
    addAgentMessage(`I didn't recognize that platform. Please type a number (1-${PLATFORMS.length}) or the platform name.`);
}

function askForOutputs() {
    addAgentMessage(`What would you like me to generate?\n\n${OUTPUTS.map((o, i) => `${i + 1}. ${o.label}`).join('\n')}\n\nYou can select multiple by typing the numbers (e.g., "1 and 2" or "all three").`);
    chatState.step = 'outputs';
    chatState.awaitingResponse = 'outputs';
    updateInputPlaceholder('Type the numbers or names of outputs you want...');
}

function processOutputsResponse(message) {
    const lower = message.toLowerCase().trim();
    const selected = [];
    
    // Check for "all" or "all three"
    if (lower.includes('all') || lower.includes('everything')) {
        chatState.outputs = OUTPUTS.map(o => o.value);
        addAgentMessage(`Perfect! I'll generate all outputs: ${OUTPUTS.map(o => o.label).join(', ')}.`);
        askForOptional();
        return;
    }
    
    // Extract numbers
    const numbers = message.match(/\b(\d+)\b/g);
    if (numbers) {
        numbers.forEach(numStr => {
            const num = parseInt(numStr);
            if (num >= 1 && num <= OUTPUTS.length) {
                const output = OUTPUTS[num - 1].value;
                if (!selected.includes(output)) {
                    selected.push(output);
                }
            }
        });
    }
    
    // Check for output names
    OUTPUTS.forEach(output => {
        if (lower.includes(output.value) || lower.includes(output.label.toLowerCase())) {
            if (!selected.includes(output.value)) {
                selected.push(output.value);
            }
        }
    });
    
    if (selected.length === 0) {
        addAgentMessage(`I didn't understand. Please type the numbers (1-${OUTPUTS.length}) or output names. You can select multiple.`);
        return;
    }
    
    chatState.outputs = selected;
    const selectedLabels = selected.map(s => OUTPUTS.find(o => o.value === s).label).join(', ');
    addAgentMessage(`Great! I'll generate: ${selectedLabels}.`);
    askForOptional();
}

function askForOptional() {
    addAgentMessage('Before I generate, do you have any additional details?\n\nYou can provide:\n• Ad text to rewrite (type "ad text: [your text]")\n• Tone preference: professional, casual, energetic, fun, or witty (type "tone: [your choice]")\n• Or just type "generate" or "ready" to proceed');
    chatState.step = 'optional';
    chatState.awaitingResponse = 'optional';
    updateInputPlaceholder('Add optional details or type "generate" to proceed...');
}

function processOptionalResponse(message) {
    const lower = message.toLowerCase().trim();
    
    // Check if they want to proceed
    if (lower.match(/^(generate|ready|proceed|go|create|start)$/)) {
        proceedToGeneration();
        return;
    }
    
    // Check for ad text
    const adTextMatch = message.match(/ad\s*text\s*:\s*(.+)/i);
    if (adTextMatch) {
        chatState.adText = adTextMatch[1].trim();
        addAgentMessage(`Got it! I'll use your ad text as a base.`);
        addAgentMessage('Any other details, or type "generate" to proceed?');
        return;
    }
    
    // Check for tone
    const toneMatch = message.match(/tone\s*:\s*(professional|casual|energetic|fun|witty)/i);
    if (toneMatch) {
        chatState.tone = toneMatch[1].toLowerCase();
        addAgentMessage(`Perfect! I'll use a ${chatState.tone} tone.`);
        addAgentMessage('Any other details, or type "generate" to proceed?');
        return;
    }
    
    // If it's just text without prefix, treat as ad text
    if (message.length > 20) {
        chatState.adText = message;
        addAgentMessage(`I'll use that as your ad text. Type "generate" when ready, or add more details.`);
        return;
    }
    
    addAgentMessage('I didn\'t understand. You can:\n• Type "ad text: [your text]" to provide ad copy\n• Type "tone: [professional/casual/energetic/fun/witty]" to set tone\n• Type "generate" to proceed');
}

function proceedToGeneration() {
    addAgentMessage('Perfect! Let me create your content. This may take a moment...');
    chatState.awaitingResponse = null;
    updateInputPlaceholder('Generating content...');
    handleGenerate();
}

async function handleGenerate() {
    try {
        // Validate required fields
        if (!chatState.platform || !chatState.platform.trim()) {
            throw new Error('Platform is required. Please select a platform first.');
        }
        
        // Validate platform is in supported list
        const validPlatforms = PLATFORMS.map(p => p.value);
        if (!validPlatforms.includes(chatState.platform)) {
            throw new Error(`Invalid platform: ${chatState.platform}. Supported platforms: ${validPlatforms.join(', ')}`);
        }
        
        if (!chatState.brandSummary || !chatState.brandSummary.trim()) {
            throw new Error('Brand summary is required.');
        }
        if (!chatState.campaignGoal || !chatState.campaignGoal.trim()) {
            throw new Error('Campaign goal is required.');
        }
        if (!chatState.targetAudience || !chatState.targetAudience.trim()) {
            throw new Error('Target audience is required.');
        }
        
        // Ensure outputs is always an array
        const outputs = Array.isArray(chatState.outputs) ? chatState.outputs : [];
        if (outputs.length === 0) {
            throw new Error('At least one output type is required. Please select what you want to generate.');
        }
        
        const payload = {
            brand_summary: chatState.brandSummary.trim(),
            campaign_goal: chatState.campaignGoal.trim(),
            target_audience: chatState.targetAudience.trim(),
            platforms: [chatState.platform],
            num_posts_per_platform: 1,
            outputs: outputs,
            logo_position: chatState.logoPosition,
            logo_scale: chatState.logoScale,
            extra_instructions: `Tone: ${chatState.tone}. Base ad text: ${chatState.adText || 'None provided'}`
        };
        
        // Add user_id for tracking if available
        const mainEl = document.querySelector('.app-main');
        const userId = mainEl?.dataset?.userId || window.ENV_CONFIG?.user_id || '';
        if (userId) {
            payload.user_id = userId;
        }
        
        // Debug: Log payload to help diagnose issues
        console.log('Sending payload:', {
            ...payload,
            platforms: payload.platforms,
            outputs: payload.outputs,
            platform_type: typeof chatState.platform,
            platform_value: chatState.platform
        });
        
        // Start status updates based on selected outputs
        // Prioritize video if both are selected, otherwise use the appropriate one
        if (outputs.includes('video') || outputs.includes('reel')) {
            startVideoStatusUpdates();
        } else if (outputs.includes('poster')) {
            startImageStatusUpdates();
        }
        
        const needsMultipart = Boolean(chatState.logoFile || chatState.referenceImageFile);
        
        let response;
        if (needsMultipart) {
            const formData = new FormData();
            Object.entries(payload).forEach(([key, value]) => {
                if (Array.isArray(value)) {
                    formData.append(key, JSON.stringify(value));
                } else {
                    formData.append(key, value);
                }
            });
            if (chatState.adText) {
                formData.append('ad_text', chatState.adText);
            }
            if (chatState.logoFile) {
                formData.append('logo_file', chatState.logoFile);
            }
            if (chatState.referenceImageFile) {
                formData.append('reference_image', chatState.referenceImageFile);
            }
            response = await fetch(CONTENT_API, { method: 'POST', body: formData });
        } else {
            const body = JSON.stringify({ 
                ...payload, 
                ad_text: chatState.adText ? chatState.adText.trim() : '' 
            });
            response = await fetch(CONTENT_API, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body
            });
        }
        
        if (!response.ok) {
            let errorMessage = 'Failed to generate content';
            try {
                const errorData = await response.json();
                errorMessage = errorData.message || errorData.error || JSON.stringify(errorData);
            } catch (e) {
                const errorText = await response.text();
                errorMessage = errorText || `HTTP ${response.status}: ${response.statusText}`;
            }
            console.error('Generation error:', {
                status: response.status,
                statusText: response.statusText,
                message: errorMessage,
                payload: payload
            });
            throw new Error(errorMessage);
        }
        
        const data = await response.json();
        if (!data?.success) {
            stopStatusUpdates();
            console.error('Generation failed:', data);
            throw new Error(data?.message || 'Generation failed');
        }
        
        // Stop status updates when we get the response
        stopStatusUpdates();
        
        // Debug: Log the response to see what we're getting
        console.log('Generation response:', data);
        console.log('Outputs requested:', chatState.outputs);
        console.log('Plan platforms:', data.plan?.platforms);
        if (data.plan?.platforms?.[0]?.posts?.[0]) {
            console.log('First post:', {
                text: data.plan.platforms[0].posts[0].text ? 'present' : 'missing',
                image_data_uri: data.plan.platforms[0].posts[0].image_data_uri ? 'present' : 'missing',
                video_data_uri: data.plan.platforms[0].posts[0].video_data_uri ? 'present' : 'missing',
                image_error: data.plan.platforms[0].posts[0].image_error || 'none'
            });
        }
        
        chatState.generatedPlan = data.plan;
        renderResults(data.plan);
    } catch (error) {
        // Stop status updates on error
        stopStatusUpdates();
        addAgentMessage(`Sorry, I couldn't generate the content: ${error.message}. Would you like to try again?`);
        chatState.awaitingResponse = 'optional';
        updateInputPlaceholder('Type "generate" to try again...');
    }
}

function renderResults(plan) {
    if (!plan || !plan.platforms || !plan.platforms.length) {
        addAgentMessage('Sorry, I received an invalid response. Please try again.');
        return;
    }
    
    const primaryPlatform = plan.platforms[0];
    const primaryPost = primaryPlatform.posts?.[0];
    if (!primaryPost) {
        addAgentMessage('Sorry, no content was generated. Please try again.');
        return;
    }
    
    addAgentMessage('Here\'s your generated content:');
    
    // Show text if text output is selected
    if (chatState.outputs.includes('text') && primaryPost.text) {
        const textMsg = addAgentMessage('', true);
        const textDiv = document.createElement('div');
        textDiv.className = 'chat-post-content';
        textDiv.textContent = primaryPost.text;
        textDiv.style.maxHeight = '300px';
        textDiv.style.overflowY = 'auto';
        textMsg.appendChild(textDiv);
        
        const copyBtn = document.createElement('button');
        copyBtn.type = 'button';
        copyBtn.className = 'btn btn-outline';
        copyBtn.textContent = 'Copy Text';
        copyBtn.style.marginTop = '0.5rem';
        copyBtn.onclick = () => {
            navigator.clipboard.writeText(primaryPost.text).then(() => {
                addAgentMessage('✓ Text copied to clipboard!');
            });
        };
        textMsg.appendChild(copyBtn);
    }
    
    // Show image if poster output is selected
    if (chatState.outputs.includes('poster')) {
        if (primaryPost.image_data_uri) {
            const imageMsg = addAgentMessage('', true);
            const img = document.createElement('img');
            img.src = primaryPost.image_data_uri;
            img.style.maxWidth = '100%';
            img.style.borderRadius = '8px';
            img.style.marginTop = '0.5rem';
            imageMsg.appendChild(img);
            
            const downloadBtn = document.createElement('button');
            downloadBtn.type = 'button';
            downloadBtn.className = 'btn btn-outline';
            downloadBtn.textContent = 'Download Image';
            downloadBtn.style.marginTop = '0.5rem';
            downloadBtn.onclick = () => {
                const link = document.createElement('a');
                link.href = primaryPost.image_data_uri;
                link.download = `content-poster-${Date.now()}.png`;
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
                addAgentMessage('✓ Image downloaded!');
            };
            imageMsg.appendChild(downloadBtn);
        } else if (primaryPost.image_error) {
            // Image generation failed
            addAgentMessage(`⚠️ Image generation failed: ${primaryPost.image_error}. The text was generated successfully.`);
        } else {
            // Image was requested but not in response
            addAgentMessage('⚠️ Image was requested but not included in the response. This might take longer to generate, or there may have been an issue.');
            console.error('Poster requested but no image_data_uri in response:', primaryPost);
        }
    }
    
    // Show video if video or reel output is selected
    const wantsVideo = chatState.outputs.includes('video') || chatState.outputs.includes('reel');
    if (wantsVideo) {
        if (primaryPost.video_data_uri) {
            const videoMsg = addAgentMessage('', true);
            const videoContainer = document.createElement('div');
            videoContainer.style.marginTop = '0.5rem';
            videoContainer.style.width = '100%';
            videoContainer.style.maxWidth = '600px';
            videoContainer.style.marginBottom = '0.5rem';
            
            const video = document.createElement('video');
            video.src = primaryPost.video_data_uri;
            video.controls = true;
            video.style.width = '100%';
            video.style.height = 'auto';
            video.style.borderRadius = '8px';
            video.style.backgroundColor = 'var(--color-card, #141414)';
            video.style.display = 'block';
            video.style.maxHeight = '500px';
            video.preload = 'auto';
            videoContainer.appendChild(video);
            videoMsg.appendChild(videoContainer);
            
            const downloadBtn = document.createElement('button');
            downloadBtn.type = 'button';
            downloadBtn.className = 'btn btn-outline';
            downloadBtn.textContent = 'Download Video';
            downloadBtn.style.marginTop = '0.5rem';
            downloadBtn.onclick = () => {
                const link = document.createElement('a');
                link.href = primaryPost.video_data_uri;
                link.download = `content-video-${Date.now()}.mp4`;
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
                addAgentMessage('✓ Video downloaded!');
            };
            videoMsg.appendChild(downloadBtn);
        } else if (primaryPost.video_error) {
            // Video generation failed
            addAgentMessage(`⚠️ Video generation failed: ${primaryPost.video_error}. The text and poster were generated successfully.`);
        } else {
            // Video was requested but not in response (might still be generating or not supported)
            addAgentMessage('⚠️ Video was requested but not included in the response. This might take longer to generate, or video generation may not be available. The text and poster were generated successfully.');
        }
    }
    
    addAgentMessage('Content generated successfully! Would you like to:\n• Type "regenerate" to create new content\n• Type "new" to start a new campaign\n• Or ask me anything else');
    chatState.step = 'complete';
    chatState.awaitingResponse = null;
    updateInputPlaceholder('Type "regenerate", "new", or ask a question...');
}

function processGeneralMessage(message) {
    const lower = message.toLowerCase().trim();
    
    if (chatState.step === 'complete') {
        if (lower.match(/^(regenerate|new|again|redo)$/)) {
            if (lower === 'new') {
                // Reset and start over
                chatState.brandSummary = '';
                chatState.campaignGoal = '';
                chatState.targetAudience = '';
                chatState.platform = '';
                chatState.outputs = [];
                chatState.adText = '';
                chatState.tone = 'professional';
                chatState.generatedPlan = null;
                initChat();
            } else {
                // Regenerate with same settings
                addUserMessage(message);
                addAgentMessage('Regenerating content with the same settings...');
                handleGenerate();
            }
            return;
        }
    }
    
    addAgentMessage('I\'m not sure what you mean. Could you clarify?');
}

function showStatus(message, type = 'info') {
    if (!elements.statusMessages) return;
    const div = document.createElement('div');
    div.className = `status-message status-${type}`;
    div.textContent = message;
    elements.statusMessages.appendChild(div);
    setTimeout(() => div.remove(), 6000);
}

