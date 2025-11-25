document.addEventListener('DOMContentLoaded', () => {
  const mainEl = document.querySelector('.app-main');
  if (!mainEl) return;
  const apiEndpoint = mainEl.dataset.contentApi || '';

  const brandSummaryInput = document.getElementById('brandSummary');
  const campaignGoalInput = document.getElementById('campaignGoal');
  const targetAudienceInput = document.getElementById('targetAudience');
  const adTextInput = document.getElementById('adText');
  const logoInput = document.getElementById('logoUpload');
  const referenceImageInput = document.getElementById('referenceImageUpload');
  const logoPositionSelect = document.getElementById('logoPosition');
  const logoScaleInput = document.getElementById('logoScale');
  const toneSelect = document.getElementById('toneSelect');
  const platformSelect = document.getElementById('platformSelect');
  const outputButtons = document.querySelectorAll('.output-type');
  const generateBtn = document.getElementById('generateBtn');
  const generatingState = document.getElementById('generatingState');
  const resultsCard = document.getElementById('resultsCard');
  const resultsPlaceholder = document.getElementById('resultsPlaceholder');
  const generatedTextEl = document.getElementById('generatedText');
  const resultItems = document.querySelectorAll('.result-item');
  const posterPreview = document.getElementById('posterPreview');
  const statusText = document.getElementById('generationStatus');
  const proposalPrefillGroup = document.getElementById('proposalPrefillGroup');
  const proposalSelect = document.getElementById('proposalSelect');
  const proposalPreview = document.getElementById('proposalPreview');
  const proposalPrefillHint = document.getElementById('proposalPrefillHint');
  const applyProposalBtn = document.getElementById('applyProposalBtn');
  const PREFILL_STORAGE_KEY = 'content-studio-prefill';
  const PROPOSAL_STORAGE_KEY = 'content-studio-proposals';

  let selectedOutputs = ['text'];
  let isGenerating = false;
  let latestImageDataUri = null;
  let latestVideoDataUri = null;
  let availableProposals = [];
  let currentProposalContext = null;
  let imageStatusInterval = null;

  const normalizeProposalContext = data => {
    if (!data || typeof data !== 'object') return null;
    return {
      trend: data.trend || 'Trend',
      coverage_level: data.coverage_level || 'gap',
      target_persona: data.target_persona || 'Product teams',
      proposal: data.proposal || '',
      why_it_helps: data.why_it_helps || '',
      success_metrics: Array.isArray(data.success_metrics) ? data.success_metrics : [],
      launch_steps: Array.isArray(data.launch_steps) ? data.launch_steps : [],
      risks: Array.isArray(data.risks) ? data.risks : [],
      system_impact: data.system_impact || '',
      working_hours: data.working_hours,
      working_price: data.working_price,
      keywords: Array.isArray(data.keywords) ? data.keywords : [],
    };
  };

  const findProposalIndex = context => {
    if (!context || !availableProposals.length) return -1;
    const trendKey = (context.trend || '').toLowerCase();
    if (!trendKey) return -1;
    return availableProposals.findIndex(item => (item.trend || '').toLowerCase() === trendKey);
  };

  const syncProposalSelection = context => {
    if (!proposalSelect || !context) return;
    const idx = findProposalIndex(context);
    if (idx >= 0) {
      proposalSelect.value = String(idx);
      updateProposalPreview(availableProposals[idx]);
    }
  };

  const setViewState = state => {
    if (state === 'loading') {
      generatingState.style.display = 'flex';
      resultsCard.style.display = 'none';
      resultsPlaceholder.style.display = 'none';
    } else if (state === 'ready') {
      generatingState.style.display = 'none';
      resultsCard.style.display = 'block';
      resultsPlaceholder.style.display = 'none';
    } else {
      generatingState.style.display = 'none';
      resultsCard.style.display = 'none';
      resultsPlaceholder.style.display = 'flex';
    }
  };

  const setStatus = message => {
    if (statusText) {
      statusText.textContent = message || '';
    }
  };

  const showStatusMessage = (message, type = 'info') => {
    const statusMessages = document.getElementById('statusMessages');
    if (!statusMessages) return;
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `status-message status-${type}`;
    messageDiv.textContent = message;
    
    statusMessages.appendChild(messageDiv);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
      if (messageDiv.parentNode) {
        messageDiv.style.opacity = '0';
        messageDiv.style.transform = 'translateY(-10px)';
        setTimeout(() => messageDiv.remove(), 300);
      }
    }, 5000);
    
    // Scroll to message
    messageDiv.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  };

  const streamText = (targetElement, text, speed = 20) => {
    if (!targetElement || !text) return;
    
    // Clear the element
    if (targetElement.tagName === 'TEXTAREA') {
      targetElement.value = '';
    } else {
      targetElement.textContent = '';
    }
    
    let index = 0;
    
    const stream = () => {
      if (index < text.length) {
        if (targetElement.tagName === 'TEXTAREA') {
          targetElement.value += text[index];
        } else {
          targetElement.textContent += text[index];
        }
        index++;
        setTimeout(stream, speed);
      }
    };
    
    stream();
  };

  const startImageStatusUpdates = () => {
    // Clear any existing interval
    if (imageStatusInterval) {
      clearInterval(imageStatusInterval);
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
      showStatusMessage(statusMessages[0], 'info');
      statusIndex = 1;
    }
    
    // Update status every 10 seconds
    imageStatusInterval = setInterval(() => {
      if (statusIndex < statusMessages.length) {
        showStatusMessage(statusMessages[statusIndex], 'info');
        statusIndex++;
      } else {
        // Loop back or stop
        clearInterval(imageStatusInterval);
        imageStatusInterval = null;
      }
    }, 10000);
  };

  const startVideoStatusUpdates = () => {
    // Clear any existing interval
    if (imageStatusInterval) {
      clearInterval(imageStatusInterval);
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
      showStatusMessage(statusMessages[0], 'info');
      statusIndex = 1;
    }
    
    // Update status every 10 seconds
    imageStatusInterval = setInterval(() => {
      if (statusIndex < statusMessages.length) {
        showStatusMessage(statusMessages[statusIndex], 'info');
        statusIndex++;
      } else {
        // Loop back or stop
        clearInterval(imageStatusInterval);
        imageStatusInterval = null;
      }
    }, 10000);
  };

  const stopImageStatusUpdates = () => {
    if (imageStatusInterval) {
      clearInterval(imageStatusInterval);
      imageStatusInterval = null;
    }
  };

  const toggleOutput = btn => {
    const value = btn.dataset.output;
    if (!value) {
      return;
    }
    if (selectedOutputs.includes(value)) {
      selectedOutputs = selectedOutputs.filter(item => item !== value);
      btn.classList.remove('active');
    } else {
      selectedOutputs.push(value);
      btn.classList.add('active');
    }
    focusResultItems();
    updateGenerateButtonState();
  };

  const updateGenerateButtonState = () => {
    const summary = brandSummaryInput.value.trim();
    const goal = campaignGoalInput.value.trim();
    const audience = targetAudienceInput.value.trim();
    const hasOutputs = selectedOutputs.length > 0;
    const hasBrief = summary.length > 0 && goal.length > 0 && audience.length > 0;
    generateBtn.disabled = !(hasBrief && hasOutputs) || isGenerating;
  };

  const focusResultItems = () => {
    resultItems.forEach(item => {
      const type = item.dataset.result;
      item.style.display = selectedOutputs.includes(type) ? 'block' : 'none';
    });
  };

  const setSelectedOutputs = outputs => {
    const normalized = Array.isArray(outputs) && outputs.length ? outputs : ['text'];
    selectedOutputs = Array.from(new Set(normalized));
    outputButtons.forEach(btn => {
      const value = btn.dataset.output;
      btn.classList.toggle('active', selectedOutputs.includes(value));
    });
    focusResultItems();
  };

  const readPrefillFromStorage = () => {
    try {
      const raw = localStorage.getItem(PREFILL_STORAGE_KEY);
      if (!raw) return null;
      localStorage.removeItem(PREFILL_STORAGE_KEY);
      const parsed = JSON.parse(raw);
      if (parsed && typeof parsed === 'object') {
        return parsed;
      }
    } catch (err) {
      console.error('Unable to parse content studio prefill', err);
    }
    return null;
  };

  const readProposalsFromStorage = () => {
    try {
      const raw = localStorage.getItem(PROPOSAL_STORAGE_KEY);
      if (!raw) return [];
      localStorage.removeItem(PROPOSAL_STORAGE_KEY);
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) {
        return parsed;
      }
    } catch (err) {
      console.error('Unable to parse proposal cache', err);
    }
    return [];
  };

  const getCoverageLabel = level => {
    const normalized = (level || '').toLowerCase();
    if (normalized === 'weak') return 'Weak';
    if (normalized === 'covered') return 'Covered';
    return 'Gap';
  };

  const updateProposalPreview = proposal => {
    if (!proposalPreview) return;
    if (!proposal) {
      proposalPreview.textContent = '';
      return;
    }
    const persona = proposal.target_persona || 'Product teams';
    const coverage = getCoverageLabel(proposal.coverage_level);
    proposalPreview.textContent = `${proposal.trend || 'Trend'} · ${persona} · ${coverage}`;
  };

  const setProposalPicker = proposals => {
    availableProposals = Array.isArray(proposals) ? proposals : [];
    if (!proposalPrefillGroup || !proposalSelect) return;
    if (!availableProposals.length) {
      proposalPrefillGroup.hidden = true;
      updateProposalPreview(null);
      return;
    }
    proposalPrefillGroup.hidden = false;
    proposalSelect.innerHTML = availableProposals
      .map((item, idx) => {
        const label = `${item.trend || 'Trend'} (${getCoverageLabel(item.coverage_level)})`;
        return `<option value="${idx}">${label}</option>`;
      })
      .join('');
    proposalSelect.value = '0';
    updateProposalPreview(availableProposals[0]);
    if (proposalPrefillHint) {
      proposalPrefillHint.textContent = 'Select a concept and click Use Proposal to auto-fill the brief.';
    }
    syncProposalSelection(currentProposalContext);
  };

  const buildPrefillFromProposal = proposal => {
    if (!proposal || typeof proposal !== 'object') return null;
    const coverage = getCoverageLabel(proposal.coverage_level);
    const persona = proposal.target_persona || 'Product teams';
    const narrative = [proposal.proposal, proposal.why_it_helps].filter(Boolean).join(' ');
    const adText = [
      `🚀 ${proposal.trend || 'New initiative'} for ${persona}.`,
      narrative,
      'Ready to pilot? Let’s talk.',
    ]
      .filter(Boolean)
      .join(' ');
    return {
      source: 'gap-proposal',
      brand_summary: `${proposal.trend || 'Trend'} (${coverage})`,
      campaign_goal: `Launch ${proposal.trend || 'new'} initiative`,
      target_audience: persona,
      ad_text: adText,
      tone: 'professional',
      platform: 'linkedin',
      outputs: ['text', 'poster'],
      proposal_details: proposal,
    };
  };

  const applyProposalPrefill = proposal => {
    const payload = buildPrefillFromProposal(proposal);
    if (!payload) return;
    applyPrefill(payload, { resetContext: false });
    currentProposalContext = normalizeProposalContext(proposal);
    syncProposalSelection(currentProposalContext);
    setStatus('Proposal context loaded. Adjust fields or generate content.');
  };

  const applyPrefill = (payload, { resetContext = true } = {}) => {
    if (!payload || typeof payload !== 'object') return;

    if (payload.brand_summary) {
      brandSummaryInput.value = payload.brand_summary;
    }
    if (payload.campaign_goal) {
      campaignGoalInput.value = payload.campaign_goal;
    }
    if (payload.target_audience) {
      targetAudienceInput.value = payload.target_audience;
    }
    if (payload.ad_text) {
      adTextInput.value = payload.ad_text;
    }

    if (payload.tone) {
      const hasTone = Array.from(toneSelect.options).some(option => option.value === payload.tone);
      if (hasTone) {
        toneSelect.value = payload.tone;
      }
    }

    if (payload.platform) {
      const hasPlatform = Array.from(platformSelect.options).some(option => option.value === payload.platform);
      if (hasPlatform) {
        platformSelect.value = payload.platform;
      }
    }

    setSelectedOutputs(payload.outputs);
    updateGenerateButtonState();
    const statusMessage =
      payload.source === 'gap-proposal'
        ? 'Loaded a proposal brief from gap analysis. Review and generate content.'
        : payload.source === 'gap-analysis'
          ? 'Loaded coverage insights into the campaign brief. Review and edit as needed.'
          : 'Loaded saved campaign brief.';
    setStatus(statusMessage);
    if (payload.proposal_details) {
      currentProposalContext = normalizeProposalContext(payload.proposal_details);
      syncProposalSelection(currentProposalContext);
    } else if (resetContext) {
      currentProposalContext = null;
    }
  };

  const renderPlan = plan => {
    if (!plan || !plan.platforms || !plan.platforms.length) {
      throw new Error('Invalid plan response');
    }
    const primaryPlatform = plan.platforms[0];
    const primaryPost = primaryPlatform.posts?.[0];
    if (!primaryPost) {
      throw new Error('No posts returned from API');
    }

    // Stop image status updates
    stopImageStatusUpdates();
    
    // Show results card immediately
    focusResultItems();
    setViewState('ready');
    
    // Stream text if text output is selected
    if (selectedOutputs.includes('text') && primaryPost.text) {
      const textToStream = primaryPost.text || 'Text not returned.';
      // Clear and start streaming
      if (generatedTextEl.tagName === 'TEXTAREA') {
        generatedTextEl.value = '';
        setTimeout(() => {
          streamText(generatedTextEl, textToStream, 20);
        }, 100);
      } else {
        generatedTextEl.textContent = '';
        setTimeout(() => {
          streamText(generatedTextEl, textToStream, 20);
        }, 100);
      }
    } else {
      if (generatedTextEl.tagName === 'TEXTAREA') {
        generatedTextEl.value = primaryPost.text || 'Text not returned.';
      } else {
        generatedTextEl.textContent = primaryPost.text || 'Text not returned.';
      }
    }

    // Handle image
    if (selectedOutputs.includes('poster')) {
      latestImageDataUri = primaryPost.image_data_uri || null;
      if (latestImageDataUri) {
        const html = `<img src="${latestImageDataUri}" alt="Generated Poster" />`;
        posterPreview.innerHTML = html + '<span class="poster-ready">Ready</span>';
        showStatusMessage('Image generated successfully!', 'success');
      } else {
        posterPreview.innerHTML = `
          <div class="poster-placeholder">
            <span>Poster preview unavailable</span>
          </div>
          <span class="poster-ready">Ready</span>
        `;
        showStatusMessage('Image generation completed, but no image was returned.', 'error');
      }
    } else {
      latestImageDataUri = null;
      posterPreview.innerHTML = `
        <div class="poster-placeholder">
          <span>Poster preview unavailable</span>
        </div>
        <span class="poster-ready">Ready</span>
      `;
    }

    // Handle video
    const videoPreview = document.getElementById('videoPreview');
    if (selectedOutputs.includes('video') || selectedOutputs.includes('reel')) {
      latestVideoDataUri = primaryPost.video_data_uri || null;
      if (videoPreview) {
        if (latestVideoDataUri) {
          const html = `
            <video controls class="generated-video">
              <source src="${latestVideoDataUri}" type="video/mp4">
              Your browser does not support the video tag.
            </video>
            <span class="video-ready">Ready</span>
          `;
          videoPreview.innerHTML = html;
          // Enable download button
          const videoDownloadBtn = videoPreview.closest('.result-item')?.querySelector('[data-action="download"]');
          if (videoDownloadBtn) {
            videoDownloadBtn.disabled = false;
          }
          showStatusMessage('Video generated successfully!', 'success');
        } else if (primaryPost.video_error) {
          videoPreview.innerHTML = `
            <div class="video-placeholder">
              <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect x="2" y="6" width="20" height="12" rx="2"></rect>
                <polygon points="10 15 15 12 10 9 10 15"></polygon>
              </svg>
              <p>Video generation failed: ${primaryPost.video_error}</p>
            </div>
          `;
          showStatusMessage('Video generation completed, but no video was returned.', 'error');
        } else {
          videoPreview.innerHTML = `
            <div class="video-placeholder">
              <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect x="2" y="6" width="20" height="12" rx="2"></rect>
                <polygon points="10 15 15 12 10 9 10 15"></polygon>
              </svg>
              <p>Video preview unavailable</p>
            </div>
          `;
        }
      }
    } else {
      latestVideoDataUri = null;
      if (videoPreview) {
        videoPreview.innerHTML = `
          <div class="video-placeholder">
            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <rect x="2" y="6" width="20" height="12" rx="2"></rect>
              <polygon points="10 15 15 12 10 9 10 15"></polygon>
            </svg>
            <p>Video preview unavailable</p>
          </div>
        `;
      }
    }

    setStatus('Content generated successfully.');
  };

  const generatePayload = () => {
    const summary = brandSummaryInput.value.trim();
    const goal = campaignGoalInput.value.trim();
    const audience = targetAudienceInput.value.trim();
    const adText = adTextInput.value.trim();
    const tone = toneSelect.value;
    const platform = platformSelect.value;
    const logoPosition = logoPositionSelect.value;
    const logoScale = logoScaleInput.value || '0.18';

    // Build proposal narrative (similar to ad_text in content studio)
    // Use adText as proposal narrative, or build from proposal context
    let proposalNarrative = adText;
    if (!proposalNarrative && currentProposalContext) {
      proposalNarrative = [
        currentProposalContext.proposal,
        currentProposalContext.why_it_helps
      ].filter(Boolean).join(' ');
    }

    const instructionParts = [`Tone: ${tone}.`, `Outputs: ${selectedOutputs.join(', ')}.`];

    const payload = {
      brand_summary: summary || proposalNarrative || 'Your brand narrative',
      campaign_goal: goal || 'General awareness',
      target_audience: audience || currentProposalContext?.target_persona || 'General audience',
      extra_instructions: instructionParts.join(' '),
      platforms: [platform],
      num_posts_per_platform: 1,
      logo_position: logoPosition,
      logo_scale: logoScale,
      outputs: [...selectedOutputs],
    };
    
    // Add proposal narrative (similar to ad_text in content studio)
    if (proposalNarrative) {
      payload.proposal_narrative = proposalNarrative;
    }
    
    // Add proposal context if available
    if (currentProposalContext) {
      payload.proposal_context = currentProposalContext;
    }
    
    return payload;
  };

  const handleCopyAction = button => {
    const textToCopy = generatedTextEl.tagName === 'TEXTAREA' 
      ? generatedTextEl.value 
      : generatedTextEl.textContent;
    if (!textToCopy) return;
    navigator.clipboard?.writeText(textToCopy).then(() => {
      const original = button.textContent;
      button.textContent = 'Copied';
      setTimeout(() => (button.textContent = original), 1200);
    });
  };

  const handleDownloadAction = (button, type) => {
    if (type === 'poster' && latestImageDataUri) {
      const link = document.createElement('a');
      link.href = latestImageDataUri;
      link.download = `nextgen-content-${Date.now()}.png`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      setStatus('Poster image downloaded.');
      return;
    }
    if (type === 'video' && latestVideoDataUri) {
      const link = document.createElement('a');
      link.href = latestVideoDataUri;
      link.download = `nextgen-content-${Date.now()}.mp4`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      setStatus('Video downloaded.');
      return;
    }
    setStatus('Download unavailable for this asset.');
  };

  const submitToBackend = async () => {
    console.log('=== PROPOSAL SUBMIT TO BACKEND START ===');
    if (!apiEndpoint) {
      console.error('API endpoint not configured:', apiEndpoint);
      throw new Error('Content API endpoint not configured.');
    }
    console.log('API endpoint:', apiEndpoint);
    
    const payload = generatePayload();
    console.log('Generated payload:', JSON.stringify(payload, null, 2));
    
    const logoFile = logoInput.files?.[0];
    const referenceImageFile = referenceImageInput?.files?.[0];
    const needsMultipart = Boolean(logoFile || referenceImageFile);
    console.log('needsMultipart:', needsMultipart);
    console.log('logoFile:', logoFile?.name, logoFile?.size);
    console.log('referenceImageFile:', referenceImageFile?.name, referenceImageFile?.size);

    let response;
    if (needsMultipart) {
      const formData = new FormData();
      Object.entries(payload).forEach(([key, value]) => {
        if (Array.isArray(value) || typeof value === 'object') {
          formData.append(key, JSON.stringify(value));
        } else {
          formData.append(key, value);
        }
      });
      // Add proposal narrative (similar to ad_text in content studio)
      if (payload.proposal_narrative) {
        formData.append('proposal_narrative', payload.proposal_narrative);
      }
      // Also include ad_text for backward compatibility
      if (adTextInput.value.trim()) {
        formData.append('ad_text', adTextInput.value.trim());
      }
      if (logoFile) {
        formData.append('logo_file', logoFile);
      }
      if (referenceImageFile) {
        formData.append('reference_image', referenceImageFile);
      }
      response = await fetch(apiEndpoint, { method: 'POST', body: formData });
    } else {
      const jsonPayload = { ...payload };
      // Include proposal_narrative if available
      if (payload.proposal_narrative) {
        jsonPayload.proposal_narrative = payload.proposal_narrative;
      }
      // Also include ad_text for backward compatibility
      if (adTextInput.value.trim()) {
        jsonPayload.ad_text = adTextInput.value.trim();
      }
      const body = JSON.stringify(jsonPayload);
      response = await fetch(apiEndpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body,
      });
    }

    console.log('Response status:', response.status, response.statusText);
    console.log('Response headers:', Object.fromEntries(response.headers.entries()));

    if (!response.ok) {
      const errorText = await response.text();
      console.error('Error response:', errorText);
      throw new Error(errorText || 'Failed to generate content');
    }
    
    const responseData = await response.json();
    console.log('Response data:', responseData);
    console.log('=== PROPOSAL SUBMIT TO BACKEND SUCCESS ===');
    return responseData;
  };

  const handleGenerate = async () => {
    if (generateBtn.disabled || isGenerating) return;
    isGenerating = true;
    updateGenerateButtonState();
    setStatus('Sending brief to backend...');
    setViewState('loading');

    // Start status updates based on selected outputs
    if (selectedOutputs.includes('poster')) {
      startImageStatusUpdates();
    } else if (selectedOutputs.includes('video') || selectedOutputs.includes('reel')) {
      startVideoStatusUpdates();
    }

    try {
      const data = await submitToBackend();
      if (!data?.success) {
        throw new Error(data?.message || 'Generation failed');
      }
      renderPlan(data.plan);
    } catch (err) {
      console.error(err);
      stopImageStatusUpdates();
      showStatusMessage('Generation failed. Please try again.', 'error');
      setStatus('Generation failed. Please try again.');
      setViewState('idle');
    } finally {
      isGenerating = false;
      updateGenerateButtonState();
      
      // Re-enable regenerate button
      const regenerateBtn = document.querySelector('[data-action="regenerate"]');
      if (regenerateBtn) {
        regenerateBtn.disabled = false;
      }
    }
  };

  [brandSummaryInput, campaignGoalInput, targetAudienceInput, logoScaleInput, adTextInput].forEach(input => {
    input.addEventListener('input', updateGenerateButtonState);
  });
  platformSelect.addEventListener('change', updateGenerateButtonState);

  outputButtons.forEach(btn => btn.addEventListener('click', () => toggleOutput(btn)));
  generateBtn.addEventListener('click', handleGenerate);

  resultsCard.addEventListener('click', event => {
    const button = event.target.closest('.action-button');
    if (!button) return;
    const action = button.dataset.action;
    const parent = button.closest('.result-item');
    const type = parent?.dataset.result || '';
    if (action === 'copy') {
      handleCopyAction(button);
    } else if (action === 'download') {
      handleDownloadAction(button, type);
    }
  });

  proposalSelect?.addEventListener('change', () => {
    const idx = Number(proposalSelect.value);
    const proposal = Number.isInteger(idx) ? availableProposals[idx] : null;
    updateProposalPreview(proposal);
  });

  applyProposalBtn?.addEventListener('click', () => {
    const idx = Number(proposalSelect?.value);
    if (!availableProposals.length) {
      setStatus('No proposals loaded from gap analysis.', true);
      return;
    }
    if (!Number.isInteger(idx) || !availableProposals[idx]) {
      setStatus('Select a valid proposal to apply.', true);
      return;
    }
    applyProposalPrefill(availableProposals[idx]);
  });

  const storedProposals = readProposalsFromStorage();
  setProposalPicker(storedProposals);

  const storedPrefill = readPrefillFromStorage();
  if (storedPrefill) {
    applyPrefill(storedPrefill);
  } else {
    setSelectedOutputs(selectedOutputs);
    updateGenerateButtonState();
  }
  setViewState('idle');
});
