document.addEventListener('DOMContentLoaded', () => {
  const mainEl = document.querySelector('.app-main');
  const apiEndpoint = mainEl?.dataset.contentApi || '';

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
  const regenerateBtn = document.getElementById('regenerateBtn');
  const generatingState = document.getElementById('generatingState');
  const resultsCard = document.getElementById('resultsCard');
  const resultsPlaceholder = document.getElementById('resultsPlaceholder');
  const generatedTextEl = document.getElementById('generatedText');
  const resultItems = document.querySelectorAll('.result-item');
  const posterPreview = document.getElementById('posterPreview');
  const statusText = document.getElementById('generationStatus');

  let selectedOutputs = ['text'];
  let isGenerating = false;
  let latestImageDataUri = null;
  let latestVideoDataUri = null;
  let imageStatusInterval = null;

  const setViewState = state => {
    if (state === 'loading') {
      generatingState.style.display = 'flex';
      resultsCard.style.display = 'none';
      resultsPlaceholder.style.display = 'none';
      if (regenerateBtn) {
        regenerateBtn.style.display = 'none';
      }
    } else if (state === 'ready') {
      generatingState.style.display = 'none';
      resultsCard.style.display = 'block';
      resultsPlaceholder.style.display = 'none';
      if (regenerateBtn) {
        regenerateBtn.style.display = 'inline-flex';
      }
    } else {
      generatingState.style.display = 'none';
      resultsCard.style.display = 'none';
      resultsPlaceholder.style.display = 'flex';
      if (regenerateBtn) {
        regenerateBtn.style.display = 'none';
      }
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
    
    targetElement.value = '';
    let index = 0;
    
    const stream = () => {
      if (index < text.length) {
        targetElement.value += text[index];
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
        posterPreview.innerHTML = `<div class="poster-placeholder"><span>Poster preview unavailable</span></div><span class="poster-ready">Ready</span>`;
        showStatusMessage('Image generation completed, but no image was returned.', 'error');
      }
    } else {
      latestImageDataUri = null;
      posterPreview.innerHTML = `<div class="poster-placeholder"><span>Poster preview unavailable</span></div><span class="poster-ready">Ready</span>`;
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
          showStatusMessage('Video generation completed, but no video was returned.', 'error');
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

    return {
      brand_summary: summary || adText,
      campaign_goal: goal || 'General awareness',
      target_audience: audience || 'General audience',
      extra_instructions: `Tone: ${tone}. Outputs: ${selectedOutputs.join(', ')}. Base ad text: ${adText}`,
      platforms: [platform],
      num_posts_per_platform: 1,
      logo_position: logoPosition,
      logo_scale: logoScale,
      outputs: selectedOutputs, // Send outputs to backend to conditionally generate images
    };
  };

  const handleCopyAction = button => {
    if (!generatedTextEl.value && !generatedTextEl.textContent) return;
    const textToCopy = generatedTextEl.value || generatedTextEl.textContent;
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
    setStatus('Download unavailable for this asset.');
  };

  const submitToBackend = async () => {
    if (!apiEndpoint) {
      throw new Error('Content API endpoint not configured.');
    }
    const payload = generatePayload();
    const logoFile = logoInput.files?.[0];
    const referenceImageFile = referenceImageInput?.files?.[0];
    const needsMultipart = Boolean(logoFile || referenceImageFile);
    
    // Debug logging
    if (referenceImageFile) {
      console.log('Reference image file selected:', referenceImageFile.name, referenceImageFile.size, 'bytes');
    } else {
      console.log('No reference image file selected');
    }

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
      const body = JSON.stringify({ ...payload, ad_text: adTextInput.value.trim() });
      response = await fetch(apiEndpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body,
      });
    }

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(errorText || 'Failed to generate content');
    }
    return response.json();
  };

  const handleGenerate = async () => {
    if (generateBtn.disabled || isGenerating) return;
    isGenerating = true;
    updateGenerateButtonState();
    
    // Disable regenerate button during generation
    if (regenerateBtn) {
      regenerateBtn.disabled = true;
    }
    
    setStatus('Sending brief to backend...');
    setViewState('loading');
    
    // Clear previous status messages
    const statusMessages = document.getElementById('statusMessages');
    if (statusMessages) {
      statusMessages.innerHTML = '';
    }
    
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
  
  // Regenerate button - same functionality as generate
  if (regenerateBtn) {
    regenerateBtn.addEventListener('click', handleGenerate);
  }

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

  document.querySelector('[data-output="text"]')?.classList.add('active');
  resultItems.forEach(item => {
    item.style.display = selectedOutputs.includes(item.dataset.result) ? 'block' : 'none';
  });
  
  // Initially hide regenerate button
  if (regenerateBtn) {
    regenerateBtn.style.display = 'none';
  }
  
  updateGenerateButtonState();
  setViewState('idle');
});
