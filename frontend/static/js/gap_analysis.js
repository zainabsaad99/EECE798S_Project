document.addEventListener('DOMContentLoaded', () => {
  const main = document.querySelector('.gap-main');
  if (!main) return;

  const apiEndpoint = main.dataset.gapApi || '';
  const keywordsApi = main.dataset.keywordsApi || '';
  const businessApi = main.dataset.businessApi || '';
  const trendsApi = main.dataset.trendsApi || '';
  const userId = main.dataset.userId || '';
  const contentStudioUrl = main.dataset.contentStudioUrl || '';
  const proposalContentUrl = main.dataset.proposalContentUrl || contentStudioUrl;
  const CONTENT_STUDIO_PREFILL_KEY = 'content-studio-prefill';
  const CONTENT_STUDIO_PROPOSALS_KEY = 'content-studio-proposals';

  const contextInput = document.getElementById('contextInput');
  const analyzeBtn = document.getElementById('analyzeBtn');
  const statusEl = document.getElementById('gapStatus');
  const placeholder = document.getElementById('resultsPlaceholder');
  const loadingEl = document.getElementById('resultsLoading');
  const body = document.getElementById('resultsBody');
  const coveredList = document.querySelector('#coveredCard ul');
  const weakList = document.querySelector('#weakCard ul');
  const gapList = document.querySelector('#gapCard ul');
  const insightEl = document.getElementById('insightSummary');
  const recommendationsList = document.getElementById('recommendationsList');
  const productProposalsList = document.getElementById('productProposalsList');
  const proposalCompareContainer = document.getElementById('productProposalsCompare');
  const filterButtons = document.querySelectorAll('.coverage-filters .chip');
  const saveFilterBtn = document.getElementById('saveFilterBtn');
  const clearFilterBtn = document.getElementById('clearFilterBtn');
  const copySummaryBtn = document.getElementById('copySummaryBtn');
  const copyRecommendationsBtn = document.getElementById('copyRecommendationsBtn');
  const copyProposalsBtn = document.getElementById('copyProposalsBtn');
  const viewProposalsModalBtn = document.getElementById('viewProposalsModalBtn');
  const generateContentBtn = document.getElementById('generateContentBtn');
  const proposalFilterButtons = Array.from(document.querySelectorAll('[data-proposal-filter]'));
  const proposalViewButtons = Array.from(document.querySelectorAll('[data-proposal-view]'));
  const exportOpportunitiesBtn = document.getElementById('exportOpportunitiesBtn');
  const progressSteps = document.querySelectorAll('.progress-step');
  const keywordList = document.getElementById('keywordList');
  const keywordEmptyState = document.getElementById('keywordEmptyState');
  const refreshKeywordsBtn = document.getElementById('refreshKeywordsBtn');
  const keywordSearchInput = document.getElementById('keywordSearch');
  const keywordCountBadge = document.getElementById('keywordCountBadge');
  const selectAllKeywordsBtn = document.getElementById('selectAllKeywordsBtn');
  const clearKeywordsBtn = document.getElementById('clearKeywordsBtn');
  const discoverTrendsBtn = document.getElementById('discoverTrendsBtn');
  const selectAllTrendsBtn = document.getElementById('selectAllTrendsBtn');
  const clearTrendsBtn = document.getElementById('clearTrendsBtn');
  const trendCard = document.querySelector('.trend-card');
  const trendResults = document.getElementById('trendResults');
  const trendEmptyState = document.getElementById('trendEmptyState');
  const trendStatusText = document.getElementById('trendStatusText');
  const catalogSummary = document.getElementById('catalogSummary');
  const catalogList = document.getElementById('catalogList');
  const catalogEmptyState = document.getElementById('catalogEmptyState');
  const productCountPill = document.getElementById('productCountPill');
  const trendCountPill = document.getElementById('trendCountPill');
  const proposalPromptModal = document.getElementById('proposalPromptModal');
  const proposalDetailsModal = document.getElementById('proposalDetailsModal');
  const confirmProposalBtn = document.getElementById('confirmProposalBtn');
  const skipProposalBtn = document.getElementById('skipProposalBtn');
  const proposalDetailsBody = document.getElementById('proposalDetailsBody');
  const downloadProposalsBtn = document.getElementById('downloadProposalsBtn');
  const panelToggleInputs = document.querySelectorAll('[data-panel-target]');
  const heroKeywordCount = document.getElementById('heroKeywordCount');
  const heroTrendCount = document.getElementById('heroTrendCount');
  const heroGapCount = document.getElementById('heroGapCount');
  const trendMarqueeTrack = document.getElementById('trendMarquee');

  if (
    !analyzeBtn ||
    !statusEl ||
    !placeholder ||
    !loadingEl ||
    !body ||
    !keywordList ||
    !trendResults ||
    !catalogList
  ) {
    return;
  }

  let lastOpportunityData = [];
  let lastRecommendationsText = '';
  let lastProposalsText = '';
  let lastProposalsData = [];
  let lastRenderedProposals = [];
  let proposalFilter = 'all';
  let proposalView = 'cards';
  let pendingContentPrefill = null;
  let lastCoverageSummary = null;
  const actionPlanStorageKey = 'gap-action-plan';
  let actionPlanStates = {};
  const fallbackKeywords = [
    { keyword: 'AI copilots', category: 'Product' },
    { keyword: 'Zero-party data', category: 'Data' },
    { keyword: 'Workflow automation', category: 'Operations' },
    { keyword: 'Revenue analytics', category: 'Growth' },
  ];
  const fallbackBusinesses = [
    {
        "name": "shein",
        "strapline": "Best chinese products.",
        "audience": "People who like shopping",
        "products": [
            {
                "name": "tshirt",
                "description": "Best black cotton tshirt"
            },
        ],
    },
  ];
  const state = {
    keywords: [],
    selectedKeywordIds: new Set(),
    businesses: [],
    trends: [],
    selectedTrendIndexes: new Set(),
    keywordFilter: '',
  };
  let proposalPreference = null;
  let pendingAnalysis = false;
  const panelStateKey = 'gap-dashboard-panels';
  let panelState = {};
  try {
    panelState = JSON.parse(localStorage.getItem(panelStateKey) || '{}');
  } catch {
    panelState = {};
  }
  const prefersReducedMotion = window.matchMedia
    ? window.matchMedia('(prefers-reduced-motion: reduce)').matches
    : false;
  const coverageCardMap = {
    covered: document.getElementById('coveredCard'),
    weak: document.getElementById('weakCard'),
    gap: document.getElementById('gapCard'),
  };
  const analysisPhases = [
    'Streaming insights in real time…',
    'Cross-checking coverage against catalog…',
    'Synthesizing insights and recommendations…',
    'Packaging product proposals for you…',
  ];
  let analysisPhaseTimer = null;
  let analysisPhaseIndex = 0;

  const startAnalysisProgress = () => {
    stopAnalysisProgress();
    analysisPhaseIndex = 0;
    setStatus(analysisPhases[analysisPhaseIndex]);
    analysisPhaseTimer = setInterval(() => {
      analysisPhaseIndex = (analysisPhaseIndex + 1) % analysisPhases.length;
      setStatus(analysisPhases[analysisPhaseIndex]);
    }, 2500);
  };

  const stopAnalysisProgress = () => {
    if (analysisPhaseTimer) {
      clearInterval(analysisPhaseTimer);
      analysisPhaseTimer = null;
    }
  };

  const setActiveProposalView = view => {
    proposalView = view;
    proposalViewButtons.forEach(btn => {
      const matches = (btn.dataset.proposalView || 'cards') === view;
      btn.classList.toggle('active', matches);
    });
  };

  const persistContentStudioPrefill = payload => {
    try {
      if (payload) {
        localStorage.setItem(CONTENT_STUDIO_PREFILL_KEY, JSON.stringify(payload));
      } else {
        localStorage.removeItem(CONTENT_STUDIO_PREFILL_KEY);
      }
    } catch (err) {
      console.error('Unable to persist content studio prefill', err);
    }
  };

  const persistProposalsForContentStudio = proposals => {
    try {
      if (Array.isArray(proposals) && proposals.length) {
        localStorage.setItem(CONTENT_STUDIO_PROPOSALS_KEY, JSON.stringify(proposals));
      } else {
        localStorage.removeItem(CONTENT_STUDIO_PROPOSALS_KEY);
      }
    } catch (err) {
      console.error('Unable to persist proposal cache', err);
    }
  };

  const updateProposalViewAvailability = hasData => {
    proposalViewButtons.forEach(btn => {
      btn.disabled = !hasData;
    });
    if (!hasData) {
      setActiveProposalView('cards');
    }
  };

  const getKeywordKey = item => String(item.id ?? item.keyword);

  const setPanelVisibility = (panelId, isVisible) => {
    const panel = document.getElementById(panelId);
    if (!panel) return;
    panel.classList.toggle('hidden', !isVisible);
  };

  const handleCoverageAnimationEnd = event => {
    const card = event.currentTarget;
    if (!card || !event.animationName) return;
    if (event.animationName === 'coverageFadeOut') {
      card.classList.add('hidden');
      card.classList.remove('fading-out');
    }
    if (event.animationName === 'coverageFadeIn') {
      card.classList.remove('fading-in');
    }
  };

  const animateCoverageCard = (card, shouldShow) => {
    if (!card) return;
    const isHidden = card.classList.contains('hidden');
    if (prefersReducedMotion) {
      card.classList.toggle('hidden', !shouldShow);
      return;
    }
    card.classList.remove('fading-in', 'fading-out');
    if (shouldShow) {
      if (isHidden) {
        card.classList.remove('hidden');
        requestAnimationFrame(() => card.classList.add('fading-in'));
      }
    } else if (!isHidden) {
      card.classList.add('fading-out');
    }
  };

  const updateHeroStats = (incomingSummary = null) => {
    if (incomingSummary) {
      lastCoverageSummary = incomingSummary;
    }
    if (heroKeywordCount) {
      heroKeywordCount.textContent = String(state.keywords.length || 0);
    }
    if (heroTrendCount) {
      heroTrendCount.textContent = String(state.selectedTrendIndexes.size || 0);
    }
    if (heroGapCount) {
      const summary = incomingSummary || lastCoverageSummary;
      const gapCount = summary && summary.gap ? summary.gap.count ?? summary.gap : 0;
      heroGapCount.textContent = String(gapCount || 0);
    }
  };

  const renderTrendMarquee = () => {
    if (!trendMarqueeTrack) return;
    trendMarqueeTrack.innerHTML = '';
    const list = state.trends.slice(0, 8);
    if (!list.length) {
      const span = document.createElement('span');
      span.textContent = 'Feed will populate after you pull live trends.';
      trendMarqueeTrack.appendChild(span);
      return;
    }
    const phrases = list
      .map(item => {
        const name = item.trend || item.name || 'Trend';
        const impact = item.impact || item.insight || '';
        return impact ? `${name} — ${impact}` : name;
      })
      .filter(Boolean);
    const loop = phrases.length ? [...phrases, ...phrases] : ['Trends updating…'];
    loop.forEach(text => {
      const span = document.createElement('span');
      span.textContent = text;
      trendMarqueeTrack.appendChild(span);
    });
  };

  const getSelectedTrends = () =>
    Array.from(state.selectedTrendIndexes)
      .map(idx => state.trends[idx])
      .filter(Boolean);

  const summarizeInsights = insightSummary => {
    if (Array.isArray(insightSummary)) {
      return insightSummary
        .map(item => {
          if (typeof item === 'string') return item;
          if (!item || typeof item !== 'object') return '';
          if (item.text) return item.text;
          return Object.values(item)
            .filter(Boolean)
            .join(' — ');
        })
        .filter(Boolean)
        .slice(0, 3)
        .join('\n');
    }
    if (typeof insightSummary === 'string') return insightSummary;
    return '';
  };

  const buildContentStudioPrefillFromTrends = (selectedTrends, analysis) => {
    const primaryBusiness = state.businesses?.[0] || {};
    const summary =
      primaryBusiness.strapline ||
      primaryBusiness.description ||
      primaryBusiness.name ||
      'Your brand narrative';
    const goalTrendNames = selectedTrends.map(item => item?.trend || item?.name).filter(Boolean);
    const campaignGoal = goalTrendNames.length
      ? `Activate campaigns around ${goalTrendNames.slice(0, 2).join(' & ')}`
      : 'Launch the next GTM campaign';
    const audience = primaryBusiness.audience || 'Product & growth teams';
    const trendNotes = selectedTrends
      .slice(0, 3)
      .map(item => {
        const desc = item?.description || item?.trend_summary || '';
        return `• ${item?.trend || item?.name || 'Trend'}${desc ? `: ${desc}` : ''}`;
      })
      .join('\n');
    const insightText = summarizeInsights(analysis?.insights?.insight_summary);
    const actionPlan = Array.isArray(analysis?.action_plan)
      ? analysis.action_plan.slice(0, 3).map((item, idx) => `${idx + 1}. ${item}`).join('\n')
      : '';
    const adTextParts = [trendNotes, insightText, actionPlan].filter(Boolean);
    return {
      source: 'gap-analysis',
      brand_summary: summary,
      campaign_goal: campaignGoal,
      target_audience: audience,
      ad_text: adTextParts.join('\n\n') || trendNotes || summary,
      tone: 'professional',
      platform: 'linkedin',
      outputs: ['text', 'poster'],
      trend_list: goalTrendNames,
    };
  };

  const buildContentStudioPrefillFromProposal = proposal => {
    const coverageLevel = getCoverageLabel(proposal.coverage_level);
    const summary = `${proposal.trend || 'Trend'} (${coverageLevel})`;
    const persona = proposal.target_persona || 'Product teams';
    const adNarrative = [
      proposal.proposal && `${proposal.proposal}`,
      proposal.why_it_helps && `${proposal.why_it_helps}`,
    ]
      .filter(Boolean)
      .join(' ');
    const adText = [
      `🚀 ${proposal.trend || 'New initiative'} for ${persona}.`,
      adNarrative,
      'Ready to pilot? Let’s talk.',
    ]
      .filter(Boolean)
      .join(' ');
    const proposalDetails = {
      trend: proposal.trend || 'Trend',
      target_persona: persona,
      coverage_level: proposal.coverage_level || 'gap',
      proposal: proposal.proposal || '',
      why_it_helps: proposal.why_it_helps || '',
      success_metrics: Array.isArray(proposal.success_metrics) ? proposal.success_metrics : [],
      launch_steps: Array.isArray(proposal.launch_steps) ? proposal.launch_steps : [],
      risks: Array.isArray(proposal.risks) ? proposal.risks : [],
      system_impact: proposal.system_impact || '',
      working_hours: proposal.working_hours,
      working_price: proposal.working_price,
      keywords: Array.isArray(proposal.keywords) ? proposal.keywords : [],
    };
    return {
      source: 'gap-proposal',
      brand_summary: summary,
      campaign_goal: `Ship ${proposal.trend || 'trend'} extension`,
      target_audience: persona,
      ad_text: adText,
      tone: 'professional',
      platform: 'linkedin',
      outputs: ['text', 'poster'],
      trend_list: proposal.keywords || [],
      proposal_details: proposalDetails,
    };
  };

  const setContentStudioPrefill = (selectedTrends, analysis) => {
    if (!selectedTrends.length || !contentStudioUrl) {
      pendingContentPrefill = null;
    } else {
      pendingContentPrefill = buildContentStudioPrefillFromTrends(selectedTrends, analysis);
    }
    updateContentStudioButtonState();
  };

  const applyCoverageFilter = filter => {
    const normalized = filter || 'all';
    Object.entries(coverageCardMap).forEach(([key, card]) => {
      const shouldShow = normalized === 'all' || normalized === key;
      animateCoverageCard(card, shouldShow);
    });
  };

  Object.values(coverageCardMap).forEach(card => {
    if (!card) return;
    card.addEventListener('animationend', handleCoverageAnimationEnd);
  });


  const getFilteredKeywords = () => {
    const filter = state.keywordFilter.trim().toLowerCase();
    if (!filter) return [...state.keywords];
    return state.keywords.filter(item => (item.keyword || '').toLowerCase().includes(filter));
  };

  const setStatus = (message, isError = false) => {
    statusEl.textContent = message || '';
    statusEl.style.color = isError ? '#f87171' : '#94a3b8';
  };

  const handleProposalContentClick = proposal => {
    if (!proposalContentUrl) {
      setStatus('Proposal studio is not configured yet.', true);
      return;
    }
    if (!proposal) {
      setStatus('Proposal data unavailable. Refresh the page and try again.', true);
      return;
    }
    const prefill = buildContentStudioPrefillFromProposal(proposal);
    try {
      localStorage.setItem(CONTENT_STUDIO_PREFILL_KEY, JSON.stringify(prefill));
      persistProposalsForContentStudio(lastProposalsData);
    } catch (err) {
      console.error('Unable to persist proposal prefill', err);
      setStatus('Unable to open content studio automatically. Please try again.', true);
      return;
    }
    window.location.href = proposalContentUrl;
  };

  const setTrendStatus = (message, isError = false) => {
    if (!trendStatusText) return;
    trendStatusText.textContent = message || '';
    trendStatusText.style.color = isError ? '#f87171' : '#94a3b8';
  };

  const setProgress = step => {
    progressSteps?.forEach(el => {
      if (el.dataset.step === step) {
        el.classList.add('active');
      } else {
        el.classList.remove('active');
      }
    });
  };

  const setView = view => {
    if (view === 'loading') {
      placeholder.style.display = 'none';
      loadingEl.style.display = 'flex';
      body.style.display = 'none';
    } else if (view === 'results') {
      placeholder.style.display = 'none';
      loadingEl.style.display = 'none';
      body.style.display = 'flex';
    } else {
      placeholder.style.display = 'block';
      loadingEl.style.display = 'none';
      body.style.display = 'none';
    }
  };

  const toggleModal = (modal, show) => {
    if (!modal) return;
    modal.classList.toggle('active', show);
  };

  const registerRevealAnimations = () => {
    const selectors = [
      '.gap-card',
      '.dashboard-panel',
      '.coverage-card',
      '.insights-card',
      '.recommendations-card',
      '.proposals-card',
      '.catalog-card',
      '.opportunity-card',
      '.action-plan-card',
    ];
    const nodes = document.querySelectorAll(selectors.join(','));
    if (!nodes.length) {
      return;
    }
    nodes.forEach(node => node.classList.add('reveal-item'));
    if (!('IntersectionObserver' in window) || prefersReducedMotion) {
      nodes.forEach(node => node.classList.add('in-view'));
      return;
    }
    const observer = new IntersectionObserver(
      entries => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            entry.target.classList.add('in-view');
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.2, rootMargin: '0px 0px -10% 0px' }
    );
    nodes.forEach(node => observer.observe(node));
  };

  const updateSelectionPills = () => {
    if (productCountPill) {
      const productCount = state.businesses.reduce((sum, biz) => sum + (biz.products?.length || 0), 0);
      productCountPill.textContent = `${productCount} product${productCount === 1 ? '' : 's'} loaded`;
    }
    if (trendCountPill) {
      const trendCount = state.selectedTrendIndexes.size;
      trendCountPill.textContent = `${trendCount} trend${trendCount === 1 ? '' : 's'} selected`;
    }
    if (keywordCountBadge) {
      keywordCountBadge.textContent = `${state.selectedKeywordIds.size} selected`;
    }
    if (viewProposalsModalBtn) {
      viewProposalsModalBtn.disabled = !lastProposalsData.length;
    }
    if (downloadProposalsBtn) {
      const hasDownloadData = Boolean((lastRenderedProposals && lastRenderedProposals.length) || lastProposalsData.length);
      downloadProposalsBtn.disabled = !hasDownloadData;
    }
    updateProposalViewAvailability(Boolean(lastProposalsData.length));
    if (discoverTrendsBtn) {
      discoverTrendsBtn.disabled = state.selectedKeywordIds.size === 0;
    }
    updateContentStudioButtonState();
  };

  const canLaunchContentStudio = () => Boolean(proposalContentUrl && (lastProposalsData.length || pendingContentPrefill));

  const updateContentStudioButtonState = () => {
    if (!generateContentBtn) return;
    generateContentBtn.disabled = !canLaunchContentStudio();
  };

  const normalizeKeywords = items => {
    if (!Array.isArray(items)) return [];
    return items
      .map(item => {
        if (typeof item === 'string') {
          return { keyword: item };
        }
        if (item && typeof item === 'object') {
          if (item.keyword && typeof item.keyword === 'string') {
            return { keyword: item.keyword, category: item.category };
          }
          if (Array.isArray(item.trend_keywords)) {
            return item.trend_keywords
              .filter(kw => typeof kw === 'string' && kw.trim())
              .map(kw => ({ keyword: kw.trim(), category: item.category }));
          }
        }
        return null;
      })
      .flat()
      .filter(Boolean);
  };

  const flattenGenerateTrendResults = (payload, fallbackKeywords = []) => {
    if (!Array.isArray(payload)) return [];
    const flattened = [];
    payload.forEach(entry => {
      if (!entry || entry.error) {
        return;
      }
      const baseKeywords = Array.isArray(entry.keywords) && entry.keywords.length
        ? entry.keywords
        : typeof entry.keyword === 'string'
        ? [entry.keyword]
        : fallbackKeywords;
      const results = Array.isArray(entry.results) ? entry.results : [];
      results.forEach(item => {
        if (!item) return;
        const title = item.trend || item.title || item.core_concept || baseKeywords[0];
        if (!title) return;
        const descriptionParts = [];
        if (item.description) descriptionParts.push(item.description);
        if (item.core_concept && (!item.description || !item.description.includes(item.core_concept))) {
          descriptionParts.push(item.core_concept);
        }
        if (item.business_value) descriptionParts.push(item.business_value);
        if (item.target_audience && item.target_audience !== 'unknown') {
          descriptionParts.push(`Audience: ${item.target_audience}`);
        }
        if (item.domain && item.domain !== 'unknown') {
          descriptionParts.push(`Domain: ${item.domain}`);
        }
        const description = descriptionParts.join(' ').trim() || `Trend insight generated for ${title}.`;
        const keywords = Array.isArray(item.keywords) && item.keywords.length
          ? item.keywords
          : baseKeywords.length
          ? baseKeywords
          : fallbackKeywords;
        flattened.push({
          trend: title,
          description,
          keywords,
          source: item.source || 'generate-trends',
          url: item.url || '',
        });
      });
    });
    return flattened;
  };

  const normalizeTrendPayloadArray = (payload, fallbackKeywords = []) => {
    if (!Array.isArray(payload) || !payload.length) return [];
    const hasNestedResults = payload.some(item => Array.isArray(item?.results));
    if (hasNestedResults) {
      return flattenGenerateTrendResults(payload, fallbackKeywords);
    }
    return payload;
  };

  const renderKeywords = () => {
    if (!keywordList) return;
    keywordList.innerHTML = '';
    const dataset = getFilteredKeywords();
    if (!Array.isArray(state.keywords) || !state.keywords.length) {
      if (keywordEmptyState) keywordEmptyState.textContent = 'No keywords saved yet. Add some from your account.';
      updateSelectionPills();
      updateHeroStats();
      return;
    }
    if (!dataset.length) {
      if (keywordEmptyState) keywordEmptyState.textContent = 'No keywords match your search.';
      updateSelectionPills();
      updateHeroStats();
      return;
    }
    if (keywordEmptyState) keywordEmptyState.textContent = '';
    dataset.forEach(item => {
      const key = getKeywordKey(item);
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'chip-option';
      btn.dataset.keywordId = key;
      btn.textContent = item.keyword;
      if (item.category) {
        btn.title = `${item.keyword} · ${item.category}`;
      }
      const toggleSelected = () => {
        if (state.selectedKeywordIds.has(key)) {
          state.selectedKeywordIds.delete(key);
          btn.classList.remove('selected');
          btn.setAttribute('aria-pressed', 'false');
        } else {
          state.selectedKeywordIds.add(key);
          btn.classList.add('selected');
          btn.setAttribute('aria-pressed', 'true');
        }
        updateSelectionPills();
      };
      btn.addEventListener('click', toggleSelected);
      if (state.selectedKeywordIds.has(key)) {
        btn.classList.add('selected');
        btn.setAttribute('aria-pressed', 'true');
      } else {
        btn.setAttribute('aria-pressed', 'false');
      }
      keywordList.appendChild(btn);
    });
    updateSelectionPills();
    updateHeroStats();
  };

  const applyFallbackKeywords = message => {
    state.keywords = fallbackKeywords.map(item => ({ ...item }));
    state.keywordFilter = '';
    state.selectedKeywordIds.clear();
    renderKeywords();
    if (keywordEmptyState) keywordEmptyState.textContent = message;
    updateSelectionPills();
    updateHeroStats();
  };

  const fetchKeywords = async () => {
    if (!keywordsApi || !userId) {
      applyFallbackKeywords('Keyword API not configured. Using starter keywords.');
      return;
    }
    if (keywordEmptyState) keywordEmptyState.textContent = 'Loading keywords…';
    try {
      const response = await fetch(`${keywordsApi}?user_id=${encodeURIComponent(userId)}`);
      if (!response.ok) throw new Error('Failed to load keywords');
      const data = await response.json();
      if (!data.success) throw new Error(data.message || 'Cannot load keywords');
      const normalized = normalizeKeywords(data.keywords || []);
      state.keywords = normalized;
      if (!state.keywords.length) {
        applyFallbackKeywords('No saved keywords yet. Using starter keywords.');
        return;
      }
      state.selectedKeywordIds.clear();
      renderKeywords();
      if (keywordEmptyState) keywordEmptyState.textContent = '';
    } catch (err) {
      applyFallbackKeywords(`Using starter keywords (${err.message}).`);
    }
  };

  const renderCatalog = () => {
    if (!catalogSummary || !catalogList) return;
    catalogList.innerHTML = '';
    const totalBusinesses = state.businesses.length;
    const totalProducts = state.businesses.reduce((sum, biz) => sum + (biz.products?.length || 0), 0);
    if (totalBusinesses === 0) {
      if (catalogEmptyState) catalogEmptyState.textContent = 'No products found. Add them from your account profile.';
      catalogSummary.innerHTML = '';
      updateSelectionPills();
      return;
    }
    if (catalogEmptyState) catalogEmptyState.textContent = '';
    catalogSummary.innerHTML = `
      <span>${totalBusinesses} business${totalBusinesses === 1 ? '' : 'es'}</span>
      <span>${totalProducts} product${totalProducts === 1 ? '' : 's'}</span>
    `;
    state.businesses.forEach(biz => {
      const li = document.createElement('li');
      const products = biz.products || [];
      const productText = products.slice(0, 3).map(p => p.name || 'Unnamed').join(' • ');
      const name = biz.name || 'Unnamed Business';
      const strapline = biz.strapline || biz.audience || 'Add a strapline to describe this business.';
      li.innerHTML = `
        <h4>${name}</h4>
        <p>${strapline}</p>
        <div class="catalog-products">${productText || 'No products added yet.'}</div>
      `;
      catalogList.appendChild(li);
    });
    updateSelectionPills();
  };

  const applyFallbackBusinesses = message => {
    state.businesses = fallbackBusinesses;
    renderCatalog();
    if (catalogEmptyState) catalogEmptyState.textContent = message;
  };

  const fetchBusinesses = async () => {
    if (!businessApi || !userId) {
      applyFallbackBusinesses('Business API not configured. Using demo products.');
      return;
    }
    if (catalogEmptyState) catalogEmptyState.textContent = 'Loading product catalog…';
    try {
      const response = await fetch(`${businessApi}?user_id=${encodeURIComponent(userId)}`);
      if (!response.ok) throw new Error('Failed to load catalog');
      const data = await response.json();
      if (!data.success) throw new Error(data.message || 'Cannot load catalog');
      state.businesses = data.businesses || [];
      if (!state.businesses.length) {
        applyFallbackBusinesses('No products saved yet. Showing demo catalog.');
        return;
      }
      renderCatalog();
      if (catalogEmptyState) catalogEmptyState.textContent = '';
    } catch (err) {
      applyFallbackBusinesses(`Using demo catalog (${err.message}).`);
    }
  };

  const renderTrends = () => {
    if (!trendResults) return;
    trendResults.innerHTML = '';
    if (!Array.isArray(state.trends) || !state.trends.length) {
      if (trendEmptyState) trendEmptyState.textContent = 'No trends yet. Try different keywords.';
      updateSelectionPills();
      updateHeroStats();
      renderTrendMarquee();
      return;
    }
    if (trendEmptyState) trendEmptyState.textContent = '';
    state.trends.forEach((item, idx) => {
      const card = document.createElement('button');
      card.type = 'button';
      card.className = 'trend-card-item';
      card.dataset.trendIndex = idx;
      const keywords = (item.keywords || []).slice(0, 4);
      const keywordHtml = keywords.length
        ? `<div class="trend-tags">${keywords.map(tag => `<span>${tag}</span>`).join('')}</div>`
        : '';
      const sourceLabel = item.source ? `<span class="trend-source">${item.source}</span>` : '';
      card.innerHTML = `
        <div class="trend-card-head">
          <h4>${item.trend || item.title}</h4>
          ${sourceLabel}
        </div>
        <p>${item.description || 'No description provided.'}</p>
        ${keywordHtml}
      `;
      if (state.selectedTrendIndexes.has(idx)) {
        card.classList.add('selected');
      }
      card.addEventListener('click', () => {
        if (state.selectedTrendIndexes.has(idx)) {
          state.selectedTrendIndexes.delete(idx);
          card.classList.remove('selected');
        } else {
          state.selectedTrendIndexes.add(idx);
          card.classList.add('selected');
        }
        updateSelectionPills();
        updateHeroStats();
      });
      trendResults.appendChild(card);
    });
    updateSelectionPills();
    updateHeroStats();
    renderTrendMarquee();
  };

  const discoverTrends = async () => {
    if (!trendsApi) {
      setTrendStatus('Trend API not configured.', true);
      return;
    }
    if (!state.selectedKeywordIds.size) {
      setTrendStatus('Select at least one keyword first.', true);
      return;
    }
    trendCard?.classList.remove('hidden');
    setTrendStatus('Fetching live trends…');
    try {
      const selectedKeys = Array.from(state.selectedKeywordIds);
      const selectedRows = state.keywords.filter(item =>
        selectedKeys.includes(String(item.id ?? item.keyword))
      );
      if (!selectedRows.length) {
        setTrendStatus('Unable to resolve selected keywords. Refresh and try again.', true);
        return;
      }
      const keywordLabels = [];
      selectedRows.forEach(item => {
        const label = item.keyword;
        if (label) keywordLabels.push(label);
      });
      if (!keywordLabels.length) {
        setTrendStatus('Unable to resolve selected keywords. Refresh and try again.', true);
        return;
      }
      const payload = { keywords: keywordLabels };
      const response = await fetch(trendsApi, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!response.ok) throw new Error('Trend fetch failed');
      const data = await response.json();
      let normalizedTrends = [];
      if (Array.isArray(data)) {
        normalizedTrends = normalizeTrendPayloadArray(data, keywordLabels);
      } else if (data && Array.isArray(data.trends)) {
        normalizedTrends = normalizeTrendPayloadArray(data.trends, keywordLabels);
      } else if (data && data.success && Array.isArray(data.data)) {
        normalizedTrends = normalizeTrendPayloadArray(data.data, keywordLabels);
      } else {
        throw new Error(data && data.message ? data.message : 'Unable to fetch trends');
      }
      state.trends = normalizedTrends || [];
      state.selectedTrendIndexes.clear();
      renderTrends();
      setTrendStatus('Trends updated. Pick the ones you want to analyze.');
      setProgress('trends');
    } catch (err) {
      setTrendStatus(err.message, true);
    }
  };

  const renderList = (element, items, emptyText) => {
    element.innerHTML = '';
    if (!Array.isArray(items) || !items.length) {
      element.innerHTML = `<li class="muted-text">${emptyText}</li>`;
      return;
    }
    items.forEach(item => {
      const li = document.createElement('li');
      li.innerHTML = `<strong>${item.trend}</strong><br><small>${item.business} → ${item.best_match_product} (${item.similarity})</small>`;
      element.appendChild(li);
    });
  };

  const renderSummary = summary => {
    if (!summary) {
      insightEl.textContent = 'No summary available.';
      return;
    }
    if (Array.isArray(summary)) {
      insightEl.innerHTML = `<ul>${summary.map(item => `<li>${item}</li>`).join('')}</ul>`;
    } else if (typeof summary === 'string') {
      insightEl.innerHTML = summary.replace(/\n/g, '<br>');
    } else {
      insightEl.textContent = JSON.stringify(summary, null, 2);
    }
  };

  const renderRecommendations = recs => {
    recommendationsList.innerHTML = '';
    if (!Array.isArray(recs) || !recs.length) {
      recommendationsList.innerHTML = '<p>No recommendations returned.</p>';
      return;
    }
    lastRecommendationsText = recs.map(rec => `${rec.title || 'Recommendation'}: ${rec.why_it_matters || ''}`).join('\n');
    recs.forEach(rec => {
      const div = document.createElement('div');
      div.className = 'recommendation-item';
      div.innerHTML = `
        <h4>${rec.title || 'Recommendation'}</h4>
        <p>${rec.why_it_matters || ''}</p>
        <p><strong>Actions:</strong> ${Array.isArray(rec.actions) ? rec.actions.join(', ') : rec.actions || ''}</p>
        <p><strong>Priority:</strong> ${rec.priority || 'Unspecified'}</p>
      `;
      recommendationsList.appendChild(div);
    });
  };

  const getCoverageLabel = level => {
    const normalized = (level || 'gap').toLowerCase();
    if (normalized === 'weak') return 'Weak Coverage';
    if (normalized === 'covered') return 'Covered';
    return 'Gap';
  };

  const coverageClassName = level => {
    const normalized = (level || 'gap').toLowerCase();
    if (normalized === 'weak') return 'coverage-weak';
    if (normalized === 'covered') return 'coverage-covered';
    return 'coverage-gap';
  };

  const formatHours = value => `${Math.round(Number(value) || 0)} hrs`;
  const formatPrice = value =>
    `$${Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;

  const createIconList = (items, type) => {
    if (!Array.isArray(items) || !items.length) return '';
    const chipClass = type === 'metric' ? 'metric' : 'risk';
    const label = type === 'metric' ? 'Success metrics' : 'Risks & dependencies';
    const symbol = type === 'metric' ? '↗' : '!';
    return `
      <div class="proposal-section">
        <h5>${label}</h5>
        <ul class="icon-list">
          ${items.map(item => `<li><span class="icon-chip ${chipClass}">${symbol}</span>${item}</li>`).join('')}
        </ul>
      </div>
    `;
  };

  const buildTimeline = steps => {
    if (!Array.isArray(steps) || !steps.length) {
      return '<p class="muted-text">No launch steps provided.</p>';
    }
    return `<ol class="launch-timeline">${steps.map(step => `<li>${step}</li>`).join('')}</ol>`;
  };

  const renderProposalCards = dataset => {
    if (!productProposalsList) return;
    productProposalsList.innerHTML = '';
    dataset.forEach((item, idx) => {
      const coverageLevel = (item.coverage_level || 'gap').toLowerCase();
      const coverageLabel = getCoverageLabel(coverageLevel);
      const metrics = Array.isArray(item.success_metrics) ? item.success_metrics : [];
      const risks = Array.isArray(item.risks) ? item.risks : [];
      const steps = Array.isArray(item.launch_steps) ? item.launch_steps : [];

      const card = document.createElement('article');
      card.className = `proposal-item ${coverageClassName(coverageLevel)}`;
      card.style.setProperty('--proposal-delay', `${idx * 80}ms`);

      const summary = document.createElement('div');
      summary.className = 'proposal-summary';
      summary.innerHTML = `
        <div>
          <h4>${item.trend || 'Trend'}</h4>
          <small>${item.proposal || 'No proposal generated.'}</small>
        </div>
      `;

      const stats = document.createElement('div');
      stats.className = 'proposal-badges';
      stats.innerHTML = `
        <span class="proposal-pill">${formatHours(item.working_hours)}</span>
        <span class="proposal-pill">${formatPrice(item.working_price)}</span>
        <span class="proposal-coverage-badge ${coverageLevel}">${coverageLabel}</span>
      `;
      summary.appendChild(stats);

      const toggleBtn = document.createElement('button');
      toggleBtn.type = 'button';
      toggleBtn.className = 'proposal-toggle-btn';
      toggleBtn.setAttribute('aria-expanded', 'false');
      toggleBtn.textContent = 'Show details';
      summary.appendChild(toggleBtn);

      const detail = document.createElement('div');
      detail.className = 'proposal-detail';
      detail.hidden = true;
      detail.innerHTML = `
        <p class="proposal-why">${item.why_it_helps || ''}</p>
        <div class="proposal-section">
          <h5>Target persona</h5>
          <p class="proposal-persona">
            <span class="icon-chip persona">🎯</span>${item.target_persona || 'N/A'}
          </p>
        </div>
        <div class="proposal-section">
          <h5>System impact</h5>
          <p class="proposal-system">${item.system_impact || 'N/A'}</p>
        </div>
        ${createIconList(metrics, 'metric')}
        ${createIconList(risks, 'risk')}
        <div class="proposal-section">
          <h5>Launch plan</h5>
          ${buildTimeline(steps)}
        </div>
      `;

      const actionRow = document.createElement('div');
      actionRow.className = 'proposal-actions';
      actionRow.innerHTML = `
        <button type="button" class="btn btn-outline btn-sm proposal-content-btn">Create Content</button>
      `;
      detail.appendChild(actionRow);

      toggleBtn.addEventListener('click', () => {
        const expanded = toggleBtn.getAttribute('aria-expanded') === 'true';
        toggleBtn.setAttribute('aria-expanded', String(!expanded));
        toggleBtn.textContent = expanded ? 'Show details' : 'Hide details';
        detail.hidden = expanded;
      });

      const contentBtn = actionRow.querySelector('.proposal-content-btn');
      contentBtn?.addEventListener('click', () => handleProposalContentClick(item));

      card.appendChild(summary);
      card.appendChild(detail);
      productProposalsList.appendChild(card);
      requestAnimationFrame(() => {
        card.classList.add('animate-ready');
      });
    });
  };

  const renderProposalCompare = dataset => {
    if (!proposalCompareContainer) return;
    proposalCompareContainer.innerHTML = '';
    if (!dataset.length) {
      proposalCompareContainer.innerHTML = '<p>No product proposals to compare yet.</p>';
      return;
    }
    const table = document.createElement('table');
    table.innerHTML = `
      <thead>
        <tr>
          <th>Trend</th>
          <th>Coverage</th>
          <th>Persona</th>
          <th>Est. Hours</th>
          <th>Budget</th>
          <th>Key Metric</th>
        </tr>
      </thead>
      <tbody>
        ${dataset
          .map(item => {
            const coverageLevel = (item.coverage_level || 'gap').toLowerCase();
            const metrics = Array.isArray(item.success_metrics) ? item.success_metrics : [];
            return `
              <tr>
                <td>${item.trend || 'Trend'}</td>
                <td>${getCoverageLabel(coverageLevel)}</td>
                <td>${item.target_persona || 'N/A'}</td>
                <td>${formatHours(item.working_hours)}</td>
                <td>${formatPrice(item.working_price)}</td>
                <td>${metrics[0] || '—'}</td>
              </tr>
            `;
          })
          .join('')}
      </tbody>
    `;
    proposalCompareContainer.appendChild(table);
  };

  const paintProposals = () => {
    if (!productProposalsList || !proposalCompareContainer) return;
    const dataset =
      proposalFilter === 'all'
        ? lastProposalsData
        : lastProposalsData.filter(item =>
            proposalFilter === 'gap'
              ? (item.coverage_level || 'gap').toLowerCase() !== 'weak'
              : (item.coverage_level || 'gap').toLowerCase() === 'weak'
          );
    lastRenderedProposals = dataset;
    if (!dataset.length) {
      const message = lastProposalsData.length
        ? proposalFilter === 'gap'
          ? 'No proposals for gap coverage yet.'
          : proposalFilter === 'weak'
            ? 'No proposals for weak coverage yet.'
            : 'No product proposals match this filter.'
        : 'No product proposals yet.';
      lastRenderedProposals = [];
      setActiveProposalView('cards');
      productProposalsList.classList.remove('hidden');
      proposalCompareContainer.classList.add('hidden');
      productProposalsList.innerHTML = `<p>${message}</p>`;
      proposalCompareContainer.innerHTML = '';
      updateSelectionPills();
      return;
    }

    if (proposalView === 'compare') {
      productProposalsList.classList.add('hidden');
      proposalCompareContainer.classList.remove('hidden');
      renderProposalCompare(dataset);
    } else {
      proposalCompareContainer.classList.add('hidden');
      productProposalsList.classList.remove('hidden');
      renderProposalCards(dataset);
    }

    updateSelectionPills();
  };

  const renderProductProposals = proposals => {
    if (!Array.isArray(proposals) || !proposals.length) {
      lastProposalsData = [];
      lastProposalsText = '';
      persistProposalsForContentStudio([]);
      updateSelectionPills();
      paintProposals();
      return;
    }
    lastProposalsData = proposals;
    persistProposalsForContentStudio(proposals);
    lastProposalsText = proposals
      .map(item => {
        const coverageLabel = getCoverageLabel(item.coverage_level);
        return `${item.trend || 'Trend'} [${coverageLabel}] -> ${item.proposal || ''} (${formatHours(
          item.working_hours
        )}, ${formatPrice(item.working_price)})`;
      })
      .join('\n');
    paintProposals();
  };

  const renderCoverageSummary = summary => {
    const container = document.getElementById('coverageSummary');
    if (!container) return;
    container.innerHTML = '';
    if (!summary) {
      container.innerHTML = '<div class="summary-chip"><p>No coverage data.</p></div>';
      updateHeroStats();
      return;
    }
    Object.entries(summary).forEach(([key, value]) => {
      const div = document.createElement('div');
      div.className = 'summary-chip';
      const label =
        key === 'covered' ? 'Covered' : key === 'weak' ? 'Weak coverage' : key === 'gap' ? 'Gaps' : key;
      div.innerHTML = `<h4>${value.count}</h4><p>${label} (${value.percent || 0}%)</p>`;
      container.appendChild(div);
    });
    updateHeroStats(summary);
  };

  const formatInteger = value => Math.round(value).toLocaleString();
  const formatCurrency = value =>
    `$${Number(value).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`;
  const formatDecimal = decimals => value =>
    Number(value).toLocaleString(undefined, {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });

  const animateNumber = (node, targetValue, { duration = 650, formatter = formatInteger } = {}) => {
    if (!node) return;
    if (typeof targetValue !== 'number' || Number.isNaN(targetValue)) {
      node.textContent = 'N/A';
      node.dataset.value = '';
      return;
    }
    const start = Number(node.dataset.value || 0);
    const startTime = performance.now();
    const tick = now => {
      const progress = Math.min((now - startTime) / duration, 1);
      const value = start + (targetValue - start) * progress;
      node.textContent = formatter(progress < 1 ? value : targetValue);
      if (progress < 1) {
        requestAnimationFrame(tick);
      } else {
        node.dataset.value = String(targetValue);
      }
    };
    requestAnimationFrame(tick);
  };

  const renderCatalogStats = (stats, pricing, description) => {
    const catalogStatsEl = document.getElementById('catalogStats');
    const pricingStatsEl = document.getElementById('pricingStats');
    const descriptionStatsEl = document.getElementById('descriptionStats');

    if (catalogStatsEl) {
      catalogStatsEl.innerHTML = '';
      if (!stats) {
        catalogStatsEl.innerHTML = '<p>No catalog data.</p>';
      } else {
        const totalProductsRow = document.createElement('p');
        totalProductsRow.innerHTML = 'Total products: <span class="stat-value" data-value="0">0</span>';
        catalogStatsEl.appendChild(totalProductsRow);
        animateNumber(totalProductsRow.querySelector('.stat-value'), stats.total_products || 0, {
          formatter: formatInteger,
        });

        const totalBusinessRow = document.createElement('p');
        totalBusinessRow.innerHTML = 'Total businesses: <span class="stat-value" data-value="0">0</span>';
        catalogStatsEl.appendChild(totalBusinessRow);
        animateNumber(totalBusinessRow.querySelector('.stat-value'), stats.total_businesses || 0, {
          formatter: formatInteger,
        });
      }
    }

    if (pricingStatsEl) {
      pricingStatsEl.innerHTML = '';
      if (!pricing || !pricing.has_pricing) {
        pricingStatsEl.innerHTML = '<p>No pricing data.</p>';
      } else {
        const avgPriceRow = document.createElement('p');
        avgPriceRow.innerHTML = 'Average price: <span class="stat-value" data-value="0">0</span>';
        pricingStatsEl.appendChild(avgPriceRow);
        animateNumber(avgPriceRow.querySelector('.stat-value'), pricing.avg_price, { formatter: formatCurrency });

        const rangeRow = document.createElement('p');
        rangeRow.innerHTML =
          'Range: <span class="stat-value" data-role="min" data-value="0">0</span> – <span class="stat-value" data-role="max" data-value="0">0</span>';
        pricingStatsEl.appendChild(rangeRow);
        animateNumber(rangeRow.querySelector('[data-role="min"]'), pricing.min_price, { formatter: formatCurrency });
        animateNumber(rangeRow.querySelector('[data-role="max"]'), pricing.max_price, { formatter: formatCurrency });
      }
    }

    if (descriptionStatsEl) {
      descriptionStatsEl.innerHTML = '';
      if (!description) {
        descriptionStatsEl.innerHTML = '<p>No description insights.</p>';
      } else {
        const emptyRow = document.createElement('p');
        emptyRow.innerHTML =
          'Empty descriptions: <span class="stat-value" data-role="count" data-value="0">0</span> (<span class="stat-value" data-role="pct" data-value="0">0</span>%)';
        descriptionStatsEl.appendChild(emptyRow);
        animateNumber(emptyRow.querySelector('[data-role="count"]'), description.empty_descriptions || 0, {
          formatter: formatInteger,
        });
        animateNumber(emptyRow.querySelector('[data-role="pct"]'), description.empty_descriptions_pct || 0, {
          formatter: formatDecimal(1),
        });
      }
    }
  };

  const renderOpportunityMap = rows => {
    const tbody = document.querySelector('#opportunityTable tbody');
    if (!tbody) return;
    tbody.innerHTML = '';
    if (!Array.isArray(rows) || !rows.length) {
      tbody.innerHTML = '<tr><td colspan="4">No gaps detected.</td></tr>';
      return;
    }
    lastOpportunityData = rows;
    rows.forEach(row => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${row.trend}</td>
        <td>${row.best_match_product}</td>
        <td>${row.business}</td>
        <td>${row.note}</td>
      `;
      tbody.appendChild(tr);
    });
  };

  const renderActionPlan = plan => {
    const list = document.getElementById('actionPlanList');
    if (!list) return;
    list.innerHTML = '';
    if (!Array.isArray(plan) || !plan.length) {
      list.innerHTML = '<li>No action items suggested.</li>';
      return;
    }
    actionPlanStates = JSON.parse(localStorage.getItem(actionPlanStorageKey) || '{}');
    plan.forEach((item, idx) => {
      const li = document.createElement('li');
      li.innerHTML = `
        <label class="plan-check">
          <input type="checkbox" data-plan-index="${idx}">
          <span>${item}</span>
        </label>
      `;
      const checkbox = li.querySelector('input');
      checkbox.checked = Boolean(actionPlanStates[item]);
      checkbox.addEventListener('change', () => {
        actionPlanStates[item] = checkbox.checked;
        localStorage.setItem(actionPlanStorageKey, JSON.stringify(actionPlanStates));
      });
      list.appendChild(li);
    });
  };

  const submitAnalysis = async (generateProposals = proposalPreference === true) => {
    if (!apiEndpoint) {
      setStatus('Gap analysis endpoint is not configured.', true);
      return;
    }

    if (!state.businesses.length) {
      setStatus('No products loaded. Add products in your account first.', true);
      return;
    }

    const selectedTrends = Array.from(state.selectedTrendIndexes).map(idx => state.trends[idx]).filter(Boolean);
    if (!selectedTrends.length) {
      setStatus('Select at least one trend to analyze.', true);
      return;
    }

    setStatus('Sending data to backend…');
    setProgress('trends');
    setView('loading');
    pendingContentPrefill = null;
    updateContentStudioButtonState();

    try {
      const response = await fetch(apiEndpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          businesses: state.businesses,
          trends: selectedTrends,
          context: (contextInput?.value || '').trim(),
          generate_proposals: Boolean(generateProposals),
        }),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || 'Gap analysis failed.');
      }

      const data = await response.json();
      if (!data.success) {
        throw new Error(data.message || 'Analysis failed.');
      }

      const coverage = data.analysis.coverage || {};
      renderList(coveredList, coverage.covered, 'No strong coverage detected yet.');
      renderList(weakList, coverage.weak, 'No weak coverage entries.');
      renderList(gapList, coverage.gap, 'No gaps detected.');
      renderCoverageSummary(data.analysis.coverage_summary);

      renderSummary(data.analysis.insights?.insight_summary || data.analysis.insights?.summary);
      renderRecommendations(data.analysis.insights?.recommendations);
      renderProductProposals(data.analysis.product_proposals);

      const catalogReport = data.analysis.catalog_report || {};
      renderCatalogStats(
        catalogReport.catalog_stats,
        catalogReport.pricing_analysis,
        catalogReport.description_quality
      );
      renderOpportunityMap(data.analysis.opportunity_map);
      renderActionPlan(data.analysis.action_plan);

      setView('results');
      setStatus('Analysis complete.');
      setProgress('insights');
      setContentStudioPrefill(selectedTrends, data.analysis);
    } catch (err) {
      console.error(err);
      setStatus(err.message || 'Analysis failed.', true);
      setProgress('trends');
      setView('idle');
    }
  };

  const handleAnalyzeClick = () => {
    if (proposalPreference === null) {
      pendingAnalysis = true;
      toggleModal(proposalPromptModal, true);
      return;
    }
    submitAnalysis(proposalPreference === true);
  };

  refreshKeywordsBtn?.addEventListener('click', fetchKeywords);
  keywordSearchInput?.addEventListener('input', event => {
    state.keywordFilter = event.target.value || '';
    renderKeywords();
  });
  selectAllKeywordsBtn?.addEventListener('click', () => {
    getFilteredKeywords().forEach(item => state.selectedKeywordIds.add(getKeywordKey(item)));
    renderKeywords();
  });
  clearKeywordsBtn?.addEventListener('click', () => {
    state.selectedKeywordIds.clear();
    renderKeywords();
  });
  discoverTrendsBtn?.addEventListener('click', discoverTrends);
  selectAllTrendsBtn?.addEventListener('click', () => {
    state.trends.forEach((_, idx) => state.selectedTrendIndexes.add(idx));
    renderTrends();
  });
  clearTrendsBtn?.addEventListener('click', () => {
    state.selectedTrendIndexes.clear();
    renderTrends();
  });
  analyzeBtn.addEventListener('click', handleAnalyzeClick);

  filterButtons?.forEach(btn => {
    btn.addEventListener('click', () => {
      filterButtons.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const filter = btn.dataset.filter || 'all';
      applyCoverageFilter(filter);
    });
  });

  proposalViewButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      if (!lastProposalsData.length) return;
      const view = btn.dataset.proposalView === 'compare' ? 'compare' : 'cards';
      setActiveProposalView(view);
      paintProposals();
    });
  });

  generateContentBtn?.addEventListener('click', () => {
    if (!proposalContentUrl) {
      setStatus('Proposal studio is not configured yet.', true);
      return;
    }
    if (!lastProposalsData.length && !pendingContentPrefill) {
      setStatus('Run gap analysis and generate proposals before creating content.', true);
      return;
    }
    try {
      if (pendingContentPrefill) {
        localStorage.setItem(CONTENT_STUDIO_PREFILL_KEY, JSON.stringify(pendingContentPrefill));
      } else {
        localStorage.removeItem(CONTENT_STUDIO_PREFILL_KEY);
      }
      persistProposalsForContentStudio(lastProposalsData);
    } catch (err) {
      console.error('Unable to persist content studio context', err);
      setStatus('Unable to open content studio automatically. Please try again.', true);
      return;
    }
    window.location.href = proposalContentUrl;
  });

  copySummaryBtn?.addEventListener('click', () => {
    navigator.clipboard
      .writeText(insightEl.textContent.trim())
      .then(() => setStatus('Insight summary copied.'))
      .catch(() => setStatus('Unable to copy summary.', true));
  });

  copyRecommendationsBtn?.addEventListener('click', () => {
    navigator.clipboard
      .writeText(lastRecommendationsText || 'No recommendations.')
      .then(() => setStatus('Recommendations copied.'))
      .catch(() => setStatus('Unable to copy recommendations.', true));
  });

  copyProposalsBtn?.addEventListener('click', () => {
    navigator.clipboard
      .writeText(lastProposalsText || 'No product proposals.')
      .then(() => setStatus('Product proposals copied.'))
      .catch(() => setStatus('Unable to copy product proposals.', true));
  });

  proposalFilterButtons?.forEach(btn => {
    btn.addEventListener('click', () => {
      proposalFilterButtons.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      proposalFilter = btn.dataset.proposalFilter || 'all';
      paintProposals();
    });
  });

  viewProposalsModalBtn?.addEventListener('click', () => {
    if (!lastProposalsData.length) {
      setStatus('Generate proposals first to view details.', true);
      return;
    }
    if (proposalDetailsBody) {
      proposalDetailsBody.innerHTML = '';
      lastProposalsData.forEach(item => {
        const steps = Array.isArray(item.launch_steps) ? item.launch_steps : [];
        const wrapper = document.createElement('div');
        wrapper.className = 'proposal-item';
        const coverageLevel = (item.coverage_level || 'gap').toLowerCase();
        const coverageLabel = getCoverageLabel(coverageLevel);
        wrapper.innerHTML = `
          <div class="proposal-header">
            <h4>${item.trend || 'Trend'}</h4>
            <span class="proposal-coverage-badge ${coverageLevel}">${coverageLabel}</span>
          </div>
          <p class="proposal-main">${item.proposal || ''}</p>
          <p class="proposal-why">${item.why_it_helps || ''}</p>
          <p class="proposal-hours">Est. ${item.working_hours || 0} hrs · $${item.working_price || 0}</p>
          <p class="proposal-persona"><strong>Target persona:</strong> ${item.target_persona || 'N/A'}</p>
          ${
            Array.isArray(item.success_metrics) && item.success_metrics.length
              ? `<div class="proposal-metrics"><strong>Success metrics:</strong><ul>${item.success_metrics
                  .map(metric => `<li>${metric}</li>`)
                  .join('')}</ul></div>`
              : ''
          }
          <p class="proposal-system"><strong>System impact:</strong> ${item.system_impact || 'N/A'}</p>
          ${
            Array.isArray(item.risks) && item.risks.length
              ? `<div class="proposal-risks"><strong>Risks & dependencies:</strong><ul>${item.risks
                  .map(risk => `<li>${risk}</li>`)
                  .join('')}</ul></div>`
              : ''
          }
          ${
            steps.length
              ? `<ol>${steps.map(step => `<li>${step}</li>`).join('')}</ol>`
              : '<p class="muted-text">No launch steps provided.</p>'
          }
        `;
        proposalDetailsBody.appendChild(wrapper);
      });
    }
    toggleModal(proposalDetailsModal, true);
  });

  downloadProposalsBtn?.addEventListener('click', () => {
    const rowsSource = lastRenderedProposals.length ? lastRenderedProposals : lastProposalsData;
    if (!rowsSource.length) {
      setStatus('No proposals to download.', true);
      return;
    }
    const header = [
      'Trend',
      'Coverage',
      'Proposal',
      'Why It Helps',
      'Target Persona',
      'Success Metrics',
      'System Impact',
      'Risks',
      'Hours',
      'Price',
      'Launch Steps',
    ];
    const rows = rowsSource.map(item => [
      item.trend || '',
      getCoverageLabel(item.coverage_level),
      item.proposal || '',
      item.why_it_helps || '',
      item.target_persona || '',
      Array.isArray(item.success_metrics) ? item.success_metrics.join(' | ') : '',
      item.system_impact || '',
      Array.isArray(item.risks) ? item.risks.join(' | ') : '',
      item.working_hours || '',
      item.working_price || '',
      Array.isArray(item.launch_steps) ? item.launch_steps.join(' | ') : '',
    ]);
    const csv = [header, ...rows]
      .map(cols =>
        cols
          .map(col => `"${String(col || '').replace(/"/g, '""')}"`)
          .join(',')
      )
      .join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'product-proposals.csv';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
    setStatus('Product proposals downloaded.');
  });

  confirmProposalBtn?.addEventListener('click', () => {
    proposalPreference = true;
    toggleModal(proposalPromptModal, false);
    if (pendingAnalysis) {
      pendingAnalysis = false;
      submitAnalysis(true);
    }
  });

  skipProposalBtn?.addEventListener('click', () => {
    proposalPreference = false;
    toggleModal(proposalPromptModal, false);
    if (pendingAnalysis) {
      pendingAnalysis = false;
      submitAnalysis(false);
    }
  });

  document.querySelectorAll('[data-close-modal]').forEach(btn => {
    btn.addEventListener('click', () => {
      const target = btn.dataset.closeModal;
      if (target) {
        const modal = document.getElementById(target);
        toggleModal(modal, false);
      }
    });
  });

  panelToggleInputs?.forEach(input => {
    const panelId = input.dataset.panelTarget;
    if (!panelId) return;
    const stored = panelState[panelId];
    if (typeof stored === 'boolean') {
      input.checked = stored;
    }
    setPanelVisibility(panelId, input.checked);
    input.addEventListener('change', () => {
      const visible = input.checked;
      setPanelVisibility(panelId, visible);
      panelState[panelId] = visible;
      localStorage.setItem(panelStateKey, JSON.stringify(panelState));
    });
  });

  exportOpportunitiesBtn?.addEventListener('click', () => {
    if (!lastOpportunityData.length) {
      setStatus('No opportunity data to export.', true);
      return;
    }
    const header = ['Trend', 'Product', 'Business', 'Note'];
    const rows = lastOpportunityData.map(row => [
      row.trend,
      row.best_match_product,
      row.business,
      row.note,
    ]);
    const csv = [header, ...rows]
      .map(cols =>
        cols
          .map(col => `"${String(col || '').replace(/"/g, '""')}"`)
          .join(',')
      )
      .join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'gap-opportunities.csv';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
    setStatus('Opportunity CSV downloaded.');
  });

  registerRevealAnimations();
  setView('idle');
  setProgress('keywords');
  updateSelectionPills();
  renderTrendMarquee();
  updateHeroStats();
  setTrendStatus('Select keywords then run Find Trends.');
  setStatus('Load your products and pick the trends you want to analyze.');
  fetchKeywords();
  fetchBusinesses();
});
