document.addEventListener('DOMContentLoaded', () => {
  const mainEl = document.querySelector('.app-main');
  const apiEndpoint = mainEl?.dataset.contentApi || '';

  const brandSummaryInput = document.getElementById('brandSummary');
  const campaignGoalInput = document.getElementById('campaignGoal');
  const targetAudienceInput = document.getElementById('targetAudience');
  const adTextInput = document.getElementById('adText');
  const logoInput = document.getElementById('logoUpload');
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

  let selectedOutputs = ['text'];
  let isGenerating = false;
  let latestImageDataUri = null;

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

    generatedTextEl.textContent = primaryPost.text || 'Text not returned.';
    focusResultItems();

    if (selectedOutputs.includes('poster')) {
      latestImageDataUri = primaryPost.image_data_uri || null;
      const html = latestImageDataUri
        ? `<img src="${latestImageDataUri}" alt="Generated Poster" />`
        : `<div class="poster-placeholder"><span>Poster preview unavailable</span></div>`;
      posterPreview.innerHTML = html + '<span class="poster-ready">Ready</span>';
    } else {
      latestImageDataUri = null;
      posterPreview.innerHTML = `<div class="poster-placeholder"><span>Poster preview unavailable</span></div><span class="poster-ready">Ready</span>`;
    }

    setViewState('ready');
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
    };
  };

  const handleCopyAction = button => {
    if (!generatedTextEl.textContent) return;
    navigator.clipboard?.writeText(generatedTextEl.textContent).then(() => {
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

    let response;
    if (logoFile) {
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
      formData.append('logo_file', logoFile);
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
    setStatus('Sending brief to backend...');
    setViewState('loading');

    try {
      const data = await submitToBackend();
      if (!data?.success) {
        throw new Error(data?.message || 'Generation failed');
      }
      renderPlan(data.plan);
    } catch (err) {
      console.error(err);
      setStatus('Generation failed. Please try again.');
      setViewState('idle');
    } finally {
      isGenerating = false;
      updateGenerateButtonState();
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

  document.querySelector('[data-output="text"]')?.classList.add('active');
  resultItems.forEach(item => {
    item.style.display = selectedOutputs.includes(item.dataset.result) ? 'block' : 'none';
  });
  updateGenerateButtonState();
  setViewState('idle');
});
