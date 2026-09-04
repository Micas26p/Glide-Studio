const state = {
  version: '1.31.0',
  mode: 'fast',
  projects: [],
  activeProjectId: null,
  queueRendering: false,
  queuePaused: false,
  queuePauseRequested: false,
  queueStopRequested: false,
  queueBatchId: '',
  dragProjectId: null,
  projectDragTarget: null,
  projectDragTargetRect: null,
  projectDragPlaceAfter: false,
  projectDragJustDropped: false,
  renderGallery: [],
  videos: [],
  audios: [],
  backgroundTracks: [],
  subtitles: [],
  captions: [],
  scriptGuides: [],
  subtitleInfo: null,
  captionInfo: null,
  scriptGuideInfo: null,
  scriptGuidePlan: null,
  registry: new Map(),
  durations: new Map(),
  durationSources: new Map(),
  audioHealth: new Map(),
  thumbs: new Map(),
  mediaStatus: new Map(),
  videoOrderEdited: false,
  audioOrderEdited: false,
  backgroundOrderEdited: false,
  activeJobId: null,
  outputDir: '',
  renderActive: false,
  renderCancelRequested: false,
  runtimeConfig: null,
  backendPreflight: null,
  ctaAssets: [],
  selectedCta: localStorage.getItem('glide_cta_language') || '',
  themeMode: localStorage.getItem('glide_theme_mode') || 'system',
  uiMode: localStorage.getItem('glide_ui_mode') || 'simple',
  musicGenre: localStorage.getItem('glide_music_genre') || 'cinematic',
  sidebarCollapsed: localStorage.getItem('glide_sidebar_collapsed') === '1',
  presetMusic: {genres: []},
  ctaPositionPreset: localStorage.getItem('glide_cta_position') || 'top_right',
  ctaOffsetX: Number.isFinite(Number(localStorage.getItem('glide_cta_offset_x'))) ? Number(localStorage.getItem('glide_cta_offset_x')) : 0,
  ctaOffsetY: Number.isFinite(Number(localStorage.getItem('glide_cta_offset_y'))) ? Number(localStorage.getItem('glide_cta_offset_y')) : 0,
  ctaPreviewSound: false,
  introMode: localStorage.getItem('glide_intro_mode') || 'standard',
  videoListSignature: '',
  audioListSignature: '',
  backgroundListSignature: '',
  uiRefreshQueued: false,
  pendingListRefresh: false,
  autoDownloadedJobs: new Set(),
  finalOutputMode: localStorage.getItem('glide_final_output_mode') || 'downloads',
  finalOutputFolder: localStorage.getItem('glide_final_output_folder') || '',
  renderPriority: normalizedRenderPriority(localStorage.getItem('glide_render_priority') || 'balanced'),
  renderBudgetEnabled: localStorage.getItem('glide_render_budget_enabled') !== '0',
  renderEstimate: null,
  renderEstimateToken: 0,
  projectQueueSignature: '',
  projectQueueStructureSignature: '',
  pendingProjectLoadFrame: 0,
  projectDecorationToken: 0,
  timelineRenderGeneration: 0,
  projectChecksSignature: '',
  reportProjectId: '',
  reportView: 'project',
  mediaAnalysisToken: 0,
  lastStatusPaint: null,
  uiSoundsEnabled: localStorage.getItem('glide_ui_sounds_enabled') === '1',
  uiSoundStyle: localStorage.getItem('glide_ui_sound_style') || 'soft_tick',
  uiSoundScope: localStorage.getItem('glide_ui_sound_scope') || 'global',
  uiProjectDoneSoundEnabled: localStorage.getItem('glide_ui_project_done_sound_enabled') !== '0',
  uiAudioContext: null,
  renderShowcaseStage: '',
  renderShowcaseTick: 0,
  automator: {
    srts: [], audios: [], folders: [],
    sort: {},
  },
  automatorDrag: null,
  automatorSessionId: '',
  automatorAbortController: null,
  automatorApplying: false,
  settingsSaving: false,
};

const $ = (sel) => document.querySelector(sel);
const editorIntro = $('#editorIntro');
const systemThemeQuery = window.matchMedia ? window.matchMedia('(prefers-color-scheme: light)') : null;
const dropZone = $('#dropZone');
const folderInput = $('#folderInput');
const fileInput = $('#fileInput');
const videoInput = $('#videoInput');
const audioInput = $('#audioInput');
const backgroundInput = $('#backgroundInput');
const subtitleInput = $('#subtitleInput');
const captionInput = $('#captionInput');
const scriptGuideInput = $('#scriptGuideInput');
const videoTimeline = $('#videoTimeline');
const audioTimeline = $('#audioTimeline');
const backgroundTimeline = $('#backgroundTimeline');
const renderBtn = $('#renderBtn');
const modal = $('#renderModal');
const progressBar = $('#progressBar');
const eyePercent = $('#eyePercent');
const renderMsg = $('#renderMsg');
const renderTitle = $('#renderTitle');
const renderProjectMeta = $('#renderProjectMeta');
const renderLog = $('#renderLog');
const downloadBtn = $('#downloadBtn');
const openOutputBtn = $('#openOutputBtn');
const openExportsBtn = $('#openExportsBtn');
const themeSelect = $('#themeSelect');
const uiModeSelect = $('#uiModeSelect');
const renderPrioritySelect = $('#renderPrioritySelect');
const renderBudgetToggle = $('#renderBudgetToggle');
const settingsBtn = $('#settingsBtn');
const settingsModal = $('#settingsModal');
const closeSettingsModal = $('#closeSettingsModal');
const uiSoundsToggle = $('#uiSoundsToggle');
const uiSoundStyleSelect = $('#uiSoundStyleSelect');
const uiSoundScopeSelect = $('#uiSoundScopeSelect');
const uiProjectDoneSoundToggle = $('#uiProjectDoneSoundToggle');
const renderTimeEstimate = $('#renderTimeEstimate');
const renderEta = $('#renderEta');
const sidebarToggle = $('#sidebarToggle');
const dockSummary = $('#dockSummary');
const outputPath = $('#outputPath');
const subtitleStatus = $('#subtitleStatus');
const captionStatus = $('#captionStatus');
const scriptGuideStatus = $('#scriptGuideStatus');
const scriptGuideDetails = $('#scriptGuideDetails');
const clearScriptGuideBtn = $('#clearScriptGuideBtn');
const viewScriptGuideBtn = $('#viewScriptGuideBtn');
const scriptGuideModal = $('#scriptGuideModal');
const scriptGuideModalBody = $('#scriptGuideModalBody');
const closeScriptGuideModal = $('#closeScriptGuideModal');
const captionPreset = $('#captionPreset');
const captionFont = $('#captionFont');
const captionAlignment = $('#captionAlignment');
const captionSize = $('#captionSize');
const captionPosition = $('#captionPosition');
const captionOutline = $('#captionOutline');
const captionColor = $('#captionColor');
const captionOutlineColor = $('#captionOutlineColor');
const captionSizeValue = $('#captionSizeValue');
const captionPositionValue = $('#captionPositionValue');
const captionOutlineValue = $('#captionOutlineValue');
const layerPreviewText = $('#layerPreviewText');
const layerPreviewCaption = $('#layerPreviewCaption');
const layerPreviewMedia = document.querySelector('#layerPreview .layer-preview-media');
const clearCaptionBtn = $('#clearCaptionBtn');
const subtitlePreset = $('#subtitlePreset');
const subtitleFontPreset = $('#subtitleFontPreset');
const subtitleAnimation = $('#subtitleAnimation');
const subtitleSize = $('#subtitleSize');
const subtitlePosition = $('#subtitlePosition');
const subtitleOutlineSize = $('#subtitleOutlineSize');
const subtitleColor = $('#subtitleColor');
const subtitleOutline = $('#subtitleOutline');
const subtitleSizeValue = $('#subtitleSizeValue');
const subtitlePositionValue = $('#subtitlePositionValue');
const subtitleOutlineSizeValue = $('#subtitleOutlineSizeValue');
const subtitleColorHex = $('#subtitleColorHex');
const subtitleOutlineHex = $('#subtitleOutlineHex');
const subtitleColorPreview = $('#subtitleColorPreview');
const subtitleOutlinePreview = $('#subtitleOutlinePreview');
const previewMedia = $('#previewMedia');
const previewCaption = $('#previewCaption');
const renderSteps = $('#renderSteps');
const toggleLogBtn = $('#toggleLogBtn');
const renderShowcase = $('#renderShowcase');
const renderShowcaseArt = $('#renderShowcaseArt');
const renderShowcaseTitle = $('#renderShowcaseTitle');
const renderShowcaseText = $('#renderShowcaseText');
const outputNameInput = $('#outputNameInput');
const finalOutputMode = $('#finalOutputMode');
const finalOutputFolder = $('#finalOutputFolder');
const finalOutputHint = $('#finalOutputHint');
const workflowPresetSelect = $('#workflowPresetSelect');
const exportProfileSelect = $('#exportProfileSelect');
const videoBitrateInput = $('#videoBitrateInput');
const bitrateField = $('#bitrateField');
const bitrateHint = $('#bitrateHint');
const backgroundSummary = $('#backgroundSummary');
const backgroundVolumePreset = $('#backgroundVolumePreset');
const backgroundVolumeDb = $('#backgroundVolumeDb');
const backgroundVolumeField = $('#backgroundVolumeField');
const backgroundDuckingToggle = $('#backgroundDuckingToggle');
const musicGenreSwitch = $('#musicGenreSwitch');
const presetMusicStatus = $('#presetMusicStatus');
const musicLibraryShelf = $('#musicLibraryShelf');
const ctaGrid = $('#ctaGrid');
const ctaStatus = $('#ctaStatus');
const ctaPreviewStage = $('#ctaPreviewStage');
const ctaPreviewMedia = $('#ctaPreviewMedia');
const ctaPreviewVideo = $('#ctaPreviewVideo');
const ctaPreviewCaption = $('#ctaPreviewCaption');
const ctaPreviewSoundBtn = $('#ctaPreviewSoundBtn');
const ctaPositionPreset = $('#ctaPositionPreset');
const ctaOffsetX = $('#ctaOffsetX');
const ctaOffsetY = $('#ctaOffsetY');
const ctaOffsetXValue = $('#ctaOffsetXValue');
const ctaOffsetYValue = $('#ctaOffsetYValue');
const qualityBoostToggle = $('#qualityBoostToggle');
const smartVisualDirectorToggle = $('#smartVisualDirectorToggle');
const referenceStyleEnabledToggle = $('#referenceStyleEnabledToggle');
const referenceStyleStatus = $('#referenceStyleStatus');
const referenceStylePickBtn = $('#referenceStylePickBtn');
const referenceStyleAnalyzeBtn = $('#referenceStyleAnalyzeBtn');
const referenceStyleRemoveBtn = $('#referenceStyleRemoveBtn');
const referenceStyleInput = $('#referenceStyleInput');
const referenceStyleModeSelect = $('#referenceStyleModeSelect');
const visualLanguagePackageSelect = $('#visualLanguagePackageSelect');
const styleIntensitySelect = $('#styleIntensitySelect');
const visualFilterLevelSelect = $('#visualFilterLevelSelect');
const adaptiveVisualFilterToggle = $('#adaptiveVisualFilterToggle');
const visualFilterHint = $('#visualFilterHint');
const voiceNormalizeToggle = $('#voiceNormalizeToggle');
const autoSoundFxToggle = $('#autoSoundFxToggle');
const allowAudioTrimToggle = $('#allowAudioTrimToggle');
const trimSilenceToggle = $('#trimSilenceToggle');
const dualExportShortsToggle = $('#dualExportShortsToggle');
const autoThumbnailsToggle = $('#autoThumbnailsToggle');
const preflightGrid = $('#preflightGrid');
const autoFixBtn = $('#autoFixBtn');
const projectToneSelect = $('#projectToneSelect');
const adaptiveDuckingToggle = $('#adaptiveDuckingToggle');
const dynamicPausesToggle = $('#dynamicPausesToggle');
const dynamicPauseIntensity = $('#dynamicPauseIntensity');
const strongMomentToggle = $('#strongMomentToggle');
const renderRecoveryToggle = $('#renderRecoveryToggle');
const autoFixPlanBox = $('#autoFixPlanBox');
const autoDirectorToggle = $('#autoDirectorToggle');
const semanticVisualIndexToggle = $('#semanticVisualIndexToggle');
const channelLearningToggle = $('#channelLearningToggle');
const energyEditingToggle = $('#energyEditingToggle');
const antiRepeatToggle = $('#antiRepeatToggle');
const continuityMatchToggle = $('#continuityMatchToggle');
const audioMasteringToggle = $('#audioMasteringToggle');
const confidenceSummaryBox = $('#confidenceSummaryBox');
const semanticModelBox = $('#semanticModelBox');
const renderGraphBox = $('#renderGraphBox');
const renderGraphNodes = $('#renderGraphNodes');
const rerunDirectorBtn = $('#rerunDirectorBtn');
const undoDirectorBtn = $('#undoDirectorBtn');
const exportLearningBtn = $('#exportLearningBtn');
const resetLearningBtn = $('#resetLearningBtn');
const learningSummaryBox = $('#learningSummaryBox');
const installVisualModelBtn = $('#installVisualModelBtn');
const visualModelInput = $('#visualModelInput');
const introPanel = $('#introPanel');
const introModeSelect = $('#introModeSelect');
const introStatus = $('#introStatus');
const introPreviewStage = $('#introPreviewStage');
const introPreviewMedia = $('#introPreviewMedia');
const introPreviewText = $('#introPreviewText');
const introVoiceBadge = $('#introVoiceBadge');
const introPreset = $('#introPreset');
const introFontPreset = $('#introFontPreset');
const introSize = $('#introSize');
const introPosition = $('#introPosition');
const introColor = $('#introColor');
const introOutline = $('#introOutline');
const introSizeValue = $('#introSizeValue');
const introPositionValue = $('#introPositionValue');
const introColorHex = $('#introColorHex');
const introOutlineHex = $('#introOutlineHex');
const introColorPreview = $('#introColorPreview');
const introOutlinePreview = $('#introOutlinePreview');
const transitionFxPreviewBtn = $('#transitionFxPreviewBtn');
const subtitleFxPreviewBtn = $('#subtitleFxPreviewBtn');
const projectQueue = $('#projectQueue');
const queueSummary = $('#queueSummary');
const queueReportsBtn = $('#queueReportsBtn');
const reportModal = $('#reportModal');
const reportModalTitle = $('#reportModalTitle');
const reportModalSubtitle = $('#reportModalSubtitle');
const reportModalBody = $('#reportModalBody');
const reportProjectViewBtn = $('#reportProjectViewBtn');
const reportQueueViewBtn = $('#reportQueueViewBtn');
const closeReportModal = $('#closeReportModal');
const newProjectBtn = $('#newProjectBtn');
const duplicateProjectBtn = $('#duplicateProjectBtn');
const removeProjectBtn = $('#removeProjectBtn');
const clearAllProjectsBtn = $('#clearAllProjectsBtn');
const saveProjectsBackupBtn = $('#saveProjectsBackupBtn');
const importProjectsBackupBtn = $('#importProjectsBackupBtn');
const projectsBackupInput = $('#projectsBackupInput');
const renderQueueBtn = $('#renderQueueBtn');
const renderHealthyBtn = $('#renderHealthyBtn');
const automatorBtn = $('#automatorBtn');
const automatorModal = $('#automatorModal');
const automatorCloseBtn = $('#automatorCloseBtn');
const automatorCancelBtn = $('#automatorCancelBtn');
const automatorAutoHealBtn = $('#automatorAutoHealBtn');
const automatorConfirmBtn = $('#automatorConfirmBtn');
const automatorConfirmHealthyBtn = $('#automatorConfirmHealthyBtn');
const automatorConfirmAndRenderBtn = $('#automatorConfirmAndRenderBtn');
const automatorPickSrt = $('#automatorPickSrt');
const automatorPickAudio = $('#automatorPickAudio');
const automatorPickScript = $('#automatorPickScript');
const automatorPickFolders = $('#automatorPickFolders');
const automatorSrtInput = $('#automatorSrtInput');
const automatorAudioInput = $('#automatorAudioInput');
const automatorScriptInput = $('#automatorScriptInput');
const automatorVideoFolderInput = $('#automatorVideoFolderInput');
const automatorSrtCount = $('#automatorSrtCount');
const automatorAudioCount = $('#automatorAudioCount');
const automatorScriptCount = $('#automatorScriptCount');
const automatorFolderCount = $('#automatorFolderCount');
const automatorWarning = $('#automatorWarning');
const automatorPreview = $('#automatorPreview');
const automatorProgress = $('#automatorProgress');
const automatorProgressText = $('#automatorProgressText');
const automatorProgressValue = $('#automatorProgressValue');
const automatorProgressBar = $('#automatorProgressBar');
const retryFailedBtn = $('#retryFailedBtn');
const pauseQueueBtn = $('#pauseQueueBtn');
const stopQueueBtn = $('#stopQueueBtn');
const retryModal = $('#retryModal');
const closeRetryModal = $('#closeRetryModal');
const retryModeAll = $('#retryModeAll');
const retryModeSelected = $('#retryModeSelected');
const retryProjectList = $('#retryProjectList');
const confirmRetryBtn = $('#confirmRetryBtn');
const sampleRenderBtn = $('#sampleRenderBtn');
const batchFolderInput = $('#batchFolderInput');
const pickBatchFolderBtn = $('#pickBatchFolderBtn');
const projectTemplateSelect = $('#projectTemplateSelect');
const identityPresetSelect = $('#identityPresetSelect');
const projectNameInput = $('#projectNameInput');
const renderGallery = $('#renderGallery');
const refreshGalleryBtn = $('#refreshGalleryBtn');
const introFxPreviewBtn = $('#introFxPreviewBtn');
const stopRenderBtn = $('#stopRenderBtn');
const healthyThresholdInput = $('#healthyThresholdInput');
const platformMasterProfileSelect = $('#platformMasterProfileSelect');
const scoreVisualWindowsToggle = $('#scoreVisualWindowsToggle');
const adaptiveQualityBoostToggle = $('#adaptiveQualityBoostToggle');
const queueAutoTestToggle = $('#queueAutoTestToggle');
const saveSettingsBtn = $('#saveSettingsBtn');
const safeRenderBtn = $('#safeRenderBtn');
const spaceManagerBtn = $('#spaceManagerBtn');
const spaceManagerBox = $('#spaceManagerBox');
const spaceSummary = $('#spaceSummary');

const videoExt = ['mp4', 'mov', 'mkv', 'webm', 'avi', 'm4v', 'mts', 'm2ts'];
const imageExt = ['jpg', 'jpeg', 'png', 'webp', 'bmp', 'tif', 'tiff'];
const audioExt = ['mp3', 'wav', 'm4a', 'aac', 'flac', 'ogg', 'webm', 'mp4', 'm4v', 'mov'];
const audioOnlyExt = ['mp3', 'wav', 'm4a', 'aac', 'flac', 'ogg'];
const audioContainerExt = ['mp3', 'wav', 'm4a', 'aac', 'flac', 'ogg', 'webm', 'mp4', 'm4v', 'mov'];
const videoOnlyExt = ['mp4', 'mov', 'mkv', 'avi', 'm4v', 'mts', 'm2ts'];
const subtitleExt = ['srt'];
const scriptGuideExt = ['txt', 'docx', 'pdf', 'html', 'htm'];
const THUMB_LIMIT = 18;
const THUMB_POOL = 1;
const DURATION_POOL = 2;
const IMPORT_DURATION_SCAN_LIMIT = 80;
const IMPORT_AUDIO_HEALTH_LIMIT = 1;
const DESKTOP_MODE = new URLSearchParams(window.location.search).get('desktop') === '1';
const subtitlePresets = {
  bold_white: {label: 'Branco bold', color: '#ffffff', outline: '#111111', box: false, weight: 900, fontPreset: 'arial_black', animation: 'mixed', outlineSize: 2.2},
  bold_yellow: {label: 'Amarelo bold', color: '#ffd83d', outline: '#121212', box: false, weight: 900, fontPreset: 'arial_black', animation: 'mixed', outlineSize: 2.4},
  dark_box: {label: 'Caixa escura', color: '#ffffff', outline: '#000000', box: true, weight: 900, fontPreset: 'segoe', animation: 'mixed', outlineSize: 1},
  cinema_white: {label: 'Cinema branco', color: '#f7f1e8', outline: '#0b0b0b', box: false, weight: 700, fontPreset: 'georgia', animation: 'mixed', outlineSize: 1.8},
  green_neon: {label: 'Verde neon', color: '#74ff8f', outline: '#052b15', box: false, weight: 900, fontPreset: 'arial_black', animation: 'mixed', outlineSize: 2.2},
  minimal: {label: 'Minimal', color: '#f4f4f4', outline: '#202020', box: false, weight: 650, fontPreset: 'segoe', animation: 'mixed', outlineSize: 1.2},
  impact_gold: {label: 'Impacto dourado', color: '#ffd36a', outline: '#1d1404', box: false, weight: 900, fontPreset: 'impact', animation: 'mixed', outlineSize: 2.8},
  documentary: {label: 'Documentario', color: '#f0f4f2', outline: '#0d1813', box: false, weight: 850, fontPreset: 'bahnschrift', animation: 'mixed', outlineSize: 1.8},
  blue_glow: {label: 'Azul glow', color: '#8edbff', outline: '#062033', box: false, weight: 900, fontPreset: 'arial_black', animation: 'mixed', outlineSize: 2.4},
  red_punch: {label: 'Vermelho punch', color: '#ff6b5f', outline: '#1b0504', box: false, weight: 900, fontPreset: 'arial_black', animation: 'mixed', outlineSize: 2.7},
  soft_pink: {label: 'Rosa suave', color: '#ffd1e8', outline: '#2d1324', box: false, weight: 800, fontPreset: 'trebuchet', animation: 'mixed', outlineSize: 1.8},
  clean_box: {label: 'Caixa clean', color: '#ffffff', outline: '#000000', box: true, weight: 850, fontPreset: 'verdana', animation: 'mixed', outlineSize: 0.8},
};
const subtitleFontPresets = {
  arial: 'Arial',
  arial_black: 'Arial Black',
  bahnschrift: 'Bahnschrift',
  segoe: 'Segoe UI Semibold',
  impact: 'Impact',
  georgia: 'Georgia',
  trebuchet: 'Trebuchet MS',
  verdana: 'Verdana',
};

const exportBitratePresets = {
  small_file: {label: 'Arquivo pequeno', hevc: {fast: 1100, standard: 1900}, h264: {fast: 1700, standard: 2800}},
  capcut_compact: {label: 'Compacto CapCut', hevc: {fast: 1500, standard: 2500}, h264: {fast: 2200, standard: 3600}},
  youtube_compact: {label: 'YouTube compacto', hevc: {fast: 1800, standard: 2800}, h264: {fast: 2500, standard: 4000}},
  balanced: {label: 'Equilibrado', hevc: {fast: 2200, standard: 3500}, h264: {fast: 3000, standard: 4800}},
  high_quality: {label: 'Qualidade alta', hevc: {fast: 3000, standard: 5200}, h264: {fast: 4200, standard: 6800}},
  compatibility: {label: 'Compatibilidade', hevc: {fast: 2200, standard: 3600}, h264: {fast: 3200, standard: 5200}},
};
const backgroundVolumePresets = {
  immersive: -22,
  silent: -28,
};
const introPresets = {
  cinema_gold: {label: 'Cinema dourado', color: '#ffd36a', outline: '#090909', box: false, weight: 900, fontPreset: 'georgia', size: 76, position: 44, outlineSize: 2.2},
  white_title: {label: 'Titulo branco', color: '#ffffff', outline: '#101010', box: false, weight: 900, fontPreset: 'arial_black', size: 72, position: 44, outlineSize: 2.4},
  dark_card: {label: 'Card escuro', color: '#ffffff', outline: '#000000', box: true, weight: 850, fontPreset: 'segoe', size: 62, position: 46, outlineSize: 0.8},
  green_premiere: {label: 'Verde premiere', color: '#98ffb0', outline: '#062412', box: false, weight: 900, fontPreset: 'bahnschrift', size: 68, position: 44, outlineSize: 2},
};
const introFontPresets = {
  georgia: 'Georgia',
  arial_black: 'Arial Black',
  bahnschrift: 'Bahnschrift',
  segoe: 'Segoe UI Semibold',
  impact: 'Impact',
};
const subtitleFxByAnimation = {
  mixed: ['subtitle_shimmer'],
  pop: ['subtitle_title_slam'],
  slide: ['subtitle_swipe'],
  zoom: ['subtitle_zoom'],
  fade: ['subtitle_shimmer'],
  cinematic: ['subtitle_luxury_doc'],
  pulse: ['subtitle_pulse'],
  glitch: ['subtitle_glitch_reveal'],
  typewriter: ['subtitle_type_classic'],
  shake: ['subtitle_shake'],
  random_text: ['subtitle_archive_caption'],
  documentary: ['subtitle_luxury_doc'],
  archive: ['subtitle_archive_caption'],
  digital: ['subtitle_digital_typing'],
  stamp: ['subtitle_stamp'],
  money: ['subtitle_money_counter'],
  warning: ['subtitle_warning_alert'],
  industrial: ['subtitle_industrial_metal'],
  luxury: ['subtitle_luxury_doc'],
  none: '',
};
const transitionFxByMode = {
  off: '',
  fade: ['transition_air'],
  random: ['transition_whoosh'],
  random_soft: ['transition_air'],
  random_cinematic: ['transition_whoosh'],
  random_documentary: ['transition_archive'],
  random_glitch: ['transition_digital_glitch'],
  random_industrial: ['transition_industrial'],
  random_fast: ['transition_swipe'],
  whoosh: ['transition_whoosh'],
  swipe: ['transition_swipe'],
  flash: ['transition_flash'],
  archive: ['transition_archive'],
  vhs: ['transition_vhs'],
  digital_glitch: ['transition_digital_glitch'],
  mechanical: ['transition_mechanical'],
  money: ['transition_money'],
  map: ['transition_map'],
  futuristic: ['transition_futuristic'],
  bass_hit: ['transition_bass_hit'],
  glass: ['transition_glass'],
  industrial: ['transition_industrial'],
  smoothleft: ['transition_swipe'],
  wiperight: ['transition_swipe'],
};
const workflowPresets = {
  youtube_doc: {
    ratio: '16:9', mode: 'standard', exportProfile: 'youtube_compact', codec: 'hevc',
    transition: 'random_documentary', zoom: 'light', intro: 'standard', subtitle: 'documentary', cta: 'top_right',
  },
  shorts: {
    ratio: '9:16', mode: 'fast', exportProfile: 'capcut_compact', codec: 'hevc',
    transition: 'random_fast', zoom: 'light', intro: 'standard', subtitle: 'bold_yellow', cta: 'top_center',
  },
  cinematic_story: {
    ratio: '16:9', mode: 'standard', exportProfile: 'balanced', codec: 'hevc',
    transition: 'random_cinematic', zoom: 'light', intro: 'cinematic', subtitle: 'cinema_white', cta: 'top_right',
  },
  light_upload: {
    ratio: '16:9', mode: 'fast', exportProfile: 'small_file', codec: 'hevc',
    transition: 'fade', zoom: 'off', intro: 'standard', subtitle: 'minimal', cta: 'top_right',
  },
  high_quality: {
    ratio: '16:9', mode: 'standard', exportProfile: 'high_quality', codec: 'hevc',
    transition: 'random', zoom: 'light', intro: 'standard', subtitle: 'bold_white', cta: 'top_right',
  },
};
const projectTemplates = {
  documentary: {label: 'Documentário', workflow: 'youtube_doc', cta: 'pt', musicGenre: 'cinematic'},
  recipe: {label: 'Receita', workflow: 'light_upload', cta: 'pt', musicGenre: 'ambient', subtitle: 'bold_yellow'},
  history: {label: 'História', workflow: 'cinematic_story', cta: 'pt', musicGenre: 'cinematic', subtitle: 'documentary'},
  curiosity: {label: 'Curiosidades', workflow: 'youtube_doc', cta: 'pt', musicGenre: 'cinematic', subtitle: 'blue_glow'},
  motivational: {label: 'Motivacional', workflow: 'cinematic_story', cta: 'pt', musicGenre: 'cinematic', subtitle: 'impact_gold'},
  short_cinema: {label: 'Cinema curto', workflow: 'shorts', cta: 'pt', musicGenre: 'cinematic', subtitle: 'cinema_white'},
};
const identityPackages = {
  default: {label: 'Padrão do editor', cta: '', musicGenre: ''},
  pt_doc: {label: 'Canal PT documentário', cta: 'pt', musicGenre: 'cinematic', subtitle: 'documentary'},
  en_doc: {label: 'Canal EN documentário', cta: 'en', musicGenre: 'cinematic', subtitle: 'documentary'},
  ambient_soft: {label: 'Narração calma', cta: 'pt', musicGenre: 'ambient', subtitle: 'minimal'},
};

function optionLabel(value){
  return String(value || '')
    .replace(/[_-]+/g, ' ')
    .replace(/\b\w/g, char => char.toUpperCase());
}

function upsertSelectOption(select, value, label){
  if(!select || !value) return;
  let option = [...select.options].find(item => item.value === value);
  if(!option){
    option = document.createElement('option');
    option.value = value;
    select.appendChild(option);
  }
  option.textContent = label || option.textContent || optionLabel(value);
}

function normalizeWorkflowPreset(key, preset = {}){
  const current = workflowPresets[key] || {};
  return {
    ...current,
    label: preset.label || current.label || optionLabel(key),
    ratio: preset.ratio || current.ratio || '16:9',
    mode: preset.mode || current.mode || 'standard',
    exportProfile: preset.exportProfile || preset.export_profile || current.exportProfile || 'capcut_compact',
    codec: preset.codec || current.codec || 'hevc',
    transition: preset.transition || preset.transitions || current.transition || 'random',
    zoom: preset.zoom || current.zoom || 'light',
    intro: preset.intro || preset.introMode || current.intro || 'standard',
    subtitle: preset.subtitle || current.subtitle || 'bold_white',
    cta: preset.cta || preset.ctaPositionPreset || current.cta || 'top_right',
  };
}

function applyRuntimeConfig(config){
  if(!config || typeof config !== 'object') return;
  if(config.export_presets && typeof config.export_presets === 'object'){
    Object.entries(config.export_presets).forEach(([key, preset]) => {
      if(!exportBitratePresets[key]){
        exportBitratePresets[key] = {label: preset?.label || optionLabel(key), hevc: {fast: 1800, standard: 2800}, h264: {fast: 2500, standard: 4000}};
      }else if(preset?.label){
        exportBitratePresets[key].label = preset.label;
      }
      upsertSelectOption(exportProfileSelect, key, preset?.label || exportBitratePresets[key]?.label);
    });
  }
  if(config.workflow_presets && typeof config.workflow_presets === 'object'){
    Object.entries(config.workflow_presets).forEach(([key, preset]) => {
      workflowPresets[key] = normalizeWorkflowPreset(key, preset);
      upsertSelectOption(workflowPresetSelect, key, workflowPresets[key].label);
    });
  }
  if(config.output?.downloadsFolder && finalOutputHint){
    refreshFinalOutputUi();
  }
  const savedGlobal = config.settings?.global;
  if(savedGlobal && typeof savedGlobal === 'object'){
    if(savedGlobal.theme){
      state.themeMode = savedGlobal.theme;
      localStorage.setItem('glide_theme_mode', state.themeMode);
      if(themeSelect) themeSelect.value = state.themeMode;
      applyThemeMode();
    }
    if(savedGlobal.uiMode){
      state.uiMode = savedGlobal.uiMode;
      localStorage.setItem('glide_ui_mode', state.uiMode);
      if(uiModeSelect) uiModeSelect.value = state.uiMode;
      applyUiMode();
    }
    if(savedGlobal.renderPriority){
      state.renderPriority = normalizedRenderPriority(savedGlobal.renderPriority);
      localStorage.setItem('glide_render_priority', state.renderPriority);
      applyRenderPriorityUi();
    }
    if(Object.prototype.hasOwnProperty.call(savedGlobal, 'renderBudgetEnabled')){
      state.renderBudgetEnabled = Boolean(savedGlobal.renderBudgetEnabled);
      localStorage.setItem('glide_render_budget_enabled', state.renderBudgetEnabled ? '1' : '0');
      if(renderBudgetToggle) renderBudgetToggle.checked = state.renderBudgetEnabled;
    }
    if(Object.prototype.hasOwnProperty.call(savedGlobal, 'uiSoundsEnabled')){
      state.uiSoundsEnabled = Boolean(savedGlobal.uiSoundsEnabled);
      localStorage.setItem('glide_ui_sounds_enabled', state.uiSoundsEnabled ? '1' : '0');
    }
    if(savedGlobal.uiSoundStyle){
      state.uiSoundStyle = savedGlobal.uiSoundStyle;
      localStorage.setItem('glide_ui_sound_style', state.uiSoundStyle);
    }
    if(savedGlobal.uiSoundScope){
      state.uiSoundScope = savedGlobal.uiSoundScope;
      localStorage.setItem('glide_ui_sound_scope', state.uiSoundScope);
    }
    if(Object.prototype.hasOwnProperty.call(savedGlobal, 'projectDoneSound')){
      state.uiProjectDoneSoundEnabled = Boolean(savedGlobal.projectDoneSound);
      localStorage.setItem('glide_ui_project_done_sound_enabled', state.uiProjectDoneSoundEnabled ? '1' : '0');
    }
    if(savedGlobal.automatorSortPreferences && typeof savedGlobal.automatorSortPreferences === 'object'){
      state.automator.sort = {...savedGlobal.automatorSortPreferences};
      saveAutomatorSortPreferences();
    }
    syncUiSoundControls();
  }
}

function cleanDisplayText(value){
  let text = String(value ?? '');
  text = text.replace(/Â·/g, '-').replace(/Â\s/g, ' ');
  if(/[ÃÂ�]/.test(text)){
    try{
      const bytes = Uint8Array.from([...text].map(char => char.charCodeAt(0) & 255));
      const repaired = new TextDecoder('utf-8', {fatal: false}).decode(bytes);
      if(repaired.trim()) text = repaired;
    }catch(_err){}
  }
  return text.replace(/�/g, '').trim();
}

function cleanDisplayData(value){
  if(Array.isArray(value)) return value.map(item => cleanDisplayData(item));
  if(value && typeof value === 'object'){
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, cleanDisplayData(item)]));
  }
  return typeof value === 'string' ? cleanDisplayText(value) : value;
}

function escapeHtml(value){
  return cleanDisplayText(value).replace(/[&<>"']/g, char => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  }[char]));
}

function rel(file){ return file?._serverRel || file?._autoRelativePath || file?.webkitRelativePath || file?.name || ''; }
function ext(file){ return (file.name.split('.').pop() || '').toLowerCase(); }
function fileKey(file, forcedKind = ''){ return `${forcedKind || kindOfFile(file) || 'file'}::${rel(file)}::${file.size}::${file.lastModified || 0}`; }
function naturalCompare(a, b){ return rel(a).localeCompare(rel(b), undefined, {numeric: true, sensitivity: 'base'}); }
function formatSize(bytes){
  const mb = bytes / 1024 / 1024;
  return mb >= 10 ? `${Math.round(mb)} MB` : `${mb.toFixed(1)} MB`;
}
function formatTime(sec){
  if(!isFinite(sec) || sec < 0) sec = 0;
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = Math.floor(sec % 60);
  return h
    ? `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
    : `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}
function timestampId(){
  const d = new Date();
  const pad = n => String(n).padStart(2, '0');
  return `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}_${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`;
}
function projectStatusLabel(status){
  return {
    draft: 'Rascunho',
    ready: 'Pronto',
    queued: 'Aguardando',
    rendering: 'Renderizando',
    paused: 'Pendente',
    cancelled: 'Cancelado',
    done: 'Concluido',
    recovered: 'Concluido com recuperacao',
    error: 'Erro',
  }[status] || 'Rascunho';
}
function projectReadiness(project){
  const files = project?.files || {};
  const options = project?.options || {};
  const activeFallback = project?.id === state.activeProjectId;
  const cta = options.selectedCta || options.ctaLanguage || (activeFallback ? state.selectedCta : '');
  const checks = [
    {key: 'videos', ok: (files.videos || []).length > 0, label: 'mídia visual'},
    {key: 'audios', ok: (files.audios || []).length > 0, label: 'narração'},
    {key: 'subtitles', ok: (files.subtitles || []).length > 0, label: 'Textos'},
    {key: 'cta', ok: Boolean(cta), label: 'CTA'},
  ];
  const missing = checks.filter(item => !item.ok).map(item => item.label);
  return {ok: missing.length === 0, missing, cta};
}
function projectStatusFor(project){
  if(['rendering', 'queued', 'paused', 'cancelled', 'done', 'recovered', 'error'].includes(project?.status)) return project.status;
  return projectReadiness(project).ok ? 'ready' : 'draft';
}
function emptyProjectFiles(){
  return {videos: [], audios: [], backgroundTracks: [], subtitles: [], captions: [], scriptGuides: []};
}
function emptyProjectMaps(){
  return {durations: new Map(), durationSources: new Map(), audioHealth: new Map(), thumbs: new Map(), mediaStatus: new Map()};
}
function createProjectModel(name = ''){
  const id = `p_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 6)}`;
  return {
    id,
    name: name || `Projeto ${state.projects.length + 1}`,
    status: 'draft',
    files: emptyProjectFiles(),
    maps: emptyProjectMaps(),
    options: captureControlSnapshot(false),
    referenceStyleVideo: null,
    subtitleInfo: null,
    captionInfo: null,
    scriptGuideInfo: null,
    scriptGuidePlan: null,
    outputDir: '',
    outputFile: '',
    outputName: '',
    backendJobId: '',
    error: '',
    estimatedSize: 0,
    lastRenderSummary: null,
    visualAnalysisDetails: null,
    directorState: null,
    timelineHistory: [],
    confidenceSummary: null,
    audioMasterSummary: null,
    renderGraphRun: null,
    retryCount: 0,
    retryHistory: [],
    createdAt: Date.now(),
    updatedAt: Date.now(),
  };
}
function storedProjectToModel(raw = {}, index = 0){
  const project = createProjectModel(raw.name || `Projeto ${index + 1}`);
  project.id = raw.id || project.id;
  project.name = raw.name || project.name;
  project.status = ['done', 'recovered', 'error', 'paused', 'cancelled'].includes(raw.status) ? raw.status : 'draft';
  project.files = emptyProjectFiles();
  project.maps = emptyProjectMaps();
  project.options = raw.options && typeof raw.options === 'object' ? raw.options : {};
  if(typeof project.options.trimSilence === 'undefined') project.options.trimSilence = true;
  if(typeof project.options.dualExportShorts === 'undefined') project.options.dualExportShorts = false;
  if(typeof project.options.autoThumbnails === 'undefined') project.options.autoThumbnails = true;
  project.referenceStyleVideo = raw.referenceStyleVideo && typeof raw.referenceStyleVideo === 'object'
    ? raw.referenceStyleVideo
    : (project.options.referenceStyleVideo && typeof project.options.referenceStyleVideo === 'object' ? project.options.referenceStyleVideo : null);
  project.options.referenceStyleVideo = project.referenceStyleVideo;
  project.subtitleInfo = raw.subtitleInfo && typeof raw.subtitleInfo === 'object' ? raw.subtitleInfo : null;
  project.captionInfo = raw.captionInfo && typeof raw.captionInfo === 'object' ? raw.captionInfo : null;
  project.scriptGuideInfo = raw.scriptGuideInfo && typeof raw.scriptGuideInfo === 'object' ? raw.scriptGuideInfo : null;
  project.scriptGuidePlan = raw.scriptGuidePlan && typeof raw.scriptGuidePlan === 'object' ? raw.scriptGuidePlan : null;
  project.outputDir = raw.outputDir || '';
  project.outputFile = raw.outputFile || '';
  project.outputName = raw.outputName || project.options.outputName || '';
  project.backendJobId = raw.jobId || '';
  project.error = raw.error || '';
  project.estimatedSize = Number(raw.estimatedSize || 0);
  project.lastRenderSummary = raw.lastRenderSummary && typeof raw.lastRenderSummary === 'object' ? raw.lastRenderSummary : null;
  project.visualAnalysisDetails = project.lastRenderSummary?.visualCleanDetails || null;
  project.directorState = raw.directorState && typeof raw.directorState === 'object' ? raw.directorState : null;
  project.timelineHistory = Array.isArray(raw.timelineHistory) ? raw.timelineHistory : [];
  project.confidenceSummary = raw.confidenceSummary && typeof raw.confidenceSummary === 'object' ? raw.confidenceSummary : null;
  project.audioMasterSummary = raw.audioMasterSummary && typeof raw.audioMasterSummary === 'object' ? raw.audioMasterSummary : null;
  project.renderGraphRun = raw.renderGraphRun && typeof raw.renderGraphRun === 'object' ? raw.renderGraphRun : null;
  project.retryCount = Number(raw.retryCount || 0);
  project.retryHistory = Array.isArray(raw.retryHistory) ? raw.retryHistory : [];
  project.createdAt = raw.createdAt ? Date.parse(raw.createdAt) || Date.now() : Date.now();
  project.updatedAt = raw.updatedAt ? Date.parse(raw.updatedAt) || Date.now() : Date.now();
  project.rememberedMedia = raw.media || {};
  return project;
}

function persistedMediaObject(projectId, meta = {}){
  const serverRel = String(meta.rel || meta.name || '');
  const contentUrl = `/api/queue/projects/${encodeURIComponent(projectId)}/media-content?rel=${encodeURIComponent(serverRel)}`;
  return {
    name: meta.name || serverRel.split('/').pop() || 'media',
    size: Number(meta.size || 0),
    type: meta.type || 'application/octet-stream',
    lastModified: Number(meta.lastModified || 0),
    webkitRelativePath: serverRel,
    _serverRel: serverRel,
    _contentUrl: contentUrl,
    _forcedKind: meta.kind || '',
    _persisted: true,
    _persistedProjectId: meta.persistedProjectId || '',
    _persistedStoredFile: meta.persistedStoredFile || '',
    _persistedJobId: meta.persistedJobId || '',
    _persistedIndex: Number.isFinite(Number(meta.persistedIndex)) ? Number(meta.persistedIndex) : -1,
    _duration: Number(meta.duration || 0),
    text: async () => {
      const response = await fetch(contentUrl, {cache: 'no-store'});
      if(!response.ok) throw new Error(await response.text());
      return response.text();
    },
    arrayBuffer: async () => {
      const response = await fetch(contentUrl, {cache: 'no-store'});
      if(!response.ok) throw new Error(await response.text());
      return response.arrayBuffer();
    },
  };
}

async function rehydrateProjectMedia(project){
  if(!project?.id) return project;
  try{
    const response = await fetch(`/api/queue/projects/${encodeURIComponent(project.id)}/media`, {cache: 'no-store'});
    if(!response.ok) return project;
    const payload = await response.json();
    const media = payload.media || {};
    const videos = (media.videos || []).map(meta => persistedMediaObject(project.id, meta));
    const audios = (media.audios || []).map(meta => persistedMediaObject(project.id, meta));
    const backgroundTracks = (media.background_music || []).map(meta => persistedMediaObject(project.id, meta));
    const subtitles = (media.texts || media.subtitles || []).map(meta => persistedMediaObject(project.id, meta));
    const captions = (media.captions || []).map(meta => persistedMediaObject(project.id, meta));
    const scriptGuides = (media.script_guides || []).map(meta => persistedMediaObject(project.id, meta));
    project.files = {videos, audios, backgroundTracks, subtitles, captions, scriptGuides};
    project.maps = emptyProjectMaps();
    [...videos, ...audios, ...backgroundTracks].forEach(file => {
      const imageDuration = isImage(file) && file._duration <= 0 ? 4 : 0;
      const duration = file._duration > 0 ? file._duration : imageDuration;
      if(duration > 0){
        project.maps.durations.set(rel(file), duration);
        project.maps.durationSources.set(rel(file), isImage(file) ? 'image_default' : 'persisted');
      }
    });
    scriptGuides.forEach(file => project.maps.mediaStatus.set(rel(file), {
      kind: 'metadata_ok',
      label: 'Roteiro persistido como guia editorial.',
    }));
    videos.forEach(file => {
      const image = isImage(file);
      if(image && file._contentUrl) project.maps.thumbs.set(rel(file), file._contentUrl);
      project.maps.mediaStatus.set(rel(file), {
        kind: image ? 'image' : (file._duration > 0 ? 'metadata_ok' : 'no_preview'),
        label: image
          ? 'Imagem preservada. O render aplica fundo blur e movimento suave.'
          : (file._duration > 0
            ? 'Midia preservada. O FFmpeg confirma no render.'
            : 'Midia preservada sem preview; o FFmpeg confirma no render.'),
      });
    });
    project.rememberedMediaMissing = Array.isArray(payload.missing) ? payload.missing : [];
  }catch(_){}
  return project;
}
function captureControlSnapshot(includeSubtitle = true){
  const smartDirectorEnabled = smartVisualDirectorToggle ? smartVisualDirectorToggle.checked : true;
  const activeProject = state.projects.find(item => item.id === state.activeProjectId);
  const referenceStyleVideo = activeProject?.referenceStyleVideo || null;
  const referenceEnabled = referenceStyleEnabledToggle ? referenceStyleEnabledToggle.checked : false;
  return {
    mode: state.mode || 'fast',
    selectedCta: state.selectedCta || '',
    musicGenre: state.musicGenre || 'cinematic',
    outputName: outputNameInput?.value || '',
    finalOutputMode: finalOutputMode?.value || state.finalOutputMode || 'downloads',
    finalOutputFolder: finalOutputFolder?.value || state.finalOutputFolder || '',
    workflowPreset: workflowPresetSelect?.value || 'custom',
    exportProfile: exportProfileSelect?.value || 'capcut_compact',
    videoBitrateKbps: Number(videoBitrateInput?.value || 2500),
    ratio: $('#ratioSelect')?.value || '16:9',
    codec: $('#codecSelect')?.value || 'hevc',
    transitions: $('#transitionSelect')?.value || 'off',
    zoom: $('#zoomSelect')?.value || 'off',
    colorGradePreset: $('#colorGradeSelect')?.value || 'natural_balanced',
    gpu: $('#gpuToggle')?.checked || false,
    qualityBoost: qualityBoostToggle ? qualityBoostToggle.checked : true,
    smartVisualDirector: smartDirectorEnabled,
    styleSource: referenceEnabled && referenceStyleVideo ? 'reference_dna' : 'glide_package',
    referenceStyleEnabled: referenceEnabled && Boolean(referenceStyleVideo),
    referenceStyleVideo,
    referenceStyleMode: referenceStyleModeSelect?.value === 'reference' ? 'reference' : 'inspiration',
    visualLanguagePackage: visualLanguagePackageSelect?.value || 'dark_doc',
    styleIntensity: styleIntensitySelect?.value || 'balanced',
    visualCleanFilter: true,
    visualFilterLevel: normalizedVisualFilterLevel(visualFilterLevelSelect?.value),
    adaptiveVisualFilter: Boolean(adaptiveVisualFilterToggle?.checked),
    voiceNormalize: voiceNormalizeToggle ? voiceNormalizeToggle.checked : true,
    autoSoundFx: autoSoundFxToggle ? autoSoundFxToggle.checked : true,
    allowAudioTrim: allowAudioTrimToggle ? allowAudioTrimToggle.checked : true,
    trimSilence: trimSilenceToggle ? trimSilenceToggle.checked : true,
    dualExportShorts: dualExportShortsToggle ? dualExportShortsToggle.checked : false,
    autoThumbnails: autoThumbnailsToggle ? autoThumbnailsToggle.checked : true,
    backgroundMusicVolumeDb: backgroundVolumeValue(),
    backgroundMusicPreset: backgroundVolumePreset?.value || 'immersive',
    backgroundMusicDucking: true,
    projectTone: projectToneSelect?.value || 'auto',
    adaptiveDucking: true,
    dynamicPauses: false,
    dynamicPauseIntensity: 'disabled',
    strongMomentEnhance: false,
    renderRecovery: renderRecoveryToggle ? renderRecoveryToggle.checked : true,
    directorDecisionMode: 'balanced',
    healthyRenderThreshold: Number(healthyThresholdInput?.value || 70),
    renderBudgetEnabled: Boolean(state.renderBudgetEnabled),
    renderBudgetTurboMultiplier: 1.35,
    renderBudgetEfficientMultiplier: 2.7,
    platformMasterProfile: platformMasterProfileSelect?.value || 'youtube_long',
    scoreVisualWindows: false,
    adaptiveQualityBoost: adaptiveQualityBoostToggle ? adaptiveQualityBoostToggle.checked : true,
    queueAutoTest: queueAutoTestToggle ? queueAutoTestToggle.checked : true,
    autoDirector: smartDirectorEnabled,
    semanticVisualIndex: semanticVisualIndexToggle ? semanticVisualIndexToggle.checked : true,
    channelLearning: channelLearningToggle ? channelLearningToggle.checked : true,
    energyEditing: energyEditingToggle ? energyEditingToggle.checked : true,
    antiRepeat: antiRepeatToggle ? antiRepeatToggle.checked : true,
    continuityMatch: false,
    continuityOutliersOnly: true,
    subtitleEditorialGrammar: true,
    audioMastering: audioMasteringToggle ? audioMasteringToggle.checked : true,
    introMode: introModeSelect?.value || state.introMode || 'standard',
    introSubtitleStyle: includeSubtitle ? currentIntroSubtitleStyle() : null,
    textStyle: includeSubtitle ? currentSubtitleStyle() : null,
    subtitleStyle: includeSubtitle ? currentSubtitleStyle() : null,
    captionStyle: includeSubtitle ? currentCaptionStyle() : null,
    cinematicOpeningPolicy: 'auto_contextual',
    ctaPositionPreset: state.ctaPositionPreset || 'top_right',
    ctaOffsetX: state.ctaOffsetX || 0,
    ctaOffsetY: state.ctaOffsetY || 0,
  };
}
function applyControlSnapshot(options = {}, {deferDecorations = false} = {}){
  state.mode = options.mode || 'fast';
  document.querySelectorAll('.preset').forEach(btn => btn.classList.toggle('active', btn.dataset.mode === state.mode));
  state.selectedCta = Object.prototype.hasOwnProperty.call(options, 'selectedCta') ? (options.selectedCta || '') : (state.selectedCta || '');
  state.musicGenre = Object.prototype.hasOwnProperty.call(options, 'musicGenre') ? (options.musicGenre || 'cinematic') : (state.musicGenre || 'cinematic');
  if(outputNameInput) outputNameInput.value = options.outputName || '';
  state.finalOutputMode = options.finalOutputMode || state.finalOutputMode || 'downloads';
  state.finalOutputFolder = Object.prototype.hasOwnProperty.call(options, 'finalOutputFolder') ? (options.finalOutputFolder || '') : (state.finalOutputFolder || '');
  if(finalOutputMode) finalOutputMode.value = state.finalOutputMode;
  if(finalOutputFolder) finalOutputFolder.value = state.finalOutputFolder;
  if(workflowPresetSelect) workflowPresetSelect.value = options.workflowPreset || 'custom';
  if(exportProfileSelect) exportProfileSelect.value = options.exportProfile || 'capcut_compact';
  if(videoBitrateInput) videoBitrateInput.value = String(options.videoBitrateKbps || 2500);
  if($('#ratioSelect')) $('#ratioSelect').value = options.ratio || '16:9';
  if($('#codecSelect')) $('#codecSelect').value = options.codec || 'hevc';
  if($('#transitionSelect')) $('#transitionSelect').value = options.transitions || 'off';
  if($('#zoomSelect')) $('#zoomSelect').value = options.zoom || 'off';
  if($('#colorGradeSelect')) $('#colorGradeSelect').value = options.colorGradePreset || 'natural_balanced';
  if($('#gpuToggle')) $('#gpuToggle').checked = Boolean(options.gpu);
  if(qualityBoostToggle) qualityBoostToggle.checked = options.qualityBoost !== false;
  if(smartVisualDirectorToggle) smartVisualDirectorToggle.checked = options.smartVisualDirector !== false;
  if(referenceStyleEnabledToggle) referenceStyleEnabledToggle.checked = Boolean(options.referenceStyleEnabled && options.referenceStyleVideo);
  if(referenceStyleModeSelect) referenceStyleModeSelect.value = options.referenceStyleMode === 'reference' ? 'reference' : 'inspiration';
  if(visualLanguagePackageSelect) visualLanguagePackageSelect.value = options.visualLanguagePackage || 'dark_doc';
  if(styleIntensitySelect) styleIntensitySelect.value = ['low', 'balanced', 'high'].includes(options.styleIntensity) ? options.styleIntensity : 'balanced';
  if(visualFilterLevelSelect) visualFilterLevelSelect.value = normalizedVisualFilterLevel(options.visualFilterLevel);
  if(adaptiveVisualFilterToggle) adaptiveVisualFilterToggle.checked = Boolean(options.adaptiveVisualFilter);
  if(voiceNormalizeToggle) voiceNormalizeToggle.checked = options.voiceNormalize !== false;
  if(autoSoundFxToggle) autoSoundFxToggle.checked = options.autoSoundFx !== false;
  if(allowAudioTrimToggle) allowAudioTrimToggle.checked = options.allowAudioTrim !== false;
  if(trimSilenceToggle) trimSilenceToggle.checked = options.trimSilence !== false;
  if(dualExportShortsToggle) dualExportShortsToggle.checked = Boolean(options.dualExportShorts);
  if(autoThumbnailsToggle) autoThumbnailsToggle.checked = options.autoThumbnails !== false;
  if(backgroundVolumePreset) backgroundVolumePreset.value = options.backgroundMusicPreset || 'immersive';
  if(backgroundVolumeDb) backgroundVolumeDb.value = String(options.backgroundMusicVolumeDb ?? -25);
  if(backgroundDuckingToggle) backgroundDuckingToggle.checked = options.backgroundMusicDucking !== false;
  if(projectToneSelect) projectToneSelect.value = options.projectTone || 'auto';
  if(adaptiveDuckingToggle) adaptiveDuckingToggle.checked = options.adaptiveDucking !== false;
  if(dynamicPausesToggle) dynamicPausesToggle.checked = Boolean(options.dynamicPauses);
  if(dynamicPauseIntensity) dynamicPauseIntensity.value = options.dynamicPauseIntensity || 'conservative';
  if(strongMomentToggle) strongMomentToggle.checked = options.strongMomentEnhance !== false;
  if(renderRecoveryToggle) renderRecoveryToggle.checked = options.renderRecovery !== false;
  if(healthyThresholdInput) healthyThresholdInput.value = String(Number(options.healthyRenderThreshold || 70));
  state.renderBudgetEnabled = options.renderBudgetEnabled !== false;
  if(renderBudgetToggle) renderBudgetToggle.checked = state.renderBudgetEnabled;
  if(platformMasterProfileSelect) platformMasterProfileSelect.value = options.platformMasterProfile || 'youtube_long';
  if(scoreVisualWindowsToggle) scoreVisualWindowsToggle.checked = options.scoreVisualWindows !== false;
  if(adaptiveQualityBoostToggle) adaptiveQualityBoostToggle.checked = options.adaptiveQualityBoost !== false;
  if(queueAutoTestToggle) queueAutoTestToggle.checked = options.queueAutoTest !== false;
  if(autoDirectorToggle) autoDirectorToggle.checked = options.autoDirector !== false;
  if(semanticVisualIndexToggle) semanticVisualIndexToggle.checked = options.semanticVisualIndex !== false;
  if(channelLearningToggle) channelLearningToggle.checked = options.channelLearning !== false;
  if(energyEditingToggle) energyEditingToggle.checked = options.energyEditing !== false;
  if(antiRepeatToggle) antiRepeatToggle.checked = options.antiRepeat !== false;
  if(continuityMatchToggle) continuityMatchToggle.checked = options.continuityMatch !== false;
  if(audioMasteringToggle) audioMasteringToggle.checked = options.audioMastering !== false;
  applyRenderPriorityUi();
  if(introModeSelect) introModeSelect.value = options.introMode || 'standard';
  state.introMode = introModeSelect?.value || 'standard';
  applySubtitleStyleSnapshot(options.textStyle || options.subtitleStyle);
  applyCaptionStyleSnapshot(options.captionStyle);
  applyIntroStyleSnapshot(options.introSubtitleStyle);
  state.ctaPositionPreset = options.ctaPositionPreset || 'top_right';
  state.ctaOffsetX = Number(options.ctaOffsetX || 0);
  state.ctaOffsetY = Number(options.ctaOffsetY || 0);
  if(ctaPositionPreset) ctaPositionPreset.value = state.ctaPositionPreset;
  if(ctaOffsetX) ctaOffsetX.value = String(state.ctaOffsetX);
  if(ctaOffsetY) ctaOffsetY.value = String(state.ctaOffsetY);
  if(deferDecorations) return;
  refreshActiveProjectDecorations();
}

function refreshActiveProjectDecorations(){
  renderCtaAssets();
  refreshExportProfileUi();
  refreshFinalOutputUi();
  refreshBackgroundMusicUi();
  updateSubtitlePreview({refreshStats: false});
  refreshCaptionInfo().catch(() => {});
  updateCtaPreview();
  updateReferenceStyleUi();
  const activeProject = state.projects.find(item => item.id === state.activeProjectId);
  updateIntelligenceV15(activeProject?.lastRenderSummary || {
    confidence: activeProject?.confidenceSummary,
    audioMaster: activeProject?.audioMasterSummary,
    renderGraph: activeProject?.renderGraphRun,
    director: activeProject?.directorState,
  });
}

function scheduleActiveProjectDecorations(projectId){
  const token = ++state.projectDecorationToken;
  const run = () => {
    if(token !== state.projectDecorationToken || projectId !== state.activeProjectId) return;
    refreshActiveProjectDecorations();
    refreshSubtitleInfo().catch(() => {});
    refreshCaptionInfo().catch(() => {});
  };
  if('requestIdleCallback' in window) window.requestIdleCallback(run, {timeout: 240});
  else window.setTimeout(run, 32);
}
function captureActiveProject(){
  const project = state.projects.find(item => item.id === state.activeProjectId);
  if(!project) return null;
  project.files = {
    videos: [...state.videos],
    audios: [...state.audios],
    backgroundTracks: [...state.backgroundTracks],
    subtitles: [...state.subtitles],
    captions: [...state.captions],
    scriptGuides: [...state.scriptGuides],
  };
  project.maps = {
    durations: new Map(state.durations),
    durationSources: new Map(state.durationSources),
    audioHealth: new Map(state.audioHealth),
    thumbs: new Map(state.thumbs),
    mediaStatus: new Map(state.mediaStatus),
  };
  project.options = captureControlSnapshot(true);
  if(projectNameInput){
    const nextName = projectNameInput.value.trim();
    if(nextName) project.name = nextName;
  }
  project.subtitleInfo = state.subtitleInfo;
  project.captionInfo = state.captionInfo;
  project.scriptGuideInfo = state.scriptGuideInfo;
  project.scriptGuidePlan = state.scriptGuidePlan;
  project.outputDir = state.outputDir || project.outputDir || '';
  project.backendJobId = state.activeJobId || project.backendJobId || '';
  project.outputName = outputNameInput?.value || project.outputName || '';
  project.estimatedSize = estimateCurrentOutputBytes();
  project.status = projectStatusFor(project);
  project.updatedAt = Date.now();
  syncProjectSnapshot(project);
  return project;
}

function cloneOptions(options = {}){
  try{
    return JSON.parse(JSON.stringify(options || {}));
  }catch(_){
    return {...(options || {})};
  }
}

function snapshotProjectForRender(project){
  const files = project?.files || emptyProjectFiles();
  const options = cloneOptions(project?.options || {});
  options.renderPriority = normalizedRenderPriority(state.renderPriority);
  options.turboPolicy = options.renderPriority === 'max' ? 'production_max' : 'disabled';
  options.selectedCta = options.selectedCta || options.ctaLanguage || state.selectedCta || '';
  options.ctaLanguage = options.ctaLanguage || options.selectedCta || state.selectedCta || '';
  options.musicGenre = options.musicGenre || options.backgroundMusicGenre || state.musicGenre || 'cinematic';
  options.backgroundMusicGenre = options.backgroundMusicGenre || options.musicGenre;
  options.outputName = project?.outputName || options.outputName || '';
  options.referenceStyleVideo = project?.referenceStyleVideo || options.referenceStyleVideo || null;
  options.referenceStyleEnabled = Boolean(options.referenceStyleEnabled && options.referenceStyleVideo);
  options.styleSource = options.referenceStyleEnabled ? 'reference_dna' : 'glide_package';
  options.visualLanguagePackage = options.visualLanguagePackage || visualLanguagePackageSelect?.value || 'dark_doc';
  options.styleIntensity = options.styleIntensity || styleIntensitySelect?.value || 'balanced';
  if(typeof options.gpu !== 'boolean'){
    options.gpu = $('#gpuToggle') ? Boolean($('#gpuToggle').checked) : true;
  }
  if(typeof options.qualityBoost !== 'boolean'){
    options.qualityBoost = qualityBoostToggle ? qualityBoostToggle.checked : true;
  }
  if(!options.codec){
    options.codec = $('#codecSelect')?.value || 'hevc';
  }
  if(!options.exportProfile){
    options.exportProfile = exportProfileSelect?.value || 'capcut_compact';
  }

  const durationMap = new Map(project?.maps?.durations || []);
  const allMedia = [...(files.videos || []), ...(files.audios || []), ...(files.backgroundTracks || [])];
  allMedia.forEach(file => {
    const r = rel(file);
    if(!durationMap.has(r)){
      const dur = (state.activeProjectId === project?.id ? state.durations.get(r) : 0)
        || file._autoDuration
        || (project?.maps?.durations instanceof Map ? project.maps.durations.get(r) : 0)
        || (isImage(file) ? 4 : 0)
        || secondsFromClipStamp(file?.name || '')
        || 0;
      if(dur > 0) durationMap.set(r, dur);
    }
  });

  return {
    id: project?.id || '',
    name: project?.name || options.outputName || 'Projeto',
    durationMap,
    files: {
      videos: [...(files.videos || [])],
      audios: [...(files.audios || [])],
      backgroundTracks: [...(files.backgroundTracks || [])],
      subtitles: [...(files.subtitles || [])],
      captions: [...(files.captions || [])],
      scriptGuides: [...(files.scriptGuides || [])],
    },
    options,
  };
}

function loadProject(projectId, options = {}){
  const capture = options.capture !== false;
  const force = options.force === true;
  if(state.activeProjectId === projectId && !force) return;
  if(capture && state.activeProjectId) captureActiveProject();
  const project = state.projects.find(item => item.id === projectId) || state.projects[0];
  if(!project) return;
  state.mediaAnalysisToken++;
  state.activeProjectId = project.id;
  localStorage.setItem('glide_active_project_id', project.id);
  if(projectNameInput) projectNameInput.value = project.name || '';
  state.videos = [...(project.files?.videos || [])];
  state.audios = [...(project.files?.audios || [])];
  state.backgroundTracks = [...(project.files?.backgroundTracks || [])];
  state.subtitles = [...(project.files?.subtitles || [])];
  state.captions = [...(project.files?.captions || [])];
  state.scriptGuides = [...(project.files?.scriptGuides || [])];
  state.registry = new Map();
  [...state.videos, ...state.audios, ...state.backgroundTracks, ...state.subtitles, ...state.captions, ...state.scriptGuides].forEach(file => state.registry.set(fileKey(file), file));
  state.durations = new Map(project.maps?.durations || []);
  state.durationSources = new Map(project.maps?.durationSources || []);
  state.audioHealth = new Map(project.maps?.audioHealth || []);
  state.thumbs = new Map(project.maps?.thumbs || []);
  state.mediaStatus = new Map(project.maps?.mediaStatus || []);
  state.subtitleInfo = project.subtitleInfo || null;
  state.captionInfo = project.captionInfo || null;
  state.scriptGuideInfo = project.scriptGuideInfo || null;
  state.scriptGuidePlan = project.scriptGuidePlan || null;
  state.outputDir = project.outputDir || '';
  state.activeJobId = project.backendJobId || null;
  state.videoOrderEdited = false;
  state.audioOrderEdited = false;
  state.backgroundOrderEdited = false;
  state.videoListSignature = '';
  state.audioListSignature = '';
  state.backgroundListSignature = '';
  if(videoTimeline) delete videoTimeline.dataset.ready;
  if(audioTimeline) delete audioTimeline.dataset.ready;
  if(backgroundTimeline) delete backgroundTimeline.dataset.ready;
  applyControlSnapshot(project.options || {}, {deferDecorations: true});
  if(state.uiSoundScope === 'identity') applyScopedUiSoundPreference(true);
  renderLists({updatePreview: false});
  updateStats();
  scheduleActiveProjectDecorations(project.id);
  loadChannelLearning().catch(() => {});
}

function activateRenderingProject(projectId){
  if(!projectId) return;
  if(state.activeProjectId === projectId) return;
  const project = state.projects.find(item => item.id === projectId);
  if(!project) return;
  loadProject(project.id, {capture: false});
}

function activeReferenceStyle(){
  const project = state.projects.find(item => item.id === state.activeProjectId);
  return project?.referenceStyleVideo || project?.options?.referenceStyleVideo || null;
}

function updateReferenceStyleUi(){
  const project = state.projects.find(item => item.id === state.activeProjectId);
  const ref = activeReferenceStyle();
  const analyzed = Boolean(ref?.styleDna);
  const enabled = Boolean(project?.options?.referenceStyleEnabled && ref);
  const requestedMode = referenceStyleModeSelect?.value === 'reference' ? 'reference' : 'inspiration';
  const eagleActive = Boolean(smartVisualDirectorToggle?.checked && String(state.renderPriority || '').toLowerCase() !== 'max');
  if(referenceStyleEnabledToggle){
    referenceStyleEnabledToggle.disabled = !ref;
    referenceStyleEnabledToggle.checked = Boolean(project?.options?.referenceStyleEnabled && ref);
  }
  if(referenceStyleModeSelect) referenceStyleModeSelect.disabled = !ref;
  if(referenceStyleAnalyzeBtn) referenceStyleAnalyzeBtn.disabled = !ref;
  if(referenceStyleRemoveBtn) referenceStyleRemoveBtn.disabled = !ref;
  if(referenceStyleStatus){
    if(ref){
      const renderMode = String(state.renderPriority || '').toLowerCase();
      const turbo = renderMode === 'max';
      const modeLabel = requestedMode === 'reference' ? 'Referência' : 'Inspiração';
      const source = enabled && analyzed ? `Estilo ativo: ${modeLabel}` : 'Estilo ativo: Pacote Glide';
      const extra = analyzed
        ? `DNA reutilizado (${Number(ref.styleDna?.scene?.cuts_per_minute || 0).toFixed(1)} cortes/min, ${ref.styleDna?.event_style?.intensity || 'ritmo balanceado'}).`
        : 'Análise pendente; o pacote Glide fica como fallback.';
      const turboNote = turbo && enabled ? ' Suspenso para análise pesada no Turbo; DNA cacheado pode orientar apenas decisões leves.' : '';
      referenceStyleStatus.textContent = `${source}. ${ref.name || 'Vídeo referência'} - ${extra}${turboNote}`;
    }else{
      referenceStyleStatus.textContent = 'Sem vídeo referência. O pacote visual do Glide será usado.';
    }
  }
}

async function uploadReferenceStyle(file){
  const project = state.projects.find(item => item.id === state.activeProjectId);
  if(!project || !file) return;
  if(dockSummary) dockSummary.textContent = 'Anexando vídeo referência ao projeto...';
  const form = new FormData();
  form.append('file', file, file.name);
  const response = await fetch(`/api/queue/projects/${encodeURIComponent(project.id)}/reference-style`, {
    method: 'POST',
    body: form,
    cache: 'no-store',
  });
  if(!response.ok) throw new Error(await response.text());
  const payload = await response.json();
  const stored = storedProjectToModel(payload.project, state.projects.indexOf(project));
  stored.files = project.files;
  stored.maps = project.maps;
  state.projects[state.projects.indexOf(project)] = stored;
  state.activeProjectId = stored.id;
  applyControlSnapshot(stored.options || {});
  updateReferenceStyleUi();
  renderProjectQueue();
  if(dockSummary) dockSummary.textContent = 'Referência anexada. Clique em Analisar referência para criar o DNA de edição, sem copiar frames.';
}

async function analyzeReferenceStyle(){
  const project = state.projects.find(item => item.id === state.activeProjectId);
  if(!project?.referenceStyleVideo) return;
  if(dockSummary) dockSummary.textContent = 'Analisando referência: ritmo, cortes, áudio, pausas, motion e energia visual...';
  const response = await fetch(`/api/queue/projects/${encodeURIComponent(project.id)}/reference-style/analyze`, {
    method: 'POST',
    cache: 'no-store',
  });
  if(!response.ok) throw new Error(await response.text());
  const payload = await response.json();
  const index = state.projects.findIndex(item => item.id === project.id);
  const stored = storedProjectToModel(payload.project, index);
  stored.files = project.files;
  stored.maps = project.maps;
  state.projects[index] = stored;
  state.activeProjectId = stored.id;
  applyControlSnapshot(stored.options || {});
  updateReferenceStyleUi();
  renderProjectQueue();
  const cpm = Number(payload.styleDna?.scene?.cuts_per_minute || 0).toFixed(1);
  if(dockSummary) dockSummary.textContent = `Style DNA pronto: ${cpm} cortes/min. O vídeo será usado apenas como guia editorial original.`;
}

async function removeReferenceStyle(){
  const project = state.projects.find(item => item.id === state.activeProjectId);
  if(!project?.referenceStyleVideo) return;
  if(!confirm('Remover o vídeo referência deste projeto? A timeline e os presets serão preservados.')) return;
  const response = await fetch(`/api/queue/projects/${encodeURIComponent(project.id)}/reference-style`, {
    method: 'DELETE',
    cache: 'no-store',
  });
  if(!response.ok) throw new Error(await response.text());
  const payload = await response.json();
  const index = state.projects.findIndex(item => item.id === project.id);
  const stored = storedProjectToModel(payload.project, index);
  stored.files = project.files;
  stored.maps = project.maps;
  state.projects[index] = stored;
  state.activeProjectId = stored.id;
  applyControlSnapshot(stored.options || {});
  updateReferenceStyleUi();
  renderProjectQueue();
  if(dockSummary) dockSummary.textContent = 'Referência removida. Pacote Glide voltou a ser a fonte ativa.';
}

function ensureProject(){
  if(!state.projects.length){
    const project = createProjectModel('Projeto 1');
    state.projects.push(project);
    state.activeProjectId = project.id;
  }
  if(!state.activeProjectId) state.activeProjectId = state.projects[0].id;
}
function estimateCurrentOutputBytes(){
  const audioTotal = state.audios.reduce((sum, file) => sum + (state.durations.get(rel(file)) || 0), 0);
  const duration = audioTotal || state.videos.reduce((sum, file) => sum + (state.durations.get(rel(file)) || 0), 0);
  const bitrate = Number(videoBitrateInput?.value || 2500);
  return Math.round(((bitrate + 160) * 1000 / 8) * duration * 1.04);
}
function mediaSummary(project){
  const files = project.files || {};
  const duration = [...(files.audios || [])].reduce((sum, file) => sum + ((project.maps?.durations || new Map()).get(rel(file)) || 0), 0);
  const retry = Number(project.retryCount || 0) > 0 ? `, retomada ${Number(project.retryCount)}` : '';
  const readiness = projectReadiness(project);
  const missing = readiness.ok ? 'pronto' : `falta ${readiness.missing.join(', ')}`;
  const vList = files.videos || [];
  const vCount = vList.filter(isVideo).length;
  const iCount = vList.filter(isImage).length;
  const mediaLabel = (vCount && iCount) ? `${vCount} vid + ${iCount} foto` : (iCount ? `${iCount} foto` : `${vCount} vid`);
  return `${mediaLabel} | ${(files.audios || []).length} aud | ${(files.subtitles || []).length} Textos | ${(files.captions || []).length} Legendas | ${formatTime(duration)} | ${missing}${retry}`;
}
function projectVisualReport(project){
  const report = project?.lastRenderSummary || {};
  const visual = report.visualClean || {};
  if(!visual || !Object.keys(visual).length) return null;
  return {
    approved: Number(visual.approved || visual.clean_clips || 0),
    rejected: Number(visual.hard_rejected || 0) + Number(visual.rejected_invalid || 0),
    fallback: Number(visual.used_as_fallback || visual.fallback_used || 0),
    analyzed: Number(visual.analyzed_clips || 0),
    imported: Number(visual.imported_clips || 0),
    planned: Number(visual.planned_clips || 0),
    notNeeded: Number(visual.not_needed || 0),
    text: Number(visual.rejected_text || 0),
    invalid: Number(visual.rejected_invalid || 0),
    black: Number(visual.rejected_black || 0),
    presenters: Number(visual.presenter_suspects || 0) + Number(visual.presenter_rejected || 0),
    presenterRejected: Number(visual.presenter_rejected || 0),
    contextualPeople: Number(visual.contextual_people || 0),
    imagesAnalyzed: Number(visual.images_analyzed || 0),
    imagesRejected: Number(visual.images_rejected || 0),
    contextMismatches: Number(visual.context_mismatches || 0),
    level: visual.requested_level || 'normal',
    adaptive: Boolean(visual.adaptive_effective),
    guardrail: visual.guardrail || {},
    demoted: Number(visual.soft_demoted || 0),
    used: Number(visual.used_in_final || 0),
    performance: report.performance || {},
    timing: report.subtitleTiming || {},
    soundFx: report.soundFx || {},
    backgroundMusic: report.backgroundMusic || {},
    director: report.director || project.directorState || {},
    editorialIntelligence: report.editorialIntelligence || {},
    details: project.visualAnalysisDetails || report.visualCleanDetails || {},
  };
}
function hasProjectReport(project){
  return Boolean(project?.lastRenderSummary && Object.keys(project.lastRenderSummary).length);
}
function rerenderEligibility(project){
  const readiness = projectReadiness(project);
  return {
    ok: readiness.ok,
    missing: readiness.missing || [],
    reason: readiness.ok ? 'Elegível' : `Faltam ${readiness.missing.join(', ')}`,
  };
}
function queueVisualMetricsHtml(project){
  const report = projectVisualReport(project);
  if(!report) return '';
  return `<span class="queue-visual-metrics">Aprovados ${report.approved} <b>|</b> Reprovados ${report.rejected} <b>|</b> Fallback ${report.fallback}</span>`;
}
function reportReasonRows(report){
  const items = Array.isArray(report?.details?.items) ? report.details.items : [];
  const groups = new Map();
  items.forEach(item => {
    const reason = item.reason || item.category || 'outro';
    if(!groups.has(reason)) groups.set(reason, []);
    groups.get(reason).push(item.name || item.file || 'clipe');
  });
  return [...groups.entries()].slice(0, 12).map(([reason, names]) => (
    `<li><strong>${escapeHtml(reason)}</strong><span>${escapeHtml(names.slice(0, 5).join(', '))}${names.length > 5 ? ` +${names.length - 5}` : ''}</span></li>`
  )).join('');
}
function reportPathName(value){
  return String(value || '').split(/[\\/]/).pop() || String(value || '');
}
function directorReportSection(director = {}){
  if(!director || !Object.keys(director).length) return '';
  const assignments = Array.isArray(director.assignment_preview) ? director.assignment_preview : (Array.isArray(director.assignments) ? director.assignments.slice(0, 8) : []);
  const changes = Array.isArray(director.comparison) ? director.comparison.filter(item => item.changed).slice(0, 8) : [];
  const coverage = Array.isArray(director.coverage_by_block) ? director.coverage_by_block : [];
  const state = director.state || (director.enabled ? 'ativo' : 'inativo');
  const changed = Number(director.changed_positions || changes.length || 0);
  return `<section class="report-section">
    <h3>Diretor Visual Inteligente</h3>
    <div class="queue-report-grid">
      <span>Estado <b>${escapeHtml(state)}</b></span>
      <span>Modo <b>${escapeHtml(director.mode || 'smart_fast')}</b></span>
      <span>Blocos <b>${Array.isArray(director.blocks) ? director.blocks.length : 0}</b></span>
      <span>Posições alteradas <b>${changed}</b></span>
      <span>Timeline <b>${director.reordered ? 'reorganizada' : 'mantida'}</b></span>
      <span>Cache <b>${director.reused ? 'reutilizado' : 'novo'}</b></span>
    </div>
    ${assignments.length ? `<ul class="report-reason-list">${assignments.slice(0, 8).map(item => `
      <li><strong>${escapeHtml(reportPathName(item.path))}</strong><span>${escapeHtml(item.reason || 'escolha por pontuação')} (${escapeHtml(item.role || 'bloco')}, confiança ${Math.round(Number(item.confidence || 0) * 100) || '--'}%)</span></li>
    `).join('')}</ul>` : '<p class="queue-report-empty">Sem escolhas detalhadas neste render.</p>'}
    ${changes.length ? `<div class="report-compare-list">${changes.map(item => `
      <span><b>#${Number(item.position || 0)}</b> ${escapeHtml(reportPathName(item.before))} -> ${escapeHtml(reportPathName(item.after))}</span>
    `).join('')}</div>` : ''}
    ${coverage.length ? `<div class="report-block-coverage">${coverage.slice(0, 8).map(item => `
      <span><b>${escapeHtml(item.role || `bloco ${item.block}`)}</b><em>${Number(item.coverage_score || 0)}%</em><small>${Number(item.selected_clips || 0)} clipe(s) - ${escapeHtml((item.matched_keywords || []).slice(0, 4).join(', ') || 'sem palavras fortes')}</small></span>
    `).join('')}</div>` : ''}
  </section>`;
}

function editorialIntelligenceSection(plan = {}){
  if(!plan || !Object.keys(plan).length) return '';
  const features = plan.features || {};
  const director = features.smartVisualDirector || {};
  const visual = features.visualSearch?.summary || {};
  const learning = features.channelLearning || {};
  const ducking = features.ducking || {};
  const continuity = features.continuity || {};
  const visualWindows = features.scoreVisualWindows || {};
  const adaptiveQuality = features.adaptiveQualityBoost || {};
  const blocks = Array.isArray(plan.blocks) ? plan.blocks : [];
  const decisions = Array.isArray(plan.decisions) ? plan.decisions : [];
  const comparison = Array.isArray(plan.timelineComparison) ? plan.timelineComparison.filter(item => item.changed).slice(0, 6) : [];
  const windows = Array.isArray(plan.smartSample?.windows) ? plan.smartSample.windows : [];
  const categories = visual.categories && typeof visual.categories === 'object'
    ? Object.entries(visual.categories).slice(0, 6).map(([key, value]) => `${key}: ${value}`).join(', ')
    : '';
  return `<section class="report-section editorial-report-section">
    <h3>Inteligência editorial</h3>
    <div class="queue-report-grid">
      <span>Fase <b>${escapeHtml(plan.phase || 'final')}</b></span>
      <span>Modo <b>${escapeHtml(renderPriorityLabel(plan.renderPriority || 'balanced'))}</b></span>
      <span>Águia <b>${escapeHtml(director.state || (director.effective ? 'ativo' : 'inativo'))}</b></span>
      <span>Decisão <b>${escapeHtml(director.decisionMode || 'balanced')}</b></span>
      <span>Blocos <b>${blocks.length}</b></span>
      <span>Trocas <b>${Number(director.changedPositions || 0)}</b></span>
      <span>Pesquisa visual <b>${escapeHtml(visual.model || (visual.enabled ? 'heurística' : 'inativa'))}</b></span>
      <span>Ducking <b>${ducking.enabled ? 'vivo' : 'padrão'}</b></span>
      <span>Continuidade <b>${continuity.enabled ? `${Number(continuity.applied || 0)} ajuste(s)` : 'sem ajuste'}</b></span>
      <span>Aprendizado <b>${escapeHtml(learning.status || (learning.enabled ? 'observando' : 'inativo'))}</b></span>
      <span>Janelas visuais <b>${visualWindows.enabled ? `${Number(visualWindows.adjusted || 0)}/${Number(visualWindows.analyzed || 0)}` : 'inativo'}</b></span>
      <span>Boost adaptativo <b>${adaptiveQuality.enabled ? `${Number(adaptiveQuality.minimal_segments || 0)} poupado(s)` : 'inativo'}</b></span>
    </div>
    ${categories ? `<p class="report-inline-note">Categorias visuais: ${escapeHtml(categories)}.</p>` : ''}
    ${(Number(adaptiveQuality.estimated_seconds_saved || 0) || Number(continuity.estimated_seconds_saved || 0)) ? `<p class="report-inline-note">Economia estimada: ~${formatTime(Number(adaptiveQuality.estimated_seconds_saved || 0) + Number(continuity.estimated_seconds_saved || 0))} em filtros visuais evitados.</p>` : ''}
    ${blocks.length ? `<div class="report-block-coverage">${blocks.slice(0, 8).map(block => `
      <span><b>${escapeHtml(block.role || `bloco ${block.block}`)}</b><em>${Number(block.coverage_score || 0)}%</em><small>${Number(block.selected_clips || 0)} clipe(s) - ${escapeHtml((block.matched_keywords || block.keywords || []).slice(0, 4).join(', ') || 'sem palavra forte')}</small></span>
    `).join('')}</div>` : '<p class="queue-report-empty">Nenhum bloco narrativo consolidado neste render.</p>'}
    ${decisions.length ? `<ul class="report-reason-list">${decisions.slice(0, 10).map(item => `
      <li><strong>${escapeHtml(item.target || item.kind || 'decisão')}</strong><span>${escapeHtml(item.reason || item.action || '')} - ${Math.round(Number(item.confidence || 0) * 100)}%</span></li>
    `).join('')}</ul>` : ''}
    ${comparison.length ? `<div class="report-compare-list">${comparison.map(item => `
      <span><b>#${Number(item.position || 0)}</b> ${escapeHtml(reportPathName(item.before))} -> ${escapeHtml(reportPathName(item.after))}</span>
    `).join('')}</div>` : ''}
    ${windows.length ? `<p class="report-inline-note">Amostra por blocos: ${windows.map(item => escapeHtml(item.role || item.label || 'trecho')).join(' + ')}.</p>` : ''}
  </section>`;
}

function performanceLabel(key){
  const labels = {
    total: 'Total',
    visual_analysis: 'Análise',
    analysis: 'Análise',
    segments: 'Segmentos',
    composition: 'Composição',
    concat: 'Composição',
    audio: 'Áudio',
    mastering: 'Master',
    mux: 'Mux',
    delivery: 'Entrega',
    continuity: 'Continuidade',
  };
  return labels[key] || String(key || '').replace(/_/g, ' ');
}

function performanceAuditSection(performance = {}, history = []){
  const ordered = ['visual_analysis', 'analysis', 'segments', 'composition', 'concat', 'audio', 'mastering', 'mux', 'delivery', 'total'];
  const seen = new Set();
  const entries = [];
  ordered.forEach(key => {
    const value = Number(performance?.[key] || 0);
    if(value > 0){
      entries.push([key, value]);
      seen.add(key);
    }
  });
  Object.entries(performance || {}).forEach(([key, value]) => {
    if(!seen.has(key) && Number(value) > 0) entries.push([key, Number(value)]);
  });
  const metricRows = entries.map(([key, value]) => `<span>${escapeHtml(performanceLabel(key))} <b>${formatTime(value)}</b></span>`).join('');
  const historyRows = (Array.isArray(history) ? history.slice(-6).reverse() : []).map(item => {
    const priority = renderPriorityLabel(item.priority || 'balanced');
    const factor = Number(item.realtime_factor || 0);
    return `<tr><td>${escapeHtml(priority)}</td><td>${formatTime(Number(item.duration_seconds || 0))}</td><td>${formatTime(Number(item.elapsed_seconds || 0))}</td><td>${factor ? `${factor.toFixed(2)}x` : '--'}</td></tr>`;
  }).join('');
  return `<section class="report-section">
    <h3>Auditoria de performance</h3>
    ${metricRows ? `<div class="queue-report-grid">${metricRows}</div>` : '<p class="queue-report-empty">Sem divisão de performance para este render.</p>'}
    ${historyRows ? `<div class="report-table-wrap compact"><table class="report-table"><thead><tr><th>Modo</th><th>Vídeo</th><th>Render</th><th>Fator</th></tr></thead><tbody>${historyRows}</tbody></table></div>` : '<p class="queue-report-empty">Histórico comparativo ainda vazio para este projeto.</p>'}
  </section>`;
}

function styleDnaReportSection(stored = {}, projectId = ''){
  const style = stored.styleProfile || {};
  const eventTimeline = stored.eventTimeline || {};
  const rhythm = stored.sceneRhythm || {};
  const dna = style.dna || {};
  const packageLabel = style.package?.label || 'Pacote Glide';
  const modeLabel = style.referenceModeEffective === 'reference' ? 'Referência precisa' : 'Inspiração';
  const source = style.source === 'reference_dna' ? modeLabel : 'Pacote Glide';
  const summary = eventTimeline.summary || {};
  return `<section class="report-section style-dna-report">
    <h3>Direção audiovisual</h3>
    <div class="queue-report-grid">
      <span>Estilo ativo <b>${escapeHtml(source)}</b></span>
      <span>Força do guia <b>${Math.round(Number(style.referenceGuidanceStrength || 0) * 100)}%</b></span>
      <span>Pacote fallback <b>${escapeHtml(packageLabel)}</b></span>
      <span>Cortes/min <b>${Number(dna.cutsPerMinute || 0).toFixed(1)}</b></span>
      <span>Plano médio <b>${Number(dna.averageShotSeconds || 0).toFixed(1)}s</b></span>
      <span>Ritmo de cena <b>${escapeHtml(rhythm.cut_rhythm || 'balanceado')}</b></span>
      <span>Motion imagens <b>${escapeHtml(rhythm.motion_graphics || 'cinemático')}</b></span>
      <span>Eventos sincronizados <b>${Number(eventTimeline.events || 0)}</b></span>
      <span>Conflitos resolvidos <b>${Number(eventTimeline.conflicts || 0)}</b></span>
      <span>Motion gráficos <b>${Number(summary.motion_graphic_events || 0)}</b></span>
      <span>Eventos de imagem <b>${Number(summary.image_events || 0)}</b></span>
    </div>
    <p class="report-inline-note">O vídeo referência é usado apenas como guia de ritmo e linguagem audiovisual; nenhum frame ou cena do original é copiado.</p>
  </section>`;
}

function projectReportHtml(project){
  if(!hasProjectReport(project)) return '<p class="report-empty">Este projeto ainda não possui um render concluído com relatório.</p>';
  const stored = project.lastRenderSummary || {};
  const report = projectVisualReport(project) || {
    approved: 0, rejected: 0, fallback: 0, analyzed: 0, imported: 0, planned: 0,
    notNeeded: 0, text: 0, invalid: 0, black: 0, presenters: 0, presenterRejected: 0,
    contextualPeople: 0, imagesAnalyzed: 0, imagesRejected: 0, contextMismatches: 0,
    level: 'normal', adaptive: false, guardrail: {}, demoted: 0, used: 0,
    performance: stored.performance || {}, timing: stored.subtitleTiming || {},
    soundFx: stored.soundFx || {}, backgroundMusic: stored.backgroundMusic || {},
    director: stored.director || project.directorState || {},
    editorialIntelligence: stored.editorialIntelligence || {},
    details: stored.visualCleanDetails || {},
  };
  const fx = report.soundFx || stored.soundFx || {};
  const music = report.backgroundMusic || stored.backgroundMusic || {};
  const timing = report.timing || {};
  const graph = stored.renderGraph || {};
  const director = stored.director || report.director || project.directorState || {};
  const editorial = stored.editorialIntelligence || report.editorialIntelligence || {};
  const renderDecisions = stored.renderDecisions || {};
  const decisions = Array.isArray(renderDecisions.decisions) ? renderDecisions.decisions : [];
  const errorActions = Array.isArray(stored.errorActions) ? stored.errorActions : [];
  const reasons = reportReasonRows(report);
  const perfHistory = stored.performanceHistory || stored.performance_history || [];
  return `
    <div class="report-summary-grid">
      <div class="report-summary-item"><span>Aprovados</span><strong>${report.approved}</strong></div>
      <div class="report-summary-item"><span>Reprovados</span><strong>${report.rejected}</strong></div>
      <div class="report-summary-item"><span>Fallback</span><strong>${report.fallback}</strong></div>
      <div class="report-summary-item"><span>Usados no MP4</span><strong>${report.used}</strong></div>
      <div class="report-summary-item"><span>FX de texto</span><strong>${Number(fx.subtitle_events || 0)}</strong></div>
      <div class="report-summary-item"><span>FX de transição</span><strong>${Number(fx.transition_events || 0)}</strong></div>
      <div class="report-summary-item"><span>Músicas/trechos</span><strong>${Number(music.used_segments || 0)}</strong></div>
      <div class="report-summary-item"><span>Tempo de render</span><strong>${formatTime(Number(report.performance?.total || 0))}</strong></div>
    </div>
    ${stored.error ? `<section class="report-section"><h3>Erro principal</h3><p class="report-inline-note">${escapeHtml(stored.error)}</p></section>` : ''}
    <section class="report-section">
      <h3>Análise visual</h3>
      <div class="queue-report-grid">
        <span>Importados <b>${report.imported}</b></span><span>Planejados <b>${report.planned}</b></span>
        <span>Analisados <b>${report.analyzed}</b></span><span>Não necessários <b>${report.notNeeded}</b></span>
        <span>Texto rejeitado <b>${report.text}</b></span><span>Inválidos/pretos <b>${report.invalid + report.black}</b></span>
        <span>Nível <b>${escapeHtml(report.adaptive ? 'Adaptativo' : visualFilterLevelLabel(report.level))}</b></span><span>Rebaixados <b>${report.demoted}</b></span>
        <span>Apresentadores rejeitados <b>${report.presenterRejected}</b></span><span>Pessoas contextuais <b>${report.contextualPeople}</b></span>
        <span>Imagens analisadas <b>${report.imagesAnalyzed}</b></span><span>Imagens rejeitadas <b>${report.imagesRejected}</b></span>
        <span>Guardrail recuperou <b>${Number(stored.visualClean?.guardrail_recovered || 0)}</b></span><span>Contexto insuficiente <b>${report.contextMismatches}</b></span>
      </div>
      ${reasons ? `<ul class="report-reason-list">${reasons}</ul>` : '<p class="queue-report-empty">Nenhum clipe problemático detalhado neste render.</p>'}
    </section>
    ${styleDnaReportSection(stored, project?.id || state.reportProjectId || state.activeProjectId)}
    ${editorialIntelligenceSection(editorial)}
    ${directorReportSection(director)}
    <section class="report-section">
      <h3>Som e sincronizacao</h3>
      <div class="queue-report-grid">
        <span>FX aplicados <b>${fx.enabled ? Number(fx.events || 0) : 0}</b></span><span>FX de Textos <b>${Number(fx.subtitle_events || 0)}</b></span>
        <span>FX transições <b>${Number(fx.transition_events || 0)}</b></span><span>FX ignorados <b>${Number(fx.skipped_events || 0)}</b></span>
        <span>FX imagens <b>${Number(fx.image_events || 0)}</b></span><span>FX gráficos <b>${Number(fx.motion_graphic_events || 0)}</b></span>
        <span>Textos verificados <b>${Number(timing.checked_cues || 0)}</b></span><span>Desvio máximo <b>${Number(timing.max_abs_deviation_ms || 0)} ms</b></span>
        <span>Música ativa <b>${music.enabled ? 'Sim' : 'Não'}</b></span><span>Ducking <b>${music.ducking ? 'Sim' : 'Não'}</b></span>
      </div>
      ${!fx.enabled ? `<p class="queue-report-empty">FX: ${escapeHtml(fx.reason || 'dados indisponíveis para este render antigo')}.</p>` : ''}
    </section>
    ${graph.nodes?.length ? `<section class="report-section">
      <h3>Render Graph</h3>
      <div class="queue-report-grid">
        <span>Processadas <b>${Number(graph.counts?.processed || 0)}</b></span>
        <span>Reutilizadas <b>${Number(graph.counts?.reused || 0)}</b></span>
        <span>Retomadas <b>${Number(graph.counts?.resumed || 0)}</b></span>
        <span>Tempo poupado <b>${formatTime(Number(graph.saved_seconds || 0))}</b></span>
      </div>
    </section>` : ''}
    ${decisions.length ? `<section class="report-section"><h3>Decisões automáticas</h3><ul class="report-reason-list">${decisions.slice(0, 12).map(item => `
      <li><strong>${escapeHtml(item.action || item.kind || 'decisão')}</strong><span>${escapeHtml(item.reason || '')} - ${Math.round(Number(item.confidence || 0) * 100)}%</span></li>
    `).join('')}</ul></section>` : ''}
    ${errorActions.length ? `<section class="report-section"><h3>Ações recomendadas</h3><ul class="report-reason-list">${errorActions.slice(0, 5).map(item => `
      <li><strong>${escapeHtml(item.label || item.action || 'Ação')}</strong><span>${escapeHtml(item.detail || '')}</span></li>
    `).join('')}</ul></section>` : ''}
    ${performanceAuditSection(report.performance || {}, perfHistory)}`;
}
function queueReportHtml(){
  const projects = state.projects.filter(hasProjectReport);
  if(!projects.length) return '<p class="report-empty">Nenhum projeto possui relatório de render ainda.</p>';
  const rows = projects.map((project, index) => {
    const report = projectVisualReport(project);
    const fx = project.lastRenderSummary?.soundFx || {};
    const perf = project.lastRenderSummary?.performance || {};
    return `<tr><td>${String(index + 1).padStart(2, '0')}</td><td><strong>${escapeHtml(project.name || `Projeto ${index + 1}`)}</strong></td>
      <td>${escapeHtml(projectStatusLabel(project.status))}</td><td>${report?.approved || 0}</td><td>${report?.rejected || 0}</td>
      <td>${report?.fallback || 0}</td><td>${Number(fx.subtitle_events || 0)}</td><td>${Number(fx.transition_events || 0)}</td>
      <td>${formatTime(Number(perf.total || 0))}</td><td><button type="button" class="queue-report-toggle" data-modal-report-project="${escapeHtml(project.id)}">Abrir</button></td></tr>`;
  }).join('');
  return `<div class="report-table-wrap"><table class="report-table"><thead><tr><th>#</th><th>Projeto</th><th>Status</th><th>Aprov.</th><th>Reprov.</th><th>Fallback</th><th>FX Textos</th><th>FX trans.</th><th>Render</th><th></th></tr></thead><tbody>${rows}</tbody></table></div>`;
}
function renderReportModal(){
  if(!reportModalBody) return;
  const project = state.projects.find(item => item.id === state.reportProjectId) || state.projects.find(hasProjectReport) || null;
  const queueView = state.reportView === 'queue';
  reportProjectViewBtn?.classList.toggle('active', !queueView);
  reportQueueViewBtn?.classList.toggle('active', queueView);
  if(queueView){
    reportModalTitle.textContent = 'Relatório da fila';
    reportModalSubtitle.textContent = `${state.projects.filter(hasProjectReport).length} projeto(s) com dados de render.`;
    reportModalBody.innerHTML = queueReportHtml();
  }else{
    reportModalTitle.textContent = project?.name || 'Resumo do projeto';
    reportModalSubtitle.textContent = project?.lastRenderSummary?.finishedAt
      ? `Ultimo render: ${new Date(project.lastRenderSummary.finishedAt).toLocaleString()}`
      : 'Dados do último render concluído.';
    reportModalBody.innerHTML = projectReportHtml(project);
  }
}
function openReportModal(projectId = '', view = 'project'){
  state.reportProjectId = projectId || state.reportProjectId || state.activeProjectId;
  state.reportView = view;
  renderReportModal();
  reportModal?.classList.add('show');
  reportModal?.setAttribute('aria-hidden', 'false');
}
function hideReportModal(){
  reportModal?.classList.remove('show');
  reportModal?.setAttribute('aria-hidden', 'true');
}
function renderProjectQueue(){
  if(!projectQueue) return;
  ensureProject();
  const active = state.projects.find(item => item.id === state.activeProjectId);
  const rows = state.projects.map((project, index) => {
    project.status = projectStatusFor(project);
    const readiness = projectReadiness(project);
    const summary = mediaSummary(project);
    return {project, index, readiness, summary};
  });
  const ready = rows.filter(row => row.readiness.ok && !['done', 'recovered', 'rendering', 'queued', 'cancelled'].includes(row.project.status)).length;
  const done = rows.filter(row => row.project.status === 'done' || row.project.status === 'recovered').length;
  const errors = rows.filter(row => row.project.status === 'error').length;
  const cancelled = rows.filter(row => row.project.status === 'cancelled').length;
  const paused = rows.filter(row => row.project.status === 'paused').length;
  const rendering = rows.filter(row => ['rendering', 'queued'].includes(row.project.status)).length;
  const skipped = state.projects.length - ready - done - rendering - errors - cancelled;
  const rerenderable = rows.filter(row => rerenderEligibility(row.project).ok).length;
  if(queueSummary){
    queueSummary.textContent = `${state.projects.length} projeto(s) na fila. ${ready} renderizável(is), ${done} concluído(s), ${errors} com erro, ${cancelled} cancelado(s), ${Math.max(0, skipped)} ignorado(s) sem requisitos.${paused ? ` ${paused} pendente(s).` : ''}${active ? ` Ativo: ${active.name}.` : ''}`;
  }
  if(renderQueueBtn){
    renderQueueBtn.disabled = state.queueRendering || ready === 0;
    renderQueueBtn.textContent = state.queuePaused ? 'Retomar fila' : 'Renderizar fila';
  }
  if(retryFailedBtn){
    retryFailedBtn.disabled = state.queueRendering || state.renderActive || rerenderable === 0;
    retryFailedBtn.textContent = rerenderable ? `Repetir fila (${rerenderable})` : 'Repetir fila';
  }
  if(renderHealthyBtn){
    const healthyReady = rows.filter(row => row.readiness.ok && !['done', 'recovered', 'rendering', 'queued', 'cancelled'].includes(row.project.status)).length;
    renderHealthyBtn.disabled = state.queueRendering || state.renderActive || healthyReady === 0;
  }
  if(safeRenderBtn) safeRenderBtn.disabled = state.queueRendering || state.renderActive || !active || !projectReadiness(active).ok;
  if(saveSettingsBtn) saveSettingsBtn.disabled = state.queueRendering || state.renderActive;
  if(spaceManagerBtn) spaceManagerBtn.disabled = state.queueRendering || state.renderActive;
  if(pauseQueueBtn){
    pauseQueueBtn.classList.toggle('hidden', !state.queueRendering);
    pauseQueueBtn.disabled = state.queuePauseRequested;
    pauseQueueBtn.textContent = state.queuePauseRequested ? 'Pausa solicitada' : 'Pausar fila';
  }
  if(stopQueueBtn){
    stopQueueBtn.classList.toggle('hidden', !(state.queueRendering || state.renderActive));
    stopQueueBtn.disabled = !state.activeJobId;
  }
  if(sampleRenderBtn) sampleRenderBtn.disabled = state.renderActive || state.queueRendering || !active || !projectReadiness(active).ok;
  if(clearAllProjectsBtn) clearAllProjectsBtn.disabled = state.renderActive || state.queueRendering || !state.projects.length;
  if(saveProjectsBackupBtn) saveProjectsBackupBtn.disabled = state.renderActive || state.queueRendering || !state.projects.length;
  if(importProjectsBackupBtn) importProjectsBackupBtn.disabled = state.renderActive || state.queueRendering;
  if(queueReportsBtn) queueReportsBtn.disabled = !state.projects.some(hasProjectReport);
  if(projectNameInput && active && document.activeElement !== projectNameInput && projectNameInput.value !== (active.name || '')) projectNameInput.value = active.name || '';
  const queueStructureSignature = rows.map(row => {
    const project = row.project;
    const visual = projectVisualReport(project);
    const visualSignature = visual ? `${visual.approved}:${visual.rejected}:${visual.fallback}:${visual.analyzed}` : '';
    return `${project.id}:${project.name}:${project.status}:${project.error || ''}:${row.summary}:${visualSignature}`;
  }).join('|') + `|rendering=${state.queueRendering ? 1 : 0}|paused=${state.queuePaused ? 1 : 0}|pauseReq=${state.queuePauseRequested ? 1 : 0}`;
  const queueSignature = `${queueStructureSignature}|active=${state.activeProjectId || ''}`;
  if(projectQueue.dataset.ready === '1' && queueSignature === state.projectQueueSignature){
    return;
  }
  if(projectQueue.dataset.ready === '1' && queueStructureSignature === state.projectQueueStructureSignature){
    state.projectQueueSignature = queueSignature;
    updateProjectQueueActiveState(state.activeProjectId);
    return;
  }
  state.projectQueueSignature = queueSignature;
  state.projectQueueStructureSignature = queueStructureSignature;
  projectQueue.dataset.ready = '1';
  projectQueue.innerHTML = '';
  const frag = document.createDocumentFragment();
  rows.forEach(({project, index, summary}) => {
    const card = document.createElement('article');
    card.className = `queue-card ${project.id === state.activeProjectId ? 'active' : ''} ${project.status}`;
    card.dataset.projectId = project.id;
    card.draggable = !state.queueRendering;
    card.tabIndex = 0;
    card.setAttribute('role', 'button');
    card.title = project.status === 'error' && project.error
      ? `Erro: ${project.error}`
      : (state.queueRendering ? 'A ordem fica bloqueada durante o render da fila.' : 'Arraste para mudar a ordem deste projeto na fila.');
    card.setAttribute('aria-label', `${project.name || `Projeto ${index + 1}`}. Arraste para reordenar.`);
    card.innerHTML = `
      <span class="queue-number">${String(index + 1).padStart(2, '0')}</span>
      <span class="queue-main">
        <strong>${escapeHtml(project.name || `Projeto ${index + 1}`)}</strong>
        <small>${escapeHtml(summary)}</small>
        ${queueVisualMetricsHtml(project)}
      </span>
      <span class="queue-status">${projectStatusLabel(project.status)}</span>
      <span class="queue-grip" aria-hidden="true">::</span>
      ${projectVisualReport(project) ? `<button type="button" class="queue-report-toggle" data-report-project="${escapeHtml(project.id)}">Ver relatório</button>` : ''}
      `;
    frag.appendChild(card);
  });
  projectQueue.appendChild(frag);
}

function updateProjectQueueActiveState(projectId){
  if(!projectQueue) return;
  projectQueue.querySelectorAll('.queue-card').forEach(card => {
    const active = card.dataset.projectId === projectId;
    card.classList.toggle('active', active);
    if(active) card.setAttribute('aria-current', 'true');
    else card.removeAttribute('aria-current');
  });
}

function selectProjectFromQueue(projectId){
  if(!projectId || projectId === state.activeProjectId) return;
  updateProjectQueueActiveState(projectId);
  if(state.pendingProjectLoadFrame) cancelAnimationFrame(state.pendingProjectLoadFrame);
  state.pendingProjectLoadFrame = requestAnimationFrame(() => {
    state.pendingProjectLoadFrame = 0;
    loadProject(projectId);
  });
}
function clearQueueDragMarkers(){
  if(!projectQueue) return;
  projectQueue.querySelectorAll('.queue-card.dragging,.queue-card.drag-over-before,.queue-card.drag-over-after').forEach(card => {
    card.classList.remove('dragging', 'drag-over-before', 'drag-over-after');
  });
  state.projectDragTarget = null;
  state.projectDragTargetRect = null;
  state.projectDragPlaceAfter = false;
}
function reorderProjectsLocal(sourceId, targetId, placeAfter = false){
  if(!sourceId || !targetId || sourceId === targetId || state.queueRendering) return false;
  const sourceIndex = state.projects.findIndex(project => project.id === sourceId);
  const targetIndex = state.projects.findIndex(project => project.id === targetId);
  if(sourceIndex < 0 || targetIndex < 0) return false;
  const [project] = state.projects.splice(sourceIndex, 1);
  let insertIndex = state.projects.findIndex(item => item.id === targetId);
  if(insertIndex < 0) insertIndex = state.projects.length;
  if(placeAfter) insertIndex += 1;
  state.projects.splice(insertIndex, 0, project);
  return true;
}
async function persistProjectOrder(){
  if(!state.projects.length) return;
  const order = state.projects.map(project => project.id);
  try{
    const response = await fetch('/api/queue/projects/reorder', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({order}),
      cache: 'no-store',
    });
    if(!response.ok) throw new Error(await response.text());
    if(dockSummary) dockSummary.textContent = 'Ordem da fila salva.';
  }catch(error){
    if(dockSummary) dockSummary.textContent = `A ordem mudou nesta sessão, mas não foi salva: ${error.message || error}`;
  }
}
const projectSnapshotTimers = new Map();
function syncProjectSnapshot(project, {immediate = false, beacon = false} = {}){
  if(!project?.id) return;
  const media = {
    videos: (project.files?.videos || []).map(rel),
    audios: (project.files?.audios || []).map(rel),
    background_music: (project.files?.backgroundTracks || []).map(rel),
    texts: (project.files?.subtitles || []).map(rel),
    captions: (project.files?.captions || []).map(rel),
  };
  const payload = {
    name: project.name,
    status: project.status,
    media,
    referenceStyleVideo: project.referenceStyleVideo || null,
    options: project.options || {},
    subtitleInfo: project.subtitleInfo || null,
    captionInfo: project.captionInfo || null,
    musicGenre: project.options?.musicGenre || state.musicGenre || 'cinematic',
    outputName: project.outputName || '',
    outputFile: project.outputFile || null,
    outputDir: project.outputDir || null,
    jobId: project.backendJobId || null,
    error: project.error || null,
    estimatedSize: project.estimatedSize || 0,
    lastRenderSummary: project.lastRenderSummary || null,
    directorState: project.directorState || null,
    timelineHistory: project.timelineHistory || [],
    confidenceSummary: project.confidenceSummary || null,
    audioMasterSummary: project.audioMasterSummary || null,
    renderGraphRun: project.renderGraphRun || null,
    retryCount: Number(project.retryCount || 0),
    retryHistory: project.retryHistory || [],
  };
  const send = () => {
    projectSnapshotTimers.delete(project.id);
    const url = `/api/queue/projects/${encodeURIComponent(project.id)}/snapshot`;
    const body = JSON.stringify(payload);
    if(beacon && navigator.sendBeacon){
      try{
        const blob = new Blob([body], {type: 'application/json'});
        if(navigator.sendBeacon(url, blob)) return Promise.resolve(true);
      }catch(_){}
    }
    return fetch(url, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body,
      cache: 'no-store',
      keepalive: Boolean(immediate),
    }).catch(() => null);
  };
  clearTimeout(projectSnapshotTimers.get(project.id));
  if(immediate) return send();
  projectSnapshotTimers.set(project.id, window.setTimeout(send, 900));
  return null;
}

async function loadStoredQueueProjects(){
  try{
    const r = await fetch('/api/queue/projects', {cache: 'no-store'});
    if(!r.ok) throw new Error(await r.text());
    const payload = await r.json();
    const stored = Array.isArray(payload.projects) ? payload.projects : [];
    if(!stored.length) return false;
    state.projects = stored.map(storedProjectToModel);
    await Promise.all(state.projects.map(project => rehydrateProjectMedia(project)));
    const savedActive = localStorage.getItem('glide_active_project_id');
    state.activeProjectId = state.projects.some(project => project.id === savedActive)
      ? savedActive
      : state.projects[0]?.id || null;
    return true;
  }catch(e){
    return false;
  }
}

function projectBackupPayload(){
  captureActiveProject();
  return {
    kind: 'glide_ultra_queue_backup',
    version: state.version,
    createdAt: new Date().toISOString(),
    activeProjectId: state.activeProjectId,
    note: 'Backup de nomes, presets, status e referências de mídia. Arquivos locais podem precisar ser reimportados pelo navegador.',
    projects: state.projects.map(project => ({
      id: project.id,
      name: project.name,
      status: project.status,
      media: {
        videos: (project.files?.videos || []).map(rel),
        audios: (project.files?.audios || []).map(rel),
        background_music: (project.files?.backgroundTracks || []).map(rel),
        texts: (project.files?.subtitles || []).map(rel),
        captions: (project.files?.captions || []).map(rel),
      },
      options: project.options || {},
      subtitleInfo: project.subtitleInfo || null,
      captionInfo: project.captionInfo || null,
      musicGenre: project.options?.musicGenre || project.musicGenre || 'cinematic',
      outputName: project.outputName || project.options?.outputName || '',
      outputFile: project.outputFile || null,
      outputDir: project.outputDir || null,
      jobId: project.backendJobId || null,
      error: project.error || null,
      estimatedSize: project.estimatedSize || 0,
      lastRenderSummary: project.lastRenderSummary || null,
      directorState: project.directorState || null,
      timelineHistory: project.timelineHistory || [],
      confidenceSummary: project.confidenceSummary || null,
      audioMasterSummary: project.audioMasterSummary || null,
      renderGraphRun: project.renderGraphRun || null,
      createdAt: project.createdAt ? new Date(project.createdAt).toISOString() : new Date().toISOString(),
      updatedAt: project.updatedAt ? new Date(project.updatedAt).toISOString() : new Date().toISOString(),
    })),
  };
}

function downloadJson(payload, filename){
  const blob = new Blob([JSON.stringify(payload, null, 2)], {type: 'application/json'});
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1200);
}

async function saveProjectsBackup(){
  const payload = projectBackupPayload();
  downloadJson(payload, `glide_ultra_projetos_backup_${timestampId()}.json`);
  dockSummary.textContent = `${payload.projects.length} projeto(s) salvos no backup.`;
  try{
    await fetch('/api/queue/backup/import', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload),
      cache: 'no-store',
    });
  }catch(_){}
}

async function importProjectsBackup(file){
  if(!file || state.renderActive || state.queueRendering) return;
  let payload;
  try{
    payload = JSON.parse(await file.text());
  }catch(error){
    dockSummary.textContent = 'Backup inválido: não foi possível ler o JSON.';
    return;
  }
  const projects = Array.isArray(payload?.projects) ? payload.projects : [];
  if(!projects.length){
    dockSummary.textContent = 'Backup invalido: nenhum projeto encontrado.';
    return;
  }
  try{
    const response = await fetch('/api/queue/backup/import', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload),
      cache: 'no-store',
    });
    if(!response.ok) throw new Error(await response.text());
    const result = await response.json();
    const previous = new Map(state.projects.map(project => [project.id, project]));
    const restored = Array.isArray(result.projects) ? result.projects : projects;
    state.projects = restored.map((raw, index) => {
      const incoming = storedProjectToModel(raw, index);
      const existing = previous.get(incoming.id);
      if(existing){
        incoming.files = existing.files;
        incoming.maps = existing.maps;
        incoming.subtitleInfo = raw.subtitleInfo || existing.subtitleInfo || null;
        incoming.captionInfo = raw.captionInfo || existing.captionInfo || null;
        incoming.outputDir = raw.outputDir || existing.outputDir || '';
        incoming.outputFile = raw.outputFile || existing.outputFile || '';
        incoming.backendJobId = raw.jobId || existing.backendJobId || '';
      }
      return incoming;
    });
    const preferred = payload.activeProjectId && state.projects.some(project => project.id === payload.activeProjectId)
      ? payload.activeProjectId
      : state.projects[0]?.id;
    state.activeProjectId = null;
    if(preferred) loadProject(preferred);
    renderProjectQueue();
    dockSummary.textContent = `Backup importado: ${result.added || 0} novo(s), ${result.updated || 0} atualizado(s). Projetos existentes foram preservados.`;
  }catch(error){
    dockSummary.textContent = `Falha ao importar backup: ${error.message || error}`;
  }
}

async function initializeProjectQueue(){
  await loadStoredQueueProjects();
  ensureProject();
  const targetId = state.activeProjectId || state.projects[0]?.id;
  state.activeProjectId = null;
  if(targetId) loadProject(targetId);
  renderProjectQueue();
  renderLists();
  updateStats();
  scheduleBackgroundVisualIndex();
}

let visualIndexScheduleTimer = null;
function scheduleBackgroundVisualIndex(){
  if(state.renderActive || state.queueRendering) return;
  clearTimeout(visualIndexScheduleTimer);
  visualIndexScheduleTimer = window.setTimeout(() => {
    state.projects
      .filter(project => project?.id && (project.files?.videos || []).length)
      .slice(0, 8)
      .forEach(project => {
        fetch(`/api/intelligence/visual-index/${encodeURIComponent(project.id)}/background`, {
          method: 'POST',
          cache: 'no-store',
        }).catch(() => {});
      });
  }, 1800);
}

let projectSyncTimer = null;
function scheduleProjectSync(){
  if(!state.activeProjectId || state.renderActive || state.queueRendering) return;
  clearTimeout(projectSyncTimer);
  projectSyncTimer = window.setTimeout(() => {
    captureActiveProject();
    renderProjectQueue();
  }, 760);
}

function playSfx(effect){
  if(!effect) {
    if(dockSummary) dockSummary.textContent = 'Este modo não usa efeito sonoro automático.';
    return;
  }
  const audio = new Audio(`/api/sfx-preview/${encodeURIComponent(effect)}?v=${state.version}&t=${Date.now()}`);
  audio.volume = 0.82;
  audio.play().catch(() => {
    if(dockSummary) dockSummary.textContent = 'Clique novamente se o navegador bloquear o preview de audio.';
  });
}

function playSfxSequence(effects, gap = 360){
  normalizeSfxSequence(effects).filter(Boolean).forEach((item, index) => {
    const effect = Array.isArray(item) ? item[0] : (typeof item === 'object' ? item.effect : item);
    const delay = Array.isArray(item) ? Number(item[1] || 0) : (typeof item === 'object' ? Number(item.delay || 0) : index * gap);
    window.setTimeout(() => playSfx(effect), Math.max(0, delay));
  });
}

function normalizeSfxSequence(value){
  if(!value) return [];
  if(typeof value === 'string') return value ? [value] : [];
  if(Array.isArray(value)) return value;
  if(typeof value === 'object' && value.effect) return [value];
  return [];
}

function applySupportedSelectOptions(select, available, always = []){
  if(!select || !available) return;
  const allowed = new Set([...(available || []), ...always]);
  let selectedStillVisible = false;
  [...select.options].forEach(option => {
    const ok = allowed.has(option.value);
    option.hidden = !ok;
    option.disabled = !ok;
    if(ok && option.value === select.value) selectedStillVisible = true;
  });
  if(!selectedStillVisible){
    const fallback = [...select.options].find(option => !option.disabled);
    if(fallback) select.value = fallback.value;
  }
}

async function loadSfxPreviewMap(){
  try{
    const response = await fetch(`/api/sfx-preview-map?v=${state.version}`, {cache: 'no-store'});
    if(!response.ok) throw new Error(await response.text());
    const data = await response.json();
    if(data.subtitle && typeof data.subtitle === 'object'){
      Object.keys(subtitleFxByAnimation).forEach(key => delete subtitleFxByAnimation[key]);
      Object.assign(subtitleFxByAnimation, data.subtitle);
    }
    if(data.transition && typeof data.transition === 'object'){
      Object.keys(transitionFxByMode).forEach(key => delete transitionFxByMode[key]);
      Object.assign(transitionFxByMode, data.transition);
    }
    applySupportedSelectOptions(subtitleAnimation, data.available_subtitle_animations, ['none']);
    applySupportedSelectOptions($('#transitionSelect'), data.available_transitions, ['off']);
  }catch(error){
    if(dockSummary) dockSummary.textContent = 'Mapa de FX indisponivel; usando presets locais de audio.';
  }
}

function secondsFromClipStamp(value){
  const text = String(value || '');
  const matches = [...text.matchAll(/(\d{1,2})m(\d{2})s-(\d{1,2})m(\d{2})s/gi)];
  const match = matches.length ? matches[matches.length - 1] : null;
  if(!match) return 0;
  const start = Number(match[1]) * 60 + Number(match[2]);
  const end = Number(match[3]) * 60 + Number(match[4]);
  return end > start ? end - start : 0;
}

function kindOfFile(file, forcedKind = null){
  if(!forcedKind && file?._forcedKind) return file._forcedKind;
  if(forcedKind === 'video') return looksLikeVideo(file) ? 'video' : (looksLikeImage(file) ? 'image' : null);
  if(forcedKind === 'audio') return looksLikeAudio(file) ? 'audio' : null;
  if(forcedKind === 'background_music') return looksLikeAudio(file) ? 'background_music' : null;
  const type = (file.type || '').toLowerCase();
  if(forcedKind === 'subtitle') return subtitleExt.includes(ext(file)) ? 'subtitle' : null;
  if(forcedKind === 'caption_srt') return subtitleExt.includes(ext(file)) ? 'caption_srt' : null;
  if(forcedKind === 'script_guide') return scriptGuideExt.includes(ext(file)) ? 'script_guide' : null;
  if(type.startsWith('video/')) return 'video';
  if(type.startsWith('image/') && ext(file) !== 'gif') return 'image';
  if(type.startsWith('audio/')) return 'audio';
  const e = ext(file);
  if(videoOnlyExt.includes(e)) return 'video';
  if(imageExt.includes(e)) return 'image';
  if(audioOnlyExt.includes(e)) return 'audio';
  if(subtitleExt.includes(e)) return 'subtitle';
  if(scriptGuideExt.includes(e)) return 'script_guide';
  if(e === 'webm') return 'video';
  return null;
}
function looksLikeVideo(file){
  const type = (file.type || '').toLowerCase();
  return type.startsWith('video/') || videoExt.includes(ext(file));
}
function looksLikeAudio(file){
  const type = (file.type || '').toLowerCase();
  return type.startsWith('audio/') || audioContainerExt.includes(ext(file));
}
function looksLikeImage(file){
  const type = (file.type || '').toLowerCase();
  return (type.startsWith('image/') && ext(file) !== 'gif') || imageExt.includes(ext(file));
}
function isVideo(file){ return kindOfFile(file) === 'video'; }
function isImage(file){ return kindOfFile(file) === 'image'; }
function isVisualMedia(file){ return isVideo(file) || isImage(file); }
function isAudio(file){ return kindOfFile(file) === 'audio'; }
function isSubtitle(file){ return kindOfFile(file) === 'subtitle'; }

function setVideoStatus(file, kind, label){
  if(!isVisualMedia(file)) return;
  state.mediaStatus.set(rel(file), {kind, label});
}

function videoStatusOf(file){
  return state.mediaStatus.get(rel(file)) || {kind: 'pending', label: 'Aguardando analise'};
}

function videoStatusClass(status, hasThumb){
  if(status.kind === 'invalid') return ' invalid';
  if(hasThumb) return '';
  if(status.kind === 'no_preview') return ' no-preview';
  if(status.kind === 'checking' || status.kind === 'metadata_ok') return ' checking';
  return '';
}

function videoPlaceholder(status){
  if(status.kind === 'image') return 'IMAGEM';
  if(status.kind === 'invalid') return 'INVALIDO';
  if(status.kind === 'no_preview') return 'SEM PREVIEW';
  if(status.kind === 'checking' || status.kind === 'metadata_ok') return 'ANALISANDO';
  return 'VIDEO';
}

function videoWarningHtml(status){
  if(!status || status.kind === 'preview_ok' || status.kind === 'pending') return '';
  const bad = status.kind === 'invalid' ? ' bad' : '';
  return `<div class="clip-warning${bad}">${escapeHtml(status.label)}</div>`;
}

function videoStatusBadgeHtml(status){
  const kind = status?.kind || 'pending';
  const labels = {
    preview_ok: 'Limpo',
    image: 'Imagem',
    invalid: 'Invalido',
    no_frames: 'Sem frames',
    no_preview: 'Sem preview',
    checking: 'Análise',
    metadata_ok: 'Análise',
    text_dominant: 'Texto',
    text_suspect: 'Texto',
    black_screen: 'Preto',
    presenter_suspect: 'Apresentador',
    presenter: 'Apresentador',
    person_contextual: 'Pessoa contextual',
    avatar: 'Avatar',
    suspect: 'Suspeito',
    static_center_suspect: 'Suspeito',
    context_mismatch: 'Contexto',
    low_quality: 'Baixa qualidade',
    analysis_unavailable: 'Sem analise',
  };
  const label = labels[kind];
  if(!label) return '';
  return `<span class="clip-status-badge ${escapeHtml(kind)}">${escapeHtml(label)}</span>`;
}

function applyVisualCleanStatusFromSummary(summary){
  if(!summary?.enabled || !Array.isArray(summary.items) || !state.videos.length) return;
  let changed = false;
  const byName = new Map();
  state.videos.forEach(file => {
    byName.set(file.name, file);
    byName.set(rel(file), file);
  });
  summary.items.forEach(item => {
    const category = String(item.category || '').trim();
    if(!category || category === 'clean') return;
    const file = byName.get(item.name) || byName.get(item.file);
    if(!file) return;
    const current = videoStatusOf(file);
    const reason = String(item.reason || '').toLowerCase();
    if(category === 'invalid' && reason.includes('sem frames para analise visual')){
      state.mediaStatus.set(rel(file), {
        kind: 'no_preview',
        label: 'Análise visual anterior falhou; o clipe será preservado e reanalisado pelo FFmpeg.',
      });
      changed = true;
      return;
    }
    if(current.kind === 'invalid') return;
    const decision = item.decision === 'removed'
      ? 'removido do render'
      : item.decision === 'fallback_only'
        ? 'rebaixado para fallback'
        : item.decision === 'kept_late'
          ? 'permitido no final'
          : 'marcado pelo filtro';
    const label = `${item.reason || 'clipe suspeito'} - ${decision}.`;
    const previous = state.mediaStatus.get(rel(file));
    if(!previous || previous.kind !== category || previous.label !== label){
      state.mediaStatus.set(rel(file), {kind: category, label});
      changed = true;
    }
  });
  if(changed){
    renderLists();
    captureActiveProject();
  }
}

async function loadVisualAnalysisDetails(jobId){
  if(!jobId) return null;
  try{
    const response = await fetch(`/api/jobs/${encodeURIComponent(jobId)}/visual-analysis?ts=${Date.now()}`, {cache: 'no-store'});
    if(!response.ok) return null;
    return await response.json();
  }catch(_){
    return null;
  }
}

function lastRenderSummaryFromJob(job, visualPayload = null){
  const fullVisual = visualPayload?.summary || {};
  const compactVisual = job?.timeline_summary?.visual_clean_summary || {};
  return {
    jobId: job?.id || '',
    status: job?.status || '',
    renderPriority: job?.render_priority_effective || 'balanced',
    visualClean: compactVisual,
    visualCleanDetails: {
      items: Array.isArray(fullVisual.items) ? fullVisual.items : [],
      fallbackUsedItems: Array.isArray(fullVisual.fallback_used_items) ? fullVisual.fallback_used_items : [],
    },
    performance: visualPayload?.performance || job?.timeline_summary?.performance_breakdown || {},
    subtitleTiming: visualPayload?.subtitleTiming || job?.timeline_summary?.subtitle_timing_summary || {},
    soundFx: job?.sound_fx_summary || {},
    backgroundMusic: job?.background_music_summary || {},
    cta: job?.cta_summary || {},
    subtitles: job?.subtitle_summary || {},
    intro: job?.intro_summary || {},
    recovery: job?.recovery_summary || {},
    director: job?.director_summary || {},
    energy: job?.energy_summary || {},
    confidence: job?.confidence_summary || {},
    continuity: job?.continuity_summary || {},
    antiRepeat: job?.anti_repeat_summary || {},
    audioMaster: job?.audio_master_summary || {},
    renderGraph: job?.render_graph_run || {},
    renderDecisions: job?.renderDecisions || job?.render_decisions || {},
    editorialIntelligence: job?.editorialIntelligence || job?.editorial_intelligence_plan || {},
    styleProfile: job?.styleProfile || job?.style_profile || job?.preflight_summary?.style_profile || {},
    eventTimeline: job?.eventTimeline || job?.event_timeline || {},
    performanceHistory: job?.performance_history || job?.performanceHistory || [],
    errorActions: job?.error_actions || job?.errorActions || [],
    outputName: job?.output_name || '',
    outputDir: job?.output_dir || '',
    finishedAt: new Date().toISOString(),
  };
}

function renderErrorSummary(message, context = {}){
  const text = cleanDisplayText(message || 'Erro desconhecido no render.');
  const lower = text.toLowerCase();
  const actions = [];
  if(lower.includes('codec') || lower.includes('hevc') || lower.includes('h.265') || lower.includes('h265')){
    actions.push({label: 'Tentar H.264 CPU', action: 'h264_cpu', reason: 'Falha provável de codec ou aceleração.', detail: 'Falha provável de codec ou aceleração.'});
  }
  if(lower.includes('clipe') || lower.includes('video') || lower.includes('vídeo') || lower.includes('corromp')){
    actions.push({label: 'Tentar sem clipes inválidos', action: 'skip_invalid_clips', reason: 'Algum clipe pode ter falhado na decodificação.', detail: 'Algum clipe pode ter falhado na decodificação.'});
  }
  if(lower.includes('srt') || lower.includes('legenda') || lower.includes('ass')){
    actions.push({label: 'Recriar legendas', action: 'rebuild_subtitles', reason: 'Falha provável no arquivo de legenda ou composição ASS.', detail: 'Falha provável no arquivo de legenda ou composição ASS.'});
  }
  if(lower.includes('audio') || lower.includes('áudio') || lower.includes('narra')){
    actions.push({label: 'Reimportar narração', action: 'reimport_audio', reason: 'A narração pode não ter sido lida corretamente.', detail: 'A narração pode não ter sido lida corretamente.'});
  }
  actions.push({label: 'Tentar novamente em Turbo', action: 'retry_turbo', reason: 'Usa caminho de produção mais simples e rápido.', detail: 'Usa caminho de produção mais simples e rápido.'});
  actions.push({label: 'Render seguro', action: 'safe_render', reason: 'Mantém o essencial e desativa automações arriscadas neste render.', detail: 'Mantém o essencial e desativa automações arriscadas neste render.'});
  return {
    status: 'error',
    renderPriority: context.renderPriority || state.renderPriority,
    error: text,
    errorActions: actions.slice(0, 5),
    performance: {},
    visualClean: {},
    confidence: {overall: 0, risk: 'alto', risks: [text]},
    outputName: context.outputName || '',
    outputDir: context.outputDir || '',
    finishedAt: new Date().toISOString(),
  };
}

function updateIntelligenceV15(payload = {}){
  const confidence = payload.confidence_summary || payload.confidence || {};
  if(confidenceSummaryBox){
    const score = confidence.overall;
    const confidenceAction = confidence.actions?.[0]?.label;
    confidenceSummaryBox.querySelector('strong').textContent = Number.isFinite(Number(score)) ? `${Math.round(Number(score))}%` : '--';
    confidenceSummaryBox.querySelector('small').textContent = confidence.risk
      ? `Risco ${confidence.risk}${confidence.risks?.length ? ` - ${confidence.risks[0]}` : ''}`
      : 'Aguardando verificação';
    if(confidenceAction){
      confidenceSummaryBox.querySelector('small').textContent += ` - ${confidenceAction}`;
    }
    confidenceSummaryBox.dataset.state = Number(score) >= 80 ? 'ok' : (Number(score) >= 60 ? 'warn' : 'neutral');
  }
  const graph = payload.render_graph_run || payload.renderGraph || {};
  if(renderGraphBox){
    const counts = graph.counts || {};
    const active = (graph.nodes || []).find(node => node.status === 'running');
    renderGraphBox.querySelector('strong').textContent = active?.label || (graph.status === 'complete' ? 'Concluido' : 'Pronto');
    const savedLabel = Number(graph.saved_seconds || 0) > 0
      ? ` - ~${formatTime(Number(graph.saved_seconds))} poupado`
      : '';
    renderGraphBox.querySelector('small').textContent = graph.nodes?.length
      ? `${counts.processed || 0} processada(s) - ${counts.reused || 0} reutilizada(s) - ${counts.resumed || 0} retomada(s) - ${counts.failed || 0} falha(s)${savedLabel}`
      : 'Nenhuma execução ativa';
    renderGraphBox.dataset.state = counts.failed ? 'warn' : (graph.status === 'complete' ? 'ok' : 'neutral');
  }
  if(renderGraphNodes){
    const statusLabel = {
      processed: 'Processada',
      reused: 'Reutilizada',
      resumed: 'Retomada',
      running: 'Processando',
      failed: 'Falhou',
    };
    renderGraphNodes.innerHTML = (graph.nodes || []).slice(-10).map(node => `
      <span class="graph-node graph-node-${escapeHtml(node.status || 'pending')}">
        <b>${escapeHtml(node.label || node.stage || 'Etapa')}</b>
        <em>${escapeHtml(statusLabel[node.status] || 'Pendente')}</em>
      </span>
    `).join('');
  }
}

async function loadSemanticModelStatus(){
  if(!semanticModelBox) return;
  try{
    const response = await fetch(`/api/intelligence/model?ts=${Date.now()}`, {cache: 'no-store'});
    if(!response.ok) throw new Error(await response.text());
    const status = await response.json();
    semanticModelBox.querySelector('strong').textContent = status.active ? 'MobileCLIP' : 'Heurístico';
    semanticModelBox.querySelector('small').textContent = status.active
      ? 'Modelo ONNX local ativo'
      : (status.installed ? 'Pacote detectado; fallback local ativo' : 'Heurísticas locais ativas');
    semanticModelBox.dataset.state = status.active ? 'ok' : 'neutral';
  }catch(_){
    semanticModelBox.querySelector('strong').textContent = 'Local';
    semanticModelBox.querySelector('small').textContent = 'Estado indisponivel';
    semanticModelBox.dataset.state = 'warn';
  }
}

async function directorProjectAction(action){
  const project = state.projects.find(item => item.id === state.activeProjectId);
  if(!project?.id) return;
  const response = await fetch(`/api/queue/projects/${encodeURIComponent(project.id)}/director/${action}`, {
    method: 'POST',
    cache: 'no-store',
  });
  if(!response.ok) throw new Error(await response.text());
  const payload = await response.json();
  if(payload.project){
    const restored = storedProjectToModel(payload.project);
    project.options = restored.options;
    project.directorState = restored.directorState;
    project.timelineHistory = restored.timelineHistory;
    if(action === 'undo' && Array.isArray(payload.project.media?.videos)){
      const byRel = new Map((project.files?.videos || []).map(file => [rel(file), file]));
      project.files.videos = payload.project.media.videos.map(key => byRel.get(key)).filter(Boolean);
      if(project.id === state.activeProjectId){
        state.videos = [...project.files.videos];
        renderLists();
      }
    }
  }
  if(dockSummary) dockSummary.textContent = action === 'undo'
    ? 'Montagem anterior restaurada.'
    : 'Direcao marcada para recalculo no proximo render.';
  renderProjectQueue();
}

async function recordLearningEvent(eventType, value = {}){
  const project = state.projects.find(item => item.id === state.activeProjectId);
  if(!project?.id || channelLearningToggle?.checked === false) return;
  const channel = encodeURIComponent(project.name || 'default');
  fetch(`/api/intelligence/learning/${channel}/correction`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      source: 'user',
      eventType,
      projectId: project.id,
      value,
    }),
    cache: 'no-store',
  }).then(response => response.ok ? response.json() : null)
    .then(payload => {
      if(payload?.active) loadChannelLearning().catch(() => {});
    })
    .catch(() => {});
}

async function loadChannelLearning(){
  const project = state.projects.find(item => item.id === state.activeProjectId);
  if(!project?.id) return {channel: '', preferences: []};
  const response = await fetch(`/api/intelligence/learning/${encodeURIComponent(project.name || 'default')}?ts=${Date.now()}`, {cache: 'no-store'});
  if(!response.ok) throw new Error(await response.text());
  const payload = await response.json();
  const preferences = Array.isArray(payload.preferences) ? payload.preferences : [];
  if(learningSummaryBox){
    learningSummaryBox.innerHTML = preferences.length
      ? preferences.slice(0, 8).map(item => `<span><b>${escapeHtml(item.preference_key || 'preferência')}</b> ${Math.round(Number(item.weight || 0) * 100)}% - ${Number(item.evidence_count || 0)} sinais</span>`).join('')
      : 'O aprendizado deste canal aparece depois de três correções manuais semelhantes.';
  }
  return payload;
}

async function checkHealth(){
  const badge = $('#healthBadge');
  try{
    const r = await fetch('/api/health?ts=' + Date.now(), {cache: 'no-store'});
    const j = await r.json();
    if(j.ffmpeg && j.ffprobe){
      badge.textContent = `FFmpeg pronto - app local - v${j.version || state.version}`;
      badge.className = 'health ok';
    }else{
      badge.textContent = 'FFmpeg não encontrado';
      badge.className = 'health bad';
    }
  }catch(e){
    badge.textContent = 'Motor local offline';
    badge.className = 'health bad';
  }
  refreshExportProfileUi();
  updateSubtitlePreview();
}

function durationOf(file){
  return new Promise((resolve) => {
    const url = URL.createObjectURL(file);
    const el = document.createElement(isAudio(file) ? 'audio' : 'video');
    const fallback = isVideo(file) ? secondsFromClipStamp(file.name) : 0;
    let settled = false;
    const done = (value, source = 'metadata') => {
      if(settled) return;
      settled = true;
      clearTimeout(timer);
      URL.revokeObjectURL(url);
      resolve({seconds: value || 0, source});
    };
    const timer = setTimeout(() => {
      done(fallback, fallback > 0 ? 'filename' : 'timeout');
    }, isVideo(file) ? (fallback > 0 ? 420 : 1800) : 3500);
    el.preload = 'metadata';
    el.onloadedmetadata = () => {
      const duration = Number.isFinite(el.duration) ? el.duration : 0;
      done(duration > 0 ? duration : fallback, duration > 0 ? 'metadata' : (fallback > 0 ? 'filename' : 'metadata'));
    };
    el.onerror = () => done(fallback, fallback > 0 ? 'filename' : 'error');
    el.src = url;
  });
}

async function analyzeAudioFileHealth(file, forcedKind = null){
  if(forcedKind !== 'audio' && (!isAudio(file) || kindOfFile(file) !== 'audio')){
    return null;
  }
  if(file.size > 45 * 1024 * 1024){
    return {status: 'unknown', message: 'Áudio grande: análise completa será feita no render.', longestSilence: 0, silenceRatio: 0};
  }
  const AudioCtx = window.AudioContext || window.webkitAudioContext;
  if(!AudioCtx){
    return {status: 'unknown', message: 'Navegador sem análise Web Audio.', longestSilence: 0, silenceRatio: 0};
  }
  let ctx;
  try{
    const buffer = await file.arrayBuffer();
    ctx = new AudioCtx();
    const decoded = await ctx.decodeAudioData(buffer.slice(0));
    const sr = decoded.sampleRate || 48000;
    const step = Math.max(512, Math.round(sr * 0.045));
    const threshold = 0.0032;
    let silentSamples = 0;
    let longest = 0;
    let current = 0;
    let peak = 0;
    const ch0 = decoded.getChannelData(0);
    const ch1 = decoded.numberOfChannels > 1 ? decoded.getChannelData(1) : ch0;
    for(let i = 0; i < decoded.length; i += step){
      let sum = 0;
      let localPeak = 0;
      const end = Math.min(decoded.length, i + step);
      for(let j = i; j < end; j += 32){
        const sample = (Math.abs(ch0[j]) + Math.abs(ch1[j])) / 2;
        localPeak = Math.max(localPeak, sample);
        sum += sample * sample;
      }
      const frames = Math.max(1, Math.ceil((end - i) / 32));
      const rms = Math.sqrt(sum / frames);
      peak = Math.max(peak, localPeak);
      const secs = (end - i) / sr;
      if(rms < threshold){
        current += secs;
        silentSamples += secs;
      }else{
        longest = Math.max(longest, current);
        current = 0;
      }
    }
    longest = Math.max(longest, current);
    const ratio = silentSamples / Math.max(decoded.duration || 1, 1);
    const clipping = peak > 0.985;
    const status = (clipping || longest >= 4 || ratio >= 0.22) ? 'problem' : ((longest >= 1.2 || ratio >= 0.08) ? 'warn' : 'ok');
    const message = status === 'ok'
      ? 'Saudavel'
      : status === 'warn'
        ? `Atencao: pausa ate ${longest.toFixed(1)}s`
        : `Problema: ${clipping ? 'pico alto' : `lacuna ${longest.toFixed(1)}s`}`;
    return {status, message, longestSilence: longest, silenceRatio: ratio, possibleClipping: clipping};
  }catch(e){
    return {status: 'unknown', message: 'Análise local falhou; backend confirma no render.', longestSilence: 0, silenceRatio: 0};
  }finally{
    if(ctx?.close) ctx.close().catch(() => {});
  }
}

function thumbOf(file){
  return new Promise((resolve) => {
    if(!isVideo(file)) return resolve(null);
    const url = URL.createObjectURL(file);
    const video = document.createElement('video');
    let settled = false;
    const finish = (value) => {
      if(settled) return;
      settled = true;
      clearTimeout(timer);
      URL.revokeObjectURL(url);
      resolve(value || null);
    };
    const timer = setTimeout(() => finish(null), 1600);
    const capture = () => {
      try{
        const canvas = document.createElement('canvas');
        canvas.width = 160;
        canvas.height = 90;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        let yavg = 0;
        let ymin = 255;
        let ymax = 0;
        try{
          const data = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
          const step = 16;
          let samples = 0;
          for(let i = 0; i < data.length; i += 4 * step){
            const y = 0.2126 * data[i] + 0.7152 * data[i + 1] + 0.0722 * data[i + 2];
            yavg += y;
            ymin = Math.min(ymin, y);
            ymax = Math.max(ymax, y);
            samples++;
          }
          yavg = samples ? yavg / samples : 0;
        }catch(e){}
        const yrange = ymax - ymin;
        const visible = !(yavg <= 12 && ymax <= 28 && yrange < 7);
        finish({src: canvas.toDataURL('image/jpeg', 0.52), visible, yavg, yrange});
      }catch(e){
        finish(null);
      }
    };
    video.muted = true;
    video.preload = 'metadata';
    video.playsInline = true;
    video.onloadedmetadata = () => {
      const duration = video.duration || 0;
      const safePoint = Math.min(Math.max(duration * 0.35, 0.08), Math.max(0.08, duration - 0.08));
      try{
        video.currentTime = isFinite(safePoint) ? safePoint : 0.08;
      }catch(e){
        capture();
      }
    };
    video.onloadeddata = () => {
      if(!isFinite(video.duration) || video.duration <= 0.12) capture();
    };
    video.onseeked = capture;
    video.onerror = () => finish(null);
    video.src = url;
  });
}

async function runPool(items, limit, worker){
  let index = 0;
  const runners = Array.from({length: Math.min(limit, items.length)}, async () => {
    while(index < items.length){
      const item = items[index++];
      await worker(item);
      await new Promise(resolve => setTimeout(resolve, 0));
    }
  });
  await Promise.all(runners);
}

function requestUiRefresh({lists = true, stats = true} = {}){
  if(state.uiRefreshQueued) return;
  state.uiRefreshQueued = true;
  requestAnimationFrame(() => {
    state.uiRefreshQueued = false;
    if(lists && !state.renderActive && !state.queueRendering) renderLists();
    if(stats) updateStats();
  });
}

function videoSignature(){
  return state.videos.map((file, idx) => {
    const r = rel(file);
    return `${idx}:${r}:${state.durations.get(r) || 0}:${state.durationSources.get(r) || ''}:${state.thumbs.has(r) ? 1 : 0}:${state.mediaStatus.get(r)?.kind || ''}`;
  }).join('|');
}

function audioSignature(){
  return state.audios.map((file, idx) => {
    const r = rel(file);
    return `${idx}:${r}:${state.durations.get(r) || 0}:${state.audioHealth.get(r)?.status || ''}:${state.audioHealth.get(r)?.message || ''}`;
  }).join('|');
}

function backgroundSignature(){
  const tracks = state.backgroundTracks.map((file, idx) => {
    const r = rel(file);
    return `${idx}:${r}:${state.durations.get(r) || 0}`;
  }).join('|');
  const info = presetMusicInfo();
  return `${state.musicGenre}:${info.count}:${tracks}`;
}

function setRenderActive(active){
  state.renderActive = Boolean(active);
  document.body.classList.toggle('render-active', state.renderActive);
  if(stopRenderBtn){
    stopRenderBtn.classList.toggle('hidden', !state.renderActive);
    stopRenderBtn.disabled = false;
    stopRenderBtn.textContent = 'Parar render';
  }
  if(stopQueueBtn) stopQueueBtn.classList.toggle('hidden', !(state.renderActive || state.queueRendering));
  if(renderPrioritySelect) renderPrioritySelect.disabled = state.renderActive || state.queueRendering;
  state.lastStatusPaint = null;
}

function resolvedThemeMode(){
  if(state.themeMode === 'light' || state.themeMode === 'dark') return state.themeMode;
  return systemThemeQuery?.matches ? 'light' : 'dark';
}

function applyThemeMode(){
  const valid = new Set(['system', 'dark', 'light']);
  if(!valid.has(state.themeMode)) state.themeMode = 'system';
  const resolved = resolvedThemeMode();
  document.body.dataset.theme = state.themeMode;
  document.body.dataset.themeResolved = resolved;
  document.documentElement.dataset.theme = state.themeMode;
  if(themeSelect) themeSelect.value = state.themeMode;
  const metaTheme = document.querySelector('meta[name="theme-color"]');
  if(metaTheme) metaTheme.content = resolved === 'light' ? '#f3f7f2' : '#080a09';
  if(state.uiSoundScope === 'theme') applyScopedUiSoundPreference(true);
}

let startupSoundPlayed = false;
let startupSoundFallbackArmed = false;

function scheduleStartupTone(ctx, destination, start, offset, length, fromFreq, toFreq, peak, type = 'sine'){
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  const at = start + offset;
  osc.type = type;
  osc.frequency.setValueAtTime(fromFreq, at);
  osc.frequency.exponentialRampToValueAtTime(Math.max(32, toFreq), at + length);
  gain.gain.setValueAtTime(0.0001, at);
  gain.gain.exponentialRampToValueAtTime(peak, at + Math.min(.055, length * .32));
  gain.gain.exponentialRampToValueAtTime(0.0001, at + length);
  osc.connect(gain);
  gain.connect(destination);
  osc.start(at);
  osc.stop(at + length + .04);
}

function playStartupChime(){
  if(startupSoundPlayed) return Promise.resolve(true);
  const AudioContext = window.AudioContext || window.webkitAudioContext;
  if(!AudioContext) return Promise.resolve(false);
  startupSoundPlayed = true;
  const ctx = new AudioContext();
  const start = ctx.currentTime + .035;
  const master = ctx.createGain();
  const toneFilter = ctx.createBiquadFilter();
  master.gain.setValueAtTime(0.0001, start);
  master.gain.exponentialRampToValueAtTime(0.32, start + .06);
  master.gain.exponentialRampToValueAtTime(0.0001, start + .74);
  toneFilter.type = 'lowpass';
  toneFilter.frequency.setValueAtTime(3600, start);
  toneFilter.frequency.exponentialRampToValueAtTime(1700, start + .74);
  master.connect(toneFilter);
  toneFilter.connect(ctx.destination);
  const ready = ctx.state === 'suspended' ? ctx.resume() : Promise.resolve();
  return ready.then(() => {
    if(ctx.state === 'suspended') throw new Error('audio-blocked');
    scheduleStartupTone(ctx, master, start, 0, .48, 147, 82, .03, 'triangle');
    scheduleStartupTone(ctx, master, start, .09, .28, 392, 523, .026, 'sine');
    scheduleStartupTone(ctx, master, start, .22, .34, 523, 740, .02, 'sine');
    scheduleStartupTone(ctx, master, start, .44, .22, 740, 659, .012, 'sine');
    window.setTimeout(() => ctx.close().catch(() => {}), 950);
    return true;
  }).catch(() => {
    startupSoundPlayed = false;
    try{ ctx.close(); }catch(_err){}
    return false;
  });
}

function armStartupSoundFallback(){
  if(startupSoundFallbackArmed || startupSoundPlayed) return;
  startupSoundFallbackArmed = true;
  const trigger = () => {
    playStartupChime();
    document.removeEventListener('pointerdown', trigger);
    document.removeEventListener('keydown', trigger);
  };
  document.addEventListener('pointerdown', trigger, {once: true, passive: true});
  document.addEventListener('keydown', trigger, {once: true});
}

function runEditorIntro(){
  if(!editorIntro) return;
  const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
  const removeAfter = reduced ? 90 : 1380;
  if(reduced){
    editorIntro.remove();
    return;
  }
  const startSound = () => {
    playStartupChime().then(played => {
      if(!played) armStartupSoundFallback();
    });
  };
  if('requestIdleCallback' in window){
    window.requestIdleCallback(startSound, {timeout: 760});
  }else{
    window.setTimeout(startSound, 720);
  }
  window.setTimeout(() => {
    editorIntro.remove();
  }, removeAfter);
}

function normalizedRenderPriority(value){
  const normalized = String(value || 'balanced').toLowerCase();
  if(['max', 'turbo', 'turbo_production', 'production_max', 'speed'].includes(normalized)) return 'max';
  if(['quality', 'quality_max', 'max_quality', 'premium', 'maximum_quality'].includes(normalized)) return 'quality';
  return 'balanced';
}

function normalizedVisualFilterLevel(value){
  const level = String(value || 'normal').toLowerCase();
  return ['light', 'normal', 'strict'].includes(level) ? level : 'normal';
}

function visualFilterLevelLabel(value){
  return {light: 'Leve', normal: 'Normal', strict: 'Rigoroso'}[normalizedVisualFilterLevel(value)];
}

function applyVisualFilterUi(){
  const directorRequested = smartVisualDirectorToggle ? smartVisualDirectorToggle.checked : true;
  const adaptiveAvailable = directorRequested && state.renderPriority !== 'max';
  if(adaptiveVisualFilterToggle){
    adaptiveVisualFilterToggle.disabled = !adaptiveAvailable;
    adaptiveVisualFilterToggle.closest('label')?.classList.toggle('is-disabled', !adaptiveAvailable);
    adaptiveVisualFilterToggle.closest('label')?.setAttribute(
      'title',
      adaptiveAvailable
        ? 'Rigoroso no primeiro terço, Normal no segundo e Leve no final.'
        : 'Disponível apenas com o Modo Águia ativo no modo Eficiente.'
    );
  }
  const adaptiveEffective = adaptiveAvailable && Boolean(adaptiveVisualFilterToggle?.checked);
  if(visualFilterLevelSelect){
    visualFilterLevelSelect.disabled = adaptiveEffective;
    visualFilterLevelSelect.closest('label')?.classList.toggle('is-disabled', adaptiveEffective);
  }
  if(visualFilterHint){
    visualFilterHint.textContent = adaptiveEffective
      ? 'Adaptativo: Rigoroso no início, Normal no meio e Leve no final. Imagens permanecem rigorosas.'
      : `${visualFilterLevelLabel(visualFilterLevelSelect?.value)}: filtro manual ativo em todo o vídeo; imagens permanecem rigorosas.`;
  }
}

function renderPriorityLabel(value = state.renderPriority){
  return '1080p Ultra Performance';
}

function applyRenderPriorityUi(){
  state.renderPriority = 'max';
  if(renderPrioritySelect) renderPrioritySelect.value = 'max';
  document.body.classList.add('render-priority-unified');
  document.body.classList.remove('render-priority-turbo', 'render-priority-quality', 'render-priority-balanced');
  applyVisualFilterUi();
}

function currentTimelineDuration(){
  const narration = state.audios.reduce((sum, file) => sum + (state.durations.get(rel(file)) || 0), 0);
  const videos = state.videos.reduce((sum, file) => sum + (state.durations.get(rel(file)) || 0), 0);
  const intro = (introModeSelect?.value || state.introMode) === 'cinematic' ? 3 : 0;
  return Math.max(0, narration || videos) + intro;
}

function estimateRangeText(estimate){
  if(!estimate?.seconds) return 'indisponível';
  return `${formatTime(estimate.minimum_seconds || estimate.seconds)}-${formatTime(estimate.maximum_seconds || estimate.seconds)}`;
}

let renderEstimateTimer = null;
function scheduleRenderEstimate(){
  if(!renderTimeEstimate) return;
  window.clearTimeout(renderEstimateTimer);
  const duration = currentTimelineDuration();
  if(duration <= 0){
    renderTimeEstimate.innerHTML = '<span>Tempo estimado</span><strong>Aguardando duração do áudio</strong>';
    return;
  }
  renderEstimateTimer = window.setTimeout(() => refreshRenderEstimate(duration), 220);
}

async function refreshRenderEstimate(duration = currentTimelineDuration()){
  if(!renderTimeEstimate || duration <= 0) return;
  const token = ++state.renderEstimateToken;
  renderTimeEstimate.innerHTML = '<span>Tempo estimado</span><strong>Calculando perfis de render...</strong>';
  const options = {
    mode: state.mode,
    codec: $('#codecSelect')?.value || 'hevc',
    gpu: $('#gpuToggle')?.checked || false,
    qualityBoost: qualityBoostToggle ? qualityBoostToggle.checked : true,
    smartVisualDirector: smartVisualDirectorToggle ? smartVisualDirectorToggle.checked : true,
    continuityMatch: false,
    continuityOutliersOnly: true,
    audioMastering: audioMasteringToggle ? audioMasteringToggle.checked : true,
    autoSoundFx: autoSoundFxToggle ? autoSoundFxToggle.checked : true,
    allowAudioTrim: allowAudioTrimToggle ? allowAudioTrimToggle.checked : true,
    trimSilence: trimSilenceToggle ? trimSilenceToggle.checked : true,
    dualExportShorts: dualExportShortsToggle ? dualExportShortsToggle.checked : false,
    autoThumbnails: autoThumbnailsToggle ? autoThumbnailsToggle.checked : true,
    zoom: $('#zoomSelect')?.value || 'off',
    transitions: $('#transitionSelect')?.value || 'off',
    renderBudgetEnabled: Boolean(state.renderBudgetEnabled),
    renderBudgetTurboMultiplier: 1.35,
    renderBudgetEfficientMultiplier: 2.7,
  };
  try{
    const response = await fetch('/api/render-estimate', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({durationSeconds: duration, options}),
      cache: 'no-store',
    });
    if(!response.ok) throw new Error(await response.text());
    const payload = await response.json();
    if(token !== state.renderEstimateToken) return;
    state.renderEstimate = payload;
    const selected = state.renderPriority === 'max'
      ? payload.max
      : (state.renderPriority === 'quality' ? (payload.quality || payload.balanced) : payload.balanced);
    const hardwareLabel = selected.hardware_acceleration && selected.hardware_acceleration !== 'CPU'
      ? ` - ${selected.hardware_acceleration}`
      : '';
    const calibration = selected.history_samples ? ' - calibrado neste PC' : '';
    renderTimeEstimate.classList.toggle('turbo', state.renderPriority === 'max');
    const budgetEnabled = selected.budget_enabled !== false;
    if(budgetEnabled && selected.budget_feasible === false){
      renderTimeEstimate.innerHTML = `
        <span>Orçamento para ${formatTime(duration)}</span>
        <strong>${selected.label}: hardware insuficiente</strong>
        <small>Mínimo ${formatTime(selected.minimum_required_seconds || 0)} - limite ${formatTime(selected.budget_seconds || 0)}</small>`;
      return;
    }
    const riskLabel = selected.budget_risk === 'high'
      ? ' · risco de ultrapassar'
      : selected.budget_risk === 'attention'
        ? ' · margem curta'
        : '';
    const budgetLabel = budgetEnabled
      ? `limite ${formatTime(selected.budget_seconds || 0)}${riskLabel}`
      : 'proteção de tempo desativada';
    renderTimeEstimate.innerHTML = `
      <span>Estimativa para ${formatTime(duration)}</span>
      <strong>${selected.label}: ${estimateRangeText(selected)}</strong>
      <small>Inclui análise, clipes, FX, CTA/legendas e mux · ${budgetLabel}${hardwareLabel}${calibration}</small>`;
  }catch(_){
    if(token !== state.renderEstimateToken) return;
    renderTimeEstimate.innerHTML = '<span>Tempo estimado</span><strong>Não foi possível calcular agora</strong>';
  }
}

function applyUiMode(){
  const valid = new Set(['simple', 'advanced']);
  if(!valid.has(state.uiMode)){
    state.uiMode = 'simple';
    localStorage.setItem('glide_ui_mode', state.uiMode);
  }
  document.body.dataset.uiMode = state.uiMode;
  if(uiModeSelect) uiModeSelect.value = state.uiMode;
  if(dockSummary && state.uiMode === 'simple'){
    dockSummary.textContent = 'Modo simples: controles avancados ficam guardados, mas continuam preservados.';
  }
}

function applySidebarState(){
  document.body.classList.toggle('sidebar-collapsed', state.sidebarCollapsed);
  if(!sidebarToggle) return;
  sidebarToggle.setAttribute('aria-expanded', String(!state.sidebarCollapsed));
  sidebarToggle.setAttribute('aria-label', state.sidebarCollapsed ? 'Expandir menu lateral' : 'Recolher menu lateral');
  sidebarToggle.title = state.sidebarCollapsed ? 'Expandir menu lateral' : 'Recolher menu lateral';
}

function exportBitrateFor(profile, mode, codec){
  const preset = exportBitratePresets[profile] || exportBitratePresets.capcut_compact;
  const codecKey = codec === 'h264' ? 'h264' : 'hevc';
  const modeKey = mode === 'fast' ? 'fast' : 'standard';
  return preset[codecKey][modeKey];
}

function refreshExportProfileUi(){
  if(!exportProfileSelect || !videoBitrateInput) return;
  const profile = exportProfileSelect.value || 'capcut_compact';
  const codecSelect = $('#codecSelect');
  if(profile === 'compatibility' && codecSelect && codecSelect.value !== 'h264'){
    codecSelect.value = 'h264';
  }
  const codec = codecSelect?.value || 'hevc';
  const bitrate = exportBitrateFor(profile, state.mode, codec);
  const custom = profile === 'custom';
  if(!custom) videoBitrateInput.value = String(bitrate);
  videoBitrateInput.disabled = !custom;
  if(bitrateField) bitrateField.classList.toggle('locked', !custom);
  const modeText = state.mode === 'fast' ? '720p' : '1080p';
  const codecText = codec === 'h264' ? 'H.264' : 'HEVC';
  const target = Number(videoBitrateInput.value || bitrate);
  if(bitrateHint){
    bitrateHint.textContent = custom
      ? `Personalizado: ${target} kbps em VBR. Use HEVC para economizar mais tamanho.`
      : `${modeText} ${codecText}: ${target} kbps em VBR para upload mais leve.`;
  }
}

function refreshFinalOutputUi(){
  if(!finalOutputMode) return;
  state.finalOutputMode = finalOutputMode.value || 'downloads';
  state.finalOutputFolder = finalOutputFolder?.value || '';
  if(finalOutputFolder){
    const custom = state.finalOutputMode === 'custom';
    finalOutputFolder.disabled = !custom;
    finalOutputFolder.closest('label')?.classList.toggle('locked', !custom);
  }
  if(finalOutputHint){
    const downloads = state.runtimeConfig?.output?.downloadsFolder || 'Downloads';
    if(state.finalOutputMode === 'custom'){
      finalOutputHint.textContent = state.finalOutputFolder
        ? `O MP4 final sera copiado para: ${state.finalOutputFolder}`
        : 'Informe a pasta local onde o MP4 final deve aparecer.';
    }else if(state.finalOutputMode === 'browser_download'){
      finalOutputHint.textContent = 'O navegador fará o download automático para a pasta padrão dele.';
    }else{
      finalOutputHint.textContent = `Padrão: o MP4 final aparece em Downloads (${downloads}).`;
    }
  }
}

function backgroundVolumeValue(){
  const preset = backgroundVolumePreset?.value || 'immersive';
  if(preset !== 'custom') return backgroundVolumePresets[preset] ?? -22;
  const value = Number(backgroundVolumeDb?.value || -25);
  return Math.max(-45, Math.min(-12, Number.isFinite(value) ? value : -25));
}

function refreshBackgroundMusicUi(){
  if(!backgroundVolumePreset || !backgroundVolumeDb) return;
  const preset = backgroundVolumePreset.value || 'immersive';
  const custom = preset === 'custom';
  if(!custom) backgroundVolumeDb.value = String(backgroundVolumeValue());
  backgroundVolumeDb.disabled = !custom;
  if(backgroundVolumeField) backgroundVolumeField.classList.toggle('locked', !custom);
  updateBackgroundSummary();
}

function musicGenreLabel(key = state.musicGenre){
  return key === 'ambient' ? 'Ambiente' : 'Cinematic';
}

function presetMusicInfo(key = state.musicGenre){
  return (state.presetMusic.genres || []).find(item => item.key === key) || {key, label: musicGenreLabel(key), count: 0, size: 0};
}

function renderMusicLibraryShelf(){
  if(!musicLibraryShelf) return;
  const genres = state.presetMusic.genres || [];
  if(!genres.length){
    musicLibraryShelf.innerHTML = '<div class="music-store-empty">Nenhuma biblioteca local encontrada ainda.</div>';
    return;
  }
  musicLibraryShelf.innerHTML = genres.map(info => {
    const active = info.key === state.musicGenre;
    const samples = (info.samples || []).slice(0, 4).map(name => `<span>${escapeHtml(name)}</span>`).join('');
    const roots = (info.roots || []).filter(root => root.exists && root.count).map(root => root.kind === 'app' ? 'App' : 'PC').join(' + ') || 'Local';
    return `
      <button type="button" class="music-store-card ${active ? 'active' : ''}" data-music-genre-card="${escapeHtml(info.key)}">
        <span class="music-store-top">
          <b>${escapeHtml(info.label || musicGenreLabel(info.key))}</b>
          <em>${active ? 'Selecionada' : 'Biblioteca'}</em>
        </span>
        <span class="music-store-meta">${info.count || 0} faixa(s) - ${formatSize(info.size || 0)} - ${escapeHtml(roots)}</span>
        <span class="music-store-samples">${samples || '<span>Sem faixas locais</span>'}</span>
      </button>
    `;
  }).join('');
}

function updateMusicGenreUi(){
  if(musicGenreSwitch){
    musicGenreSwitch.querySelectorAll('[data-music-genre]').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.musicGenre === state.musicGenre);
    });
  }
  const info = presetMusicInfo();
  if(presetMusicStatus){
    if(info.count){
      presetMusicStatus.textContent = state.backgroundTracks.length
        ? `Biblioteca ${musicGenreLabel()} pausada: você importou música manual, então o render usará somente essa timeline.`
        : `Biblioteca ${musicGenreLabel()}: ${info.count} faixa(s) locais. Se a timeline estiver vazia, o render sorteia e mixa automaticamente.`;
    }else{
      presetMusicStatus.textContent = `Biblioteca ${musicGenreLabel()} ainda sem faixas locais. Adicione músicas manuais ou use Cinematic.`;
    }
  }
  renderMusicLibraryShelf();
  updateBackgroundSummary();
  renderProjectChecks();
}

function setMusicGenre(nextGenre){
  state.musicGenre = nextGenre === 'ambient' ? 'ambient' : 'cinematic';
  localStorage.setItem('glide_music_genre', state.musicGenre);
  state.backgroundListSignature = '';
  updateMusicGenreUi();
  renderLists();
  updateStats();
  captureActiveProject();
  renderProjectQueue();
  recordLearningEvent('reorder_clip', {kind: key, order});
}

async function loadPresetMusicStatus(){
  try{
    const response = await fetch('/api/preset-music', {cache: 'no-store'});
    if(!response.ok) throw new Error(await response.text());
    state.presetMusic = await response.json();
  }catch(e){
    state.presetMusic = {genres: []};
  }
  updateMusicGenreUi();
}

async function loadRuntimeConfig(){
  try{
    if(window.GlideRuntime?.loadConfig) state.runtimeConfig = await window.GlideRuntime.loadConfig();
    else{
      const response = await fetch('/api/config', {cache: 'no-store'});
      if(response.ok) state.runtimeConfig = await response.json();
    }
    applyRuntimeConfig(state.runtimeConfig);
  }catch(_e){
    state.runtimeConfig = null;
  }
}

function warmBackendCache(){
  const startWarm = () => {
    if(state.renderActive || state.queueRendering) return;
    if(window.GlideRuntime?.warmCache) window.GlideRuntime.warmCache();
    else fetch('/api/warm-cache', {method: 'POST', cache: 'no-store'}).catch(() => {});
  };
  if('requestIdleCallback' in window) window.requestIdleCallback(startWarm, {timeout: 12000});
  else window.setTimeout(startWarm, 8000);
}

function updateBackgroundSummary(){
  if(!backgroundSummary) return;
  const total = state.backgroundTracks.reduce((sum, file) => sum + (state.durations.get(rel(file)) || 0), 0);
  const volume = backgroundVolumeValue();
  if(!state.backgroundTracks.length){
    const info = presetMusicInfo();
    backgroundSummary.textContent = info.count
      ? `Automática: biblioteca ${musicGenreLabel()} com ${info.count} faixa(s). O render sorteia, corta, reparte faixas longas e aplica fades até cobrir a narração. Base ${volume} dB + ducking; no Imersivo as pausas podem respirar até -13.5 dB sem subir abrupto. Gêneros nunca se misturam.`
      : `Sem música manual e sem biblioteca ${musicGenreLabel()} encontrada. Use Cinematic ou adicione músicas de fundo.`;
    return;
  }
  backgroundSummary.textContent = `${state.backgroundTracks.length} música(s) manual(is), ${formatTime(total)} no total. Biblioteca automática pausada neste render; o app usa somente as faixas importadas, com fades, cortes e ducking em base ${volume} dB.`;
}

function aggregateAudioHealth(){
  const items = state.audios.map(file => state.audioHealth.get(rel(file))).filter(Boolean);
  if(!state.audios.length) return {state: 'bad', text: 'Adicione a narração.'};
  if(!items.length) return {state: 'warn', text: 'Analisando lacunas da narração...'};
  const problem = items.find(item => item.status === 'problem');
  const warn = items.find(item => item.status === 'warn' || item.status === 'unknown');
  const longest = Math.max(...items.map(item => item.longestSilence || 0), 0);
  const ratio = Math.max(...items.map(item => item.silenceRatio || 0), 0);
  if(problem) return {state: 'warn', text: `${problem.message}. Maior pausa ${longest.toFixed(1)}s; silêncio ${(ratio * 100).toFixed(0)}%.`};
  if(warn) return {state: 'warn', text: `${warn.message}. O backend confirma antes do render.`};
  return {state: 'ok', text: `Saudável. Maior pausa ${longest.toFixed(1)}s.`};
}

function projectChecks(){
  const audioTotal = state.audios.reduce((sum, file) => sum + (state.durations.get(rel(file)) || 0), 0);
  const videoTotal = state.videos.reduce((sum, file) => sum + (state.durations.get(rel(file)) || 0), 0);
  const invalidVideos = state.videos.filter(file => videoStatusOf(file).kind === 'invalid').length;
  const noPreviewVideos = state.videos.filter(file => videoStatusOf(file).kind === 'no_preview').length;
  const checkingVideos = state.videos.filter(file => ['pending', 'checking', 'metadata_ok'].includes(videoStatusOf(file).kind)).length;
  const profile = exportProfileSelect?.value || 'capcut_compact';
  const codec = $('#codecSelect')?.value || 'hevc';
  const bitrate = Number(videoBitrateInput?.value || exportBitrateFor(profile, state.mode, codec));
  const estimatedMb = audioTotal > 0 ? Math.max(1, Math.round((bitrate * audioTotal / 8) / 1024 + audioTotal * 0.02)) : 0;
  const cta = selectedCtaAsset();
  const audioHealth = aggregateAudioHealth();
  const missingRequiredSrt = !state.subtitles.length;
  const introUsesFadeOnly = introModeSelect?.value === 'cinematic' && missingRequiredSrt;
  return [
    {
      state: state.videos.length ? (invalidVideos ? 'warn' : 'ok') : 'bad',
      title: 'Mídia Visual',
      text: state.videos.length
        ? `${state.videos.length} arquivo(s) de mídia. ${invalidVideos ? `${invalidVideos} suspeito(s) podem ser pulados.` : 'Lista pronta.'}`
        : 'Adicione vídeos ou imagens.',
    },
    {
      state: state.audios.length && audioTotal > 0 ? audioHealth.state : 'bad',
      title: 'Narração',
      text: state.audios.length ? `${state.audios.length} áudio(s), ${formatTime(audioTotal)}. ${audioHealth.text}` : 'Adicione a narração.',
    },
    {
      state: introModeSelect?.value === 'cinematic' ? 'ok' : 'neutral',
      title: 'Abertura',
      text: introModeSelect?.value === 'cinematic'
        ? (introUsesFadeOnly ? 'Abertura cinematográfica seguirá com fade-in, sem Texto inicial.' : 'Cinemática contextual: música primeiro, voz em cerca de 4s e Texto apenas quando houver gancho forte.')
        : 'Padrão: fade in simples no início.',
    },
    {
      state: cta ? 'ok' : 'bad',
      title: 'CTA',
      text: cta ? `${ctaLabel(cta)} selecionado, posição ajustável no preview.` : 'Escolha um CTA obrigatório.',
    },
    {
      state: state.subtitles.length ? 'ok' : 'bad',
      title: 'Textos',
      text: state.subtitles.length
        ? `${state.subtitleInfo?.valid || 0} Texto(s) válido(s).`
        : 'Textos obrigatórios para entrar na fila de render.',
    },
    {
      state: state.captions.length ? 'ok' : 'neutral',
      title: 'Legendas',
      text: state.captions.length
        ? `${state.captionInfo?.valid || 0} legenda(s) opcional(is), limpas e sem FX.`
        : 'Opcionais. Adicione um SRT separado para leitura contínua.',
    },
    {
      state: state.backgroundTracks.length || presetMusicInfo().count ? 'ok' : 'warn',
      title: 'Música',
      text: state.backgroundTracks.length
        ? `${state.backgroundTracks.length} faixa(s) manual(is), com ducking profissional automático.`
        : presetMusicInfo().count
          ? `Automática: biblioteca ${musicGenreLabel()} será sorteada no render.`
          : `Nenhuma faixa manual e biblioteca ${musicGenreLabel()} vazia.`,
    },
    {
      state: 'ok',
      title: 'Tom',
      text: `${projectToneSelect?.selectedOptions?.[0]?.textContent || 'Automático'}; músicas e FX ponderados por emoção do projeto.`,
    },
    {
      state: 'ok',
      title: 'Ducking profissional',
      text: 'Música sobe suavemente nas pausas e recua com voz/CTA, sem saltos de volume.',
    },
    {
      state: 'ok',
      title: 'Ritmo dos Textos',
      text: 'Ênfases e variações seguem o contexto sem alterar a duração da narração.',
    },
    {
      state: renderRecoveryToggle?.checked ? 'ok' : 'neutral',
      title: 'Recuperação',
      text: renderRecoveryToggle?.checked
        ? 'Se falhar, tenta pular clipe suspeito, H.264 e CPU antes de marcar erro.'
        : 'Falhas param no primeiro erro do FFmpeg.',
    },
    {
      state: state.renderPriority === 'max' ? 'warn' : 'ok',
      title: 'Modo render',
      text: state.renderPriority === 'max'
        ? 'Turbo Produção global: toda a fila preserva resolução, bitrate, Textos, Legendas, CTA e áudio; filtros caros ficam suspensos.'
        : 'Eficiente global: toda a fila preserva os recursos completos com intermediários rápidos e composição final otimizada.',
    },
    {
      state: checkingVideos ? 'warn' : 'ok',
      title: 'Preview',
      text: checkingVideos
        ? `${checkingVideos} clip(s) ainda em análise. Pode renderizar; o FFmpeg confirma no backend.`
        : noPreviewVideos ? `${noPreviewVideos} sem preview visual, mas o render tentara usar FFmpeg.` : 'Thumbs/status atualizados.',
    },
    {
      state: 'ok',
      title: 'Filtro visual',
      text: adaptiveVisualFilterToggle?.checked && state.renderPriority !== 'max' && smartVisualDirectorToggle?.checked
        ? 'Adaptativo: Rigoroso no início, Normal no meio e Leve no final; imagens sempre rigorosas.'
        : `${visualFilterLevelLabel(visualFilterLevelSelect?.value)} em todo o vídeo; imagens sempre rigorosas.`,
    },
    {
      state: smartVisualDirectorToggle?.checked ? (state.renderPriority === 'max' ? 'warn' : 'ok') : 'neutral',
      title: 'Diretor visual',
      text: smartVisualDirectorToggle?.checked
        ? (state.renderPriority === 'max'
          ? 'Marcado, mas suspenso no Turbo para preservar velocidade máxima.'
          : 'Ativo: usa Textos, nomes, categorias e numeração como pistas para ordenar sem reconstruir tudo.')
        : 'Desligado: a timeline segue a ordem atual do projeto.',
    },
    {
      state: 'ok',
      title: 'Exportação',
      text: `${exportBitratePresets[profile]?.label || 'Personalizado'} em ${codec.toUpperCase()}. ${estimatedMb ? `Estimativa: ~${estimatedMb} MB.` : 'Estimativa aparece após ler o áudio.'}`,
    },
    {
      state: qualityBoostToggle?.checked ? 'ok' : 'neutral',
      title: 'Qualidade',
      text: `${qualityBoostToggle?.checked ? 'Quality Boost ligado' : 'Quality Boost desligado'}; voz ${voiceNormalizeToggle?.checked ? 'nivelada' : 'sem nivelamento'}.`,
    },
    {
      state: autoSoundFxToggle?.checked ? 'ok' : 'neutral',
      title: 'Sound FX',
      text: autoSoundFxToggle?.checked
        ? 'Automático: Textos animados e a abertura cinematográfica recebem efeitos sincronizados. Legendas permanecem limpas e sem FX.'
        : 'Desligado: render sem efeitos sonoros automáticos.',
    },
    {
      state: 'ok',
      title: 'Entregáveis & Automações',
      text: `Miniaturas HD: ${autoThumbnailsToggle?.checked ? '3 automáticas' : 'desligado'} | Cadência: ${trimSilenceToggle?.checked ? 'silêncios mortos compactados' : 'original'} | Formato: ${dualExportShortsToggle?.checked ? 'Master 16:9 + Shorts 9:16' : '16:9 único'}.`,
    },
  ];
}

function renderProjectChecks(){
  if(!preflightGrid) return;
  const checks = projectChecks();
  const signature = checks.map(item => `${item.state}:${item.title}:${item.text}`).join('|');
  if(signature === state.projectChecksSignature) return;
  state.projectChecksSignature = signature;
  preflightGrid.innerHTML = checks.map(item => `
    <div class="preflight-item ${item.state}">
      <strong>${escapeHtml(item.title)}</strong>
      <span>${escapeHtml(item.text)}</span>
    </div>
  `).join('');
}

function renderAutoFixPlan(payload = state.backendPreflight){
  if(!autoFixPlanBox) return;
  const plan = payload?.auto_fix_plan;
  const tone = payload?.emotion_summary;
  const actions = Array.isArray(plan?.actions) ? plan.actions : [];
  if(!actions.length){
    autoFixPlanBox.innerHTML = 'Sem correções automáticas pendentes. O projeto está coerente para o render.';
    return;
  }
  const top = actions.slice(0, 5).map(item => `<span><strong>${escapeHtml(item.label || item.action)}</strong>: ${escapeHtml(item.reason || '')}</span>`).join('<br>');
  const toneText = tone?.tone ? `<br><span><strong>Tom detectado:</strong> ${escapeHtml(tone.tone)}${tone.mode === 'manual' ? ' manual' : ''}</span>` : '';
  autoFixPlanBox.innerHTML = `${top}${actions.length > 5 ? `<br><span>+${actions.length - 5} ajuste(s) menores.</span>` : ''}${toneText}`;
}

function ctaLabel(asset){
  const labels = {
    pt: 'Português',
    en: 'English',
    es: 'Español',
    fr: 'Français',
    ru: 'Russo',
    de: 'Alemão',
    it: 'Italiano',
    pl: 'Polonês',
  };
  return labels[asset.key] || asset.label || asset.key;
}

function renderCtaAssets(){
  if(!ctaGrid) return;
  if(!state.ctaAssets.length){
    ctaGrid.innerHTML = '<div class="empty">Nenhum CTA local encontrado.</div>';
    return;
  }
  ctaGrid.innerHTML = '';
  const frag = document.createDocumentFragment();
  state.ctaAssets.forEach(asset => {
    const card = document.createElement('button');
    const selected = asset.key === state.selectedCta;
    card.type = 'button';
    card.className = `cta-card${selected ? ' active' : ''}${asset.available ? '' : ' disabled'}`;
    card.dataset.cta = asset.key;
    card.disabled = !asset.available;
    const audioBadge = asset.has_audio ? 'com som' : 'sem som';
    const sourceBadge = 'oficial';
    card.innerHTML = `
      <span class="cta-lang">${escapeHtml(ctaLabel(asset))}</span>
      <span class="cta-meta">${escapeHtml(sourceBadge)} - ${escapeHtml(audioBadge)}</span>
      <span class="cta-time">${formatTime(asset.duration || 0)} - 2x no vídeo</span>
    `;
    frag.appendChild(card);
  });
  ctaGrid.appendChild(frag);
  updateCtaStatus();
  updateCtaPreview();
}

function updateCtaStatus(){
  if(!ctaStatus) return;
  const asset = state.ctaAssets.find(item => item.key === state.selectedCta);
  if(!asset){
    ctaStatus.textContent = 'Obrigatório: escolha um CTA antes de renderizar. Ajuste a posição no preview para não cobrir as legendas.';
    return;
  }
  const audio = asset.has_audio ? 'com som preservado' : 'sem som';
  ctaStatus.textContent = `${ctaLabel(asset)} selecionado (asset oficial, ${audio}). Será aplicado no início e no final com a posição do preview.`;
}

function selectedCtaAsset(){
  return state.ctaAssets.find(item => item.key === state.selectedCta) || null;
}

function ctaAnchor(preset){
  return {
    top_left: {left: 4, top: 6, tx: 0, ty: 0},
    top_center: {left: 50, top: 6, tx: -50, ty: 0},
    top_right: {left: 96, top: 6, tx: -100, ty: 0},
    middle_left: {left: 4, top: 50, tx: 0, ty: -50},
    center: {left: 50, top: 50, tx: -50, ty: -50},
    middle_right: {left: 96, top: 50, tx: -100, ty: -50},
    bottom_left: {left: 4, top: 92, tx: 0, ty: -100},
    bottom_center: {left: 50, top: 92, tx: -50, ty: -100},
    bottom_right: {left: 96, top: 92, tx: -100, ty: -100},
  }[preset] || {left: 96, top: 6, tx: -100, ty: 0};
}

function updateCtaControlVisuals(){
  if(ctaPositionPreset) ctaPositionPreset.value = state.ctaPositionPreset;
  if(ctaOffsetX) ctaOffsetX.value = String(state.ctaOffsetX);
  if(ctaOffsetY) ctaOffsetY.value = String(state.ctaOffsetY);
  if(ctaOffsetXValue) ctaOffsetXValue.textContent = `${state.ctaOffsetX}%`;
  if(ctaOffsetYValue) ctaOffsetYValue.textContent = `${state.ctaOffsetY}%`;
}

function updateCtaPreview(){
  if(!ctaPreviewStage || !ctaPreviewVideo) return;
  const asset = selectedCtaAsset();
  const ratio = $('#ratioSelect')?.value || '16:9';
  ctaPreviewStage.dataset.ratio = ratio;
  const firstVideo = state.videos[0];
  const thumb = firstVideo ? state.thumbs.get(rel(firstVideo)) : null;
  if(ctaPreviewMedia){
    if(thumb){
      ctaPreviewMedia.style.backgroundImage = `url("${thumb}")`;
      ctaPreviewMedia.classList.add('has-thumb');
    }else{
      ctaPreviewMedia.style.backgroundImage = '';
      ctaPreviewMedia.classList.remove('has-thumb');
    }
  }

  if(asset){
    const nextSrc = `${asset.preview || `/api/cta-preview/${asset.key}`}?v=${state.version}`;
    if(!ctaPreviewVideo.src.endsWith(nextSrc)) ctaPreviewVideo.src = nextSrc;
    ctaPreviewVideo.classList.remove('hidden');
    ctaPreviewVideo.muted = !state.ctaPreviewSound;
    ctaPreviewVideo.play().catch(() => {});
  }else{
    ctaPreviewVideo.removeAttribute('src');
    ctaPreviewVideo.classList.add('hidden');
  }

  const width = ratio === '9:16' ? 68 : 42;
  const anchor = ctaAnchor(state.ctaPositionPreset);
  ctaPreviewVideo.style.width = `${width}%`;
  ctaPreviewVideo.style.left = `${anchor.left + state.ctaOffsetX}%`;
  ctaPreviewVideo.style.top = `${anchor.top + state.ctaOffsetY}%`;
  ctaPreviewVideo.style.transform = `translate(${anchor.tx}%, ${anchor.ty}%)`;

  if(ctaPreviewCaption){
    const style = currentSubtitleStyle();
    const preset = subtitlePresets[subtitlePreset.value] || subtitlePresets.bold_white;
    ctaPreviewCaption.textContent = previewCaption?.textContent || 'Sua legenda aparece aqui';
    ctaPreviewCaption.style.color = style.primary;
    ctaPreviewCaption.style.fontSize = `${Math.max(18, Math.round(style.size * 0.44))}px`;
    ctaPreviewCaption.style.bottom = `${style.position}%`;
    ctaPreviewCaption.style.fontFamily = `"${style.font}", Arial, sans-serif`;
    ctaPreviewCaption.style.fontWeight = String(preset.weight);
    const outlinePx = Math.max(1, style.outlineSize);
    ctaPreviewCaption.style.textShadow = `0 ${outlinePx}px 0 ${style.outline}, 0 0 ${Math.round(outlinePx * 7)}px ${style.outline}`;
    ctaPreviewCaption.classList.toggle('caption-box', Boolean(style.box));
  }

  if(ctaPreviewSoundBtn){
    const canHear = Boolean(asset?.has_audio);
    ctaPreviewSoundBtn.disabled = !canHear;
    ctaPreviewSoundBtn.classList.toggle('hidden', !canHear);
    ctaPreviewSoundBtn.textContent = state.ctaPreviewSound ? 'Silenciar CTA' : 'Ouvir CTA';
  }
  updateCtaControlVisuals();
}

async function loadCtaAssets(){
  if(!ctaGrid) return;
  try{
    const response = await fetch('/api/cta-assets', {cache: 'no-store'});
    if(!response.ok) throw new Error(await response.text());
    const payload = await response.json();
    state.ctaAssets = payload.items || [];
    if(state.selectedCta && !state.ctaAssets.some(asset => asset.key === state.selectedCta && asset.available)){
      state.selectedCta = '';
      localStorage.removeItem('glide_cta_language');
    }
    renderCtaAssets();
    updateStats();
  }catch(error){
    ctaGrid.innerHTML = '<div class="empty">Não foi possível carregar os CTAs locais.</div>';
    if(ctaStatus) ctaStatus.textContent = error.message || 'Erro ao carregar CTAs.';
  }
}

function addUniqueFile(file, forcedKind = null){
  const kind = kindOfFile(file, forcedKind);
  if(!kind) return {added: false, kind: null, reason: 'unsupported'};
  const key = fileKey(file, kind);
  if(state.registry.has(key)) return {added: false, kind, reason: 'duplicate'};
  state.registry.set(key, file);
  if(kind === 'video' || kind === 'image') state.videos.push(file);
  if(kind === 'audio') state.audios.push(file);
  if(kind === 'background_music') state.backgroundTracks.push(file);
  if(kind === 'subtitle'){
    state.subtitles.forEach(oldFile => {
      for(const [oldKey, registered] of state.registry.entries()){
        if(registered === oldFile) state.registry.delete(oldKey);
      }
    });
    state.subtitles = [file];
  }
  if(kind === 'caption_srt'){
    state.captions.forEach(oldFile => {
      for(const [oldKey, registered] of state.registry.entries()){
        if(registered === oldFile) state.registry.delete(oldKey);
      }
    });
    state.captions = [file];
  }
  if(kind === 'script_guide'){
    state.scriptGuides.forEach(oldFile => {
      for(const [oldKey, registered] of state.registry.entries()){
        if(registered === oldFile) state.registry.delete(oldKey);
      }
    });
    state.scriptGuides = [file];
    state.scriptGuideInfo = null;
    state.scriptGuidePlan = null;
  }
  return {added: true, kind};
}

async function persistImportedMedia(projectId, entries){
  if(!projectId || !entries?.length) return {saved: 0, failed: 0};
  let saved = 0;
  let failed = 0;
  const poolSize = entries.length > 40 ? 4 : entries.length > 12 ? 3 : 2;
  await runPool(entries, poolSize, async ({file, kind}) => {
    if(file?._persisted) return;
    const fd = new FormData();
    fd.append('file', file, rel(file));
    fd.append('rel', rel(file));
    fd.append('kind', kind || kindOfFile(file) || 'file');
    fd.append('duration', String(state.durations.get(rel(file)) || 0));
    try{
      const response = await fetch(`/api/queue/projects/${encodeURIComponent(projectId)}/media-file`, {
        method: 'POST',
        body: fd,
        cache: 'no-store',
      });
      if(!response.ok) throw new Error(await response.text());
      const persisted = await response.json();
      file._persisted = true;
      file._persistedProjectId = persisted.persistedProjectId || projectId;
      file._persistedStoredFile = persisted.persistedStoredFile || '';
      file._serverRel = persisted.rel || rel(file);
      saved++;
    }catch(_){
      failed++;
    }
  });
  return {saved, failed};
}

function scheduleImportedMediaFinalization(context){
  window.setTimeout(() => {
    finalizeImportedMedia(context).catch((error) => {
      console.warn('Finalizacao leve de importacao falhou', error);
      if(dockSummary) dockSummary.textContent += ' Análise leve será retomada no render.';
    });
  }, 0);
}

async function finalizeImportedMedia({projectId, token, entries, unsupported = 0}){
  if(!projectId || !entries?.length) return;
  const sameProject = () => token === state.mediaAnalysisToken && projectId === state.activeProjectId;
  const persistencePromise = persistImportedMedia(projectId, entries);
  const imageEntries = entries.filter(item => item.kind === 'image');
  imageEntries.forEach(({file}) => {
    const r = rel(file);
    if(!state.durations.has(r)) state.durations.set(r, 4);
    state.durationSources.set(r, 'image_default');
    if(!state.thumbs.has(r)){
      try{
        state.thumbs.set(r, URL.createObjectURL(file));
      }catch(_){}
    }
    setVideoStatus(file, 'image', 'Imagem pronta. Ritmo saudável (3-5s), Ken Burns suave e Background Blur.');
  });
  const needsDuration = entries.filter(({file}) => !state.durations.has(rel(file)));
  const durationJobs = [
    ...needsDuration.filter(item => item.kind !== 'video' && item.kind !== 'image'),
    ...needsDuration.filter(item => item.kind === 'video').slice(0, IMPORT_DURATION_SCAN_LIMIT),
  ];

  await runPool(durationJobs, DURATION_POOL, async ({file, kind}) => {
    if(!sameProject()) return;
    const r = rel(file);
    if(state.durations.has(r)) return;
    const durationInfo = await durationOf(file);
    const duration = durationInfo.seconds || 0;
    state.durations.set(r, duration);
    state.durationSources.set(r, durationInfo.source || 'metadata');
    if(kind === 'video'){
      if(duration <= 0.08){
        setVideoStatus(file, 'no_preview', 'Duração não confirmada no navegador. FFmpeg confirma no render.');
      }else if(durationInfo.source === 'filename'){
        setVideoStatus(file, 'metadata_ok', 'Duração estimada pelo nome. FFmpeg confirma no render.');
      }else if(!state.thumbs.has(r)){
        setVideoStatus(file, 'metadata_ok', 'Duração OK. Preview econômico em segundo plano.');
      }
    }
  });

  const audioJobs = entries.filter(item => item.kind === 'audio').map(item => item.file).slice(0, IMPORT_AUDIO_HEALTH_LIMIT);
  await runPool(audioJobs, 1, async (file) => {
    if(!sameProject()) return;
    const r = rel(file);
    if(state.audioHealth.has(r)) return;
    state.audioHealth.set(r, {status: 'unknown', message: 'Análise completa será feita no render.', longestSilence: 0, silenceRatio: 0});
    const health = await analyzeAudioFileHealth(file, 'audio');
    if(health) state.audioHealth.set(r, health);
  });

  const videoFilesForThumbs = entries.filter(item => item.kind === 'video').map(item => item.file);
  const thumbJobs = videoFilesForThumbs.slice(0, THUMB_LIMIT);
  await runPool(thumbJobs, THUMB_POOL, async (file) => {
    if(!sameProject() || state.renderActive || state.queueRendering) return;
    const r = rel(file);
    if(state.thumbs.has(r)) return;
    const duration = state.durations.get(r) || secondsFromClipStamp(file.name) || 0;
    if(duration <= 0.08){
      setVideoStatus(file, 'no_preview', 'Preview adiado. FFmpeg confirma no render.');
      return;
    }
    const thumb = await thumbOf(file);
    if(thumb?.src){
      state.thumbs.set(r, thumb.src);
      if(file.size <= 0.22 * 1024 * 1024 && thumb.visible === false){
        setVideoStatus(file, 'invalid', 'Arquivo muito leve com preview preto. O render ira pular automaticamente.');
      }else{
        setVideoStatus(file, 'preview_ok', 'Preview pronto');
      }
    }else{
      setVideoStatus(file, 'no_preview', 'Sem preview no navegador. FFmpeg tentara no render.');
    }
  });

  videoFilesForThumbs.slice(THUMB_LIMIT).forEach(file => {
    if(!sameProject()) return;
    const r = rel(file);
    if(!state.thumbs.has(r)) setVideoStatus(file, 'no_preview', 'Preview economizado para manter o editor leve.');
  });

  if(!sameProject()) return;
  if(entries.some(item => item.kind === 'subtitle')) await refreshSubtitleInfo();
  if(entries.some(item => item.kind === 'caption_srt')) await refreshCaptionInfo();
  if(entries.some(item => item.kind === 'script_guide')) await refreshScriptGuideInfo();
  const persistence = await persistencePromise;
  renderLists();
  updateStats();
  captureActiveProject();
  renderProjectQueue();
  if(dockSummary){
    const parts = [];
    if(persistence.saved) parts.push(`${persistence.saved} arquivo(s) guardado(s) no projeto`);
    if(persistence.failed) parts.push(`${persistence.failed} arquivo(s) aguardam nova tentativa`);
    if(unsupported) parts.push(`${unsupported} ignorado(s)`);
    if(parts.length) dockSummary.textContent += ` ${parts.join('. ')}.`;
  }
}

async function ingestFiles(fileList, forcedKind = null){
  const list = Array.from(fileList || []);
  if(!list.length) return;
  const ingestProjectId = state.activeProjectId;
  const ingestToken = ++state.mediaAnalysisToken;

  const added = [];
  const addedEntries = [];
  let addedVideos = 0;
  let addedAudios = 0;
  let addedBackground = 0;
  let addedSubtitles = 0;
  let addedCaptions = 0;
  let addedScripts = 0;
  let skipped = 0;
  let unsupported = 0;

  for(const file of list){
    const perFileKind = typeof forcedKind === 'function' ? forcedKind(file) : forcedKind;
    const result = addUniqueFile(file, perFileKind);
    if(result.added){
      added.push(file);
      addedEntries.push({file, kind: result.kind});
      if(result.kind === 'video') addedVideos++;
      if(result.kind === 'image') addedVideos++;
      if(result.kind === 'audio') addedAudios++;
      if(result.kind === 'background_music') addedBackground++;
      if(result.kind === 'subtitle') addedSubtitles++;
      if(result.kind === 'caption_srt') addedCaptions++;
      if(result.kind === 'script_guide') addedScripts++;
      if(result.kind === 'image'){
        state.durations.set(rel(file), 4);
        state.durationSources.set(rel(file), 'image_default');
        try{ state.thumbs.set(rel(file), URL.createObjectURL(file)); }catch(_){}
        setVideoStatus(file, 'image', 'Imagem pronta. O render aplica fundo blur e movimento suave.');
      }
      if(result.kind === 'video'){
        const guessedDuration = secondsFromClipStamp(file.name);
        if(guessedDuration > 0){
          state.durations.set(rel(file), guessedDuration);
          state.durationSources.set(rel(file), 'filename');
          setVideoStatus(file, 'metadata_ok', 'Duração estimada pelo nome. Preview será carregado em segundo plano.');
        }else{
          setVideoStatus(file, 'checking', 'Arquivo recebido. Análise leve em segundo plano...');
        }
      }
    }else if(result.reason === 'duplicate'){
      skipped++;
    }else{
      unsupported++;
    }
  }

  if(addedVideos && !state.videoOrderEdited) state.videos.sort(naturalCompare);
  if(addedAudios && !state.audioOrderEdited) state.audios.sort(naturalCompare);
  if(addedBackground && !state.backgroundOrderEdited) state.backgroundTracks.sort(naturalCompare);

  if(!added.length){
    dockSummary.textContent = skipped
      ? 'Esses arquivos ja estavam carregados.'
      : 'Nenhum arquivo de vídeo ou áudio compatível foi encontrado.';
    renderLists();
    updateStats();
    return;
  }

  dockSummary.textContent = `Importados: +${addedVideos} vídeo(s), +${addedAudios} áudio(s), +${addedBackground} música(s), +${addedSubtitles} Textos, +${addedCaptions} Legendas, +${addedScripts} Roteiro(s).${addedBackground ? ' Biblioteca automática pausada para este projeto.' : ''}`;
  renderLists();
  if(addedBackground) updateMusicGenreUi();
  updateStats();
  captureActiveProject();
  renderProjectQueue();
  scheduleImportedMediaFinalization({projectId: ingestProjectId, token: ingestToken, entries: addedEntries, unsupported});
}

function parseSrtTime(value){
  const match = String(value).trim().match(/(\d+):(\d{2}):(\d{2})[,.](\d{1,3})/);
  if(!match) return null;
  const [, h, m, s, ms] = match;
  return Number(h) * 3600 + Number(m) * 60 + Number(s) + Number(ms.padEnd(3, '0')) / 1000;
}

function parseSrtText(text){
  const blocks = text.replace(/\r\n/g, '\n').replace(/\r/g, '\n').trim().split(/\n\s*\n/);
  const cues = [];
  for(const block of blocks){
    const lines = block.split('\n').map(line => line.trim()).filter(Boolean);
    const timeLine = lines.findIndex(line => line.includes('-->'));
    if(timeLine < 0) continue;
    const [startText, endText] = lines[timeLine].split('-->');
    const start = parseSrtTime(startText);
    const end = parseSrtTime((endText || '').split(/\s+/)[0]);
    const body = lines.slice(timeLine + 1).join(' ').replace(/<[^>]+>/g, '').trim();
    if(start == null || end == null || !body) continue;
    cues.push({start, end: Math.max(end, start), text: body});
  }
  return cues;
}

function estimateSubtitleCleanup(cues){
  const audioTotal = state.audios.reduce((sum, file) => sum + (state.durations.get(rel(file)) || 0), 0);
  const timeline = audioTotal || Number.POSITIVE_INFINITY;
  const adjusted = cues
    .filter(cue => cue.start < timeline)
    .map(cue => ({...cue, end: Math.min(timeline, Math.max(cue.end, cue.start + 6))}))
    .filter(cue => cue.end - cue.start >= 5.98)
    .sort((a, b) => a.start - b.start);
  let valid = 0;
  let removedOverlap = 0;
  let i = 0;
  while(i < adjusted.length){
    let cluster = [adjusted[i]];
    let end = adjusted[i].end;
    i++;
    while(i < adjusted.length && adjusted[i].start < end){
      cluster.push(adjusted[i]);
      end = Math.max(end, adjusted[i].end);
      i++;
    }
    valid++;
    removedOverlap += cluster.length - 1;
  }
  return {
    original: cues.length,
    valid,
    removed: Math.max(0, cues.length - valid),
    removedOverlap,
  };
}

async function refreshSubtitleInfo(){
  if(!state.subtitles.length){
    state.subtitleInfo = null;
    subtitleStatus.textContent = 'Adicione um SRT de Textos para orientar o Águia e criar chamadas animadas.';
    previewCaption.textContent = 'Seu texto animado aparece assim';
    updateIntroPreview();
    return;
  }
  const file = state.subtitles[0];
  const text = await file.text();
  const cues = parseSrtText(text);
  const info = estimateSubtitleCleanup(cues);
  state.subtitleInfo = info;
  const firstText = cues[0]?.text || 'Seu texto animado aparece assim';
  previewCaption.textContent = firstText.slice(0, 90);
  subtitleStatus.textContent = `${file.name}: ${info.valid} texto(s) válido(s), ${info.removed} removido(s) por tempo/sobreposição.`;
  updateSubtitlePreview();
  updateLayerPreview();
}

async function refreshCaptionInfo(){
  if(!state.captions.length){
    state.captionInfo = null;
    if(captionStatus) captionStatus.textContent = 'Adicione um SRT para legendas limpas em até duas linhas, sem FX sonoro.';
    if(layerPreviewCaption) layerPreviewCaption.textContent = 'Legenda limpa em até duas linhas';
    updateLayerPreview();
    return;
  }
  const file = state.captions[0];
  const cues = parseSrtText(await file.text());
  state.captionInfo = {original: cues.length, valid: cues.length, maxLines: 2};
  if(captionStatus) captionStatus.textContent = `${file.name}: ${cues.length} legenda(s) pronta(s), sem FX sonoro.`;
  if(layerPreviewCaption) layerPreviewCaption.textContent = (cues[0]?.text || 'Legenda limpa em até duas linhas').slice(0, 110);
  updateLayerPreview();
}

async function analyzeScriptGuideFile(file){
  const fd = new FormData();
  fd.append('file', file, file.name);
  fd.append('rel', rel(file));
  const response = await fetch('/api/script-guide/analyze', {
    method: 'POST',
    body: fd,
    cache: 'no-store',
  });
  if(!response.ok) throw new Error(await response.text());
  return response.json();
}

async function refreshScriptGuideInfo(){
  if(!state.scriptGuides.length){
    state.scriptGuideInfo = null;
    state.scriptGuidePlan = null;
    if(scriptGuideStatus) scriptGuideStatus.textContent = 'Opcional. Anexe TXT, DOCX, PDF ou HTML para orientar capítulos, rankings e cenas.';
    if(scriptGuideDetails) scriptGuideDetails.innerHTML = '<span>Nenhum roteiro anexado.</span>';
    return;
  }
  const file = state.scriptGuides[0];
  if(scriptGuideStatus) scriptGuideStatus.textContent = `Analisando roteiro: ${file.name}...`;
  try{
    let payload = null;
    if(file._persistedProjectId && file._serverRel){
      const response = await fetch(`/api/queue/projects/${encodeURIComponent(file._persistedProjectId)}/script-guide/analyze`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({rel: file._serverRel || rel(file)}),
        cache: 'no-store',
      });
      if(!response.ok) throw new Error(await response.text());
      payload = await response.json();
    }else{
      payload = await analyzeScriptGuideFile(file);
    }
    const plan = payload.plan || {};
    const summary = plan.summary || {};
    state.scriptGuidePlan = plan;
    state.scriptGuideInfo = payload.info || {
      name: file.name,
      rel: rel(file),
      format: ext(file),
      blocks: Number(summary.blocks || 0),
      confidence: Number(summary.avg_confidence || 0),
      warnings: plan.warnings || [],
      updatedAt: new Date().toISOString(),
    };
    if(scriptGuideStatus){
      scriptGuideStatus.textContent = `${file.name}: ${state.scriptGuideInfo.blocks || 0} bloco(s), confiança ${Math.round((state.scriptGuideInfo.confidence || 0) * 100)}%.`;
    }
    if(scriptGuideDetails){
      const warnings = (state.scriptGuideInfo.warnings || []).length ? ` · ${state.scriptGuideInfo.warnings[0]}` : '';
      scriptGuideDetails.innerHTML = `<span>Guia editorial ativo para Águia, pesquisa visual e CTA.${escapeHtml(warnings)}</span>`;
    }
  }catch(error){
    state.scriptGuideInfo = {name: file.name, rel: rel(file), format: ext(file), blocks: 0, confidence: 0, warnings: [error.message || String(error)]};
    state.scriptGuidePlan = null;
    if(scriptGuideStatus) scriptGuideStatus.textContent = `Roteiro não interpretado: ${error.message || error}`;
    if(scriptGuideDetails) scriptGuideDetails.innerHTML = '<span>O render continuará sem guia de roteiro.</span>';
  }
}

function renderScriptGuidePlan(){
  if(!scriptGuideModalBody) return;
  const plan = state.scriptGuidePlan || {};
  const blocks = Array.isArray(plan.blocks) ? plan.blocks : [];
  if(!blocks.length){
    scriptGuideModalBody.innerHTML = '<p class="queue-report-empty">Nenhuma interpretação disponível para este roteiro.</p>';
    return;
  }
  scriptGuideModalBody.innerHTML = `
    <div class="report-kpi-grid compact">
      <span><b>${Number(plan.summary?.blocks || blocks.length)}</b> blocos</span>
      <span><b>${Math.round(Number(plan.summary?.avg_confidence || 0) * 100)}%</b> confiança</span>
      <span><b>${plan.summary?.ranking_detected ? 'Sim' : 'Não'}</b> ranking</span>
      <span><b>${plan.summary?.cta_detected ? 'Sim' : 'Não'}</b> CTA</span>
    </div>
    <div class="report-list">
      ${blocks.slice(0, 40).map(block => `
        <article class="report-card">
          <strong>${escapeHtml(block.title || `Bloco ${Number(block.index || 0) + 1}`)}</strong>
          <small>${escapeHtml(block.type || 'bloco')} · ${Math.round(Number(block.confidence || 0) * 100)}%</small>
          <p>${escapeHtml(String(block.text || '').slice(0, 280))}</p>
          <span>${escapeHtml((block.keywords || []).slice(0, 8).join(', ') || 'sem palavras-chave')}</span>
        </article>
      `).join('')}
    </div>
  `;
}

function currentSubtitleStyle(){
  const preset = subtitlePresets[subtitlePreset.value] || subtitlePresets.bold_white;
  const fontPreset = subtitleFontPreset?.value || preset.fontPreset || 'arial_black';
  return {
    preset: subtitlePreset.value,
    fontPreset,
    font: subtitleFontPresets[fontPreset] || subtitleFontPresets.arial_black,
    animation: subtitleAnimation?.value || preset.animation || 'mixed',
    primary: subtitleColor.value || preset.color,
    outline: subtitleOutline.value || preset.outline,
    size: Number(subtitleSize.value || 64),
    position: Number(subtitlePosition.value || 16),
    outlineSize: Number(subtitleOutlineSize?.value || preset.outlineSize || 2),
    shadow: preset.box ? 0 : 1,
    box: preset.box,
    bold: preset.weight >= 800,
  };
}

function currentCaptionStyle(){
  return {
    preset: captionPreset?.value || 'clean_two_lines',
    font: captionFont?.value || 'Arial',
    size: Number(captionSize?.value || 38),
    position: Number(captionPosition?.value || 10),
    alignment: captionAlignment?.value || 'center',
    primary: captionColor?.value || '#ffffff',
    outline: captionOutlineColor?.value || '#111111',
    outline_size: Number(captionOutline?.value || 2),
    box: captionPreset?.value === 'soft_box',
  };
}

function applyCaptionStyleSnapshot(style = null){
  if(!style || typeof style !== 'object') return;
  if(captionPreset && style.preset) captionPreset.value = style.preset;
  if(captionFont && style.font) captionFont.value = style.font;
  if(captionSize && Number.isFinite(Number(style.size))) captionSize.value = String(style.size);
  if(captionPosition && Number.isFinite(Number(style.position))) captionPosition.value = String(style.position);
  if(captionAlignment && style.alignment) captionAlignment.value = style.alignment;
  if(captionColor && style.primary) captionColor.value = normalizeHex(style.primary, '#ffffff');
  if(captionOutlineColor && style.outline) captionOutlineColor.value = normalizeHex(style.outline, '#111111');
  if(captionOutline && Number.isFinite(Number(style.outline_size))) captionOutline.value = String(style.outline_size);
}

function updateLayerPreview(){
  const textStyle = currentSubtitleStyle();
  const capStyle = currentCaptionStyle();
  if(layerPreviewText){
    layerPreviewText.textContent = previewCaption?.textContent || 'Texto editorial';
    layerPreviewText.style.color = textStyle.primary;
    layerPreviewText.style.fontFamily = textStyle.font;
    layerPreviewText.style.fontSize = `${Math.max(18, textStyle.size * .48)}px`;
  }
  if(layerPreviewCaption){
    layerPreviewCaption.style.color = capStyle.primary;
    layerPreviewCaption.style.fontFamily = capStyle.font;
    layerPreviewCaption.style.fontSize = `${Math.max(15, capStyle.size * .48)}px`;
    layerPreviewCaption.style.textAlign = capStyle.alignment;
    layerPreviewCaption.style.bottom = `${Math.max(5, capStyle.position)}%`;
    layerPreviewCaption.style.webkitTextStroke = `${Math.max(0, capStyle.outline_size * .35)}px ${capStyle.outline}`;
    layerPreviewCaption.classList.toggle('boxed', capStyle.box);
  }
  const firstVisual = state.videos[0];
  const thumb = firstVisual ? state.thumbs.get(rel(firstVisual)) : null;
  if(layerPreviewMedia){
    layerPreviewMedia.style.backgroundImage = thumb ? `url("${thumb}")` : '';
    layerPreviewMedia.classList.toggle('has-thumb', Boolean(thumb));
  }
  if(captionSizeValue) captionSizeValue.textContent = String(capStyle.size);
  if(captionPositionValue) captionPositionValue.textContent = `${capStyle.position}%`;
  if(captionOutlineValue) captionOutlineValue.textContent = `${capStyle.outline_size.toFixed(1)}px`;
}

function currentIntroSubtitleStyle(){
  const preset = introPresets[introPreset?.value] || introPresets.cinema_gold;
  const fontPreset = introFontPreset?.value || preset.fontPreset || 'georgia';
  return {
    preset: introPreset?.value || 'cinema_gold',
    fontPreset,
    font: introFontPresets[fontPreset] || introFontPresets.georgia,
    primary: introColor?.value || preset.color,
    outline: introOutline?.value || preset.outline,
    size: Number(introSize?.value || preset.size || 76),
    position: Number(introPosition?.value || preset.position || 44),
    outlineSize: Number(preset.outlineSize || 2.2),
    shadow: preset.box ? 0 : 1.2,
    box: preset.box,
    bold: preset.weight >= 800,
  };
}

function applySubtitleStyleSnapshot(style = null){
  if(!style || typeof style !== 'object') return;
  if(subtitlePreset && style.preset && subtitlePresets[style.preset]) subtitlePreset.value = style.preset;
  if(subtitleFontPreset && style.fontPreset && subtitleFontPresets[style.fontPreset]) subtitleFontPreset.value = style.fontPreset;
  if(subtitleAnimation && style.animation) subtitleAnimation.value = style.animation;
  if(subtitleColor && style.primary) subtitleColor.value = normalizeHex(style.primary, subtitleColor.value || '#ffffff');
  if(subtitleOutline && style.outline) subtitleOutline.value = normalizeHex(style.outline, subtitleOutline.value || '#111111');
  if(subtitleSize && Number.isFinite(Number(style.size))) subtitleSize.value = String(style.size);
  if(subtitlePosition && Number.isFinite(Number(style.position))) subtitlePosition.value = String(style.position);
  if(subtitleOutlineSize && Number.isFinite(Number(style.outlineSize))) subtitleOutlineSize.value = String(style.outlineSize);
}

function applyIntroStyleSnapshot(style = null){
  if(!style || typeof style !== 'object') return;
  if(introPreset && style.preset && introPresets[style.preset]) introPreset.value = style.preset;
  if(introFontPreset && style.fontPreset && introFontPresets[style.fontPreset]) introFontPreset.value = style.fontPreset;
  if(introColor && style.primary) introColor.value = normalizeHex(style.primary, introColor.value || '#ffd36a');
  if(introOutline && style.outline) introOutline.value = normalizeHex(style.outline, introOutline.value || '#090909');
  if(introSize && Number.isFinite(Number(style.size))) introSize.value = String(style.size);
  if(introPosition && Number.isFinite(Number(style.position))) introPosition.value = String(style.position);
}

function normalizeHex(value, fallback = '#ffffff'){
  const clean = String(value || '').trim();
  if(/^#[0-9a-f]{6}$/i.test(clean)) return clean.toUpperCase();
  return fallback.toUpperCase();
}

function updateColorControl(input, preview, label, fallback){
  if(!input) return;
  const color = normalizeHex(input.value, fallback);
  input.value = color;
  if(preview) preview.style.background = color;
  if(label) label.textContent = color;
}

function updateSubtitleControlVisuals(){
  const size = Number(subtitleSize.value || 64);
  const position = Number(subtitlePosition.value || 16);
  const outlineSize = Number(subtitleOutlineSize?.value || 2);
  if(subtitleSizeValue) subtitleSizeValue.textContent = `${size}px`;
  if(subtitlePositionValue) subtitlePositionValue.textContent = `${position}%`;
  if(subtitleOutlineSizeValue) subtitleOutlineSizeValue.textContent = `${outlineSize.toFixed(1)}px`;
  updateColorControl(subtitleColor, subtitleColorPreview, subtitleColorHex, '#ffffff');
  updateColorControl(subtitleOutline, subtitleOutlinePreview, subtitleOutlineHex, '#111111');
  document.querySelectorAll('.swatch-row').forEach(row => {
    const input = $(`#${row.dataset.target}`);
    const active = normalizeHex(input?.value || '', '#ffffff');
    row.querySelectorAll('.color-swatch').forEach(btn => {
      btn.classList.toggle('active', normalizeHex(btn.dataset.color, '#ffffff') === active);
    });
  });
}

function applyPresetToControls(){
  const preset = subtitlePresets[subtitlePreset.value] || subtitlePresets.bold_white;
  subtitleColor.value = preset.color;
  subtitleOutline.value = preset.outline;
  if(subtitleFontPreset) subtitleFontPreset.value = preset.fontPreset || 'arial_black';
  if(subtitleAnimation) subtitleAnimation.value = preset.animation || 'mixed';
  if(subtitleOutlineSize) subtitleOutlineSize.value = String(preset.outlineSize || 2);
  updateSubtitlePreview();
}

function applyIntroPresetToControls(){
  const preset = introPresets[introPreset?.value] || introPresets.cinema_gold;
  if(introColor) introColor.value = preset.color;
  if(introOutline) introOutline.value = preset.outline;
  if(introFontPreset) introFontPreset.value = preset.fontPreset || 'georgia';
  if(introSize) introSize.value = String(preset.size || 76);
  if(introPosition) introPosition.value = String(preset.position || 44);
  updateIntroPreview();
}

function updateIntroPreview({refreshStats = true} = {}){
  if(!introPanel || !introPreviewText) return;
  const mode = introModeSelect?.value || 'standard';
  introPanel.classList.toggle('standard', mode !== 'cinematic');
  const style = currentIntroSubtitleStyle();
  const firstText = previewCaption?.textContent || 'Seu primeiro Texto';
  introPreviewText.textContent = firstText.slice(0, 100);
  introPreviewText.style.color = style.primary;
  introPreviewText.style.fontSize = `${Math.max(24, Math.round(style.size * 0.42))}px`;
  introPreviewText.style.top = `${style.position}%`;
  introPreviewText.style.fontFamily = `"${style.font}", Arial, sans-serif`;
  introPreviewText.style.fontWeight = style.bold ? '900' : '700';
  const outlinePx = Math.max(1, style.outlineSize);
  introPreviewText.style.textShadow = `0 ${outlinePx}px 0 ${style.outline}, 0 0 ${Math.round(outlinePx * 9)}px ${style.outline}`;
  introPreviewText.classList.toggle('caption-box', Boolean(style.box));
  if(introStatus){
    introStatus.textContent = mode === 'cinematic'
      ? 'Cinemática contextual: 3–5s, música primeiro e Texto inicial apenas quando houver um gancho forte.'
      : 'Padrão: fade in simples no primeiro clipe, sem atraso na narração.';
  }
  if(introVoiceBadge) introVoiceBadge.textContent = mode === 'cinematic' ? 'Voz entra em ~4s' : 'Voz entra em 0s';
  if(introSizeValue) introSizeValue.textContent = `${style.size}px`;
  if(introPositionValue) introPositionValue.textContent = `${style.position}%`;
  updateColorControl(introColor, introColorPreview, introColorHex, '#ffd36a');
  updateColorControl(introOutline, introOutlinePreview, introOutlineHex, '#090909');
  const firstVideo = state.videos[0];
  const thumb = firstVideo ? state.thumbs.get(rel(firstVideo)) : null;
  if(introPreviewMedia){
    if(thumb){
      introPreviewMedia.style.backgroundImage = `url("${thumb}")`;
      introPreviewMedia.classList.add('has-thumb');
    }else{
      introPreviewMedia.style.backgroundImage = '';
      introPreviewMedia.classList.remove('has-thumb');
    }
  }
  if(refreshStats) updateStats();
}

function updateSubtitlePreview({refreshStats = true} = {}){
  const preset = subtitlePresets[subtitlePreset.value] || subtitlePresets.bold_white;
  const style = currentSubtitleStyle();
  previewCaption.style.color = style.primary;
  previewCaption.style.fontSize = `${Math.max(22, Math.round(style.size * 0.58))}px`;
  previewCaption.style.bottom = `${style.position}%`;
  previewCaption.style.fontFamily = `"${style.font}", Arial, sans-serif`;
  previewCaption.style.fontWeight = String(preset.weight);
  const outlinePx = Math.max(1, style.outlineSize);
  previewCaption.style.textShadow = `0 ${outlinePx}px 0 ${style.outline}, 0 0 ${Math.round(outlinePx * 8)}px ${style.outline}`;
  previewCaption.classList.toggle('caption-box', Boolean(style.box));
  previewCaption.classList.remove(
    'anim-mixed', 'anim-pop', 'anim-slide', 'anim-zoom', 'anim-fade', 'anim-cinematic', 'anim-pulse', 'anim-glitch', 'anim-typewriter', 'anim-shake',
    'anim-random_text', 'anim-documentary', 'anim-archive', 'anim-digital', 'anim-stamp', 'anim-money', 'anim-warning', 'anim-industrial', 'anim-luxury',
    'anim-none'
  );
  previewCaption.classList.add(`anim-${style.animation || 'mixed'}`);
  updateSubtitleControlVisuals();
  const firstVideo = state.videos[0];
  const thumb = firstVideo ? state.thumbs.get(rel(firstVideo)) : null;
  if(thumb){
    previewMedia.style.backgroundImage = `url("${thumb}")`;
    previewMedia.classList.add('has-thumb');
  }else{
    previewMedia.style.backgroundImage = '';
    previewMedia.classList.remove('has-thumb');
  }
  updateIntroPreview({refreshStats: false});
  updateCtaPreview();
  if(refreshStats) updateStats();
}

function updateStats(){
  const audioTotal = state.audios.reduce((sum, file) => sum + (state.durations.get(rel(file)) || 0), 0);
  const videoTotal = state.videos.reduce((sum, file) => sum + (state.durations.get(rel(file)) || 0), 0);
  const backgroundCount = state.backgroundTracks.length;
  $('#videoCount').textContent = state.videos.length;
  $('#audioCount').textContent = state.audios.length;
  $('#audioTotal').textContent = formatTime(audioTotal);
  $('#videoEstimate').textContent = formatTime(audioTotal || videoTotal);
  updateBackgroundSummary();

  const ctaOk = Boolean(state.selectedCta);
  const textsOk = state.subtitles.length > 0;
  const ok = state.videos.length > 0 && state.audios.length > 0 && textsOk && ctaOk;
  const invalidVideos = state.videos.filter(file => videoStatusOf(file).kind === 'invalid').length;
  renderBtn.disabled = !ok || state.queueRendering;
  if(ok){
    const musicText = backgroundCount ? ` + ${backgroundCount} música(s) baixa(s)` : '';
    const invalidText = invalidVideos ? ` ${invalidVideos} item(ns) serao pulados se continuarem invalidos.` : '';
    const vCount = state.videos.filter(isVideo).length;
    const iCount = state.videos.filter(isImage).length;
    const mediaBreakdown = (vCount && iCount) ? `${vCount} vídeo(s) e ${iCount} foto(s)` : (iCount ? `${iCount} foto(s)` : `${vCount} vídeo(s)`);
    dockSummary.textContent = `${mediaBreakdown} + ${state.audios.length} áudio(s)${musicText}. Final aproximado: ${formatTime(audioTotal || videoTotal)}.${invalidText}`;
  }else if(state.videos.length && state.audios.length && !textsOk){
    dockSummary.textContent = 'Adicione Textos em SRT para orientar a edição e liberar o render.';
  }else if(state.videos.length && state.audios.length && !ctaOk){
    dockSummary.textContent = 'Escolha um CTA de inscricao para liberar o render.';
  }else if(state.videos.length){
    dockSummary.textContent = `${state.videos.length} arquivo(s) de mídia carregado(s). Adicione áudio para liberar o render.`;
  }else if(state.audios.length){
    dockSummary.textContent = `${state.audios.length} áudio(s) carregado(s). Adicione vídeos ou imagens para liberar o render.`;
  }else{
    dockSummary.textContent = 'Importe vídeos, imagens e áudios em qualquer ordem.';
  }
  renderProjectChecks();
  renderProjectQueue();
  scheduleRenderEstimate();
}

function createVideoTimelineCard(file, idx, total){
  const card = document.createElement('div');
  const r = rel(file);
  const safeName = escapeHtml(file.name);
  const safeRel = escapeHtml(r);
  const thumb = state.thumbs.get(r);
  const status = videoStatusOf(file);
  const thumbClass = videoStatusClass(status, Boolean(thumb));
  card.className = 'clip-card';
  card.dataset.dragItem = 'true';
  card.tabIndex = 0;
  card.dataset.rel = r;
  card.setAttribute('aria-posinset', String(idx + 1));
  card.setAttribute('aria-setsize', String(total));
  card.innerHTML = `
    <button class="remove-file" type="button" title="Remover este clip" aria-label="Remover este clip"></button>
    <div class="clip-index">#${String(idx + 1).padStart(2, '0')}</div>
    <div class="thumb${thumbClass}">${thumb ? `<img src="${thumb}" alt="thumb"/>` : `<span>${videoPlaceholder(status)}</span>`}</div>
    <div class="clip-body">
      <div class="clip-title" title="${safeRel}">${safeName}</div>
      <div class="clip-meta"><span>${formatTime(state.durations.get(r) || 0)}</span><span>${formatSize(file.size)}</span></div>
      ${videoStatusBadgeHtml(status)}
      ${videoWarningHtml(status)}
    </div>`;
  return card;
}

function appendVideoTimelineChunk(files, startIndex, signature, generation){
  if(generation !== state.timelineRenderGeneration || signature !== state.videoListSignature) return;
  const end = Math.min(files.length, startIndex + 36);
  const frag = document.createDocumentFragment();
  for(let idx = startIndex; idx < end; idx++){
    frag.appendChild(createVideoTimelineCard(files[idx], idx, files.length));
  }
  videoTimeline.appendChild(frag);
  if(end >= files.length){
    videoTimeline.dataset.complete = '1';
    return;
  }
  const resume = () => appendVideoTimelineChunk(files, end, signature, generation);
  if('requestIdleCallback' in window) window.requestIdleCallback(resume, {timeout: 140});
  else window.setTimeout(resume, 12);
}

function renderLists({updatePreview = true} = {}){
  if(activeDrag){
    state.pendingListRefresh = true;
    return;
  }
  state.pendingListRefresh = false;
  const nextVideoSignature = videoSignature();
  if(nextVideoSignature !== state.videoListSignature || !videoTimeline.dataset.ready){
    state.videoListSignature = nextVideoSignature;
    const generation = ++state.timelineRenderGeneration;
    videoTimeline.dataset.ready = '1';
    videoTimeline.dataset.complete = '0';
    if(!state.videos.length){
      videoTimeline.innerHTML = '<div class="empty"><div class="empty-icon"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="2" width="20" height="20" rx="2.18" ry="2.18"/><line x1="7" y1="2" x2="7" y2="22"/><line x1="17" y1="2" x2="17" y2="22"/><line x1="2" y1="12" x2="22" y2="12"/></svg></div><strong>Nenhum clipe na timeline</strong><span>Arraste vídeos e imagens para esta área ou use os botões de envio acima.</span></div>';
      videoTimeline.dataset.complete = '1';
    }else{
      videoTimeline.innerHTML = '';
      const frag = document.createDocumentFragment();
      const immediateCount = Math.min(state.videos.length, 42);
      for(let idx = 0; idx < immediateCount; idx++){
        frag.appendChild(createVideoTimelineCard(state.videos[idx], idx, state.videos.length));
      }
      videoTimeline.appendChild(frag);
      if(immediateCount < state.videos.length){
        const files = [...state.videos];
        const resume = () => appendVideoTimelineChunk(files, immediateCount, nextVideoSignature, generation);
        if('requestIdleCallback' in window) window.requestIdleCallback(resume, {timeout: 100});
        else window.setTimeout(resume, 8);
      }else{
        videoTimeline.dataset.complete = '1';
      }
    }
  }

  const nextAudioSignature = audioSignature();
  if(nextAudioSignature !== state.audioListSignature || !audioTimeline.dataset.ready){
    state.audioListSignature = nextAudioSignature;
    audioTimeline.dataset.ready = '1';
    if(!state.audios.length){
      audioTimeline.innerHTML = '<div class="empty"><div class="empty-icon"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg></div><strong>Nenhuma narração carregada</strong><span>Adicione arquivos de áudio para definir o tempo do vídeo e liberar a exportação.</span></div>';
    }else{
      audioTimeline.innerHTML = '';
      const frag = document.createDocumentFragment();
      state.audios.forEach((file, idx) => {
        const item = document.createElement('div');
        const r = rel(file);
        const health = state.audioHealth.get(r);
        const healthClass = health?.status ? ` audio-health-${health.status}` : '';
        item.className = 'audio-item';
        item.dataset.dragItem = 'true';
        item.tabIndex = 0;
        item.dataset.rel = r;
        item.innerHTML = `
          <strong>${String(idx + 1).padStart(2, '0')} - ${escapeHtml(file.name)}</strong>
          <span>${formatTime(state.durations.get(r) || 0)}${health ? ` - <em class="audio-health${healthClass}">${escapeHtml(health.message)}</em>` : ''}</span>
          <button class="remove-file audio-remove" type="button" title="Remover este audio" aria-label="Remover este audio"></button>`;
        frag.appendChild(item);
      });
      audioTimeline.appendChild(frag);
    }
  }

  const nextBackgroundSignature = backgroundSignature();
  if(backgroundTimeline && (nextBackgroundSignature !== state.backgroundListSignature || !backgroundTimeline.dataset.ready)){
    state.backgroundListSignature = nextBackgroundSignature;
    backgroundTimeline.dataset.ready = '1';
    if(!state.backgroundTracks.length){
      const info = presetMusicInfo();
      backgroundTimeline.innerHTML = `<div class="empty">${info.count
        ? `Biblioteca ${escapeHtml(musicGenreLabel())} ativa: ${info.count} faixa(s) locais. O render sorteia um mix novo, corta/reutiliza e aplica fades até cobrir a narração.`
        : `Músicas de fundo manuais aparecem aqui. Biblioteca ${escapeHtml(musicGenreLabel())} sem faixas locais no momento.`}</div>`;
    }else{
      backgroundTimeline.innerHTML = '';
      const frag = document.createDocumentFragment();
      state.backgroundTracks.forEach((file, idx) => {
        const item = document.createElement('div');
        const r = rel(file);
        item.className = 'audio-item background-item';
        item.dataset.dragItem = 'true';
        item.tabIndex = 0;
        item.dataset.rel = r;
        item.innerHTML = `
          <strong>${String(idx + 1).padStart(2, '0')} - ${escapeHtml(file.name)}</strong>
          <span>${formatTime(state.durations.get(r) || 0)}</span>
          <button class="remove-file audio-remove" type="button" title="Remover esta música" aria-label="Remover esta música"></button>`;
        frag.appendChild(item);
      });
      backgroundTimeline.appendChild(frag);
    }
  }
  if(updatePreview) updateSubtitlePreview({refreshStats: false});
}

const dragSelector = '[data-drag-item="true"]';
let activeDrag = null;

function setupDrag(container, key){
  let candidate = null;

  container.addEventListener('dragstart', (event) => event.preventDefault());

  container.addEventListener('pointerdown', (event) => {
    if(event.button !== 0 || state.renderActive || state.queueRendering) return;
    if(event.target.closest('button,a,input,select,textarea,[data-no-drag]')) return;
    const item = event.target.closest(dragSelector);
    if(!item || !container.contains(item)) return;
    candidate = {
      container,
      key,
      item,
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      latestX: event.clientX,
      latestY: event.clientY,
      started: false,
      raf: 0,
    };
    item.setPointerCapture?.(event.pointerId);
  });

  container.addEventListener('pointermove', (event) => {
    if(!candidate || candidate.pointerId !== event.pointerId) return;
    const dx = event.clientX - candidate.startX;
    const dy = event.clientY - candidate.startY;
    if(!candidate.started && Math.hypot(dx, dy) < 6) return;
    if(!candidate.started) beginTimelineDrag(candidate, event);
    moveTimelineDrag(event);
  });

  const finish = (event) => {
    if(!candidate || candidate.pointerId !== event.pointerId) return;
    const session = candidate;
    candidate = null;
    if(session.started) endTimelineDrag(session, true);
    else session.item.releasePointerCapture?.(event.pointerId);
  };

  container.addEventListener('pointerup', finish);
  container.addEventListener('pointercancel', (event) => {
    if(!candidate || candidate.pointerId !== event.pointerId) return;
    const session = candidate;
    candidate = null;
    endTimelineDrag(session, false);
  });
}

function beginTimelineDrag(session, event){
  const rect = session.item.getBoundingClientRect();
  const placeholder = document.createElement('div');
  placeholder.className = session.item.classList.contains('clip-card') ? 'timeline-drag-placeholder clip-placeholder' : 'timeline-drag-placeholder audio-placeholder';
  placeholder.style.width = `${rect.width}px`;
  placeholder.style.height = `${rect.height}px`;
  session.placeholder = placeholder;
  session.rect = rect;
  session.offsetX = event.clientX - rect.left;
  session.offsetY = event.clientY - rect.top;
  session.item.parentNode.insertBefore(placeholder, session.item.nextSibling);
  session.item.classList.add('dragging', 'pointer-dragging');
  session.item.style.position = 'fixed';
  session.item.style.left = `${rect.left}px`;
  session.item.style.top = `${rect.top}px`;
  session.item.style.width = `${rect.width}px`;
  session.item.style.height = `${rect.height}px`;
  session.item.style.zIndex = '120';
  session.item.style.pointerEvents = 'none';
  session.item.style.transform = 'translate3d(0,0,0)';
  session.container.classList.add('is-reordering');
  document.body.classList.add('timeline-drag-active');
  session.started = true;
  refreshTimelineDragPositions(session);
  activeDrag = session;
}

function moveTimelineDrag(event){
  if(!activeDrag) return;
  activeDrag.latestX = event.clientX;
  activeDrag.latestY = event.clientY;
  event.preventDefault();
  if(!activeDrag.raf){
    activeDrag.raf = requestAnimationFrame(() => {
      activeDrag.raf = 0;
      updateTimelineDragPosition(activeDrag);
    });
  }
}

function updateTimelineDragPosition(session){
  if(!session?.item) return;
  const x = session.latestX;
  const y = session.latestY;
  session.item.style.transform = `translate3d(${x - session.startX}px, ${y - session.startY}px, 0)`;
  autoScrollDuringDrag(y);
  const after = getAfterElementFromCache(session, y, x);
  if(after == null){
    if(session.container.lastElementChild !== session.placeholder) session.container.appendChild(session.placeholder);
  }else if(after !== session.placeholder && after.previousElementSibling !== session.placeholder){
    session.container.insertBefore(session.placeholder, after);
  }
}

function autoScrollDuringDrag(y){
  const margin = 82;
  const speed = 18;
  if(y < margin) window.scrollBy({top: -speed, behavior: 'auto'});
  else if(y > window.innerHeight - margin) window.scrollBy({top: speed, behavior: 'auto'});
}

function endTimelineDrag(session, commit){
  if(session.raf) cancelAnimationFrame(session.raf);
  session.item.releasePointerCapture?.(session.pointerId);
  if(commit && session.placeholder?.parentNode){
    session.container.insertBefore(session.item, session.placeholder);
  }
  session.item.classList.remove('dragging', 'pointer-dragging');
  session.item.style.position = '';
  session.item.style.left = '';
  session.item.style.top = '';
  session.item.style.width = '';
  session.item.style.height = '';
  session.item.style.zIndex = '';
  session.item.style.pointerEvents = '';
  session.item.style.transform = '';
  session.placeholder?.remove();
  session.container.classList.remove('is-reordering');
  document.body.classList.remove('timeline-drag-active');
  activeDrag = null;
  const hadPendingRefresh = state.pendingListRefresh;
  if(commit) syncOrder(session.container, session.key);
  else if(hadPendingRefresh) renderLists();
}

function refreshTimelineDragPositions(session){
  const scrollY = window.scrollY || document.documentElement.scrollTop || 0;
  const scrollX = window.scrollX || document.documentElement.scrollLeft || 0;
  session.dragPositions = [...session.container.querySelectorAll(`${dragSelector}:not(.dragging)`)]
    .filter(child => child !== session.placeholder)
    .map(child => {
      const box = child.getBoundingClientRect();
      return {
        element: child,
        top: box.top + scrollY,
        left: box.left + scrollX,
        width: box.width,
        height: box.height,
      };
    });
}

function getAfterElementFromCache(session, y, x){
  if(!session.dragPositions) refreshTimelineDragPositions(session);
  const scrollY = window.scrollY || document.documentElement.scrollTop || 0;
  const scrollX = window.scrollX || document.documentElement.scrollLeft || 0;
  const pageY = y + scrollY;
  const pageX = x + scrollX;
  return (session.dragPositions || []).reduce((closest, box) => {
    const sameRowBias = Math.abs(pageY - (box.top + box.height / 2)) < box.height * 0.62 ? 0.18 : 0.05;
    const offset = (pageY - box.top - box.height / 2) + (pageX - box.left - box.width / 2) * sameRowBias;
    if(offset < 0 && offset > closest.offset) return {offset, element: box.element};
    return closest;
  }, {offset: Number.NEGATIVE_INFINITY}).element;
}

function syncOrder(container, key){
  const order = [...container.querySelectorAll('[data-rel]')].map(el => el.dataset.rel);
  const map = new Map(state[key].map(file => [rel(file), file]));
  state[key] = order.map(r => map.get(r)).filter(Boolean);
  if(key === 'videos') state.videoOrderEdited = true;
  if(key === 'audios') state.audioOrderEdited = true;
  if(key === 'backgroundTracks') state.backgroundOrderEdited = true;
  renderLists();
  updateStats();
  captureActiveProject();
  renderProjectQueue();
}

function removeFromState(kind, relValue){
  const listKey = kind === 'audio' ? 'audios' : (kind === 'background_music' ? 'backgroundTracks' : 'videos');
  const target = state[listKey].find(file => rel(file) === relValue);
  if(!target) return;
  state[listKey] = state[listKey].filter(file => rel(file) !== relValue);
  for(const [key, file] of state.registry.entries()){
    if(file === target) state.registry.delete(key);
  }
  const stillUsed = [...state.videos, ...state.audios, ...state.backgroundTracks, ...state.subtitles].some(file => rel(file) === relValue);
  if(!stillUsed){
    state.durations.delete(relValue);
    state.durationSources.delete(relValue);
    state.audioHealth.delete(relValue);
    state.thumbs.delete(relValue);
    state.mediaStatus.delete(relValue);
  }
  renderLists();
  updateStats();
  captureActiveProject();
  recordLearningEvent('remove_clip', {kind, rel: relValue});
}

function setRenderProjectMeta({projectName = '', queueIndex = 0, renderLabel = '', status = ''} = {}){
  if(!renderProjectMeta) return;
  const parts = [];
  if(projectName) parts.push(`Projeto: ${projectName}`);
  if(queueIndex) parts.push(`Fila: #${queueIndex}`);
  if(renderLabel) parts.push(`Modo: ${renderLabel}`);
  if(status) parts.push(status);
  renderProjectMeta.textContent = parts.length ? parts.join(' - ') : 'Projeto: aguardando início';
}

function formatEtaSummary(eta, status = 'running'){
  if(!eta) return 'Tempo restante: calculando...';
  const elapsed = formatTime(eta.elapsed_seconds || 0);
  if(status !== 'running') return `Tempo total ${elapsed}`;
  const limitText = Number(eta.budget_seconds || 0) > 0 ? ` · limite ${formatTime(eta.budget_seconds || 0)}` : '';
  const stateName = String(eta.state || eta.confidence || '').toLowerCase();
  if(stateName === 'warming_up' || stateName === 'unknown'){
    return `Decorrido ${elapsed} - calculando tempo restante...${limitText}`;
  }
  if(stateName === 'variable' || Number(eta.remaining_min_seconds) || Number(eta.remaining_max_seconds)){
    const min = Number(eta.remaining_min_seconds || 0);
    const max = Number(eta.remaining_max_seconds || 0);
    if(stateName === 'variable' && min && max && max > min){
      return `Decorrido ${elapsed} - tempo estimado variável: ${formatTime(min)}-${formatTime(max)}${limitText}`;
    }
    if(min && max && max > min * 1.12){
      return `Decorrido ${elapsed} - restante aprox. ${formatTime(min)}-${formatTime(max)}${limitText}`;
    }
  }
  return `Decorrido ${elapsed} - restante aprox. ${formatTime(eta.estimated_remaining_seconds || 0)}${limitText}`;
}

function renderDoneIsValidated(job){
  const delivery = job?.delivery_summary || {};
  return Boolean(job?.download && delivery.validated === true && delivery.ok !== false);
}

function outputValidationError(job){
  const delivery = job?.delivery_summary || {};
  if(delivery.errors?.length) return `Arquivo final não confirmado: ${delivery.errors.join('; ')}`;
  if(delivery.error) return `Falha ao salvar o MP4 final: ${delivery.error}`;
  if(!job?.download) return 'Arquivo final não confirmado: download ou saída ausente.';
  return 'Arquivo final não foi validado pelo motor local.';
}

function resetProgress({preserveMinimized = false} = {}){
  if(!preserveMinimized) modal.classList.remove('minimized');
  progressBar.style.width = '0%';
  eyePercent.textContent = '0%';
  renderMsg.textContent = 'Preparando arquivos';
  if(renderEta) renderEta.textContent = 'Tempo restante: calculando...';
  renderTitle.textContent = 'Preparando render';
  setRenderProjectMeta();
  renderLog.textContent = '';
  renderLog.classList.add('hidden');
  toggleLogBtn.textContent = 'Detalhes técnicos';
  state.renderShowcaseStage = '';
  setRenderStage('preparing');
  downloadBtn.classList.add('hidden');
  downloadBtn.textContent = 'Baixar MP4';
  downloadBtn.removeAttribute('href');
  openOutputBtn.classList.add('hidden');
  const closeBtn = $('#closeModal');
  if(closeBtn) closeBtn.textContent = 'Minimizar';
  if(stopRenderBtn){
    stopRenderBtn.classList.add('hidden');
    stopRenderBtn.disabled = false;
    stopRenderBtn.textContent = 'Parar render';
  }
  outputPath.textContent = '';
}

const RENDER_SHOWCASE = {
  preparing: {
    title: 'Organizando o projeto',
    text: 'Preparando arquivos, cache e verificações antes do render.',
    art: [
      '<div class="stage-art stage-preparing"><span></span><span></span><span></span><i></i></div>',
      '<div class="stage-art stage-preparing stage-preparing-alt"><span></span><span></span><span></span><i></i></div>',
    ],
  },
  uploading: {
    title: 'Copiando para o motor local',
    text: 'Transferindo mídias preservadas para uma área técnica segura.',
    art: [
      '<div class="stage-art stage-uploading"><span></span><span></span><span></span><i></i><b></b></div>',
      '<div class="stage-art stage-uploading stage-uploading-alt"><span></span><span></span><span></span><i></i><b></b></div>',
    ],
  },
  audio: {
    title: 'Desenhando o áudio',
    text: 'Narração, música, CTA e efeitos entram no mesmo mapa de tempo.',
    art: [
      '<div class="stage-art stage-audio"><span></span><span></span><span></span><span></span><span></span><i></i></div>',
      '<div class="stage-art stage-audio stage-audio-alt"><span></span><span></span><span></span><span></span><span></span><i></i></div>',
    ],
  },
  rendering: {
    title: 'Montando clipes',
    text: 'Frames saudáveis, CTA e ritmo visual seguem o plano do projeto.',
    art: [
      '<div class="stage-art stage-clips"><span></span><span></span><span></span><i></i></div>',
      '<div class="stage-art stage-clips stage-clips-alt"><span></span><span></span><span></span><i></i></div>',
    ],
  },
  cta: {
    title: 'Compondo CTA, Textos e Legendas',
    text: 'As três camadas visuais são aplicadas juntas, com zonas seguras e progresso medido por frame.',
    art: [
      '<div class="stage-art stage-cta"><span class="cta-shell"><i class="cta-avatar"></i><b class="cta-line"></b><b class="cta-line"></b><button type="button" tabindex="-1">Subscrever</button><em class="cta-cursor"></em><u class="cta-ripple"></u></span></div>',
      '<div class="stage-art stage-cta stage-cta-alt"><span class="cta-shell"><i class="cta-avatar"></i><b class="cta-line"></b><b class="cta-line"></b><button type="button" tabindex="-1">Seguir</button><em class="cta-cursor"></em><u class="cta-ripple"></u></span></div>',
    ],
  },
  muxing: {
    title: 'Finalizando exportação',
    text: 'O MP4 final está sendo fechado e preparado para entrega.',
    art: [
      '<div class="stage-art stage-finalizing"><span></span><i></i><b></b></div>',
      '<div class="stage-art stage-finalizing stage-finalizing-alt"><span></span><i></i><b></b></div>',
    ],
  },
  done: {
    title: 'Render concluído',
    text: 'Arquivo final pronto. Use Abrir pasta ou baixar quando disponível.',
    art: [
      '<div class="stage-art stage-done"><span></span><i></i><b></b></div>',
      '<div class="stage-art stage-done stage-done-alt"><span></span><i></i><b></b></div>',
    ],
  },
  queue_done: {
    title: 'Fila concluída',
    text: 'Todos os projetos elegíveis foram processados. Relatórios e vídeos estão prontos.',
    art: [
      '<div class="stage-art stage-celebrate"><span></span><span></span><span></span><i></i><b></b></div>',
      '<div class="stage-art stage-celebrate stage-celebrate-alt"><span></span><span></span><span></span><i></i><b></b></div>',
    ],
  },
  error: {
    title: 'Render interrompido',
    text: 'Abra os detalhes técnicos para ver a causa e tentar novamente.',
    art: [
      '<div class="stage-art stage-error"><span></span><i></i><b></b></div>',
      '<div class="stage-art stage-error stage-error-alt"><span></span><i></i><b></b></div>',
    ],
  },
  cancelled: {
    title: 'Render cancelado',
    text: 'A fila parou com segurança. Projetos pendentes podem ser retomados.',
    art: [
      '<div class="stage-art stage-error"><span></span><i></i><b></b></div>',
      '<div class="stage-art stage-error stage-error-alt"><span></span><i></i><b></b></div>',
    ],
  },
};

function normalizeRenderStage(stage){
  const safe = String(stage || 'preparing').toLowerCase();
  if(safe === 'finalizing') return 'muxing';
  if(safe === 'clips') return 'rendering';
  if(safe === 'legendas' || safe === 'subtitles' || safe === 'analyzing_subtitles') return 'cta';
  if(safe === 'queue_done' || safe === 'queue-done') return 'queue_done';
  return RENDER_SHOWCASE[safe] ? safe : 'rendering';
}

function activeProject(){
  return state.projects.find(item => item.id === state.activeProjectId) || null;
}

function normalizeShowcaseTone(rawTone){
  const tone = String(rawTone || '').toLowerCase();
  if(/suspense|terror|horror|dark|misterio|mystery|sombrio/.test(tone)) return 'suspense';
  if(/tech|tecnolog|cyber|digital|futur|industrial|machine|maquina/.test(tone)) return 'tech';
  if(/doc|hist|archive|arquivo|document|news|investig/.test(tone)) return 'documentary';
  if(/emotion|emoc|calm|ambient|seren|peace|quiet/.test(tone)) return 'emotional';
  if(/energetic|energia|epic|cinema|cinematic|trailer|motiv/.test(tone)) return 'cinematic';
  return 'cinematic';
}

function getShowcaseTone(){
  const project = activeProject();
  const explicit = project?.options?.projectTone || projectToneSelect?.value || '';
  if(explicit && explicit !== 'auto') return normalizeShowcaseTone(explicit);
  const haystack = [
    project?.name || '',
    project?.template || '',
    project?.identity || '',
    identityPresetSelect?.selectedOptions?.[0]?.textContent || '',
    projectToneSelect?.selectedOptions?.[0]?.textContent || '',
    project?.lastRenderSummary?.emotion_summary?.tone || '',
    project?.lastRenderSummary?.emotionSummary?.tone || '',
  ].join(' ');
  return normalizeShowcaseTone(haystack);
}

function setRenderStage(stage){
  const normalized = normalizeRenderStage(stage);
  renderSteps.querySelectorAll('span').forEach(item => {
    item.classList.toggle('active', item.dataset.stage === normalized);
    item.classList.toggle('done', item.dataset.stage !== normalized && progressBar.style.width === '100%');
  });
  updateRenderShowcase(normalized);
}

function updateRenderShowcase(stage){
  if(!renderShowcase) return;
  const normalized = normalizeRenderStage(stage);
  if(state.renderShowcaseStage === normalized) return;
  state.renderShowcaseStage = normalized;
  const spec = RENDER_SHOWCASE[normalized] || RENDER_SHOWCASE.rendering;
  renderShowcase.dataset.stage = normalized;
  renderShowcase.dataset.tone = getShowcaseTone();
  const variants = Array.isArray(spec.art) ? spec.art : [spec.art];
  const variantIndex = variants.length ? state.renderShowcaseTick % variants.length : 0;
  state.renderShowcaseTick += 1;
  renderShowcase.dataset.variant = String(variantIndex + 1);
  renderShowcase.classList.remove('stage-changing');
  void renderShowcase.offsetWidth;
  renderShowcase.classList.add('stage-changing');
  if(renderShowcaseArt) renderShowcaseArt.innerHTML = variants[variantIndex] || '';
  if(renderShowcaseTitle) renderShowcaseTitle.textContent = spec.title;
  if(renderShowcaseText) renderShowcaseText.textContent = spec.text;
}

function setRenderProgress(pct, title, msg){
  const safe = Math.max(0, Math.min(100, pct || 0));
  progressBar.style.width = safe + '%';
  eyePercent.textContent = Math.round(safe) + '%';
  if(title) renderTitle.textContent = title;
  if(msg) renderMsg.textContent = msg;
}

function syncUiSoundControls(){
  applyScopedUiSoundPreference(false);
  if(uiSoundsToggle) uiSoundsToggle.checked = Boolean(state.uiSoundsEnabled);
  if(renderBudgetToggle) renderBudgetToggle.checked = Boolean(state.renderBudgetEnabled);
  if(uiSoundStyleSelect) uiSoundStyleSelect.value = state.uiSoundStyle;
  if(uiSoundScopeSelect) uiSoundScopeSelect.value = state.uiSoundScope;
  if(uiProjectDoneSoundToggle) uiProjectDoneSoundToggle.checked = Boolean(state.uiProjectDoneSoundEnabled);
}

function safePreferenceKey(value){
  return String(value || 'default').toLowerCase().replace(/[^a-z0-9_-]+/g, '_').replace(/^_+|_+$/g, '') || 'default';
}

function uiSoundScopedStorageKey(){
  const scope = state.uiSoundScope === 'theme' || state.uiSoundScope === 'identity' ? state.uiSoundScope : 'global';
  if(scope === 'theme') return `glide_ui_sound_style_theme_${safePreferenceKey(resolvedThemeMode())}`;
  if(scope === 'identity'){
    const project = activeProject();
    const identity = project?.identity || identityPresetSelect?.value || 'default';
    return `glide_ui_sound_style_identity_${safePreferenceKey(identity)}`;
  }
  return 'glide_ui_sound_style';
}

function applyScopedUiSoundPreference(updateSelect = true){
  const scopedKey = uiSoundScopedStorageKey();
  const scopedValue = localStorage.getItem(scopedKey);
  const globalValue = localStorage.getItem('glide_ui_sound_style') || 'soft_tick';
  state.uiSoundStyle = scopedValue || globalValue || 'soft_tick';
  if(updateSelect && uiSoundStyleSelect) uiSoundStyleSelect.value = state.uiSoundStyle;
}

function saveScopedUiSoundPreference(style){
  const next = style || 'soft_tick';
  state.uiSoundStyle = next;
  localStorage.setItem(uiSoundScopedStorageKey(), next);
  localStorage.setItem('glide_ui_sound_style', next);
}

function getUiAudioContext(){
  const AudioCtor = window.AudioContext || window.webkitAudioContext;
  if(!AudioCtor) return null;
  if(!state.uiAudioContext) state.uiAudioContext = new AudioCtor();
  if(state.uiAudioContext.state === 'suspended'){
    state.uiAudioContext.resume().catch(() => {});
  }
  return state.uiAudioContext;
}

function uiBeep(ctx, when, {freq = 440, endFreq = freq, duration = .055, gain = .035, type = 'sine', filter = 3600} = {}){
  const osc = ctx.createOscillator();
  const amp = ctx.createGain();
  const tone = ctx.createBiquadFilter();
  osc.type = type;
  osc.frequency.setValueAtTime(freq, when);
  osc.frequency.exponentialRampToValueAtTime(Math.max(40, endFreq), when + duration);
  tone.type = 'lowpass';
  tone.frequency.setValueAtTime(filter, when);
  amp.gain.setValueAtTime(0.0001, when);
  amp.gain.exponentialRampToValueAtTime(Math.max(0.0002, gain), when + .008);
  amp.gain.exponentialRampToValueAtTime(0.0001, when + duration);
  osc.connect(tone);
  tone.connect(amp);
  amp.connect(ctx.destination);
  osc.start(when);
  osc.stop(when + duration + .018);
}

function playUiSound(style = state.uiSoundStyle, {force = false, allowHidden = false} = {}){
  if(!force && !state.uiSoundsEnabled) return;
  if(document.hidden && !allowHidden) return;
  const ctx = getUiAudioContext();
  if(!ctx) return;
  const now = ctx.currentTime + .004;
  const sound = String(style || 'soft_tick');
  if(sound === 'success_chime'){
    uiBeep(ctx, now, {freq: 520, endFreq: 690, duration: .085, gain: .026, type: 'sine', filter: 4200});
    uiBeep(ctx, now + .082, {freq: 690, endFreq: 920, duration: .095, gain: .024, type: 'triangle', filter: 4600});
    uiBeep(ctx, now + .178, {freq: 920, endFreq: 1180, duration: .12, gain: .018, type: 'sine', filter: 5200});
  }else if(sound === 'queue_complete'){
    uiBeep(ctx, now, {freq: 220, endFreq: 160, duration: .09, gain: .022, type: 'sine', filter: 1200});
    uiBeep(ctx, now + .07, {freq: 620, endFreq: 840, duration: .11, gain: .026, type: 'triangle', filter: 4400});
    uiBeep(ctx, now + .18, {freq: 980, endFreq: 1240, duration: .14, gain: .02, type: 'sine', filter: 5400});
  }else if(sound === 'glass_click'){
    uiBeep(ctx, now, {freq: 940, endFreq: 1420, duration: .045, gain: .028, type: 'triangle', filter: 5400});
    uiBeep(ctx, now + .026, {freq: 1780, endFreq: 980, duration: .048, gain: .017, type: 'sine', filter: 6200});
  }else if(sound === 'neon_pop'){
    uiBeep(ctx, now, {freq: 520, endFreq: 1180, duration: .062, gain: .034, type: 'square', filter: 2600});
    uiBeep(ctx, now + .038, {freq: 1320, endFreq: 760, duration: .06, gain: .016, type: 'sine', filter: 4200});
  }else if(sound === 'deep_tap'){
    uiBeep(ctx, now, {freq: 160, endFreq: 92, duration: .075, gain: .045, type: 'sine', filter: 1200});
    uiBeep(ctx, now + .018, {freq: 620, endFreq: 420, duration: .042, gain: .016, type: 'triangle', filter: 2400});
  }else{
    uiBeep(ctx, now, {freq: 760, endFreq: 560, duration: .052, gain: .03, type: 'sine', filter: 3600});
  }
}

function playCompletionSound(kind = 'project'){
  if(!state.uiSoundsEnabled || !state.uiProjectDoneSoundEnabled) return;
  playUiSound(kind === 'queue' ? 'queue_complete' : 'success_chime', {allowHidden: true});
}

function shouldPlayUiSound(event){
  if(!state.uiSoundsEnabled) return false;
  const target = event.target;
  if(!(target instanceof HTMLElement)) return false;
  if(target.closest('[data-ui-sound-preview]')) return false;
  if(target.closest('.render-showcase')) return false;
  const interactive = target.closest('button,a.btn,input[type="checkbox"],input[type="radio"],select,.nav-item,.preset,.cta-card,.music-store-card');
  if(!interactive) return false;
  if(interactive.disabled || interactive.getAttribute('aria-disabled') === 'true') return false;
  return true;
}

async function prepareRenderNotification(){
  if(!('Notification' in window)) return;
  if(Notification.permission !== 'default') return;
  try{ await Notification.requestPermission(); }catch(_){}
}

function notifyRenderComplete(job){
  document.title = 'Glide Studio - Render concluído';
  playCompletionSound('project');
  if(!('Notification' in window) || Notification.permission !== 'granted') return;
  const delivery = job.delivery_summary || {};
  const body = delivery.mode === 'browser_download'
    ? `${job.output_name || 'MP4 final'} esta pronto e o download foi iniciado.`
    : `${job.output_name || 'MP4 final'} foi salvo em ${delivery.folder || job.output_dir || 'Downloads'}.`;
  try{
    new Notification('Glide Studio', {
      body,
      icon: '/assets/glide_studio_icon_256.png',
      silent: false,
    });
  }catch(_){}
}

function autoDownloadRender(job){
  if(!job?.download || state.autoDownloadedJobs.has(job.id)) return;
  if((job.delivery_summary?.mode || 'downloads') !== 'browser_download') return;
  state.autoDownloadedJobs.add(job.id);
  const a = document.createElement('a');
  a.href = `${job.download}?auto=1&t=${Date.now()}`;
  a.download = job.output_name || 'video.mp4';
  a.rel = 'noopener';
  a.style.display = 'none';
  document.body.appendChild(a);
  a.click();
  window.setTimeout(() => a.remove(), 1200);
}

async function runBackendPreflight(manifest, options){
  const fd = new FormData();
  fd.append('manifest', JSON.stringify(manifest));
  fd.append('options', JSON.stringify(options));
  const response = await fetch('/api/preflight', {method: 'POST', body: fd, cache: 'no-store'});
  if(!response.ok) throw new Error(await response.text());
  const payload = await response.json();
  state.backendPreflight = payload;
  renderAutoFixPlan(payload);
  updateIntelligenceV15({confidence: payload.confidence});
  if(payload?.ok === false){
    const detail = [...(payload.errors || []), ...(payload.warnings || [])].filter(Boolean).join('\n');
    throw new Error(detail || 'Preflight bloqueou o render.');
  }
  if(payload?.warnings?.length){
    renderLog.textContent = `Preflight:\n${payload.warnings.join('\n')}`;
  }
  if(payload?.turbo_summary?.enabled){
    const turbo = payload.turbo_summary;
    renderLog.textContent = [
      renderLog.textContent,
      `Turbo Produção: ${turbo.resolution} | ${turbo.bitrate_kbps} kbps | ${String(turbo.codec_requested || '').toUpperCase()} -> ${String(turbo.codec_effective || '').toUpperCase()} | ${turbo.encoder_effective}.`,
      `Suspensos somente neste render: ${(turbo.suspended_features || []).join(', ')}.`,
    ].filter(Boolean).join('\n');
  }
  return payload;
}

async function uploadOne(jobId, file, index, kind, total){
  const fd = new FormData();
  fd.append('file', file, rel(file));
  fd.append('rel', rel(file));
  fd.append('kind', kind);
  fd.append('index', String(index));
  const r = await fetch(`/api/upload-file/${jobId}`, {method: 'POST', body: fd, cache: 'no-store'});
  if(!r.ok) throw new Error(await r.text());
  const uploaded = index + 1;
  const pct = total ? (uploaded / total) * 10 : 5;
  setRenderStage('uploading');
  setRenderProgress(pct, 'Copiando para o motor local', `Arquivo ${uploaded}/${total}: ${file.name}`);
  renderLog.textContent = `Copia local em partes.\n${uploaded}/${total} arquivo(s) prontos.\nVoce pode minimizar o app; mantenha a janela aberta ate concluir.`;
  await new Promise(resolve => setTimeout(resolve, 0));
}

function buildRenderPayload(extraOptions = {}, projectSnapshot = null){
  const sourceFiles = projectSnapshot?.files || {
    videos: state.videos,
    audios: state.audios,
    backgroundTracks: state.backgroundTracks,
    subtitles: state.subtitles,
    captions: state.captions,
    scriptGuides: state.scriptGuides,
  };
  const sourceOptions = projectSnapshot?.options || null;
  const sourceVideos = [...(sourceFiles.videos || [])];
  const sourceAudios = [...(sourceFiles.audios || [])];
  const sourceBackground = [...(sourceFiles.backgroundTracks || [])];
  const sourceSubtitles = [...(sourceFiles.subtitles || [])];
  const sourceCaptions = [...(sourceFiles.captions || [])];
  const sourceScripts = [...(sourceFiles.scriptGuides || [])];
  const files = [...sourceVideos, ...sourceAudios, ...sourceBackground, ...sourceSubtitles, ...sourceCaptions, ...sourceScripts];
  const optionValue = (key, fallback) => (
    sourceOptions && Object.prototype.hasOwnProperty.call(sourceOptions, key)
      ? sourceOptions[key]
      : fallback
  );
  const snapshotCta = optionValue('ctaLanguage', optionValue('selectedCta', state.selectedCta));
  const snapshotMusicGenre = optionValue('musicGenre', optionValue('backgroundMusicGenre', state.musicGenre));
  const snapshotRenderPriority = normalizedRenderPriority(state.renderPriority);
  const smartDirectorEnabled = optionValue(
    'smartVisualDirector',
    smartVisualDirectorToggle ? smartVisualDirectorToggle.checked : true
  ) !== false;
  const manifest = files.map(file => ({
    name: file.name,
    rel: rel(file),
    kind: sourceVideos.includes(file)
      ? (isImage(file) ? 'image' : 'video')
      : (sourceAudios.includes(file)
        ? 'audio'
        : (sourceBackground.includes(file)
          ? 'background_music'
          : (sourceCaptions.includes(file) ? 'caption_srt' : (sourceScripts.includes(file) ? 'script_guide' : 'text_srt')))),
    size: file.size,
    lastModified: Number(file.lastModified || 0),
    ...(file._persistedProjectId && file._persistedStoredFile ? {
      persistedProjectId: file._persistedProjectId,
      persistedStoredFile: file._persistedStoredFile,
    } : {}),
    ...(file._persistedJobId && file._persistedIndex >= 0 ? {
      persistedJobId: file._persistedJobId,
      persistedIndex: file._persistedIndex,
    } : {}),
  }));
  const options = {
    mode: optionValue('mode', state.mode),
    ratio: optionValue('ratio', $('#ratioSelect')?.value || '16:9'),
    codec: optionValue('codec', $('#codecSelect')?.value || 'hevc'),
    exportProfile: optionValue('exportProfile', exportProfileSelect?.value || 'capcut_compact'),
    videoBitrateKbps: Number(optionValue('videoBitrateKbps', videoBitrateInput?.value || 2500)),
    rateControl: 'vbr',
    transitions: optionValue('transitions', $('#transitionSelect')?.value || 'off'),
    zoom: optionValue('zoom', $('#zoomSelect')?.value || 'off'),
    gpu: Boolean(optionValue('gpu', $('#gpuToggle')?.checked || false)),
    qualityBoost: optionValue('qualityBoost', qualityBoostToggle ? qualityBoostToggle.checked : true) !== false,
    smartVisualDirector: smartDirectorEnabled,
    styleSource: optionValue('styleSource', 'glide_package'),
    referenceStyleEnabled: Boolean(optionValue('referenceStyleEnabled', referenceStyleEnabledToggle ? referenceStyleEnabledToggle.checked : false)),
    referenceStyleVideo: optionValue('referenceStyleVideo', state.projects.find(item => item.id === state.activeProjectId)?.referenceStyleVideo || null),
    referenceStyleMode: optionValue('referenceStyleMode', referenceStyleModeSelect?.value === 'reference' ? 'reference' : 'inspiration') === 'reference' ? 'reference' : 'inspiration',
    visualLanguagePackage: optionValue('visualLanguagePackage', visualLanguagePackageSelect?.value || 'dark_doc'),
    styleIntensity: optionValue('styleIntensity', styleIntensitySelect?.value || 'balanced'),
    visualCleanFilter: true,
    visualFilterLevel: normalizedVisualFilterLevel(optionValue('visualFilterLevel', visualFilterLevelSelect?.value || 'normal')),
    adaptiveVisualFilter: Boolean(optionValue('adaptiveVisualFilter', adaptiveVisualFilterToggle?.checked || false)),
    voiceNormalize: optionValue('voiceNormalize', voiceNormalizeToggle ? voiceNormalizeToggle.checked : true) !== false,
    autoSoundFx: optionValue('autoSoundFx', autoSoundFxToggle ? autoSoundFxToggle.checked : true) !== false,
    allowAudioTrim: optionValue('allowAudioTrim', allowAudioTrimToggle ? allowAudioTrimToggle.checked : true) !== false,
    trimSilence: optionValue('trimSilence', trimSilenceToggle ? trimSilenceToggle.checked : true) !== false,
    dualExportShorts: Boolean(optionValue('dualExportShorts', dualExportShortsToggle ? dualExportShortsToggle.checked : false)),
    autoThumbnails: optionValue('autoThumbnails', autoThumbnailsToggle ? autoThumbnailsToggle.checked : true) !== false,
    videoOrder: sourceVideos.map(rel),
    imageOrder: sourceVideos.filter(isImage).map(rel),
    imageDefaultDurationSeconds: Number(optionValue('imageDefaultDurationSeconds', 4)) || 4,
    imageMotion: optionValue('imageMotion', 'auto_cinematic') || 'auto_cinematic',
    soundFxGainDb: Number(optionValue('soundFxGainDb', 2)) || 2,
    audioOrder: sourceAudios.map(rel),
    backgroundMusicOrder: sourceBackground.map(rel),
    backgroundMusicVolumeDb: Number(optionValue('backgroundMusicVolumeDb', backgroundVolumeValue())),
    backgroundMusicPreset: optionValue('backgroundMusicPreset', backgroundVolumePreset?.value || 'immersive'),
    backgroundMusicGenre: snapshotMusicGenre,
    backgroundMusicUseLibrary: sourceBackground.length === 0,
    backgroundMusicManualOverride: sourceBackground.length > 0,
    backgroundMusicPolicy: 'fit_voiceover_random_reuse',
    backgroundMusicDucking: true,
    projectTone: optionValue('projectTone', projectToneSelect?.value || 'auto'),
    adaptiveDucking: true,
    dynamicPauses: false,
    dynamicPauseIntensity: 'disabled',
    strongMomentEnhance: false,
    renderRecovery: optionValue('renderRecovery', renderRecoveryToggle ? renderRecoveryToggle.checked : true) !== false,
    directorDecisionMode: 'balanced',
    healthyRenderThreshold: Number(optionValue('healthyRenderThreshold', healthyThresholdInput?.value || 70)),
    renderBudgetEnabled: optionValue('renderBudgetEnabled', state.renderBudgetEnabled) !== false,
    renderBudgetTurboMultiplier: Number(optionValue('renderBudgetTurboMultiplier', 1.35)) || 1.35,
    renderBudgetEfficientMultiplier: Number(optionValue('renderBudgetEfficientMultiplier', 2.7)) || 2.7,
    platformMasterProfile: optionValue('platformMasterProfile', platformMasterProfileSelect?.value || 'youtube_long'),
    scoreVisualWindows: snapshotRenderPriority === 'quality' && optionValue('scoreVisualWindows', scoreVisualWindowsToggle ? scoreVisualWindowsToggle.checked : true) !== false,
    adaptiveQualityBoost: snapshotRenderPriority === 'quality' && optionValue('adaptiveQualityBoost', adaptiveQualityBoostToggle ? adaptiveQualityBoostToggle.checked : true) !== false,
    queueAutoTest: optionValue('queueAutoTest', queueAutoTestToggle ? queueAutoTestToggle.checked : true) !== false,
    autoDirector: smartDirectorEnabled,
    semanticVisualIndex: optionValue('semanticVisualIndex', semanticVisualIndexToggle ? semanticVisualIndexToggle.checked : true) !== false,
    channelLearning: optionValue('channelLearning', channelLearningToggle ? channelLearningToggle.checked : true) !== false,
    energyEditing: optionValue('energyEditing', energyEditingToggle ? energyEditingToggle.checked : true) !== false,
    antiRepeat: optionValue('antiRepeat', antiRepeatToggle ? antiRepeatToggle.checked : true) !== false,
    continuityMatch: false,
    continuityOutliersOnly: true,
    subtitleEditorialGrammar: true,
    audioMastering: optionValue('audioMastering', audioMasteringToggle ? audioMasteringToggle.checked : true) !== false,
    renderPriority: snapshotRenderPriority,
    renderExecutionProfile: snapshotRenderPriority === 'max'
      ? 'turbo_production'
      : (snapshotRenderPriority === 'quality' ? 'quality_max' : 'efficient_intelligent'),
    motionGraphicsPremium: snapshotRenderPriority === 'quality',
    turboPolicy: snapshotRenderPriority === 'max' ? 'production_max' : 'disabled',
    estimatedDurationSeconds: (() => {
      const durationMap = projectSnapshot?.durationMap instanceof Map ? projectSnapshot.durationMap : state.durations;
      const narration = sourceAudios.reduce((sum, file) => sum + (durationMap.get(rel(file)) || 0), 0);
      const videos = sourceVideos.reduce((sum, file) => sum + (durationMap.get(rel(file)) || (isImage(file) ? 4 : 0)), 0);
      return Math.max(0, narration || videos) + (optionValue('introMode', introModeSelect?.value || 'standard') === 'cinematic' ? 4 : 0);
    })(),
    introMode: optionValue('introMode', introModeSelect?.value || 'standard'),
    introDuration: 4,
    backgroundIntroVolumeDb: -20,
    voiceIntroFade: 0.45,
    introMusicFade: 0.55,
    introSubtitleStyle: optionValue('introSubtitleStyle', currentIntroSubtitleStyle()) || currentIntroSubtitleStyle(),
    subtitleOrder: sourceSubtitles.map(rel),
    textOrder: sourceSubtitles.map(rel),
    captionOrder: sourceCaptions.map(rel),
    scriptGuideOrder: sourceScripts.map(rel),
    scriptGuideInfo: optionValue('scriptGuideInfo', state.scriptGuideInfo) || null,
    scriptGuidePlan: optionValue('scriptGuidePlan', state.scriptGuidePlan) || null,
    textStyle: optionValue('textStyle', optionValue('subtitleStyle', currentSubtitleStyle())) || currentSubtitleStyle(),
    subtitleStyle: optionValue('textStyle', optionValue('subtitleStyle', currentSubtitleStyle())) || currentSubtitleStyle(),
    captionStyle: optionValue('captionStyle', currentCaptionStyle()) || currentCaptionStyle(),
    cinematicOpeningPolicy: 'auto_contextual',
    subtitleMinDuration: 6,
    subtitleConflictRule: 'longest_text',
    ctaLanguage: snapshotCta,
    ctaRequired: true,
    ctaPolicy: 'manual_position',
    ctaTimingPolicy: 'fixed_start_end',
    ctaPositionPreset: optionValue('ctaPositionPreset', state.ctaPositionPreset),
    ctaOffsetX: Number(optionValue('ctaOffsetX', state.ctaOffsetX)),
    ctaOffsetY: Number(optionValue('ctaOffsetY', state.ctaOffsetY)),
    durationPolicy: 'smart_fit_reuse',
    minSpeed: 0.80,
    outputName: String(optionValue('outputName', outputNameInput?.value || '') || '').trim(),
    finalOutputMode: optionValue('finalOutputMode', finalOutputMode?.value || state.finalOutputMode || 'downloads'),
    finalOutputFolder: optionValue('finalOutputFolder', finalOutputFolder?.value || state.finalOutputFolder || ''),
    ...extraOptions,
  };
  options.referenceStyleEnabled = Boolean(options.referenceStyleEnabled && options.referenceStyleVideo);
  options.styleSource = options.referenceStyleEnabled ? 'reference_dna' : 'glide_package';
  options.referenceStyleMode = options.referenceStyleMode === 'reference' ? 'reference' : 'inspiration';
  return {files, manifest, options};
}

async function startRender(context = {}){
  const projectSnapshot = context.projectSnapshot || null;
  const checkFiles = projectSnapshot?.files || {
    videos: state.videos,
    audios: state.audios,
    subtitles: state.subtitles,
    captions: state.captions,
  };
  const checkCta = projectSnapshot?.options?.ctaLanguage || projectSnapshot?.options?.selectedCta || state.selectedCta;
  const hasVisualMedia = (checkFiles.videos || []).length > 0;
  if(!hasVisualMedia || !(checkFiles.audios || []).length || !(checkFiles.subtitles || []).length || !checkCta){
    updateStats();
    throw new Error('Projeto incompleto: mídia visual (vídeos ou imagens), narração, Textos e CTA são obrigatórios para renderizar.');
  }
  if(!projectSnapshot) captureActiveProject();
  state.renderCancelRequested = false;
  const preserveMinimized = Boolean(context.queue && modal.classList.contains('minimized'));
  resetProgress({preserveMinimized});
  modal.classList.add('show');
  modal.setAttribute('aria-hidden', 'false');
  setRenderProjectMeta({
    projectName: context.projectName || state.projects.find(item => item.id === (context.projectId || state.activeProjectId))?.name || '',
    queueIndex: context.queueIndex || 0,
    status: context.queue ? 'Preparando fila' : 'Render único',
  });
  prepareRenderNotification();
  document.title = context.queue ? `Glide Studio - Fila ${context.queueIndex || ''}` : 'Glide Studio - Renderizando';

  const {files, manifest, options} = buildRenderPayload({
    queueBatchId: context.batchId || '',
    queueProjectId: context.projectId || state.activeProjectId || '',
    queueProjectName: context.projectName || state.projects.find(item => item.id === state.activeProjectId)?.name || '',
    queueProjectIndex: context.queueIndex || 0,
    sampleRender: Boolean(context.sampleRender),
    smartSampleBlocks: Boolean(context.smartSampleBlocks),
    previewDurationSeconds: context.previewDurationSeconds || 30,
    ...(context.safeRender ? {
      safeRenderMode: true,
      codec: 'h264',
      gpu: false,
      transitions: 'off',
      zoom: 'off',
      qualityBoost: false,
      smartVisualDirector: false,
      autoDirector: false,
      visualCleanFilter: true,
      visualFilterLevel: 'light',
      adaptiveVisualFilter: false,
      dynamicPauses: false,
      strongMomentEnhance: false,
      renderRecovery: true,
    } : {safeRenderMode: false}),
  }, projectSnapshot);
  const renderLabel = renderPriorityLabel(options.renderPriority);
  setRenderProjectMeta({
    projectName: context.projectName || options.queueProjectName || options.projectName || options.outputName || '',
    queueIndex: context.queueIndex || 0,
    renderLabel,
    status: 'Validando',
  });

  try{
    setRenderStage('preparing');
    setRenderProgress(0, context.sampleRender ? 'Preflight da amostra' : 'Preflight local', `Render: ${renderLabel}. Validando CTA, áudio, Textos, Legendas, música e políticas antes de copiar arquivos.`);
    await runBackendPreflight(manifest, options);
    const budgetResponse = await fetch('/api/render-estimate', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        durationSeconds: options.estimatedDurationSeconds || currentTimelineDuration(),
        options,
      }),
      cache: 'no-store',
    });
    if(!budgetResponse.ok) throw new Error(await budgetResponse.text());
    const budgetPayload = cleanDisplayData(await budgetResponse.json());
    const budgetEstimate = options.renderPriority === 'max'
      ? budgetPayload.max
      : (options.renderPriority === 'quality' ? (budgetPayload.quality || budgetPayload.balanced) : budgetPayload.balanced);
    if(budgetEstimate?.budget_feasible === false){
      throw new Error(
        `${renderLabel} bloqueado antes do render: mínimo previsto ${formatTime(budgetEstimate.minimum_required_seconds || 0)}, `
        + `limite ${formatTime(budgetEstimate.budget_seconds || 0)}. Use um codec por hardware ou prepare o cache.`
      );
    }
    setRenderProgress(0, 'Criando projeto local', 'Preparando pasta exports/render_...');
    const createFd = new FormData();
    createFd.append('manifest', JSON.stringify(manifest));
    createFd.append('options', JSON.stringify(options));
    const createResp = await fetch('/api/create-render-job', {method: 'POST', body: createFd, cache: 'no-store'});
    if(!createResp.ok) throw new Error(await createResp.text());
    const created = await createResp.json();
    state.activeJobId = created.job_id;
    state.outputDir = created.export_dir || '';
    const activeProject = state.projects.find(item => item.id === (context.projectId || state.activeProjectId));
    if(activeProject){
      activeProject.backendJobId = state.activeJobId;
      syncProjectSnapshot(activeProject, {immediate: true});
    }
    setRenderActive(true);
    localStorage.setItem('glide_active_job', state.activeJobId);
    localStorage.setItem('glide_active_output_dir', state.outputDir);
    outputPath.textContent = '';
    openOutputBtn.classList.remove('hidden');

    for(let i = 0; i < files.length; i++){
      if(state.renderCancelRequested){
        await cancelCurrentRender({silent: true});
        throw new Error('Render cancelado pelo usuário.');
      }
      if(files[i]._persisted){
        const ready = i + 1;
        setRenderStage('uploading');
        setRenderProgress(
          files.length ? (ready / files.length) * 10 : 5,
          'Reutilizando mídia preservada',
          `Arquivo ${ready}/${files.length}: ${files[i].name}`,
        );
        continue;
      }
      await uploadOne(state.activeJobId, files[i], i, manifest[i].kind, files.length);
    }

    setRenderStage('rendering');
    setRenderProgress(10, 'Render iniciado', `Render ${renderLabel} iniciado em segundo plano.`);
    const launchResp = await fetch(`/api/launch-render/${state.activeJobId}`, {method: 'POST', cache: 'no-store'});
    if(!launchResp.ok) throw new Error(await launchResp.text());
    renderLog.textContent += `\n\nJob: ${state.activeJobId}\nRender: ${renderLabel}\nPasta tecnica: ${state.outputDir || 'exports/render_...'}\nDestino final: ${finalOutputMode?.selectedOptions?.[0]?.textContent || 'Downloads'}`;
    return await pollStatus(state.activeJobId, context);
  }catch(e){
    setRenderActive(false);
    const cancelled = /cancelado/i.test(e.message || '');
    renderTitle.textContent = cancelled ? 'Render cancelado' : 'Erro ao iniciar render';
    setRenderStage(cancelled ? 'cancelled' : 'error');
    renderMsg.textContent = cleanDisplayText(e.message);
    renderLog.textContent = cleanDisplayText(e.stack || String(e));
    if(cancelled){
      const project = state.projects.find(item => item.id === (context.projectId || state.activeProjectId));
      if(project){
        project.status = 'cancelled';
        project.backendJobId = state.activeJobId || project.backendJobId || '';
        project.error = 'Render cancelado pelo usuário.';
        syncProjectSnapshot(project);
        renderProjectQueue();
      }
      localStorage.removeItem('glide_active_job');
    }else{
      const project = state.projects.find(item => item.id === (context.projectId || state.activeProjectId));
      if(project){
        project.status = 'error';
        project.error = e.message || String(e);
        project.lastRenderSummary = renderErrorSummary(project.error, {
          renderPriority: project.options?.renderPriority || state.renderPriority,
          outputName: project.outputName || project.name,
          outputDir: project.outputDir || '',
        });
        syncProjectSnapshot(project);
        renderProjectQueue();
      }
    }
    throw e;
  }
}

async function pollStatus(jobId, context = {}){
  let done = false;
  while(!done){
    try{
      const r = await fetch(`/api/status/${jobId}?ts=${Date.now()}`, {cache: 'no-store'});
      if(!r.ok) throw new Error(await r.text());
      const j = cleanDisplayData(await r.json());
      const activeProjectFromStatus = j.project_id || j.queueProjectId || j.queue_project_id || context.projectId || '';
      if(activeProjectFromStatus) activateRenderingProject(activeProjectFromStatus);
      setRenderProjectMeta({
        projectName: j.queueProjectName || context.projectName || state.projects.find(item => item.id === activeProjectFromStatus)?.name || '',
        queueIndex: context.queueIndex || 0,
        renderLabel: renderPriorityLabel(j.render_priority_effective || context.projectSnapshot?.options?.renderPriority || state.renderPriority),
        status: j.stage_label || j.stage || '',
      });
      const pct = Math.max(0, Math.min(100, j.percent || 0));
      progressBar.style.width = pct + '%';
      eyePercent.textContent = Math.round(pct) + '%';
      renderMsg.textContent = cleanDisplayText(j.message || '');
      if(renderEta && j.eta_summary){
        renderEta.textContent = formatEtaSummary(j.eta_summary, j.status);
      }
      setRenderStage(j.stage || 'rendering');
      if(j.output_dir){
        state.outputDir = j.output_dir;
        outputPath.textContent = '';
        openOutputBtn.classList.remove('hidden');
      }
      const extra = [];
      if(j.status === 'running') extra.push('Render ativo. O app pode ficar minimizado; não feche a janela.');
      if(j.render_priority_effective) extra.push(`Render: ${renderPriorityLabel(j.render_priority_effective)}${j.gpu_enabled ? ' + GPU' : ''}.`);
      if(j.turbo_summary?.enabled){
        const turbo = j.turbo_summary;
        extra.push(`Turbo: ${turbo.resolution}, ${turbo.bitrate_kbps} kbps, ${String(turbo.codec_effective || '').toUpperCase()}, ${turbo.encoder_effective}.`);
        if(turbo.codec_fallback) extra.push('Turbo: HEVC solicitado convertido temporariamente para H.264 CPU ultrafast.');
        if(turbo.unified_composition) extra.push('Turbo: CTA + Textos + Legendas em uma passagem visual; 1 reencode completo evitado.');
        if(turbo.fallback_used) extra.push('Turbo: composição unificada usou fallback compatível neste equipamento.');
      }
      if(j.render_priority_effective !== 'max' && j.timeline_summary?.unified_final_composition){
        extra.push('Eficiente otimizado: CTA + Textos + Legendas em uma passagem final, mantendo todos os efeitos.');
      }
      if(j.timeline_summary?.playback_speed) extra.push(`Velocidade: ${j.timeline_summary.playback_speed}x | clipes reutilizados: ${j.timeline_summary.reused_segments || 0}`);
      if(j.timeline_summary?.quality_boost) extra.push('Quality Boost natural aplicado aos clipes.');
      if(j.intro_summary?.mode === 'cinematic') extra.push(`Intro Cinematic: voz em ${j.intro_summary.voice_delay || 3}s; duração final ${formatTime(j.intro_summary.timeline_duration || 0)}.`);
      if(j.audio_health_summary?.status && j.audio_health_summary.status !== 'ok') extra.push(`Áudio: ${j.audio_health_summary.message || 'verifique lacunas'}`);
      if(j.preflight_summary?.voice_normalize) extra.push('Voz nivelada para manter volume consistente.');
      if(j.preflight_summary?.videos_invalid) extra.push(`Pré-checagem: ${j.preflight_summary.videos_invalid} vídeo(s) inválido(s) ignorado(s).`);
      if(j.timeline_summary?.visual_clean_summary?.enabled){
        const clean = j.timeline_summary.visual_clean_summary;
        applyVisualCleanStatusFromSummary(clean);
        extra.push(`Filtro visual: ${clean.hard_rejected || 0} removido(s), ${clean.soft_demoted || 0} rebaixado(s), ${clean.fallback_used || 0} fallback.`);
      }else if(j.preflight_summary?.visual_clean_filter?.enabled){
        extra.push('Filtro visual inteligente ativo.');
      }
      if(j.cta_summary?.enabled) extra.push(`CTA: ${j.cta_summary.label || j.cta_summary.language} em ${j.cta_summary.occurrences || 0} ponto(s)`);
      if(j.subtitle_summary?.valid) extra.push(`Legendas aplicadas: ${j.subtitle_summary.valid}`);
      if(j.background_music_summary?.enabled) extra.push(`Música: ${j.background_music_summary.used_segments || 0} trecho(s) em ${j.background_music_summary.volume_db || -30} dB${j.background_music_summary.ducking ? ' + ducking' : ''}`);
      if(j.emotion_summary?.tone) extra.push(`Tom musical: ${j.emotion_summary.tone} (${j.emotion_summary.mode || 'auto'}).`);
      if(j.ducking_summary?.adaptive) extra.push(`Ducking profissional: base ${j.ducking_summary.base_db} dB, pausas até ${j.ducking_summary.pause_ceiling_db} dB.`);
      if(j.strong_moments_summary?.count) extra.push(`Ênfases editoriais dos Textos: ${j.strong_moments_summary.count}.`);
      if(j.recovery_summary?.attempt) extra.push(`Recuperacao ativa: tentativa ${j.recovery_summary.attempt}/4.`);
      if(j.sound_fx_summary?.enabled) extra.push(`Sound FX: ${j.sound_fx_summary.events || 0} efeito(s) automáticos imersivos com ducking.`);
      if(j.director_summary?.enabled) extra.push(`Diretor: ${j.director_summary.blocks?.length || 0} bloco(s), timeline ${j.director_summary.reordered ? 'reorganizada' : 'mantida'}.`);
      if(j.audio_master_summary?.enabled) extra.push(`Master: ${j.audio_master_summary.output_lufs ?? '-14'} LUFS, pico ${j.audio_master_summary.output_true_peak_dbtp ?? '-1'} dBTP.`);
      updateIntelligenceV15(j);
      const paintKey = `${Math.round(pct)}:${j.stage || ''}:${j.status || ''}:${j.message || ''}`;
      const now = Date.now();
      const shouldPaintLog = !state.lastStatusPaint
        || state.lastStatusPaint.key !== paintKey
        || now - state.lastStatusPaint.at > 1800
        || j.status === 'done'
        || j.status === 'error';
      if(shouldPaintLog){
        const logs = (j.log || []).slice(-18).join('\n');
        renderLog.textContent = `${extra.join('\n')}\n${logs}`.trim();
        renderLog.scrollTop = renderLog.scrollHeight;
        state.lastStatusPaint = {key: paintKey, at: now};
      }
      if(j.status === 'done'){
        if(!renderDoneIsValidated(j)){
          done = true;
          setRenderActive(false);
          setRenderStage('error');
          document.title = 'Glide Studio - Saída não confirmada';
          renderTitle.textContent = 'Arquivo final não confirmado';
          const closeBtn = $('#closeModal');
          if(closeBtn) closeBtn.textContent = 'Fechar';
        renderMsg.textContent = cleanDisplayText(outputValidationError(j));
          const project = state.projects.find(item => item.id === (context.projectId || state.activeProjectId));
          if(project){
            project.status = 'error';
            project.backendJobId = j.id;
            project.error = renderMsg.textContent;
            syncProjectSnapshot(project);
            renderProjectQueue();
          }
          localStorage.removeItem('glide_active_job');
          return {...j, status: 'error', error: renderMsg.textContent};
        }
        done = true;
        setRenderActive(false);
        setRenderStage('done');
        renderTitle.textContent = 'Render concluído';
        const closeBtn = $('#closeModal');
        if(closeBtn) closeBtn.textContent = 'Fechar';
        const delivery = j.delivery_summary || {};
        renderMsg.textContent = delivery.mode === 'browser_download'
          ? 'MP4 final pronto para download do navegador.'
          : 'MP4 final salvo na pasta definida.';
        progressBar.style.width = '100%';
        eyePercent.textContent = '100%';
        downloadBtn.href = j.download;
        downloadBtn.setAttribute('download', j.output_name || 'video.mp4');
        downloadBtn.textContent = `Baixar ${j.output_name || 'MP4'}`;
        downloadBtn.classList.remove('hidden');
        openOutputBtn.classList.remove('hidden');
        const project = state.projects.find(item => item.id === (context.projectId || state.activeProjectId));
        if(project){
          const visualPayload = await loadVisualAnalysisDetails(j.id);
          project.status = j.recovery_summary?.recovered ? 'recovered' : 'done';
          project.backendJobId = j.id;
          project.outputDir = j.output_dir || '';
          project.outputFile = j.output_name || '';
          project.error = '';
          project.lastRenderSummary = lastRenderSummaryFromJob(j, visualPayload);
          project.visualAnalysisDetails = project.lastRenderSummary.visualCleanDetails;
          project.directorState = j.director_summary || project.directorState;
          project.confidenceSummary = j.confidence_summary || project.confidenceSummary;
          project.audioMasterSummary = j.audio_master_summary || project.audioMasterSummary;
          project.renderGraphRun = j.render_graph_run || project.renderGraphRun;
          const directedOrder = j.director_summary?.video_order;
          if(Array.isArray(directedOrder) && directedOrder.length){
            const byRel = new Map((project.files?.videos || []).map(file => [rel(file), file]));
            const ordered = directedOrder.map(key => byRel.get(key)).filter(Boolean);
            ordered.push(...(project.files?.videos || []).filter(file => !ordered.includes(file)));
            project.files.videos = ordered;
            if(project.id === state.activeProjectId){
              state.videos = [...ordered];
              renderLists();
            }
          }
          if(visualPayload?.summary && project.id === state.activeProjectId) applyVisualCleanStatusFromSummary(visualPayload.summary);
          updateIntelligenceV15(project.lastRenderSummary);
          syncProjectSnapshot(project);
          renderProjectQueue();
        }
        autoDownloadRender(j);
        notifyRenderComplete(j);
        localStorage.removeItem('glide_active_job');
        return j;
      }else if(j.status === 'cancelled'){
        done = true;
        setRenderActive(false);
        setRenderStage('cancelled');
        document.title = 'Glide Studio - Render cancelado';
        renderTitle.textContent = 'Render cancelado';
        const closeBtn = $('#closeModal');
        if(closeBtn) closeBtn.textContent = 'Fechar';
        renderMsg.textContent = cleanDisplayText(j.error || 'Render cancelado pelo usuário.');
        const project = state.projects.find(item => item.id === (context.projectId || state.activeProjectId));
        if(project){
          project.status = 'cancelled';
          project.backendJobId = j.id;
          project.error = j.error || 'Render cancelado pelo usuário.';
          syncProjectSnapshot(project);
          renderProjectQueue();
        }
        localStorage.removeItem('glide_active_job');
        return j;
      }else if(j.status === 'error'){
        done = true;
        setRenderActive(false);
        setRenderStage('error');
        document.title = 'Glide Studio - Erro no render';
        renderTitle.textContent = 'Erro no render';
        const closeBtn = $('#closeModal');
        if(closeBtn) closeBtn.textContent = 'Fechar';
        renderMsg.textContent = j.error || 'Erro desconhecido';
        const project = state.projects.find(item => item.id === (context.projectId || state.activeProjectId));
        if(project){
          project.status = 'error';
          project.backendJobId = j.id;
          project.error = j.error || 'Erro desconhecido';
          syncProjectSnapshot(project);
          renderProjectQueue();
        }
        return j;
      }
    }catch(e){
      renderMsg.textContent = 'Aguardando motor local...';
    }
    if(!done){
      const pollDelay = modal.classList.contains('minimized') ? 2800 : 1700;
      await new Promise(resolve => setTimeout(resolve, pollDelay));
    }
  }
}

async function resumeActiveJob(){
  const jobId = localStorage.getItem('glide_active_job');
  if(!jobId) return;
  try{
    const r = await fetch(`/api/status/${jobId}?ts=${Date.now()}`, {cache: 'no-store'});
    if(!r.ok){
      localStorage.removeItem('glide_active_job');
      return;
    }
    const j = await r.json();
    if(['running', 'ready', 'uploading'].includes(j.status)){
      state.activeJobId = jobId;
      setRenderActive(true);
      resetProgress();
      modal.classList.add('show');
      modal.setAttribute('aria-hidden', 'false');
      const closeBtn = $('#closeModal');
      if(closeBtn) closeBtn.textContent = 'Minimizar';
      renderTitle.textContent = 'Render local encontrado';
      pollStatus(jobId);
    }else if(['done', 'error', 'cancelled'].includes(j.status)){
      localStorage.removeItem('glide_active_job');
    }
  }catch(e){
    localStorage.removeItem('glide_active_job');
  }
}

async function openOutput(){
  const jobId = state.activeJobId || localStorage.getItem('glide_active_job');
  if(!jobId) return;
  const r = await fetch(`/api/open-output/${jobId}`, {method: 'POST', cache: 'no-store'});
  if(!r.ok) renderMsg.textContent = 'Não foi possível abrir a pasta de saída.';
}

async function openExports(){
  const r = await fetch('/api/open-exports', {method: 'POST', cache: 'no-store'});
  if(!r.ok) dockSummary.textContent = 'Não foi possível abrir a pasta exports.';
}

function requestQueuePause(){
  if(!state.queueRendering) return;
  state.queuePauseRequested = true;
  dockSummary.textContent = 'Pausa solicitada: o Glide terminara este projeto e aguardara.';
  renderProjectQueue();
}

async function cancelCurrentRender({silent = false} = {}){
  state.renderCancelRequested = true;
  state.queueStopRequested = true;
  state.queuePauseRequested = true;
  if(stopRenderBtn){
    stopRenderBtn.disabled = true;
    stopRenderBtn.textContent = 'Parando...';
  }
  if(stopQueueBtn) stopQueueBtn.disabled = true;
  if(!silent){
    renderTitle.textContent = 'Cancelando render';
    renderMsg.textContent = 'Encerrando FFmpeg e marcando o projeto como cancelado...';
    dockSummary.textContent = 'Render cancelado pelo usuário.';
  }
  const jobId = state.activeJobId || localStorage.getItem('glide_active_job');
  if(!jobId) return null;
  try{
    const response = await fetch(`/api/cancel-render/${jobId}`, {method: 'POST', cache: 'no-store'});
    if(!response.ok) throw new Error(await response.text());
    return await response.json();
  }catch(error){
    if(!silent) renderMsg.textContent = `Não foi possível cancelar pelo backend: ${error.message || error}`;
    return null;
  }finally{
    renderProjectQueue();
  }
}

function clearRuntimeReportFields(project){
  if(!project) return;
  project.backendJobId = '';
  project.outputDir = '';
  project.outputFile = '';
  project.error = '';
  project.estimatedSize = 0;
  project.lastRenderSummary = null;
  project.visualAnalysisDetails = null;
  project.renderGraphRun = null;
  project.confidenceSummary = null;
  project.audioMasterSummary = null;
  project.directorState = null;
  project.timelineHistory = [];
  project.retryCount = 0;
  project.retryHistory = [];
}

function resetProjectState(){
  state.videos = [];
  state.audios = [];
  state.backgroundTracks = [];
  state.subtitles = [];
  state.captions = [];
  state.scriptGuides = [];
  state.subtitleInfo = null;
  state.captionInfo = null;
  state.scriptGuideInfo = null;
  state.scriptGuidePlan = null;
  state.registry.clear();
  state.durations.clear();
  state.durationSources.clear();
  state.audioHealth.clear();
  state.thumbs.clear();
  state.mediaStatus.clear();
  state.videoOrderEdited = false;
  state.audioOrderEdited = false;
  state.backgroundOrderEdited = false;
  state.activeJobId = null;
  state.outputDir = '';
  const project = state.projects.find(item => item.id === state.activeProjectId);
  if(project){
    project.files = emptyProjectFiles();
    project.maps = emptyProjectMaps();
    project.subtitleInfo = null;
    project.captionInfo = null;
    project.scriptGuideInfo = null;
    project.scriptGuidePlan = null;
    project.outputName = outputNameInput?.value || project.outputName || '';
    clearRuntimeReportFields(project);
    project.status = 'draft';
    project.updatedAt = Date.now();
    syncProjectSnapshot(project);
  }
  localStorage.removeItem('glide_active_job');
  localStorage.removeItem('glide_active_output_dir');
  if(outputPath) outputPath.textContent = '';
  if(openOutputBtn) openOutputBtn.classList.add('hidden');
  if(downloadBtn) downloadBtn.classList.add('hidden');
  renderLists();
  refreshSubtitleInfo();
  refreshCaptionInfo();
  updateMusicGenreUi();
  updateStats();
}

function automatorSortPreference(type){
  const saved = state.automator.sort?.[type] || {};
  return {
    criterion: saved.criterion || 'smart',
    direction: saved.direction === 'desc' ? 'desc' : 'asc',
  };
}

function saveAutomatorSortPreferences(){
  try{
    localStorage.setItem('glide_auto_sort_preferences', JSON.stringify(state.automator.sort || {}));
  }catch(_){}
}

function annotateAutomatorItems(items, batchStamp = Date.now()){
  items.forEach((item, index) => {
    if(item._autoImportedAt == null) item._autoImportedAt = batchStamp;
    if(item._autoSelectionIndex == null) item._autoSelectionIndex = index;
    if(item._autoUsageIndex == null) item._autoUsageIndex = index;
  });
  return items;
}

function automatorNaturalNumber(item){
  const text = String(item?.name || item?.sourceName || '');
  const matches = [...text.matchAll(/(\d+)/g)];
  return matches.length ? Number(matches[matches.length - 1][1]) : null;
}

function automatorDuration(item, type){
  if(type === 'folder'){
    return (item?.files || []).reduce((sum, file) => sum + (secondsFromClipStamp(file.name) || Number(file._autoDuration || 0)), 0);
  }
  if(type === 'image') return 4;
  return Number(item?._autoDuration || state.durations.get(rel(item)) || secondsFromClipStamp(item?.name || '') || 0);
}

function applySmartExplorerOrder(items){
  const ordered = [...items];
  const numbered = ordered.map(item => automatorNaturalNumber(item)).filter(Number.isFinite);
  const reliable = ordered.length > 0
    && numbered.length / ordered.length >= 0.70
    && new Set(numbered).size === numbered.length;
  if(reliable){
    ordered.sort((a, b) => {
      const av = automatorNaturalNumber(a);
      const bv = automatorNaturalNumber(b);
      if(Number.isFinite(av) && Number.isFinite(bv) && av !== bv) return av - bv;
      return naturalCompare(a, b);
    });
  }else{
    ordered.reverse();
  }
  return ordered;
}

function sortAutomatorItems(type, criterion = null, direction = null){
  const list = automatorItems(type);
  if(!list.length){
    updateAutomatorPreview();
    return;
  }
  const current = automatorSortPreference(type);
  const next = {
    criterion: criterion || current.criterion,
    direction: direction || current.direction,
  };
  let ordered = [...list];
  if(next.criterion === 'smart'){
    ordered = applySmartExplorerOrder(ordered);
  }else if(next.criterion === 'name'){
    ordered.sort(naturalCompare);
  }else if(next.criterion === 'type'){
    ordered.sort((a, b) => {
      const ae = String(a?.name || '').split('.').pop().toLowerCase();
      const be = String(b?.name || '').split('.').pop().toLowerCase();
      return ae.localeCompare(be) || naturalCompare(a, b);
    });
  }else if(next.criterion === 'duration'){
    ordered.sort((a, b) => automatorDuration(a, type) - automatorDuration(b, type) || naturalCompare(a, b));
  }else if(next.criterion === 'imported'){
    ordered.sort((a, b) => Number(a._autoImportedAt || 0) - Number(b._autoImportedAt || 0)
      || Number(a._autoSelectionIndex || 0) - Number(b._autoSelectionIndex || 0));
  }else{
    ordered.sort((a, b) => Number(a._autoUsageIndex || 0) - Number(b._autoUsageIndex || 0));
  }
  if(next.direction === 'desc') ordered.reverse();
  list.splice(0, list.length, ...ordered);
  state.automator.sort[type] = next;
  saveAutomatorSortPreferences();
  updateAutomatorPreview();
}

async function hydrateAutomatorDurations(type, items){
  if(!['audio', 'music', 'reference'].includes(type)) return;
  const pending = items.filter(item => !Number(item._autoDuration || 0));
  await runPool(pending, 2, async item => {
    try{
      const info = await durationOf(item);
      item._autoDuration = Number(info?.seconds || 0);
    }catch(_){
      item._autoDuration = 0;
    }
  });
  if(automatorSortPreference(type).criterion === 'duration') sortAutomatorItems(type);
}

function automatorFolderGroups(fileList){
  const rootFiles = new Map();
  const childFiles = new Map();
  const roots = new Set();
  const looseFiles = [];
  Array.from(fileList || []).forEach(file => {
    const kind = kindOfFile(file, 'video');
    if(kind !== 'video' && kind !== 'image') return;
    const path = file._autoRelativePath || file.webkitRelativePath || file.name || '';
    const parts = path.split(/[\\/]/).filter(Boolean);
    if(parts.length < 2){
      looseFiles.push(file);
      return;
    }
    const root = parts[0];
    roots.add(root);
    if(!rootFiles.has(root)) rootFiles.set(root, []);
    rootFiles.get(root).push(file);
    if(parts.length === 2) return;
    const child = `${root}/${parts[1]}`;
    if(!childFiles.has(child)) childFiles.set(child, []);
    childFiles.get(child).push(file);
  });
  const directRootVideoCount = Array.from(fileList || []).filter(file => {
    const kind = kindOfFile(file, 'video');
    const parts = String(file._autoRelativePath || file.webkitRelativePath || file.name || '').split(/[\\/]/).filter(Boolean);
    return (kind === 'video' || kind === 'image') && parts.length === 2;
  }).length;
  const shouldSplitSingleParent = roots.size === 1 && directRootVideoCount === 0 && childFiles.size > 1;
  const sourceGroups = shouldSplitSingleParent ? childFiles : rootFiles;
  const result = Array.from(sourceGroups.entries()).map(([name, files]) => {
    const visibleName = name.split('/').filter(Boolean).pop() || name || 'Pasta';
    files.sort((a, b) => naturalCompare(a._autoRelativePath || a.webkitRelativePath || a.name, b._autoRelativePath || b.webkitRelativePath || b.name));
    let totalSize = 0;
    let newest = 0;
    files.forEach(file => {
      totalSize += Number(file.size || 0);
      newest = Math.max(newest, Number(file.lastModified || 0));
    });
    const first = files[0]?.name || '';
    const last = files[files.length - 1]?.name || '';
    const signature = `${name}|${files.length}|${totalSize}|${newest}|${first}|${last}`;
    return {
      name: visibleName,
      sourceName: name,
      signature,
      files,
      _autoImportedAt: Date.now(),
      _autoSelectionIndex: 0,
      _autoUsageIndex: 0,
    };
  }).filter(group => group.files.length);

  if(looseFiles.length){
    looseFiles.sort((a, b) => naturalCompare(a._autoRelativePath || a.webkitRelativePath || a.name, b._autoRelativePath || b.webkitRelativePath || b.name));
    let totalSize = 0;
    let newest = 0;
    looseFiles.forEach(file => {
      totalSize += Number(file.size || 0);
      newest = Math.max(newest, Number(file.lastModified || 0));
    });
    const first = looseFiles[0]?.name || '';
    const last = looseFiles[looseFiles.length - 1]?.name || '';
    const name = 'Mídia Avulsa';
    const signature = `${name}|${looseFiles.length}|${totalSize}|${newest}|${first}|${last}`;
    result.push({
      name,
      sourceName: name,
      signature,
      files: looseFiles,
      _autoImportedAt: Date.now(),
      _autoSelectionIndex: 0,
      _autoUsageIndex: 0,
    });
  }

  return result;
}

function appendAutomatorFolders(fileList){
  const incoming = automatorFolderGroups(fileList);
  if(!incoming.length) return 0;
  const existing = new Set(state.automator.folders.map(folder => folder.signature || `${folder.name}:${folder.files?.length || 0}`));
  let added = 0;
  annotateAutomatorItems(incoming, Date.now()).forEach(folder => {
    const signature = folder.signature || `${folder.name}:${folder.files?.length || 0}`;
    if(existing.has(signature)) return;
    state.automator.folders.push(folder);
    existing.add(signature);
    added += 1;
  });
  return added;
}

function automatorReadDirectoryEntry(directoryEntry, prefix = ''){
  const reader = directoryEntry.createReader();
  const entries = [];
  return new Promise((resolve, reject) => {
    const readBatch = () => {
      reader.readEntries(batch => {
        if(!batch.length){
          resolve(entries);
          return;
        }
        entries.push(...batch);
        readBatch();
      }, reject);
    };
    readBatch();
  }).then(async allEntries => {
    const files = [];
    for(const entry of allEntries){
      const nextPath = `${prefix}${directoryEntry.name}/${entry.name}`;
      if(entry.isDirectory){
        files.push(...await automatorReadDirectoryEntry(entry, `${prefix}${directoryEntry.name}/`));
      }else if(entry.isFile){
        const file = await new Promise((resolve, reject) => entry.file(resolve, reject));
        file._autoRelativePath = nextPath;
        files.push(file);
      }
    }
    return files;
  });
}

async function automatorFilesFromDrop(dataTransfer){
  const files = [];
  const items = Array.from(dataTransfer?.items || []);
  if(items.length && items.some(item => typeof item.webkitGetAsEntry === 'function')){
    for(const item of items){
      const entry = item.webkitGetAsEntry?.();
      if(!entry) continue;
      if(entry.isDirectory){
        files.push(...await automatorReadDirectoryEntry(entry));
      }else if(entry.isFile){
        const file = await new Promise((resolve, reject) => entry.file(resolve, reject));
        file._autoRelativePath = file.name;
        files.push(file);
      }
    }
    return files;
  }
  return Array.from(dataTransfer?.files || []);
}

function automatorItems(type){
  if(type === 'srt') return state.automator.srts;
  if(type === 'audio') return state.automator.audios;
  if(type === 'script') return state.automator.scripts;
  if(type === 'folder') return state.automator.folders;
  return [];
}

function removeAutomatorItem(type, index){
  const numIndex = Number(index);
  if(isNaN(numIndex) || numIndex < 0) return;
  if(type === 'srt' && numIndex < state.automator.srts.length){
    state.automator.srts.splice(numIndex, 1);
  }else if(type === 'audio' && numIndex < state.automator.audios.length){
    state.automator.audios.splice(numIndex, 1);
  }else if(type === 'script' && numIndex < state.automator.scripts.length){
    state.automator.scripts.splice(numIndex, 1);
  }else if(type === 'folder' && numIndex < state.automator.folders.length){
    state.automator.folders.splice(numIndex, 1);
  }
  updateAutomatorPreview();
}

function clearAutomatorList(type){
  if(type === 'srt') state.automator.srts = [];
  else if(type === 'audio') state.automator.audios = [];
  else if(type === 'script') state.automator.scripts = [];
  else if(type === 'folder') state.automator.folders = [];
  updateAutomatorPreview();
}

function automatorItemLabel(item, type){
  if(!item) return '-';
  if(type === 'folder') return `${item.name || 'Pasta'} (${Number(item.files?.length || 0)} ficheiro(s))`;
  return item.name || '-';
}

function renderAutomatorList(type, title, items){
  const empty = type === 'folder' ? 'Nenhuma pasta selecionada' : 'Nenhum ficheiro selecionado';
  const preference = automatorSortPreference(type);
  const selected = value => preference.criterion === value ? ' selected' : '';
  const clearBtnHtml = items.length ? `<button type="button" class="automation-sort-clear" data-automator-clear="${type}" title="Limpar todos os ${escapeHtml(title)}">Limpar</button>` : '';
  return `
    <section class="automation-sort-list" data-automator-list="${type}">
      <div class="automation-sort-head">
        <div class="automation-sort-head-top">
          <h3>${escapeHtml(title)}</h3>
          <div class="automation-sort-head-actions">
            <span class="automation-sort-badge">${items.length}</span>
            ${clearBtnHtml}
          </div>
        </div>
        <div class="automation-sort-head-controls">
          <select class="automation-sort-select" data-automator-sort="${type}" aria-label="Ordenar ${escapeHtml(title)}">
            <option value="smart"${selected('smart')}>Ordem Inteligente</option>
            <option value="name"${selected('name')}>Nome (A-Z)</option>
            <option value="usage"${selected('usage')}>Manual (Arrastar)</option>
            <option value="imported"${selected('imported')}>Data Importação</option>
            <option value="duration"${selected('duration')}>Duração</option>
          </select>
          <button type="button" class="automation-sort-direction" data-automator-direction="${type}" title="Inverter direção">${automatorSortPreference(type).direction === 'desc' ? '↓' : '↑'}</button>
          <button type="button" class="automation-sort-reverse" data-automator-reverse="${type}" title="Inverter lista">⇅</button>
        </div>
      </div>
      <div class="automation-sort-items" data-automator-items="${type}">
        ${items.length ? items.map((item, index) => `
          <div class="automation-sort-item" draggable="true" data-automator-type="${type}" data-automator-index="${index}" title="Arraste para reposicionar ou use as setas">
            <span class="automation-sort-grip" aria-hidden="true" title="Arraste para mover">⋮⋮</span>
            <span class="automation-sort-number">${String(index + 1).padStart(2, '0')}</span>
            <span class="automation-sort-name" title="${escapeHtml(automatorItemLabel(item, type))}">${escapeHtml(automatorItemLabel(item, type))}</span>
            <div class="automation-item-actions">
              <button type="button" class="automation-item-move-btn" data-automator-move="up" data-automator-type="${type}" data-automator-index="${index}" title="Mover para cima"${index === 0 ? ' disabled' : ''}>▲</button>
              <button type="button" class="automation-item-move-btn" data-automator-move="down" data-automator-type="${type}" data-automator-index="${index}" title="Mover para baixo"${index === items.length - 1 ? ' disabled' : ''}>▼</button>
              <button type="button" class="automation-item-remove" role="button" data-automator-remove-type="${type}" data-automator-remove-index="${index}" title="Remover este item">✕</button>
            </div>
          </div>
        `).join('') : `<p class="automation-sort-empty">${empty}</p>`}
      </div>
    </section>
  `;
}

function reorderAutomatorItems(type, fromIndex, toIndex, placeAfter = false){
  const list = automatorItems(type);
  if(!list.length || fromIndex === toIndex || fromIndex < 0 || toIndex < 0 || fromIndex >= list.length || toIndex >= list.length) return false;
  const [item] = list.splice(fromIndex, 1);
  let targetIndex = toIndex;
  if(fromIndex < toIndex){
    targetIndex = toIndex - 1;
    if(placeAfter) targetIndex += 1;
  }else{
    if(placeAfter) targetIndex += 1;
  }
  targetIndex = Math.max(0, Math.min(targetIndex, list.length));
  list.splice(targetIndex, 0, item);
  list.forEach((entry, index) => { entry._autoUsageIndex = index; });
  state.automator.sort[type] = {criterion: 'usage', direction: 'asc'};
  saveAutomatorSortPreferences();
  return true;
}

function refreshAutomatorListOrder(type){
  const list = automatorPreview?.querySelector(`[data-automator-list="${type}"] .automation-sort-items`);
  if(!list) return;
  list.querySelectorAll('.automation-sort-item').forEach((item, index) => {
    item.dataset.automatorIndex = String(index);
    const number = item.querySelector('.automation-sort-number');
    if(number) number.textContent = String(index + 1).padStart(2, '0');
  });
}

function estimateAudioFileSeconds(file){
  if(!file || !file.size) return 0;
  const name = String(file.name || '').toLowerCase();
  const ext = name.split('.').pop() || '';
  if(ext === 'wav') return file.size / 176400;
  if(ext === 'flac') return file.size / 90000;
  if(ext === 'aac' || ext === 'm4a') return file.size / 24000;
  // Narração de alta fidelidade em MP3 (320 kbps = 40.000 bytes/s)
  return file.size / 38000;
}

function probeAutomatorRowDurations(row){
  if(!row || row._probed) return;
  row._probed = true;
  if(row.srt && !row._audioDuration && typeof row.srt.slice === 'function'){
    try{
      const slice = row.srt.slice(Math.max(0, row.srt.size - 8192));
      const reader = new FileReader();
      reader.onload = () => {
        const text = String(reader.result || '');
        const matches = [...text.matchAll(/-->\s*(\d{2}:\d{2}:\d{2}[,.]\d{3})/g)];
        if(matches.length){
          const lastMatch = matches[matches.length - 1][1];
          const sec = parseSrtTime(lastMatch);
          if(sec && sec > 0){
            row._audioDuration = sec;
            const tbody = automatorPreview?.querySelector('.automation-table tbody');
            const plan = automatorPlan();
            if(tbody) tbody.innerHTML = automatorTableRowsHtml(plan.rows);
          }
        }
      };
      reader.readAsText(slice);
    }catch(_){ }
  }
  if(row.audio && !row._audioDuration && typeof durationOf === 'function'){
    durationOf(row.audio).then(info => {
      if(info?.seconds > 0){
        row._audioDuration = info.seconds;
        const tbody = automatorPreview?.querySelector('.automation-table tbody');
        const plan = automatorPlan();
        if(tbody) tbody.innerHTML = automatorTableRowsHtml(plan.rows);
      }
    }).catch(() => {});
  }
}

function automatorRowHealth(row){
  const files = row.folder?.files || [];
  const vCount = files.filter(f => kindOfFile(f, 'video') === 'video').length;
  const iCount = files.filter(f => kindOfFile(f, 'video') === 'image').length;
  const totalItems = vCount + iCount;
  if(!row.audio && !totalItems) return {tag: '<span class="health-tag tag-neutral">Vazio</span>', ready: false};
  if(!row.audio) return {tag: '<span class="health-tag tag-short">Sem áudio</span>', ready: false};
  if(totalItems === 0) return {tag: '<span class="health-tag tag-short">Sem mídia</span>', ready: false};

  probeAutomatorRowDurations(row);
  const audioDur = row._audioDuration || (row.audio && state.durations.get(rel(row.audio))) || (row.audio ? estimateAudioFileSeconds(row.audio) : 0);
  const mediaDur = (vCount * 6.5) + (iCount * 4.5);
  const ratio = audioDur > 0 ? (mediaDur / audioDur) : 1;

  if(ratio >= 0.85){
    return {tag: `<span class="health-tag tag-ready" title="Mídia suficiente com folga (${Math.round(mediaDur)}s de mídia para ${Math.round(audioDur)}s de voz)">🟢 Pronto</span>`, ready: true};
  }
  if(ratio >= 0.45){
    return {tag: `<span class="health-tag tag-auto" title="Ajuste automático: compensado suavemente pelo Auto-Healer (${Math.round(mediaDur)}s de mídia para ${Math.round(audioDur)}s de voz)">🟡 Ajuste Automático</span>`, ready: true};
  }
  return {tag: `<span class="health-tag tag-short" title="Mídia curta: sugerido adicionar mais vídeos (${Math.round(mediaDur)}s de mídia para ${Math.round(audioDur)}s de voz)">🔴 Mídia Curta</span>`, ready: false};
}

function automatorTableRowsHtml(rows){
  return rows.map(row => {
    const files = row.folder?.files || [];
    const vCount = files.filter(f => kindOfFile(f, 'video') === 'video').length;
    const iCount = files.filter(f => kindOfFile(f, 'video') === 'image').length;
    let detail = `${files.length} arquivo(s)`;
    if(vCount > 0 && iCount > 0){
      detail = `${vCount} vídeo(s), ${iCount} imagem(ns)`;
    }else if(iCount > 0){
      detail = `${iCount} imagem(ns)`;
    }else if(vCount > 0){
      detail = `${vCount} vídeo(s)`;
    }
    const health = automatorRowHealth(row);
    return `
    <tr class="${row.occupied ? 'automation-row-blocked' : ''}">
      <td>${escapeHtml(row.project?.name || 'Projeto')}${row.occupied ? ' <small>ocupado</small>' : ''}</td>
      <td>${escapeHtml(row.srt?.name || '-')}</td>
      <td>${escapeHtml(row.audio?.name || '-')}</td>
      <td>${escapeHtml(row.script?.name || '-')}</td>
      <td>${escapeHtml(row.folder?.name || '-')} <small>${detail}</small></td>
      <td>${health.tag}</td>
    </tr>
  `}).join('');
}

function refreshAutomatorPlanAfterReorder(){
  const plan = automatorPlan();
  if(automatorWarning){
    automatorWarning.hidden = !plan.warnings.length;
    automatorWarning.textContent = plan.warnings.join(' ');
  }
  const hasHealthy = plan.rows.some(r => automatorRowHealth(r).ready);
  if(automatorAutoHealBtn) automatorAutoHealBtn.disabled = !plan.rows.length;
  if(automatorConfirmBtn) automatorConfirmBtn.disabled = Boolean(plan.warnings.length) || !plan.rows.length;
  if(automatorConfirmHealthyBtn) automatorConfirmHealthyBtn.disabled = !hasHealthy || Boolean(plan.warnings.length);
  if(automatorConfirmAndRenderBtn) automatorConfirmAndRenderBtn.disabled = Boolean(plan.warnings.length) || !plan.rows.length;
  const tbody = automatorPreview?.querySelector('.automation-table tbody');
  if(tbody) tbody.innerHTML = automatorTableRowsHtml(plan.rows);
}

function applyAutomatorFilesToProject(project, row){
  if(!project || !row) return [];
  const visualEntries = (row.folder?.files || [])
    .map(file => ({file, kind: kindOfFile(file, 'video')}))
    .filter(item => item.kind === 'video' || item.kind === 'image');
  const audioEntries = row.audio ? [{file: row.audio, kind: 'audio'}] : [];
  const subtitleEntries = row.srt ? [{file: row.srt, kind: 'subtitle'}] : [];
  const scriptEntries = row.script ? [{file: row.script, kind: 'script_guide'}] : [];
  const entries = [...visualEntries, ...audioEntries, ...subtitleEntries, ...scriptEntries];
  project.files = {
    videos: visualEntries.map(item => item.file),
    audios: audioEntries.map(item => item.file),
    backgroundTracks: project.files?.backgroundTracks || [],
    subtitles: subtitleEntries.map(item => item.file),
    captions: project.files?.captions || [],
    scriptGuides: scriptEntries.map(item => item.file),
  };
  project.maps = emptyProjectMaps();
  visualEntries.forEach(({file}) => {
    project.maps.mediaStatus.set(rel(file), {kind: 'pending', label: 'Mídia adicionada pelo AUTO. O FFmpeg confirma no render.'});
  });
  clearRuntimeReportFields(project);
  project.error = null;
  project.backendJobId = null;
  project.outputFile = null;
  project.outputDir = null;
  project.status = projectStatusFor(project);
  project.updatedAt = Date.now();
  return entries;
}

function resetAutomator(){
  let savedSort = {};
  try{ savedSort = JSON.parse(localStorage.getItem('glide_auto_sort_preferences') || '{}'); }catch(_){}
  state.automator = {
    srts: [], audios: [], scripts: [], folders: [],
    sort: savedSort,
  };
  state.automatorDrag = null;
  state.automatorSessionId = '';
  state.automatorApplying = false;
  if(automatorSrtInput) automatorSrtInput.value = '';
  if(automatorAudioInput) automatorAudioInput.value = '';
  if(automatorScriptInput) automatorScriptInput.value = '';
  if(automatorVideoFolderInput) automatorVideoFolderInput.value = '';
  if(automatorProgress) automatorProgress.hidden = true;
  updateAutomatorPreview();
}

function openAutomator(){
  captureActiveProject();
  resetAutomator();
  automatorModal?.classList.add('show');
  automatorModal?.setAttribute('aria-hidden', 'false');
}

function closeAutomator(){
  if(state.automatorApplying) return;
  automatorModal?.classList.remove('show');
  automatorModal?.setAttribute('aria-hidden', 'true');
}

async function cancelAutomator(){
  state.automatorAbortController?.abort();
  const sessionId = state.automatorSessionId;
  state.automatorApplying = false;
  state.automatorSessionId = '';
  if(sessionId){
    await fetch(`/api/queue/automator/sessions/${encodeURIComponent(sessionId)}`, {
      method: 'DELETE',
      cache: 'no-store',
    }).catch(() => {});
  }
  automatorModal?.classList.remove('show');
  automatorModal?.setAttribute('aria-hidden', 'true');
}

function automatorPlan(){
  const activeIndex = Math.max(0, state.projects.findIndex(project => project.id === state.activeProjectId));
  const startIndex = activeIndex >= 0 ? activeIndex : 0;
  const requiredCounts = [
    state.automator.srts.length,
    state.automator.audios.length,
    state.automator.folders.length,
  ];
  if(state.automator.scripts.length > 0) requiredCounts.push(state.automator.scripts.length);
  const targetCount = Math.max(...requiredCounts, 0);
  const available = Math.max(0, state.projects.length - startIndex);
  const warnings = [];
  if(!state.projects.length) warnings.push('Crie pelo menos um projeto na fila.');
  if(!state.automator.srts.length) warnings.push('Selecione os Textos em SRT.');
  if(!state.automator.audios.length) warnings.push('Selecione arquivos de áudio.');
  if(!state.automator.folders.length) warnings.push('Selecione pastas com mídia (vídeos e imagens).');
  if(targetCount && requiredCounts.some(count => count !== targetCount)){
    warnings.push(`Quantidade diferente: ${state.automator.srts.length} Textos, ${state.automator.audios.length} áudio(s), ${state.automator.scripts.length} roteiro(s), ${state.automator.folders.length} pasta(s) de mídia.`);
  }
  if(targetCount > available){
    warnings.push('Não existem projetos suficientes a partir do projeto selecionado para distribuir todos os ficheiros. Reduza a quantidade ou selecione outro projeto.');
  }
  const rows = [];
  const rowCount = warnings.length ? 0 : targetCount;
  for(let i = 0; i < rowCount; i++){
    const project = state.projects[startIndex + i];
    const occupied = Boolean(
      project?.files?.videos?.length
      || project?.files?.audios?.length
      || project?.files?.subtitles?.length
    );
    if(occupied){
      warnings.push(`Projeto ocupado: ${project?.name || `#${startIndex + i + 1}`}. O AUTO aceita somente projetos vazios.`);
    }
    rows.push({
      project,
      srt: state.automator.srts[i],
      audio: state.automator.audios[i],
      script: state.automator.scripts[i],
      folder: state.automator.folders[i],
      occupied,
    });
  }
  return {startIndex, maxCount: targetCount, targetCount: rowCount, available, warnings, rows};
}

function updateAutomatorPreview(){
  if(automatorSrtCount) automatorSrtCount.textContent = `${state.automator.srts.length} selecionado(s)`;
  if(automatorAudioCount) automatorAudioCount.textContent = `${state.automator.audios.length} selecionado(s)`;
  if(automatorScriptCount) automatorScriptCount.textContent = `${state.automator.scripts.length} selecionado(s)`;
  if(automatorFolderCount) automatorFolderCount.textContent = `${state.automator.folders.length} pasta(s) adicionada(s)`;
  const plan = automatorPlan();
  if(automatorWarning){
    automatorWarning.hidden = !plan.warnings.length;
    automatorWarning.textContent = plan.warnings.join(' ');
  }
  const hasHealthy = plan.rows.some(r => automatorRowHealth(r).ready);
  if(automatorConfirmBtn) automatorConfirmBtn.disabled = Boolean(plan.warnings.length) || !plan.rows.length;
  if(automatorConfirmHealthyBtn) automatorConfirmHealthyBtn.disabled = !hasHealthy || Boolean(plan.warnings.length);
  if(automatorConfirmAndRenderBtn) automatorConfirmAndRenderBtn.disabled = Boolean(plan.warnings.length) || !plan.rows.length;
  if(!automatorPreview) return;
  const hasAnySelection = state.automator.srts.length || state.automator.audios.length || state.automator.scripts.length || state.automator.folders.length;
  if(!hasAnySelection){
    automatorPreview.innerHTML = '<p class="queue-report-empty">Selecione Textos, áudios, roteiros e pastas para ver a pré-visualização. Você também pode arrastar várias pastas de vídeos para o cartão de pastas.</p>';
    return;
  }
  const listsHtml = `
    <p class="automation-sort-hint">Arraste itens dentro de cada lista para corrigir a ordem antes de confirmar.</p>
    <div class="automation-sort-grid">
      ${renderAutomatorList('srt', 'TEXTOS (SRT)', state.automator.srts)}
      ${renderAutomatorList('audio', 'ÁUDIO', state.automator.audios)}
      ${renderAutomatorList('script', 'ROTEIROS', state.automator.scripts)}
      ${renderAutomatorList('folder', 'PASTAS DE MÍDIA', state.automator.folders)}
    </div>
  `;
  if(!plan.rows.length){
    automatorPreview.innerHTML = listsHtml;
    return;
  }
  automatorPreview.innerHTML = `
    ${listsHtml}
    <div class="automation-table-wrap">
      <table class="automation-table">
        <thead><tr><th>Projeto</th><th>Textos</th><th>Áudio</th><th>Roteiro</th><th>Pasta com vídeos e imagens</th><th>Saúde do Lote</th></tr></thead>
        <tbody>${automatorTableRowsHtml(plan.rows)}</tbody>
      </table>
    </div>
  `;
}

async function applyAutomatorDistribution(options = {}){
  const plan = automatorPlan();
  const onlyHealthy = Boolean(options?.onlyHealthy);
  const rowsToApply = onlyHealthy ? plan.rows.filter(r => automatorRowHealth(r).ready) : plan.rows;
  if(plan.warnings.length || !rowsToApply.length){
    updateAutomatorPreview();
    return;
  }
  if(state.automatorApplying) return;
  state.automatorApplying = true;
  state.automatorAbortController = new AbortController();
  if(automatorConfirmBtn){
    automatorConfirmBtn.disabled = true;
    automatorConfirmBtn.textContent = 'Preparando...';
  }
  if(automatorConfirmHealthyBtn){
    automatorConfirmHealthyBtn.disabled = true;
    automatorConfirmHealthyBtn.textContent = 'Preparando...';
  }
  if(automatorConfirmAndRenderBtn){
    automatorConfirmAndRenderBtn.disabled = true;
    automatorConfirmAndRenderBtn.textContent = 'Preparando...';
  }
  const previousActive = state.activeProjectId;
  let lastProgressUpdate = 0;
  const progress = (value, text) => {
    const now = performance.now();
    const percent = Math.max(0, Math.min(100, Math.round(value)));
    if(automatorProgress) automatorProgress.hidden = false;
    if(automatorProgressBar) automatorProgressBar.value = percent;
    if(automatorProgressValue) automatorProgressValue.textContent = `${percent}%`;
    if(now - lastProgressUpdate > 60 || percent === 100 || percent <= 5){
      lastProgressUpdate = now;
      if(automatorProgressText) automatorProgressText.textContent = text;
    }
  };
  try{
    if(state.automatorSessionId){
      await fetch(`/api/queue/automator/sessions/${encodeURIComponent(state.automatorSessionId)}`, {
        method: 'DELETE',
        cache: 'no-store',
      }).catch(() => {});
      state.automatorSessionId = '';
    }
    const fileSpecs = [];
    const sessionRows = rowsToApply.map((row, rowIndex) => {
      const projectId = row.project.id;
      const add = (file, kind, lane, relValue, suffix) => {
        if(!file) return;
        const slot = `p${rowIndex}_${lane}_${suffix}`;
        fileSpecs.push({
          slot,
          projectId,
          kind,
          lane,
          rel: relValue || file.name,
          name: file.name,
          size: Number(file.size || 0),
          duration: automatorDuration(file, lane),
          file,
        });
      };
      (row.folder?.files || []).forEach((file, index) => {
        const kind = kindOfFile(file, 'video');
        if(kind === 'video' || kind === 'image') add(file, kind, 'folder', rel(file), index);
      });
      add(row.audio, 'audio', 'audio', row.audio?.name, 0);
      add(row.srt, 'subtitle', 'srt', row.srt?.name, 0);
      add(row.script, 'script_guide', 'script', row.script?.name, 0);
      return {
        projectId,
        projectName: row.project.name,
      };
    });
    progress(2, 'Validando projetos e associações...');
    const createResponse = await fetch('/api/queue/automator/sessions', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        rows: sessionRows,
        files: fileSpecs.map(({file, ...spec}) => spec),
      }),
      cache: 'no-store',
      signal: state.automatorAbortController.signal,
    });
    if(!createResponse.ok) throw new Error(await createResponse.text());
    const created = await createResponse.json();
    state.automatorSessionId = created.sessionId;
    let uploaded = 0;
    const batchSize = 6;
    const batches = [];
    for(let i = 0; i < fileSpecs.length; i += batchSize){
      batches.push(fileSpecs.slice(i, i + batchSize));
    }
    const poolSize = batches.length > 50 ? 5 : (batches.length > 15 ? 4 : 2);
    await runPool(batches, poolSize, async batch => {
      const form = new FormData();
      const slots = [];
      for(const spec of batch){
        form.append('files', spec.file, spec.file.name);
        slots.push(spec.slot);
      }
      form.append('slots', JSON.stringify(slots));
      let response = await fetch(`/api/queue/automator/sessions/${encodeURIComponent(state.automatorSessionId)}/batch`, {
        method: 'POST',
        body: form,
        cache: 'no-store',
        signal: state.automatorAbortController.signal,
      }).catch(() => null);

      if(!response || !response.ok){
        for(const spec of batch){
          const singleForm = new FormData();
          singleForm.append('file', spec.file, spec.file.name);
          singleForm.append('slot', spec.slot);
          const singleResp = await fetch(`/api/queue/automator/sessions/${encodeURIComponent(state.automatorSessionId)}/file`, {
            method: 'POST',
            body: singleForm,
            cache: 'no-store',
            signal: state.automatorAbortController.signal,
          });
          if(!singleResp.ok) throw new Error(`${spec.name}: ${await singleResp.text()}`);
          uploaded += 1;
          progress(5 + uploaded / Math.max(1, fileSpecs.length) * 85, `Enviando ${uploaded}/${fileSpecs.length}: ${spec.name}`);
        }
      } else {
        uploaded += batch.length;
        const lastName = batch[batch.length - 1]?.name || '';
        progress(5 + uploaded / Math.max(1, fileSpecs.length) * 85, `Enviando ${uploaded}/${fileSpecs.length}: ${lastName}`);
      }
    });
    progress(92, 'Confirmando a distribuição de forma atômica...');
    const commitResponse = await fetch(`/api/queue/automator/sessions/${encodeURIComponent(state.automatorSessionId)}/commit`, {
      method: 'POST',
      cache: 'no-store',
      signal: state.automatorAbortController.signal,
    });
    if(!commitResponse.ok) throw new Error(await commitResponse.text());
    const committed = await commitResponse.json();
    progress(97, 'Verificando projetos persistidos...');
    const expectedByProject = new Map(committed.projects.map(item => [item.projectId, item.counts]));
    for(const row of rowsToApply){
      const counts = expectedByProject.get(row.project.id);
      const expectedAudios = row.audio ? 1 : 0;
      const expectedTexts = row.srt ? 1 : 0;
      const expectedVisuals = (row.folder?.files || []).filter(f => {
        const k = kindOfFile(f, 'video');
        return k === 'video' || k === 'image';
      }).length;
      if(!counts || (expectedVisuals > 0 && counts.videos !== expectedVisuals) || counts.audios !== expectedAudios || counts.texts !== expectedTexts){
        throw new Error(`Verificação falhou em ${row.project.name}: contagens incompletas.`);
      }
    }
    await loadStoredQueueProjects();
    if(previousActive && state.projects.some(project => project.id === previousActive)) state.activeProjectId = previousActive;
    loadProject(state.activeProjectId || state.projects[0]?.id, {capture: false, force: true});
    renderProjectQueue();
    updateStats();
    progress(100, `${rowsToApply.length} projeto(s) distribuído(s) e verificado(s).`);
    state.automatorApplying = false;
    closeAutomator();
    if(dockSummary) dockSummary.textContent = `AUTO concluído: ${rowsToApply.length} projeto(s) receberam mídia com persistência verificada.`;
  }catch(error){
    const cancelled = error?.name === 'AbortError';
    const message = cancelled ? 'Operação cancelada.' : (error.message || String(error));
    progress(Number(automatorProgressBar?.value || 0), `AUTO não alterou os projetos: ${message}`);
    if(dockSummary) dockSummary.textContent = `AUTO falhou sem alterar projetos: ${message}`;
    updateAutomatorPreview();
  }finally{
    state.automatorApplying = false;
    state.automatorAbortController = null;
    if(automatorConfirmBtn){
      automatorConfirmBtn.textContent = 'Confirmar';
      automatorConfirmBtn.disabled = Boolean(automatorPlan().warnings.length);
    }
    if(automatorConfirmHealthyBtn){
      automatorConfirmHealthyBtn.textContent = 'Renderizar Saudáveis';
      automatorConfirmHealthyBtn.disabled = !plan.rows.some(r => automatorRowHealth(r).ready) || Boolean(automatorPlan().warnings.length);
    }
    if(automatorConfirmAndRenderBtn){
      automatorConfirmAndRenderBtn.textContent = 'Confirmar & Renderizar Agora';
      automatorConfirmAndRenderBtn.disabled = Boolean(automatorPlan().warnings.length);
    }
  }
}

async function clearProject(){
  if(state.renderActive){
    dockSummary.textContent = 'Aguarde o render terminar antes de limpar o projeto.';
    return;
  }
  const hasProjectData = state.videos.length || state.audios.length || state.backgroundTracks.length || state.subtitles.length || state.captions.length || state.scriptGuides.length || state.activeJobId;
  const message = hasProjectData
    ? 'Limpar timeline, áudios, Textos, Legendas, Roteiro e renders antigos? Seus presets e opções de exportação serão mantidos.'
    : 'Apagar renders antigos e temporarios para liberar espaco? Seus presets serao mantidos.';
  if(!window.confirm(message)) return;

  dockSummary.textContent = 'Limpando projeto e renders antigos...';
  try{
    const projectId = state.activeProjectId;
    const r = await fetch(`/api/queue/projects/${encodeURIComponent(projectId)}/clear-media`, {method: 'POST', cache: 'no-store'});
    if(!r.ok) throw new Error(await r.text());
    const j = await r.json();
    resetProjectState();
    dockSummary.textContent = `Projeto limpo. Presets mantidos. ${j.space_recovered || '0 B'} liberado(s).`;
  }catch(e){
    dockSummary.textContent = `Não foi possível limpar o projeto: ${e.message || e}`;
  }
}

async function clearAllProjects(){
  if(state.renderActive || state.queueRendering){
    if(dockSummary) dockSummary.textContent = 'Aguarde o render ou a fila terminar antes de limpar todos os projetos.';
    return;
  }
  captureActiveProject();
  if(!state.projects.length) ensureProject();
  const message = 'Limpar mídias, Textos, Legendas, jobs e renders de TODOS os projetos? Os nomes de canal/projeto e presets individuais serão mantidos.';
  if(!window.confirm(message)) return;

  if(dockSummary) dockSummary.textContent = 'Limpando todos os projetos e renders antigos...';

  try{
    const r = await fetch('/api/queue/projects/clear-all-media', {method: 'POST', cache: 'no-store'});
    if(!r.ok) throw new Error(await r.text());
    const j = await r.json();
    if(Array.isArray(j.projects)){
      state.projects = j.projects.map(storedProjectToModel);
    }else{
      state.projects.forEach(project => {
        project.files = emptyProjectFiles();
        project.maps = emptyProjectMaps();
        project.subtitleInfo = null;
        project.captionInfo = null;
        project.scriptGuideInfo = null;
        project.scriptGuidePlan = null;
        clearRuntimeReportFields(project);
        project.status = 'draft';
        project.updatedAt = Date.now();
      });
    }
    const activeId = state.projects.find(item => item.id === state.activeProjectId)?.id || state.projects[0]?.id || '';
    state.activeProjectId = '';
    if(activeId) loadProject(activeId, {capture: false});
    localStorage.removeItem('glide_active_job');
    localStorage.removeItem('glide_active_output_dir');
    if(outputPath) outputPath.textContent = '';
    if(openOutputBtn) openOutputBtn.classList.add('hidden');
    if(downloadBtn) downloadBtn.classList.add('hidden');
    hideReportModal();
    renderProjectQueue();
    if(dockSummary) dockSummary.textContent = `Fila limpa. Presets e nomes mantidos. ${j.storage?.removed || 0} item(ns), ${j.space_recovered || '0 B'} liberado(s).`;
  }catch(e){
    if(dockSummary) dockSummary.textContent = `Não foi possível limpar a fila: ${e.message || e}`;
  }
}

async function addQueueProject(name = ''){
  captureActiveProject();
  const project = createProjectModel(name || `Projeto ${state.projects.length + 1}`);
  state.projects.push(project);
  loadProject(project.id);
  syncProjectSnapshot(project);
  renderProjectQueue();
  if(dockSummary) dockSummary.textContent = `${project.name} criado na fila.`;
  return project;
}

async function duplicateActiveProject(){
  const current = captureActiveProject();
  if(!current) return;
  const clone = createProjectModel(`${current.name} copia`);
  clone.files = {
    videos: [...current.files.videos],
    audios: [...current.files.audios],
    backgroundTracks: [...current.files.backgroundTracks],
    subtitles: [...current.files.subtitles],
    captions: [...(current.files.captions || [])],
    scriptGuides: [...(current.files.scriptGuides || [])],
  };
  clone.maps = {
    durations: new Map(current.maps.durations),
    durationSources: new Map(current.maps.durationSources),
    audioHealth: new Map(current.maps.audioHealth),
    thumbs: new Map(current.maps.thumbs),
    mediaStatus: new Map(current.maps.mediaStatus),
  };
  clone.options = {...current.options};
  clone.subtitleInfo = current.subtitleInfo;
  clone.captionInfo = current.captionInfo;
  clone.scriptGuideInfo = current.scriptGuideInfo;
  clone.scriptGuidePlan = current.scriptGuidePlan;
  state.projects.push(clone);
  loadProject(clone.id);
  syncProjectSnapshot(clone);
}

async function removeActiveProject(){
  if(state.queueRendering) return;
  const current = state.projects.find(item => item.id === state.activeProjectId);
  if(!current) return;
  if(state.projects.length <= 1){
    resetProjectState();
    captureActiveProject();
    renderProjectQueue();
    return;
  }
  if(!window.confirm(`Remover ${current.name} da fila? Os arquivos originais no disco não serão apagados.`)) return;
  state.projects = state.projects.filter(item => item.id !== current.id);
  fetch(`/api/queue/projects/${encodeURIComponent(current.id)}`, {method: 'DELETE', cache: 'no-store'}).catch(() => {});
  state.activeProjectId = null;
  loadProject(state.projects[0].id);
  renderProjectQueue();
}

function inferBatchKind(file){
  const path = rel(file).toLowerCase().replace(/\\/g, '/');
  if(path.endsWith('.srt')) return 'subtitle';
  if(path.includes('/music/') || path.includes('/musica') || path.includes('/música') || path.includes('/background') || path.includes('/bgm')) return 'background_music';
  if(path.includes('/video') || path.includes('/clips')) return 'video';
  if(path.includes('/audio') || path.includes('/voice') || path.includes('/voz') || path.includes('/narracao') || path.includes('/narração')) return 'audio';
  return null;
}

function groupBatchFiles(fileList){
  const groups = new Map();
  Array.from(fileList || []).forEach(file => {
    const path = rel(file).replace(/\\/g, '/');
    const parts = path.split('/').filter(Boolean);
    const key = parts.length > 1 ? parts[0] : 'Projeto importado';
    if(!groups.has(key)) groups.set(key, []);
    groups.get(key).push(file);
  });
  return groups;
}

async function importBatchFolder(fileList){
  if(state.renderActive || state.queueRendering){
    dockSummary.textContent = 'Aguarde o render terminar antes de importar lote.';
    return;
  }
  const groups = groupBatchFiles(fileList);
  if(!groups.size) return;
  captureActiveProject();
  const current = state.projects.find(item => item.id === state.activeProjectId);
  const currentEmpty = current && !(current.files.videos.length || current.files.audios.length || current.files.backgroundTracks.length || current.files.subtitles.length);
  if(currentEmpty && state.projects.length === 1){
    state.projects = [];
    state.activeProjectId = null;
  }
  let created = 0;
  for(const [name, files] of groups.entries()){
    const project = createProjectModel(name);
    state.projects.push(project);
    loadProject(project.id);
    await ingestFiles(files, inferBatchKind);
    captureActiveProject();
    created++;
  }
  renderProjectQueue();
  if(queueSummary) queueSummary.textContent = `${created} projeto(s) criados a partir da pasta em lote.`;
}

function applyProjectTemplate(key){
  const tpl = projectTemplates[key];
  if(!tpl) return;
  if(workflowPresetSelect && tpl.workflow){
    workflowPresetSelect.value = tpl.workflow;
    applyWorkflowPreset(tpl.workflow);
  }
  if(tpl.cta && state.ctaAssets.some(asset => asset.key === tpl.cta && asset.available)){
    state.selectedCta = tpl.cta;
    localStorage.setItem('glide_cta_language', tpl.cta);
  }
  if(tpl.musicGenre) setMusicGenre(tpl.musicGenre);
  if(tpl.subtitle && subtitlePreset){
    subtitlePreset.value = tpl.subtitle;
    applyPresetToControls();
  }
  captureActiveProject();
  renderCtaAssets();
  renderProjectQueue();
}

function applyIdentityPackage(key){
  const pack = identityPackages[key];
  if(!pack) return;
  if(pack.cta && state.ctaAssets.some(asset => asset.key === pack.cta && asset.available)){
    state.selectedCta = pack.cta;
    localStorage.setItem('glide_cta_language', pack.cta);
  }
  if(pack.musicGenre) setMusicGenre(pack.musicGenre);
  if(pack.subtitle && subtitlePreset){
    subtitlePreset.value = pack.subtitle;
    applyPresetToControls();
  }
  captureActiveProject();
  renderCtaAssets();
  renderProjectQueue();
}

async function saveQueueBatchReport(batchId, queueItems, counters){
  const projects = queueItems.map(({project}) => ({
    id: project.id,
    name: project.name,
    status: project.status,
    outputFile: project.outputFile || null,
    outputDir: project.outputDir || null,
    error: project.error || null,
    lastRenderSummary: project.lastRenderSummary || null,
  }));
  try{
    const response = await fetch('/api/queue/batch-report', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        batchId,
        renderMode: normalizedRenderPriority(state.renderPriority),
        summary: counters,
        outputDirs: [...new Set(projects.map(item => item.outputDir).filter(Boolean))],
        projects,
      }),
      cache: 'no-store',
    });
    if(!response.ok) throw new Error(await response.text());
    return await response.json();
  }catch(error){
    console.warn('Falha ao salvar batch_report.json', error);
    return null;
  }
}

function summarizeQueuePlan(plan){
  const summary = plan?.summary || {};
  const ignored = Number(summary.ignored || 0);
  const healthy = Number(summary.healthy || 0);
  const avg = Number(summary.averageConfidence || 0);
  return `Plano da fila: ${healthy} saudavel(is), ${ignored} ignorado(s), confianca media ${avg || '--'}%.`;
}

async function buildQueuePreflightPlan(mode = 'all', projectIds = []){
  try{
    const response = await fetch('/api/queue/preflight-plan', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({mode, projectIds}),
      cache: 'no-store',
    });
    if(!response.ok) throw new Error(await response.text());
    const payload = await response.json();
    const plan = payload.plan || payload;
    const text = summarizeQueuePlan(plan);
    if(queueSummary) queueSummary.textContent = text;
    if(dockSummary) dockSummary.textContent = text;
    return plan;
  }catch(error){
    if(dockSummary) dockSummary.textContent = `Plano da fila indisponivel: ${error.message || error}`;
    return null;
  }
}

async function prepareHealthyProjects(){
  const response = await fetch('/api/queue/projects/prepare-healthy', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({threshold: Number(healthyThresholdInput?.value || 70)}),
    cache: 'no-store',
  });
  if(!response.ok) throw new Error(await response.text());
  const payload = await response.json();
  if(Array.isArray(payload.projects)){
    state.projects = payload.projects.map(storedProjectToModel);
    await Promise.all(state.projects.map(project => rehydrateProjectMedia(project)));
    ensureProject();
  }
  return payload;
}

async function renderQueue(config = {}){
  if(state.queueRendering || state.renderActive) return;
  if(renderQueueBtn){
    renderQueueBtn.disabled = true;
    renderQueueBtn.textContent = 'Preparando fila...';
  }
  dockSummary.textContent = 'Preparando plano da fila antes de iniciar o render...';
  try{
    await new Promise(resolve => requestAnimationFrame(resolve));
    captureActiveProject();
    await Promise.all(state.projects.map(project => syncProjectSnapshot(project, {immediate: true}) || Promise.resolve()));
    const requestedIds = new Set(Array.isArray(config.projectIds) ? config.projectIds : []);
    const planMode = config.healthyOnly ? 'healthy' : (requestedIds.size ? 'selected' : 'all');
    let queuePlan = null;
    try{
      queuePlan = await buildQueuePreflightPlan(planMode, [...requestedIds]);
    }catch(error){
      dockSummary.textContent = `Não foi possível preparar a fila: ${error.message || error}`;
      return;
    }
    const plannedRenderable = new Set(
      Array.isArray(queuePlan?.projects)
        ? queuePlan.projects.filter(item => item.renderable).map(item => String(item.id || ''))
        : []
    );
    const projects = state.projects.filter(project => {
      if(requestedIds.size && !requestedIds.has(project.id)) return false;
      if(['done', 'recovered', 'rendering', 'queued', 'cancelled'].includes(project.status)) return false;
      if(queuePlan && !plannedRenderable.has(project.id)) return false;
      return projectReadiness(project).ok;
    });
    const queueItems = projects.map(project => ({project, snapshot: snapshotProjectForRender(project)}));
    const queueScope = requestedIds.size
      ? state.projects.filter(project => requestedIds.has(project.id))
      : state.projects;
    const skipped = queueScope.filter(project => !projects.includes(project) && !['done', 'recovered'].includes(project.status));
    if(!projects.length){
      dockSummary.textContent = 'Nenhum projeto com vídeos, narração, Textos e CTA pronto para renderizar.';
      return;
    }
    state.queueRendering = true;
    if(renderPrioritySelect) renderPrioritySelect.disabled = true;
    state.queuePaused = false;
    state.queuePauseRequested = false;
    state.queueStopRequested = false;
    document.body.classList.add('queue-rendering');
    state.queueBatchId = `batch_${timestampId()}`;
    prepareRenderNotification();
    dockSummary.textContent = config.retryFailed
      ? `Repetindo ${projects.length} projeto(s). O Render Graph reutilizará etapas válidas quando possível.`
      : `Fila validada: ${projects.length} projeto(s) pronto(s), ${skipped.length} ignorado(s). Plano inicial salvo antes do render.`;
    let done = 0;
    let failed = 0;
    let cancelled = 0;
    for(let i = 0; i < queueItems.length; i++){
      if(state.queuePauseRequested || state.queueStopRequested) break;
      const {project} = queueItems[i];
      activateRenderingProject(project.id);
      project.status = 'rendering';
      project.error = '';
      syncProjectSnapshot(project);
      renderProjectQueue();
      const activeSnapshot = snapshotProjectForRender(project);
      try{
        const result = await startRender({
          queue: true,
          batchId: state.queueBatchId,
          queueIndex: i + 1,
          projectId: project.id,
          projectName: project.name,
          projectSnapshot: activeSnapshot,
        });
        if(result?.status === 'done'){
          project.status = result.recovery_summary?.recovered ? 'recovered' : 'done';
          project.backendJobId = result.id;
          project.outputDir = result.output_dir || '';
          project.outputFile = result.output_name || '';
          done++;
        }else if(result?.status === 'cancelled'){
          project.status = 'cancelled';
          project.backendJobId = result.id;
          project.error = result?.error || 'Render cancelado pelo usuário.';
          cancelled++;
          state.queueStopRequested = true;
        }else{
          project.status = 'error';
          project.error = result?.error || 'Erro desconhecido no render.';
          project.lastRenderSummary = renderErrorSummary(project.error, {
            renderPriority: activeSnapshot?.options?.renderPriority,
            outputName: project.outputName || project.name,
            outputDir: project.outputDir || '',
          });
          failed++;
        }
      }catch(error){
        if(/cancelado/i.test(error.message || String(error))){
          project.status = 'cancelled';
          project.error = 'Render cancelado pelo usuário.';
          cancelled++;
          state.queueStopRequested = true;
        }else{
          project.status = 'error';
          project.error = error.message || String(error);
          project.lastRenderSummary = renderErrorSummary(project.error, {
            renderPriority: activeSnapshot?.options?.renderPriority,
            outputName: project.outputName || project.name,
            outputDir: project.outputDir || '',
          });
          failed++;
        }
      }
      syncProjectSnapshot(project);
      renderProjectQueue();
      if(state.queuePauseRequested || state.queueStopRequested) break;
      // Cooldown to allow OS, disk buffers and GPU driver (NVENC/AMF) to release handles before next project
      await new Promise(resolve => setTimeout(resolve, 1200));
    }
    state.queueRendering = false;
    if(renderPrioritySelect) renderPrioritySelect.disabled = false;
    document.body.classList.remove('queue-rendering');
    await refreshRenderGallery();
    if(state.queuePauseRequested && !state.queueStopRequested){
      let pending = 0;
      for(const {project} of queueItems){
        if(projectReadiness(project).ok && !['done', 'recovered', 'error', 'cancelled'].includes(project.status)){
          project.status = 'paused';
          syncProjectSnapshot(project);
          pending++;
        }
      }
      state.queuePaused = true;
      renderTitle.textContent = 'Fila pausada';
      renderMsg.textContent = `Fila pausada. ${pending} projeto(s) pendente(s).`;
      dockSummary.textContent = `Fila pausada. ${pending} projeto(s) pendente(s).`;
    }else if(state.queueStopRequested){
      let pending = 0;
      for(const {project} of queueItems){
        if(projectReadiness(project).ok && !['done', 'recovered', 'error', 'cancelled'].includes(project.status)){
          project.status = 'paused';
          syncProjectSnapshot(project);
          pending++;
        }
      }
      state.queuePaused = true;
      renderTitle.textContent = 'Render cancelado';
      renderMsg.textContent = `${done} concluído(s), ${cancelled} cancelado(s), ${failed} erro(s). ${pending} projeto(s) pendente(s) para retomar.`;
      dockSummary.textContent = `Render cancelado. ${pending} projeto(s) pendente(s).`;
    }else{
      state.queuePaused = false;
      setRenderStage('queue_done');
      setRenderProgress(100);
      renderTitle.textContent = 'Fila concluída';
      renderMsg.textContent = `${done} projeto(s) concluído(s), ${failed} com erro, ${skipped.length} ignorado(s) sem requisitos. Veja a galeria e os cards da fila.`;
      dockSummary.textContent = `Fila finalizada: ${done} concluído(s), ${failed} erro(s), ${skipped.length} ignorado(s).`;
      if(done > 0) playCompletionSound('queue');
    }
    const batchReport = await saveQueueBatchReport(state.queueBatchId, queueItems, {
      total: queueItems.length,
      completed: done,
      failed,
      cancelled,
      skipped: skipped.length,
      paused: Boolean(state.queuePauseRequested || state.queueStopRequested),
    });
    if(batchReport?.savedPaths?.length){
      dockSummary.textContent = `${dockSummary.textContent} Relatório consolidado salvo.`;
    }
    state.queuePauseRequested = false;
    state.queueStopRequested = false;
  }catch(outerError){
    dockSummary.textContent = `Falha inesperada na fila: ${outerError.message || outerError}`;
  }finally{
    state.queueRendering = false;
    if(renderPrioritySelect) renderPrioritySelect.disabled = false;
    document.body.classList.remove('queue-rendering');
    renderProjectQueue();
  }
}

async function retryFailedRenders(){
  openRetryModal();
}

function openRetryModal(){
  if(state.queueRendering || state.renderActive || !retryModal || !retryProjectList) return;
  captureActiveProject();
  const rows = state.projects.map((project, index) => ({project, index, eligibility: rerenderEligibility(project)}));
  retryProjectList.innerHTML = rows.map(({project, index, eligibility}) => `
    <label class="retry-row ${eligibility.ok ? '' : 'disabled'}">
      <input type="checkbox" value="${escapeHtml(project.id)}" ${eligibility.ok ? 'checked' : 'disabled'} />
      <span><strong>${String(index + 1).padStart(2, '0')} - ${escapeHtml(project.name || `Projeto ${index + 1}`)}</strong><small>${escapeHtml(eligibility.reason)}</small></span>
    </label>
  `).join('');
  if(retryModeAll) retryModeAll.checked = true;
  retryModal.classList.add('show');
  retryModal.setAttribute('aria-hidden', 'false');
}

function closeRetryDialog(){
  retryModal?.classList.remove('show');
  retryModal?.setAttribute('aria-hidden', 'true');
}

async function confirmRetryQueue(){
  if(state.queueRendering || state.renderActive) return;
  const active = captureActiveProject();
  if(active) await syncProjectSnapshot(active, {immediate: true});
  const mode = retryModeSelected?.checked ? 'selected' : 'all';
  const selected = [...(retryProjectList?.querySelectorAll('input[type="checkbox"]:checked') || [])].map(input => input.value);
  if(mode === 'selected' && !selected.length){
    dockSummary.textContent = 'Selecione pelo menos um projeto elegivel para repetir.';
    return;
  }
  if(confirmRetryBtn) confirmRetryBtn.disabled = true;
  dockSummary.textContent = 'Preparando repeticao da fila...';
  try{
    const response = await fetch('/api/queue/projects/prepare-rerender', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({mode, projectIds: selected}),
      cache: 'no-store',
    });
    if(!response.ok) throw new Error(await response.text());
    const payload = await response.json();
    const retryable = new Set(payload.retryable || []);
    if(Array.isArray(payload.projects)){
      state.projects = payload.projects.map(storedProjectToModel);
      await Promise.all(state.projects.map(project => rehydrateProjectMedia(project)));
    }else{
      state.projects.forEach(project => {
        if(!retryable.has(project.id)) return;
        project.status = 'ready';
        project.error = '';
      });
    }
    closeRetryDialog();
    renderProjectQueue();
    if(!retryable.size){
      const reasons = (payload.skipped || []).map(item => item.reason).filter(Boolean).join('; ');
      dockSummary.textContent = `Nenhum projeto pode ser repetido agora${reasons ? `: ${reasons}` : '.'}`;
      return;
    }
    await renderQueue({projectIds: [...retryable], retryFailed: true});
  }catch(error){
    dockSummary.textContent = `Não foi possível repetir a fila: ${error.message || error}`;
    renderProjectQueue();
  }finally{
    if(confirmRetryBtn) confirmRetryBtn.disabled = false;
  }
}

async function renderSample(){
  if(state.renderActive || state.queueRendering) return;
  try{
    const result = await startRender({sampleRender: true, smartSampleBlocks: true, previewDurationSeconds: 30, projectId: state.activeProjectId, projectName: state.projects.find(item => item.id === state.activeProjectId)?.name || 'amostra'});
    if(result?.status === 'done') await refreshRenderGallery();
  }catch(_){}
}

async function renderHealthyQueue(){
  if(state.queueRendering || state.renderActive) return;
  const active = captureActiveProject();
  if(active) await syncProjectSnapshot(active, {immediate: true});
  dockSummary.textContent = 'Analisando projetos saudáveis antes da fila...';
  try{
    const payload = await prepareHealthyProjects();
    renderProjectQueue();
    const ids = Array.isArray(payload.retryable) ? payload.retryable : [];
    if(!ids.length){
      const skipped = (payload.skipped || []).map(item => `${item.name || item.id}: ${item.reason}`).slice(0, 3).join('; ');
      dockSummary.textContent = `Nenhum projeto saudavel para renderizar${skipped ? `: ${skipped}` : '.'}`;
      return;
    }
    await renderQueue({projectIds: ids, healthyOnly: true});
  }catch(error){
    dockSummary.textContent = `Não foi possível preparar saudáveis: ${error.message || error}`;
  }
}

async function renderSafeCurrentProject(){
  if(state.queueRendering || state.renderActive) return;
  try{
    const active = captureActiveProject();
    if(active) await syncProjectSnapshot(active, {immediate: true});
    await startRender({safeRender: true, projectId: state.activeProjectId, projectName: state.projects.find(item => item.id === state.activeProjectId)?.name || 'render seguro'});
  }catch(error){
    dockSummary.textContent = `Render seguro falhou: ${error.message || error}`;
  }
}

async function saveSettingsNow(){
  if(state.settingsSaving) return;
  state.settingsSaving = true;
  const originalLabel = saveSettingsBtn?.textContent || 'Salvar configurações';
  if(saveSettingsBtn){
    saveSettingsBtn.disabled = true;
    saveSettingsBtn.textContent = 'Salvando...';
  }
  try{
    const project = captureActiveProject();
    if(project) await syncProjectSnapshot(project, {immediate: true});
    localStorage.setItem('glide_theme_mode', state.themeMode || 'system');
    localStorage.setItem('glide_ui_mode', state.uiMode || 'simple');
    localStorage.setItem('glide_render_priority', normalizedRenderPriority(state.renderPriority));
    localStorage.setItem('glide_render_budget_enabled', state.renderBudgetEnabled ? '1' : '0');
    localStorage.setItem('glide_ui_sounds_enabled', state.uiSoundsEnabled ? '1' : '0');
    localStorage.setItem('glide_ui_sound_style', state.uiSoundStyle || 'soft_tick');
    localStorage.setItem('glide_ui_sound_scope', state.uiSoundScope || 'global');
    localStorage.setItem('glide_ui_project_done_sound_enabled', state.uiProjectDoneSoundEnabled ? '1' : '0');
    saveAutomatorSortPreferences();
    const response = await fetch('/api/settings/save', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        projectId: project?.id || state.activeProjectId || '',
        name: project?.name || projectNameInput?.value || '',
        options: project?.options || captureControlSnapshot(true),
        musicGenre: state.musicGenre,
        subtitleInfo: state.subtitleInfo,
        captionInfo: state.captionInfo,
        global: {
          theme: state.themeMode,
          uiMode: state.uiMode,
          renderPriority: normalizedRenderPriority(state.renderPriority),
          renderBudgetEnabled: state.renderBudgetEnabled,
          uiSoundsEnabled: state.uiSoundsEnabled,
          uiSoundStyle: state.uiSoundStyle,
          uiSoundScope: state.uiSoundScope,
          projectDoneSound: state.uiProjectDoneSoundEnabled,
          automatorSortPreferences: state.automator.sort || {},
        },
      }),
      cache: 'no-store',
    });
    if(!response.ok) throw new Error(await response.text());
    const payload = await response.json();
    if(payload.project){
      const index = state.projects.findIndex(item => item.id === payload.project.id);
      if(index >= 0) state.projects[index] = await rehydrateProjectMedia(storedProjectToModel(payload.project, index));
    }
    dockSummary.textContent = payload.message || 'Configurações salvas.';
    playUiSound('confirm');
    renderProjectQueue();
  }catch(error){
    dockSummary.textContent = `Falha ao salvar configurações: ${error.message || error}`;
  }finally{
    state.settingsSaving = false;
    if(saveSettingsBtn){
      saveSettingsBtn.disabled = state.queueRendering || state.renderActive;
      saveSettingsBtn.textContent = originalLabel;
    }
  }
}

function renderSpaceReport(report){
  if(!spaceSummary) return;
  const items = Array.isArray(report?.items) ? report.items : [];
  const byKey = new Map(items.map(item => [item.key, item]));
  const keys = [
    ['render_cache', 'Cache'],
    ['exports', 'Exports'],
    ['temporary_uploads', 'Temporarios'],
    ['cta_preview_cache', 'Previews CTA'],
    ['old_logs', 'Logs antigos'],
    ['project_media', 'Midia salva'],
  ];
  spaceSummary.innerHTML = keys.map(([key, label]) => {
    const bucket = byKey.get(key) || {};
    return `<span><b>${escapeHtml(bucket.label || '0 B')}</b>${escapeHtml(label)}</span>`;
  }).join('');
}

async function refreshSpaceReport(){
  if(!spaceManagerBox) return;
  spaceManagerBox.classList.remove('hidden');
  if(spaceSummary) spaceSummary.textContent = 'Calculando espaco usado pelo Glide...';
  try{
    const response = await fetch('/api/storage/space-report', {cache: 'no-store'});
    if(!response.ok) throw new Error(await response.text());
    renderSpaceReport(await response.json());
  }catch(error){
    if(spaceSummary) spaceSummary.textContent = `Não foi possível calcular espaço: ${error.message || error}`;
  }
}

async function cleanSpace(action){
  if(state.renderActive || state.queueRendering){
    dockSummary.textContent = 'Limpeza de espaco fica bloqueada durante render para proteger arquivos temporarios.';
    return;
  }
  try{
    const response = await fetch('/api/storage/clean', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({action}),
      cache: 'no-store',
    });
    if(!response.ok) throw new Error(await response.text());
    const payload = await response.json();
    dockSummary.textContent = `Limpeza concluida: ${payload.summary?.space_recovered || '0 B'} liberado(s).`;
    renderSpaceReport(payload.space);
  }catch(error){
    dockSummary.textContent = `Limpeza não executada: ${error.message || error}`;
  }
}

async function refreshRenderGallery(){
  if(!renderGallery) return;
  try{
    const r = await fetch('/api/renders', {cache: 'no-store'});
    if(!r.ok) throw new Error(await r.text());
    const payload = await r.json();
    state.renderGallery = payload.items || [];
    renderGallery.innerHTML = state.renderGallery.length
      ? state.renderGallery.slice(0, 16).map(item => `
        <div class="gallery-item">
          <div class="gallery-top">
            <strong title="${escapeHtml(item.path)}">${escapeHtml(item.name)}</strong>
            <div class="gallery-badges">
              ${item.is_shorts ? '<span class="gallery-chip shorts">9:16 Shorts</span>' : ''}
              ${item.thumbnails?.length ? `<span class="gallery-chip thumbs">${item.thumbnails.length} Thumbs</span>` : ''}
            </div>
          </div>
          <span>${escapeHtml(item.size_label || '')} - ${escapeHtml(item.batch || 'render avulso')}</span>
          <small>${escapeHtml(item.output_dir || '')}</small>
        </div>`).join('')
      : '<div class="empty">Os renders finalizados aparecem aqui.</div>';
  }catch(error){
    renderGallery.innerHTML = '<div class="empty">Não foi possível carregar a galeria de renders.</div>';
  }
}

function applyWorkflowPreset(value){
  const preset = workflowPresets[value];
  if(!preset) return;
  const ratioSelect = $('#ratioSelect');
  const codecSelect = $('#codecSelect');
  const transitionSelect = $('#transitionSelect');
  const zoomSelect = $('#zoomSelect');
  if(ratioSelect) ratioSelect.value = preset.ratio;
  if(codecSelect) codecSelect.value = preset.codec;
  if(exportProfileSelect) exportProfileSelect.value = preset.exportProfile;
  if(transitionSelect) transitionSelect.value = preset.transition;
  if(zoomSelect) zoomSelect.value = preset.zoom;
  if(introModeSelect){
    introModeSelect.value = preset.intro;
    state.introMode = preset.intro;
    localStorage.setItem('glide_intro_mode', state.introMode);
  }
  if(subtitlePreset){
    subtitlePreset.value = preset.subtitle;
    applyPresetToControls();
  }
  if(ctaPositionPreset){
    ctaPositionPreset.value = preset.cta;
    state.ctaPositionPreset = preset.cta;
    state.ctaOffsetX = 0;
    state.ctaOffsetY = 0;
    if(ctaOffsetX) ctaOffsetX.value = '0';
    if(ctaOffsetY) ctaOffsetY.value = '0';
    localStorage.setItem('glide_cta_position', state.ctaPositionPreset);
    localStorage.setItem('glide_cta_offset_x', '0');
    localStorage.setItem('glide_cta_offset_y', '0');
  }
  document.querySelectorAll('.preset').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.mode === preset.mode);
  });
  state.mode = preset.mode;
  if(qualityBoostToggle) qualityBoostToggle.checked = true;
  if(smartVisualDirectorToggle) smartVisualDirectorToggle.checked = true;
  if(visualFilterLevelSelect) visualFilterLevelSelect.value = 'normal';
  if(adaptiveVisualFilterToggle) adaptiveVisualFilterToggle.checked = false;
  if(voiceNormalizeToggle) voiceNormalizeToggle.checked = true;
  if(autoSoundFxToggle) autoSoundFxToggle.checked = true;
  if(backgroundDuckingToggle) backgroundDuckingToggle.checked = true;
  refreshExportProfileUi();
  updateIntroPreview();
  updateCtaPreview();
  updateBackgroundSummary();
  updateStats();
  if(dockSummary) dockSummary.textContent = `Fluxo aplicado: ${workflowPresetSelect?.selectedOptions?.[0]?.textContent || 'preset'}.`;
}

async function autoFixProject(){
  try{
    const {manifest, options} = buildRenderPayload();
    await runBackendPreflight(manifest, options);
  }catch(_){
    // Mesmo quando o preflight bloqueia, ele ja deixou o plano em state.backendPreflight.
  }
  const actions = Array.isArray(state.backendPreflight?.auto_fix_plan?.actions) ? state.backendPreflight.auto_fix_plan.actions : [];
  actions.forEach(item => {
    if(item.action === 'set_cta' && item.value && state.ctaAssets.some(asset => asset.key === item.value && asset.available)){
      state.selectedCta = item.value;
      localStorage.setItem('glide_cta_language', state.selectedCta);
    }
    if(item.action === 'cap_bitrate' && videoBitrateInput && item.value) videoBitrateInput.value = String(item.value);
    if(item.action === 'enable_balanced_transitions' && $('#transitionSelect') && $('#transitionSelect').value === 'off') $('#transitionSelect').value = item.value || 'random_soft';
  });
  if(!state.selectedCta){
    const preferred = state.ctaAssets.find(asset => asset.key === 'pt' && asset.available) || state.ctaAssets.find(asset => asset.available);
    if(preferred){
      state.selectedCta = preferred.key;
      localStorage.setItem('glide_cta_language', state.selectedCta);
    }
  }
  state.videos.sort(naturalCompare);
  state.audios.sort(naturalCompare);
  state.backgroundTracks.sort(naturalCompare);
  state.videoOrderEdited = false;
  state.audioOrderEdited = false;
  state.backgroundOrderEdited = false;
  if(exportProfileSelect && exportProfileSelect.value === 'custom') exportProfileSelect.value = 'capcut_compact';
  if($('#codecSelect')) $('#codecSelect').value = 'hevc';
  if($('#zoomSelect')) $('#zoomSelect').value = 'light';
  if($('#transitionSelect') && $('#transitionSelect').value === 'off') $('#transitionSelect').value = 'fade';
  if(ctaPositionPreset){
    const subPos = Number(subtitlePosition?.value || 16);
    ctaPositionPreset.value = subPos <= 18 ? 'top_right' : 'bottom_right';
    state.ctaPositionPreset = ctaPositionPreset.value;
    localStorage.setItem('glide_cta_position', state.ctaPositionPreset);
  }
  if(qualityBoostToggle) qualityBoostToggle.checked = true;
  if(smartVisualDirectorToggle) smartVisualDirectorToggle.checked = true;
  if(visualFilterLevelSelect) visualFilterLevelSelect.value = 'normal';
  if(adaptiveVisualFilterToggle) adaptiveVisualFilterToggle.checked = false;
  if(voiceNormalizeToggle) voiceNormalizeToggle.checked = true;
  if(autoSoundFxToggle) autoSoundFxToggle.checked = true;
  if(backgroundDuckingToggle) backgroundDuckingToggle.checked = true;
  if(adaptiveDuckingToggle) adaptiveDuckingToggle.checked = true;
  if(strongMomentToggle) strongMomentToggle.checked = true;
  if(renderRecoveryToggle) renderRecoveryToggle.checked = true;
  renderCtaAssets();
  renderLists();
  refreshExportProfileUi();
  updateIntroPreview();
  updateCtaPreview();
  updateBackgroundSummary();
  updateStats();
  if(dockSummary) dockSummary.textContent = `Ajuste automático aplicado: ${actions.length || 'regras locais'} correção(ões), CTA, codec, ordem, quality boost e recuperação revisados.`;
}

$('#pickFolder').addEventListener('click', () => folderInput.click());
$('#pickFiles').addEventListener('click', () => fileInput.click());
$('#pickVideos').addEventListener('click', () => videoInput.click());
$('#pickAudios').addEventListener('click', () => audioInput.click());
$('#pickBackground').addEventListener('click', () => backgroundInput.click());
$('#pickSubtitles').addEventListener('click', () => subtitleInput.click());
$('#pickCaptions').addEventListener('click', () => captionInput.click());
$('#pickScriptGuide')?.addEventListener('click', () => scriptGuideInput?.click());
if(themeSelect){
  themeSelect.value = state.themeMode;
  themeSelect.addEventListener('change', () => {
    state.themeMode = themeSelect.value || 'system';
    localStorage.setItem('glide_theme_mode', state.themeMode);
    applyThemeMode();
  });
}
if(uiModeSelect){
  uiModeSelect.value = state.uiMode;
  uiModeSelect.addEventListener('change', () => {
    state.uiMode = uiModeSelect.value || 'simple';
    localStorage.setItem('glide_ui_mode', state.uiMode);
    applyUiMode();
  });
}
if(renderPrioritySelect){
  applyRenderPriorityUi();
  renderPrioritySelect.addEventListener('change', () => {
    state.renderPriority = normalizedRenderPriority(renderPrioritySelect.value);
    localStorage.setItem('glide_render_priority', state.renderPriority);
    applyRenderPriorityUi();
    updateStats();
    renderProjectQueue();
    if(dockSummary){
      dockSummary.textContent = state.renderPriority === 'max'
        ? 'Turbo Produção ativo globalmente: próximos renders usam cache e composição rápida.'
        : (state.renderPriority === 'quality'
          ? 'Qualidade Máxima ativa: recursos premium liberados, sem foco rígido em tempo.'
          : 'Eficiente Inteligente ativo: qualidade forte com automações caras controladas.');
    }
    scheduleRenderEstimate();
  });
}
if(renderBudgetToggle){
  renderBudgetToggle.checked = Boolean(state.renderBudgetEnabled);
  renderBudgetToggle.addEventListener('change', () => {
    state.renderBudgetEnabled = renderBudgetToggle.checked;
    localStorage.setItem('glide_render_budget_enabled', state.renderBudgetEnabled ? '1' : '0');
    scheduleProjectSync();
    scheduleRenderEstimate();
    if(dockSummary){
      dockSummary.textContent = state.renderBudgetEnabled
        ? 'Proteção de tempo ativada: o Glide usa limites com margem maior antes de interromper renders lentos.'
        : 'Proteção de tempo desativada: o Glide tentará concluir renders mesmo se ultrapassarem o limite estimado.';
    }
  });
}
if(sidebarToggle){
  sidebarToggle.addEventListener('click', () => {
    state.sidebarCollapsed = !state.sidebarCollapsed;
    localStorage.setItem('glide_sidebar_collapsed', state.sidebarCollapsed ? '1' : '0');
    applySidebarState();
  });
}
if(systemThemeQuery){
  const onThemeSystemChange = () => {
    if(state.themeMode === 'system') applyThemeMode();
  };
  if(systemThemeQuery.addEventListener) systemThemeQuery.addEventListener('change', onThemeSystemChange);
  else if(systemThemeQuery.addListener) systemThemeQuery.addListener(onThemeSystemChange);
}
folderInput.addEventListener('change', e => { ingestFiles(e.target.files); e.target.value = ''; });
fileInput.addEventListener('change', e => { ingestFiles(e.target.files); e.target.value = ''; });
videoInput.addEventListener('change', e => { ingestFiles(e.target.files, 'video'); e.target.value = ''; });
audioInput.addEventListener('change', e => { ingestFiles(e.target.files, 'audio'); e.target.value = ''; });
backgroundInput.addEventListener('change', e => { ingestFiles(e.target.files, 'background_music'); e.target.value = ''; });
subtitleInput.addEventListener('change', e => { ingestFiles(e.target.files, 'subtitle'); e.target.value = ''; });
captionInput.addEventListener('change', e => { ingestFiles(e.target.files, 'caption_srt'); e.target.value = ''; });
if(scriptGuideInput) scriptGuideInput.addEventListener('change', e => { ingestFiles(e.target.files, 'script_guide'); e.target.value = ''; });

dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('drag'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag'));
dropZone.addEventListener('drop', e => { e.preventDefault(); dropZone.classList.remove('drag'); ingestFiles(e.dataTransfer.files); });

document.querySelectorAll('.preset').forEach(btn => btn.addEventListener('click', () => {
  document.querySelectorAll('.preset').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  state.mode = btn.dataset.mode;
  refreshExportProfileUi();
  updateStats();
}));
if(exportProfileSelect) exportProfileSelect.addEventListener('change', () => { refreshExportProfileUi(); updateStats(); });
if(workflowPresetSelect) workflowPresetSelect.addEventListener('change', () => applyWorkflowPreset(workflowPresetSelect.value));
if(autoFixBtn) autoFixBtn.addEventListener('click', autoFixProject);
if(rerunDirectorBtn) rerunDirectorBtn.addEventListener('click', () => {
  directorProjectAction('rerun').catch(error => {
    if(dockSummary) dockSummary.textContent = `Não foi possível refazer a direção: ${error.message || error}`;
  });
});
if(undoDirectorBtn) undoDirectorBtn.addEventListener('click', () => {
  directorProjectAction('undo').catch(error => {
    if(dockSummary) dockSummary.textContent = `Não foi possível desfazer a direção: ${error.message || error}`;
  });
});
if(exportLearningBtn) exportLearningBtn.addEventListener('click', async () => {
  try{
    const payload = await loadChannelLearning();
    const project = state.projects.find(item => item.id === state.activeProjectId);
    downloadJson(payload, `glide_aprendizado_${String(project?.name || 'canal').replace(/[^\w-]+/g, '_')}.json`);
  }catch(error){
    if(dockSummary) dockSummary.textContent = `Falha ao exportar aprendizado: ${error.message || error}`;
  }
});
if(resetLearningBtn) resetLearningBtn.addEventListener('click', async () => {
  const project = state.projects.find(item => item.id === state.activeProjectId);
  if(!project?.id) return;
  try{
    const response = await fetch(`/api/intelligence/learning/${encodeURIComponent(project.name || 'default')}`, {
      method: 'DELETE',
      cache: 'no-store',
    });
    if(!response.ok) throw new Error(await response.text());
    await loadChannelLearning();
    if(dockSummary) dockSummary.textContent = 'Aprendizado local deste canal foi zerado.';
  }catch(error){
    if(dockSummary) dockSummary.textContent = `Falha ao zerar aprendizado: ${error.message || error}`;
  }
});
if(installVisualModelBtn && visualModelInput){
  installVisualModelBtn.addEventListener('click', () => visualModelInput.click());
  visualModelInput.addEventListener('change', async () => {
    const file = visualModelInput.files?.[0];
    visualModelInput.value = '';
    if(!file) return;
    installVisualModelBtn.disabled = true;
    installVisualModelBtn.textContent = 'Instalando...';
    try{
      const data = new FormData();
      data.append('file', file, file.name);
      const response = await fetch('/api/intelligence/model/install', {method: 'POST', body: data, cache: 'no-store'});
      if(!response.ok) throw new Error(await response.text());
      await loadSemanticModelStatus();
      if(dockSummary) dockSummary.textContent = 'Pacote visual local instalado.';
    }catch(error){
      if(dockSummary) dockSummary.textContent = `Falha ao instalar modelo: ${error.message || error}`;
    }finally{
      installVisualModelBtn.disabled = false;
      installVisualModelBtn.textContent = 'Instalar modelo local';
    }
  });
}
if(videoBitrateInput) videoBitrateInput.addEventListener('input', () => { refreshExportProfileUi(); updateStats(); });
const codecSelect = $('#codecSelect');
if(codecSelect) codecSelect.addEventListener('change', () => { refreshExportProfileUi(); updateStats(); });
if(backgroundVolumePreset) backgroundVolumePreset.addEventListener('change', () => {
  refreshBackgroundMusicUi();
  recordLearningEvent('music_intensity', {preset: backgroundVolumePreset.value});
});
if(backgroundVolumeDb) backgroundVolumeDb.addEventListener('input', refreshBackgroundMusicUi);
if(backgroundDuckingToggle){
  const savedDucking = localStorage.getItem('glide_background_ducking');
  if(savedDucking !== null) backgroundDuckingToggle.checked = savedDucking === '1';
  backgroundDuckingToggle.addEventListener('change', () => {
    localStorage.setItem('glide_background_ducking', backgroundDuckingToggle.checked ? '1' : '0');
    updateBackgroundSummary();
    updateStats();
  });
}
if(musicGenreSwitch){
  musicGenreSwitch.addEventListener('click', (event) => {
    const button = event.target.closest('[data-music-genre]');
    if(!button) return;
    setMusicGenre(button.dataset.musicGenre);
    recordLearningEvent('music_genre', {genre: button.dataset.musicGenre});
  });
}
if(musicLibraryShelf){
  musicLibraryShelf.addEventListener('click', (event) => {
    const card = event.target.closest('[data-music-genre-card]');
    if(!card) return;
    setMusicGenre(card.dataset.musicGenreCard);
  });
}
if(qualityBoostToggle){
  const savedBoost = localStorage.getItem('glide_quality_boost');
  if(savedBoost !== null) qualityBoostToggle.checked = savedBoost === '1';
  qualityBoostToggle.addEventListener('change', () => {
    localStorage.setItem('glide_quality_boost', qualityBoostToggle.checked ? '1' : '0');
    updateStats();
  });
}
if(smartVisualDirectorToggle){
  const savedDirector = localStorage.getItem('glide_smart_visual_director');
  if(savedDirector !== null) smartVisualDirectorToggle.checked = savedDirector === '1';
  applyRenderPriorityUi();
  smartVisualDirectorToggle.addEventListener('change', () => {
    localStorage.setItem('glide_smart_visual_director', smartVisualDirectorToggle.checked ? '1' : '0');
    applyRenderPriorityUi();
    updateStats();
    scheduleRenderEstimate();
  });
}
if(referenceStylePickBtn) referenceStylePickBtn.addEventListener('click', () => referenceStyleInput?.click());
if(referenceStyleInput) referenceStyleInput.addEventListener('change', event => {
  const file = event.target.files?.[0];
  event.target.value = '';
  uploadReferenceStyle(file).catch(error => {
    if(dockSummary) dockSummary.textContent = `Falha ao anexar referência: ${error.message || error}`;
  });
});
if(referenceStyleAnalyzeBtn) referenceStyleAnalyzeBtn.addEventListener('click', () => {
  analyzeReferenceStyle().catch(error => {
    if(dockSummary) dockSummary.textContent = `Falha ao analisar referência: ${error.message || error}`;
  });
});
if(referenceStyleRemoveBtn) referenceStyleRemoveBtn.addEventListener('click', () => {
  removeReferenceStyle().catch(error => {
    if(dockSummary) dockSummary.textContent = `Falha ao remover referência: ${error.message || error}`;
  });
});
if(referenceStyleEnabledToggle) referenceStyleEnabledToggle.addEventListener('change', () => {
  const project = state.projects.find(item => item.id === state.activeProjectId);
  if(project){
    project.options = captureControlSnapshot(true);
    syncProjectSnapshot(project);
  }
  updateReferenceStyleUi();
  updateStats();
});
[referenceStyleModeSelect, visualLanguagePackageSelect, styleIntensitySelect].forEach(input => {
  if(!input) return;
  input.addEventListener('change', () => {
    const project = state.projects.find(item => item.id === state.activeProjectId);
    if(project){
      project.options = captureControlSnapshot(true);
      syncProjectSnapshot(project);
    }
    updateReferenceStyleUi();
    scheduleRenderEstimate();
  });
});
if(visualFilterLevelSelect){
  visualFilterLevelSelect.addEventListener('change', () => {
    localStorage.setItem('glide_visual_filter_level', normalizedVisualFilterLevel(visualFilterLevelSelect.value));
    applyVisualFilterUi();
    scheduleProjectSync();
    updateStats();
  });
}
if(adaptiveVisualFilterToggle){
  adaptiveVisualFilterToggle.addEventListener('change', () => {
    applyVisualFilterUi();
    scheduleProjectSync();
    updateStats();
  });
}
if(voiceNormalizeToggle){
  const savedVoice = localStorage.getItem('glide_voice_normalize');
  if(savedVoice !== null) voiceNormalizeToggle.checked = savedVoice === '1';
  voiceNormalizeToggle.addEventListener('change', () => {
    localStorage.setItem('glide_voice_normalize', voiceNormalizeToggle.checked ? '1' : '0');
    updateStats();
  });
}
if(autoSoundFxToggle){
  const savedFx = localStorage.getItem('glide_auto_sound_fx');
  if(savedFx !== null) autoSoundFxToggle.checked = savedFx === '1';
  autoSoundFxToggle.addEventListener('change', () => {
    localStorage.setItem('glide_auto_sound_fx', autoSoundFxToggle.checked ? '1' : '0');
    updateStats();
  });
}
[
  [projectToneSelect, 'glide_project_tone'],
  [adaptiveDuckingToggle, 'glide_adaptive_ducking'],
  [dynamicPausesToggle, 'glide_dynamic_pauses'],
  [dynamicPauseIntensity, 'glide_dynamic_pause_intensity'],
  [strongMomentToggle, 'glide_strong_moments'],
  [renderRecoveryToggle, 'glide_render_recovery'],
  [healthyThresholdInput, 'glide_healthy_render_threshold'],
  [platformMasterProfileSelect, 'glide_platform_master_profile'],
  [scoreVisualWindowsToggle, 'glide_score_visual_windows'],
  [adaptiveQualityBoostToggle, 'glide_adaptive_quality_boost'],
  [queueAutoTestToggle, 'glide_queue_auto_test'],
].forEach(([el, key]) => {
  if(!el) return;
  const saved = localStorage.getItem(key);
  if(saved !== null){
    if(el.type === 'checkbox') el.checked = saved === '1';
    else el.value = saved;
  }
  el.addEventListener('change', () => {
    localStorage.setItem(key, el.type === 'checkbox' ? (el.checked ? '1' : '0') : el.value);
    scheduleProjectSync();
    updateStats();
  });
});
if(introModeSelect){
  introModeSelect.value = state.introMode === 'cinematic' ? 'cinematic' : 'standard';
  introModeSelect.addEventListener('change', () => {
    state.introMode = introModeSelect.value || 'standard';
    localStorage.setItem('glide_intro_mode', state.introMode);
    updateIntroPreview();
    if(autoSoundFxToggle?.checked && state.introMode === 'cinematic') playSfxSequence(['subtitle_luxury_doc']);
  });
}
if(introPreset) introPreset.addEventListener('change', applyIntroPresetToControls);
[introFontPreset, introSize, introPosition, introColor, introOutline].filter(Boolean).forEach(input => {
  input.addEventListener('input', updateIntroPreview);
  input.addEventListener('change', updateIntroPreview);
});
subtitlePreset.addEventListener('change', () => {
  applyPresetToControls();
  recordLearningEvent('subtitle_style', {preset: subtitlePreset.value});
});
let captionPreviewTimer = 0;
[captionPreset, captionFont, captionAlignment, captionSize, captionPosition, captionOutline, captionColor, captionOutlineColor]
  .filter(Boolean)
  .forEach(input => {
    const refresh = () => {
      window.clearTimeout(captionPreviewTimer);
      captionPreviewTimer = window.setTimeout(() => {
        updateLayerPreview();
        scheduleProjectSync();
      }, 70);
    };
    input.addEventListener('input', refresh, {passive: true});
    input.addEventListener('change', refresh);
  });
[subtitleFontPreset, subtitleAnimation, subtitleSize, subtitlePosition, subtitleOutlineSize, subtitleColor, subtitleOutline].filter(Boolean).forEach(input => {
  input.addEventListener('input', updateSubtitlePreview);
  input.addEventListener('change', updateSubtitlePreview);
});
if(subtitleAnimation){
  subtitleAnimation.addEventListener('change', () => {
    if(autoSoundFxToggle?.checked) playSfxSequence(subtitleFxByAnimation[subtitleAnimation.value] || []);
    recordLearningEvent('subtitle_animation', {animation: subtitleAnimation.value});
  });
}
if(transitionFxPreviewBtn){
  transitionFxPreviewBtn.disabled = false;
  transitionFxPreviewBtn.hidden = false;
  transitionFxPreviewBtn.addEventListener('click', () => {
    const mode = $('#transitionSelect')?.value || 'off';
    playSfxSequence(transitionFxByMode[mode] || []);
  });
}
if(subtitleFxPreviewBtn){
  subtitleFxPreviewBtn.addEventListener('click', () => {
    playSfxSequence(subtitleFxByAnimation[subtitleAnimation?.value || 'mixed'] || []);
  });
}
if(introFxPreviewBtn){
  introFxPreviewBtn.addEventListener('click', () => {
    const mode = introModeSelect?.value || 'standard';
    if(mode === 'cinematic') playSfxSequence(['subtitle_luxury_doc']);
  });
}
document.addEventListener('click', (e) => {
  const openColor = e.target.closest('[data-color-open]');
  if(openColor){
    const input = $(`#${openColor.dataset.colorOpen}`);
    if(input) input.click();
    return;
  }
  const swatch = e.target.closest('.color-swatch');
  if(!swatch) return;
  const row = swatch.closest('.swatch-row');
  const input = row ? $(`#${row.dataset.target}`) : null;
  if(!input) return;
  input.value = normalizeHex(swatch.dataset.color, input.value).toLowerCase();
  if(input.id && input.id.startsWith('intro')) updateIntroPreview();
  else updateSubtitlePreview();
});

if(ctaGrid){
  ctaGrid.addEventListener('click', (e) => {
    const card = e.target.closest('.cta-card');
    if(!card || card.disabled) return;
    state.selectedCta = card.dataset.cta || '';
    state.ctaPreviewSound = false;
    localStorage.setItem('glide_cta_language', state.selectedCta);
    renderCtaAssets();
    updateStats();
    captureActiveProject();
    renderProjectQueue();
    recordLearningEvent('cta_language', {language: state.selectedCta});
  });
}

if(ctaPositionPreset){
  ctaPositionPreset.addEventListener('change', () => {
    state.ctaPositionPreset = ctaPositionPreset.value || 'top_right';
    localStorage.setItem('glide_cta_position', state.ctaPositionPreset);
    updateCtaPreview();
    captureActiveProject();
  });
}
[ctaOffsetX, ctaOffsetY].filter(Boolean).forEach(input => {
  input.addEventListener('input', () => {
    state.ctaOffsetX = Number(ctaOffsetX?.value || 0);
    state.ctaOffsetY = Number(ctaOffsetY?.value || 0);
    localStorage.setItem('glide_cta_offset_x', String(state.ctaOffsetX));
    localStorage.setItem('glide_cta_offset_y', String(state.ctaOffsetY));
    updateCtaPreview();
    captureActiveProject();
  });
});
if(ctaPreviewSoundBtn){
  ctaPreviewSoundBtn.addEventListener('click', () => {
    state.ctaPreviewSound = !state.ctaPreviewSound;
    updateCtaPreview();
    if(state.ctaPreviewSound) ctaPreviewVideo?.play().catch(() => {});
  });
}
const ratioSelect = $('#ratioSelect');
if(ratioSelect) ratioSelect.addEventListener('change', () => { updateCtaPreview(); updateStats(); });
const transitionSelect = $('#transitionSelect');
if(transitionSelect){
  transitionSelect.addEventListener('change', () => {
    if(autoSoundFxToggle?.checked) playSfxSequence(transitionFxByMode[transitionSelect.value] || []);
    recordLearningEvent('transition_style', {transition: transitionSelect.value});
    scheduleProjectSync();
    updateStats();
  });
}
const zoomSelectGlobal = $('#zoomSelect');
if(zoomSelectGlobal) zoomSelectGlobal.addEventListener('change', updateStats);
const gpuToggleGlobal = $('#gpuToggle');
if(gpuToggleGlobal) gpuToggleGlobal.addEventListener('change', updateStats);

$('#sortNumericBtn').addEventListener('click', () => {
  state.videos.sort(naturalCompare);
  state.audios.sort(naturalCompare);
  state.backgroundTracks.sort(naturalCompare);
  state.videoOrderEdited = false;
  state.audioOrderEdited = false;
  state.backgroundOrderEdited = false;
  renderLists();
  updateStats();
});
$('#clearBtn').addEventListener('click', clearProject);
if(clearAllProjectsBtn) clearAllProjectsBtn.addEventListener('click', clearAllProjects);
$('#clearSubtitleBtn').addEventListener('click', () => {
  state.subtitles.forEach(file => {
    for(const [key, registered] of state.registry.entries()){
      if(registered === file) state.registry.delete(key);
    }
  });
  state.subtitles = [];
  state.subtitleInfo = null;
  refreshSubtitleInfo();
  updateStats();
  captureActiveProject();
  renderProjectQueue();
});
if(clearCaptionBtn) clearCaptionBtn.addEventListener('click', () => {
  state.captions.forEach(file => {
    for(const [key, registered] of state.registry.entries()){
      if(registered === file) state.registry.delete(key);
    }
  });
  state.captions = [];
  state.captionInfo = null;
  refreshCaptionInfo();
  updateStats();
  captureActiveProject();
  renderProjectQueue();
});
if(clearScriptGuideBtn) clearScriptGuideBtn.addEventListener('click', () => {
  state.scriptGuides.forEach(file => {
    for(const [key, registered] of state.registry.entries()){
      if(registered === file) state.registry.delete(key);
    }
  });
  state.scriptGuides = [];
  state.scriptGuideInfo = null;
  state.scriptGuidePlan = null;
  refreshScriptGuideInfo();
  updateStats();
  captureActiveProject();
  renderProjectQueue();
});
if(viewScriptGuideBtn) viewScriptGuideBtn.addEventListener('click', () => {
  renderScriptGuidePlan();
  scriptGuideModal?.classList.add('show');
  scriptGuideModal?.setAttribute('aria-hidden', 'false');
});
if(closeScriptGuideModal) closeScriptGuideModal.addEventListener('click', () => {
  scriptGuideModal?.classList.remove('show');
  scriptGuideModal?.setAttribute('aria-hidden', 'true');
});
if(scriptGuideModal) scriptGuideModal.addEventListener('click', event => {
  if(event.target === scriptGuideModal){
    scriptGuideModal.classList.remove('show');
    scriptGuideModal.setAttribute('aria-hidden', 'true');
  }
});
renderBtn.addEventListener('click', () => startRender().catch(() => {}));
if(newProjectBtn) newProjectBtn.addEventListener('click', () => addQueueProject());
if(duplicateProjectBtn) duplicateProjectBtn.addEventListener('click', duplicateActiveProject);
if(removeProjectBtn) removeProjectBtn.addEventListener('click', removeActiveProject);
if(renderQueueBtn) renderQueueBtn.addEventListener('click', renderQueue);
if(renderHealthyBtn) renderHealthyBtn.addEventListener('click', renderHealthyQueue);
if(automatorBtn) automatorBtn.addEventListener('click', openAutomator);
if(automatorCloseBtn) automatorCloseBtn.addEventListener('click', () => cancelAutomator());
if(automatorCancelBtn) automatorCancelBtn.addEventListener('click', () => cancelAutomator());
if(automatorModal) automatorModal.addEventListener('click', event => {
  if(event.target === automatorModal) closeAutomator();
});
if(automatorPreview){
  automatorPreview.addEventListener('change', event => {
    const select = event.target.closest('[data-automator-sort]');
    if(select) sortAutomatorItems(select.dataset.automatorSort, select.value);
  });
  automatorPreview.addEventListener('click', event => {
    const direction = event.target.closest('[data-automator-direction]');
    if(direction){
      const type = direction.dataset.automatorDirection;
      const current = automatorSortPreference(type);
      sortAutomatorItems(type, current.criterion, current.direction === 'asc' ? 'desc' : 'asc');
      return;
    }
    const reverse = event.target.closest('[data-automator-reverse]');
    if(reverse){
      const type = reverse.dataset.automatorReverse;
      const list = automatorItems(type);
      list.reverse();
      list.forEach((item, index) => { item._autoUsageIndex = index; });
      state.automator.sort[type] = {criterion: 'usage', direction: 'asc'};
      saveAutomatorSortPreferences();
      updateAutomatorPreview();
    }
  });
  let automatorInternalDrag = null;

  automatorPreview.addEventListener('dragstart', event => {
    const item = event.target.closest('.automation-sort-item');
    if(!item){
      return;
    }
    const type = item.dataset.automatorType;
    const index = Number(item.dataset.automatorIndex);
    automatorInternalDrag = { type, index, element: item };
    item.classList.add('dragging');
    event.dataTransfer.effectAllowed = 'move';
    event.dataTransfer.setData('text/plain', `${type}:${index}`);
    try{
      if(event.dataTransfer.setDragImage) event.dataTransfer.setDragImage(item, 24, 20);
    }catch(_){}
  });

  automatorPreview.addEventListener('dragover', event => {
    if(automatorInternalDrag){
      const targetItem = event.target.closest('.automation-sort-item');
      if(targetItem && targetItem.dataset.automatorType === automatorInternalDrag.type && targetItem !== automatorInternalDrag.element){
        event.preventDefault();
        event.dataTransfer.dropEffect = 'move';
        const rect = targetItem.getBoundingClientRect();
        const placeAfter = event.clientY > rect.top + rect.height / 2;
        automatorPreview.querySelectorAll('.drag-over-before, .drag-over-after').forEach(el => {
          if(el !== targetItem) el.classList.remove('drag-over-before', 'drag-over-after');
        });
        targetItem.classList.toggle('drag-over-before', !placeAfter);
        targetItem.classList.toggle('drag-over-after', placeAfter);
        return;
      }
    }
    // Handle external file dragover
    event.preventDefault();
    const listEl = event.target.closest('[data-automator-list]');
    automatorPreview.querySelectorAll('[data-automator-list]').forEach(el => {
      el.classList.toggle('automation-drop-active', Boolean(listEl && el === listEl && !automatorInternalDrag));
    });
  });

  automatorPreview.addEventListener('dragleave', event => {
    const targetItem = event.target.closest('.automation-sort-item');
    if(targetItem && (!event.relatedTarget || !targetItem.contains(event.relatedTarget))){
      targetItem.classList.remove('drag-over-before', 'drag-over-after');
    }
    const listEl = event.target.closest('[data-automator-list]');
    if(listEl && (!event.relatedTarget || !listEl.contains(event.relatedTarget))){
      listEl.classList.remove('automation-drop-active');
    }
  });

  automatorPreview.addEventListener('dragend', () => {
    automatorPreview.querySelectorAll('.dragging, .drag-over-before, .drag-over-after, .automation-drop-active').forEach(el => {
      el.classList.remove('dragging', 'drag-over-before', 'drag-over-after', 'automation-drop-active');
    });
    automatorInternalDrag = null;
  });

  automatorPreview.addEventListener('drop', async event => {
    event.preventDefault();
    automatorPreview.querySelectorAll('.dragging, .drag-over-before, .drag-over-after, .automation-drop-active').forEach(el => {
      el.classList.remove('dragging', 'drag-over-before', 'drag-over-after', 'automation-drop-active');
    });

    // 1. Check if this is an internal item reorder drop:
    if(automatorInternalDrag){
      const targetItem = event.target.closest('.automation-sort-item');
      if(targetItem && targetItem.dataset.automatorType === automatorInternalDrag.type){
        event.stopPropagation();
        const rect = targetItem.getBoundingClientRect();
        const placeAfter = event.clientY > rect.top + rect.height / 2;
        const fromIndex = automatorInternalDrag.index;
        const toIndex = Number(targetItem.dataset.automatorIndex);
        if(fromIndex !== toIndex){
          const changed = reorderAutomatorItems(automatorInternalDrag.type, fromIndex, toIndex, placeAfter);
          if(changed){
            updateAutomatorPreview();
          }
        }
      }
      automatorInternalDrag = null;
      return;
    }

    // 2. Otherwise, this is an external file drop from OS:
    const listEl = event.target.closest('[data-automator-list]');
    const files = await automatorFilesFromDrop(event.dataTransfer).catch(() => []);
    if(!files.length) return;
    const targetType = listEl?.dataset.automatorList;
    if(targetType === 'folder'){
      const added = appendAutomatorFolders(files);
      if(!added && dockSummary) dockSummary.textContent = 'AUTO: nenhuma pasta nova com vídeos foi encontrada.';
      if(added) sortAutomatorItems('folder');
      else updateAutomatorPreview();
    }else if(targetType === 'srt'){
      const srtFiles = files.filter(file => kindOfFile(file, 'subtitle') === 'subtitle');
      if(srtFiles.length){
        state.automator.srts = annotateAutomatorItems([...state.automator.srts, ...srtFiles]);
        sortAutomatorItems('srt');
      }
    }else if(targetType === 'audio'){
      const audioFiles = files.filter(file => kindOfFile(file, 'audio') === 'audio');
      if(audioFiles.length){
        state.automator.audios = annotateAutomatorItems([...state.automator.audios, ...audioFiles]);
        sortAutomatorItems('audio');
        hydrateAutomatorDurations('audio', state.automator.audios);
      }
    }else if(targetType === 'script'){
      const scriptFiles = files.filter(file => kindOfFile(file, 'script_guide') === 'script_guide');
      if(scriptFiles.length){
        state.automator.scripts = annotateAutomatorItems([...state.automator.scripts, ...scriptFiles]);
        sortAutomatorItems('script');
      }
    }else{
      const srtFiles = files.filter(file => kindOfFile(file, 'subtitle') === 'subtitle');
      const audioFiles = files.filter(file => kindOfFile(file, 'audio') === 'audio');
      const scriptFiles = files.filter(file => kindOfFile(file, 'script_guide') === 'script_guide');
      const folderAdded = appendAutomatorFolders(files);
      if(srtFiles.length) state.automator.srts = annotateAutomatorItems([...state.automator.srts, ...srtFiles]);
      if(audioFiles.length){
        state.automator.audios = annotateAutomatorItems([...state.automator.audios, ...audioFiles]);
        hydrateAutomatorDurations('audio', state.automator.audios);
      }
      if(scriptFiles.length) state.automator.scripts = annotateAutomatorItems([...state.automator.scripts, ...scriptFiles]);
      if(srtFiles.length) sortAutomatorItems('srt');
      if(audioFiles.length) sortAutomatorItems('audio');
      if(scriptFiles.length) sortAutomatorItems('script');
      if(folderAdded) sortAutomatorItems('folder');
      else updateAutomatorPreview();
    }
  });

  automatorPreview.addEventListener('click', event => {
    // 1. Move up or down button
    const moveBtn = event.target.closest('.automation-item-move-btn');
    if(moveBtn){
      event.preventDefault();
      event.stopPropagation();
      const type = moveBtn.dataset.automatorType;
      const index = Number(moveBtn.dataset.automatorIndex);
      const dir = moveBtn.dataset.automatorMove;
      const targetIndex = dir === 'up' ? index - 1 : index + 1;
      const list = automatorItems(type);
      if(targetIndex >= 0 && targetIndex < list.length){
        const [item] = list.splice(index, 1);
        list.splice(targetIndex, 0, item);
        list.forEach((entry, idx) => { entry._autoUsageIndex = idx; });
        state.automator.sort[type] = {criterion: 'usage', direction: 'asc'};
        saveAutomatorSortPreferences();
        updateAutomatorPreview();
      }
      return;
    }

    // 2. Remove single item
    const removeBtn = event.target.closest('.automation-item-remove');
    if(removeBtn){
      event.preventDefault();
      event.stopPropagation();
      const type = removeBtn.dataset.automatorRemoveType;
      const index = Number(removeBtn.dataset.automatorRemoveIndex);
      removeAutomatorItem(type, index);
      return;
    }

    // 3. Clear entire list
    const clearBtn = event.target.closest('.automation-sort-clear');
    if(clearBtn){
      event.preventDefault();
      event.stopPropagation();
      const type = clearBtn.dataset.automatorClear;
      clearAutomatorList(type);
      return;
    }
  });
}
if(automatorPickSrt) automatorPickSrt.addEventListener('click', () => automatorSrtInput?.click());
if(automatorPickAudio) automatorPickAudio.addEventListener('click', () => automatorAudioInput?.click());
if(automatorPickScript) automatorPickScript.addEventListener('click', () => automatorScriptInput?.click());
if(automatorPickFolders) automatorPickFolders.addEventListener('click', () => automatorVideoFolderInput?.click());

function bindAutomatorPickerDrop(element, handler){
  if(!element) return;
  ['dragenter', 'dragover'].forEach(type => {
    element.addEventListener(type, event => {
      event.preventDefault();
      element.classList.add('automation-drop-active');
    });
  });
  ['dragleave', 'drop'].forEach(type => {
    element.addEventListener(type, event => {
      if(type !== 'drop') element.classList.remove('automation-drop-active');
    });
  });
  element.addEventListener('drop', async event => {
    event.preventDefault();
    element.classList.remove('automation-drop-active');
    const files = await automatorFilesFromDrop(event.dataTransfer).catch(() => []);
    if(!files.length) return;
    handler(files);
  });
}

bindAutomatorPickerDrop(automatorPickFolders, files => {
  const added = appendAutomatorFolders(files);
  if(!added && dockSummary) dockSummary.textContent = 'AUTO: nenhuma pasta nova com vídeos foi encontrada.';
  if(added) sortAutomatorItems('folder');
  else updateAutomatorPreview();
});

bindAutomatorPickerDrop(automatorPickSrt, files => {
  const srtFiles = files.filter(file => kindOfFile(file, 'subtitle') === 'subtitle');
  if(srtFiles.length){
    state.automator.srts = annotateAutomatorItems([...state.automator.srts, ...srtFiles]);
    sortAutomatorItems('srt');
  }
});

bindAutomatorPickerDrop(automatorPickAudio, files => {
  const audioFiles = files.filter(file => kindOfFile(file, 'audio') === 'audio');
  if(audioFiles.length){
    state.automator.audios = annotateAutomatorItems([...state.automator.audios, ...audioFiles]);
    sortAutomatorItems('audio');
    hydrateAutomatorDurations('audio', state.automator.audios);
  }
});

bindAutomatorPickerDrop(automatorPickScript, files => {
  const scriptFiles = files.filter(file => kindOfFile(file, 'script_guide') === 'script_guide');
  if(scriptFiles.length){
    state.automator.scripts = annotateAutomatorItems([...state.automator.scripts, ...scriptFiles]);
    sortAutomatorItems('script');
  }
});

if(automatorSrtInput) automatorSrtInput.addEventListener('change', event => {
  state.automator.srts = annotateAutomatorItems(
    Array.from(event.target.files || []).filter(file => kindOfFile(file, 'subtitle') === 'subtitle')
  );
  sortAutomatorItems('srt');
});
if(automatorAudioInput) automatorAudioInput.addEventListener('change', event => {
  state.automator.audios = annotateAutomatorItems(
    Array.from(event.target.files || []).filter(file => kindOfFile(file, 'audio') === 'audio')
  );
  sortAutomatorItems('audio');
  hydrateAutomatorDurations('audio', state.automator.audios);
});
if(automatorScriptInput) automatorScriptInput.addEventListener('change', event => {
  state.automator.scripts = annotateAutomatorItems(
    Array.from(event.target.files || []).filter(file => kindOfFile(file, 'script_guide') === 'script_guide')
  );
  sortAutomatorItems('script');
});
if(automatorVideoFolderInput) automatorVideoFolderInput.addEventListener('change', event => {
  const added = appendAutomatorFolders(event.target.files || []);
  if(!added && dockSummary) dockSummary.textContent = 'AUTO: nenhuma pasta nova com vídeos foi encontrada.';
  event.target.value = '';
  if(added) sortAutomatorItems('folder');
  else updateAutomatorPreview();
});
if(automatorAutoHealBtn) automatorAutoHealBtn.addEventListener('click', () => {
  const plan = automatorPlan();
  if(!plan.rows.length) return;
  state.projects.forEach(p => {
    if(!p.options) p.options = defaultProjectOptions();
    p.options.allowAudioTrim = true;
  });
  if(dockSummary) dockSummary.textContent = '🪄 Auto-Healer aplicado: todos os projetos com déficit de mídia foram ajustados para renderização sem falhas com sacrifício de áudio e ritmo saudável!';
  if(automatorConfirmBtn) automatorConfirmBtn.disabled = false;
  if(automatorConfirmAndRenderBtn) automatorConfirmAndRenderBtn.disabled = false;
  if(automatorConfirmHealthyBtn) automatorConfirmHealthyBtn.disabled = false;
  automatorAutoHealBtn.textContent = '✨ Lote Balanceado!';
  setTimeout(() => { if(automatorAutoHealBtn) automatorAutoHealBtn.textContent = '🪄 Auto-Healer (Balancear Lote)'; }, 3000);
});
if(automatorConfirmBtn) automatorConfirmBtn.addEventListener('click', () => {
  applyAutomatorDistribution().catch(error => {
    if(dockSummary) dockSummary.textContent = `AUTO falhou: ${error.message || error}`;
  });
});
if(automatorConfirmHealthyBtn) automatorConfirmHealthyBtn.addEventListener('click', async () => {
  try{
    await applyAutomatorDistribution({onlyHealthy: true});
    renderQueue().catch(err => {
      if(dockSummary) dockSummary.textContent = `Erro ao iniciar render: ${err.message || err}`;
    });
  }catch(error){
    if(dockSummary) dockSummary.textContent = `AUTO falhou: ${error.message || error}`;
  }
});
if(automatorConfirmAndRenderBtn) automatorConfirmAndRenderBtn.addEventListener('click', async () => {
  try{
    await applyAutomatorDistribution();
    renderQueue().catch(err => {
      if(dockSummary) dockSummary.textContent = `Erro ao iniciar render: ${err.message || err}`;
    });
  }catch(error){
    if(dockSummary) dockSummary.textContent = `AUTO falhou: ${error.message || error}`;
  }
});
if(retryFailedBtn) retryFailedBtn.addEventListener('click', retryFailedRenders);
if(safeRenderBtn) safeRenderBtn.addEventListener('click', renderSafeCurrentProject);
if(saveSettingsBtn) saveSettingsBtn.addEventListener('click', saveSettingsNow);
if(spaceManagerBtn) spaceManagerBtn.addEventListener('click', refreshSpaceReport);
if(spaceManagerBox){
  spaceManagerBox.addEventListener('click', event => {
    const btn = event.target.closest('[data-space-clean]');
    if(btn) cleanSpace(btn.dataset.spaceClean);
  });
}
if(pauseQueueBtn) pauseQueueBtn.addEventListener('click', requestQueuePause);
if(stopQueueBtn) stopQueueBtn.addEventListener('click', () => cancelCurrentRender().catch(() => {}));
if(stopRenderBtn) stopRenderBtn.addEventListener('click', () => cancelCurrentRender().catch(() => {}));
if(settingsBtn) settingsBtn.addEventListener('click', () => {
  settingsModal?.classList.add('show');
  settingsModal?.setAttribute('aria-hidden', 'false');
});
if(closeSettingsModal) closeSettingsModal.addEventListener('click', () => {
  settingsModal?.classList.remove('show');
  settingsModal?.setAttribute('aria-hidden', 'true');
});
if(settingsModal) settingsModal.addEventListener('click', event => {
  if(event.target === settingsModal){
    settingsModal.classList.remove('show');
    settingsModal.setAttribute('aria-hidden', 'true');
  }
});
syncUiSoundControls();
if(uiSoundsToggle) uiSoundsToggle.addEventListener('change', () => {
  state.uiSoundsEnabled = uiSoundsToggle.checked;
  localStorage.setItem('glide_ui_sounds_enabled', state.uiSoundsEnabled ? '1' : '0');
  if(state.uiSoundsEnabled) playUiSound(state.uiSoundStyle, {force: true});
});
if(uiProjectDoneSoundToggle) uiProjectDoneSoundToggle.addEventListener('change', () => {
  state.uiProjectDoneSoundEnabled = uiProjectDoneSoundToggle.checked;
  localStorage.setItem('glide_ui_project_done_sound_enabled', state.uiProjectDoneSoundEnabled ? '1' : '0');
  if(state.uiProjectDoneSoundEnabled) playCompletionSound('project');
});
if(uiSoundScopeSelect) uiSoundScopeSelect.addEventListener('change', () => {
  state.uiSoundScope = uiSoundScopeSelect.value || 'global';
  localStorage.setItem('glide_ui_sound_scope', state.uiSoundScope);
  applyScopedUiSoundPreference(true);
  playUiSound(state.uiSoundStyle, {force: true});
});
if(uiSoundStyleSelect) uiSoundStyleSelect.addEventListener('change', () => {
  saveScopedUiSoundPreference(uiSoundStyleSelect.value || 'soft_tick');
  playUiSound(state.uiSoundStyle, {force: true});
});
document.querySelectorAll('[data-ui-sound-preview]').forEach(btn => {
  btn.addEventListener('click', () => {
    const style = btn.dataset.uiSoundPreview || state.uiSoundStyle;
    saveScopedUiSoundPreference(style);
    syncUiSoundControls();
    playUiSound(style, {force: true});
  });
});
if(closeRetryModal) closeRetryModal.addEventListener('click', closeRetryDialog);
if(confirmRetryBtn) confirmRetryBtn.addEventListener('click', confirmRetryQueue);
if(retryModal) retryModal.addEventListener('click', event => {
  if(event.target === retryModal) closeRetryDialog();
});
if(saveProjectsBackupBtn) saveProjectsBackupBtn.addEventListener('click', saveProjectsBackup);
if(importProjectsBackupBtn) importProjectsBackupBtn.addEventListener('click', () => projectsBackupInput?.click());
if(projectsBackupInput) projectsBackupInput.addEventListener('change', event => {
  importProjectsBackup(event.target.files?.[0]);
  event.target.value = '';
});
if(sampleRenderBtn) sampleRenderBtn.addEventListener('click', renderSample);
if(pickBatchFolderBtn) pickBatchFolderBtn.addEventListener('click', () => batchFolderInput?.click());
if(batchFolderInput) batchFolderInput.addEventListener('change', e => { importBatchFolder(e.target.files); e.target.value = ''; });
if(projectTemplateSelect) projectTemplateSelect.addEventListener('change', () => applyProjectTemplate(projectTemplateSelect.value));
if(identityPresetSelect) identityPresetSelect.addEventListener('change', () => {
  applyIdentityPackage(identityPresetSelect.value);
  if(state.uiSoundScope === 'identity') applyScopedUiSoundPreference(true);
});
if(projectNameInput){
  projectNameInput.addEventListener('input', () => {
    const project = state.projects.find(item => item.id === state.activeProjectId);
    if(!project) return;
    const nextName = projectNameInput.value.trim();
    project.name = nextName || `Projeto ${state.projects.indexOf(project) + 1}`;
    project.updatedAt = Date.now();
    renderProjectQueue();
    scheduleProjectSync();
  });
}
if(finalOutputMode){
  finalOutputMode.addEventListener('change', () => {
    state.finalOutputMode = finalOutputMode.value || 'downloads';
    localStorage.setItem('glide_final_output_mode', state.finalOutputMode);
    refreshFinalOutputUi();
    scheduleProjectSync();
  });
}
if(finalOutputFolder){
  finalOutputFolder.addEventListener('input', () => {
    state.finalOutputFolder = finalOutputFolder.value || '';
    localStorage.setItem('glide_final_output_folder', state.finalOutputFolder);
    refreshFinalOutputUi();
    scheduleProjectSync();
  });
}
if(refreshGalleryBtn) refreshGalleryBtn.addEventListener('click', refreshRenderGallery);
if(projectQueue){
  projectQueue.addEventListener('click', (event) => {
    if(state.projectDragJustDropped){
      state.projectDragJustDropped = false;
      event.preventDefault();
      return;
    }
    const reportToggle = event.target.closest('.queue-report-toggle');
    if(reportToggle){
      event.preventDefault();
      event.stopPropagation();
      const projectId = reportToggle.dataset.reportProject;
      openReportModal(projectId, 'project');
      return;
    }
    const card = event.target.closest('[data-project-id]');
    if(!card) return;
    selectProjectFromQueue(card.dataset.projectId);
  });
  projectQueue.addEventListener('keydown', (event) => {
    if(event.target.closest('.queue-report-toggle')) return;
    const card = event.target.closest('[data-project-id]');
    if(!card || !['Enter', ' '].includes(event.key)) return;
    event.preventDefault();
    selectProjectFromQueue(card.dataset.projectId);
  });
  projectQueue.addEventListener('dragstart', (event) => {
    if(event.target.closest('.queue-report-toggle')){
      event.preventDefault();
      return;
    }
    const card = event.target.closest('[data-project-id]');
    if(!card || state.queueRendering){
      event.preventDefault();
      return;
    }
    captureActiveProject();
    state.dragProjectId = card.dataset.projectId;
    state.projectDragTarget = null;
    state.projectDragTargetRect = null;
    state.projectDragPlaceAfter = false;
    card.classList.add('dragging');
    projectQueue.classList.add('project-queue-dragging');
    document.body.classList.add('interaction-drag-active');
    event.dataTransfer.effectAllowed = 'move';
    event.dataTransfer.setData('text/plain', state.dragProjectId);
  });
  projectQueue.addEventListener('dragover', (event) => {
    const card = event.target.closest('[data-project-id]');
    if(!card || !state.dragProjectId || state.queueRendering) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
    if(state.projectDragTarget !== card){
      state.projectDragTarget?.classList.remove('drag-over-before', 'drag-over-after');
      state.projectDragTarget = card;
      state.projectDragTargetRect = card.getBoundingClientRect();
    }
    const rect = state.projectDragTargetRect;
    const placeAfter = event.clientX > rect.left + rect.width / 2 || event.clientY > rect.top + rect.height * 0.72;
    state.projectDragPlaceAfter = placeAfter;
    card.classList.toggle('drag-over-before', !placeAfter && card.dataset.projectId !== state.dragProjectId);
    card.classList.toggle('drag-over-after', placeAfter && card.dataset.projectId !== state.dragProjectId);
  });
  projectQueue.addEventListener('dragleave', (event) => {
    const card = event.target.closest('[data-project-id]');
    if(!card || card.contains(event.relatedTarget)) return;
    card.classList.remove('drag-over-before', 'drag-over-after');
    if(state.projectDragTarget === card){
      state.projectDragTarget = null;
      state.projectDragTargetRect = null;
    }
  });
  projectQueue.addEventListener('drop', async (event) => {
    const card = event.target.closest('[data-project-id]');
    if(!card || !state.dragProjectId || state.queueRendering) return;
    event.preventDefault();
    const placeAfter = state.projectDragTarget === card ? state.projectDragPlaceAfter : card.classList.contains('drag-over-after');
    const changed = reorderProjectsLocal(state.dragProjectId, card.dataset.projectId, placeAfter);
    state.projectDragJustDropped = true;
    clearQueueDragMarkers();
    projectQueue.classList.remove('project-queue-dragging');
    document.body.classList.remove('interaction-drag-active');
    state.dragProjectId = null;
    if(changed){
      renderProjectQueue();
      await persistProjectOrder();
    }
  });
  projectQueue.addEventListener('dragend', () => {
    clearQueueDragMarkers();
    projectQueue.classList.remove('project-queue-dragging');
    document.body.classList.remove('interaction-drag-active');
    state.dragProjectId = null;
    window.setTimeout(() => { state.projectDragJustDropped = false; }, 50);
  });
}
if(queueReportsBtn) queueReportsBtn.addEventListener('click', () => openReportModal(state.activeProjectId, 'queue'));
if(reportProjectViewBtn) reportProjectViewBtn.addEventListener('click', () => {
  state.reportView = 'project';
  renderReportModal();
});
if(reportQueueViewBtn) reportQueueViewBtn.addEventListener('click', () => {
  state.reportView = 'queue';
  renderReportModal();
});
if(closeReportModal) closeReportModal.addEventListener('click', hideReportModal);
if(reportModal){
  reportModal.addEventListener('click', event => {
    const openProject = event.target.closest('[data-modal-report-project]');
    if(openProject){
      state.reportProjectId = openProject.dataset.modalReportProject;
      state.reportView = 'project';
      renderReportModal();
      return;
    }
    if(event.target === reportModal) hideReportModal();
  });
}
openOutputBtn.addEventListener('click', openOutput);
openExportsBtn.addEventListener('click', openExports);
toggleLogBtn.addEventListener('click', () => {
  renderLog.classList.toggle('hidden');
  toggleLogBtn.textContent = renderLog.classList.contains('hidden') ? 'Detalhes técnicos' : 'Ocultar detalhes';
});
$('#closeModal').addEventListener('click', () => {
  if(state.renderActive || state.queueRendering){
    renderLog.classList.add('hidden');
    toggleLogBtn.textContent = 'Detalhes técnicos';
    const isMinimized = modal.classList.toggle('minimized');
    $('#closeModal').textContent = isMinimized ? 'Expandir' : 'Minimizar';
    dockSummary.textContent = isMinimized
      ? 'Render minimizado. Use Pausar fila ou Parar render no painel compacto se necessário.'
      : 'Render em foco. O fundo fica levemente desfocado enquanto acompanha o progresso.';
    return;
  }
  modal.classList.remove('minimized');
  modal.classList.remove('show');
  modal.setAttribute('aria-hidden', 'true');
});

window.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    const activeModals = [
      $('#settingsModal'),
      $('#retryModal'),
      $('#reportModal'),
      $('#scriptGuideModal'),
      $('#automatorModal')
    ];
    for (const m of activeModals) {
      if (m && m.classList.contains('show')) {
        m.classList.remove('show');
        m.setAttribute('aria-hidden', 'true');
        return;
      }
    }
    const renderModal = $('#renderModal');
    if (renderModal && renderModal.classList.contains('show') && !state.renderActive && !state.queueRendering) {
      renderModal.classList.remove('minimized');
      renderModal.classList.remove('show');
      renderModal.setAttribute('aria-hidden', 'true');
    }
  }
});

document.addEventListener('click', event => {
  if(shouldPlayUiSound(event)) playUiSound();
}, true);

document.addEventListener('click', (e) => {
  const btn = e.target.closest('.remove-file');
  if(!btn) return;
  e.preventDefault();
  e.stopPropagation();
  const row = btn.closest('[data-rel]');
  if(!row) return;
  const kind = row.classList.contains('background-item') ? 'background_music' : (row.classList.contains('audio-item') ? 'audio' : 'video');
  removeFromState(kind, row.dataset.rel);
});

document.querySelectorAll('.nav-item[data-target]').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    const targetId = btn.dataset.target;
    if(targetId === 'subtitleSection' && state.uiMode === 'simple'){
      state.uiMode = 'advanced';
      document.body.dataset.uiMode = 'advanced';
      if(uiModeSelect) uiModeSelect.value = 'advanced';
      localStorage.setItem('glide_ui_mode', 'advanced');
    }
    const el = document.getElementById(targetId);
    if(el){
      window.requestAnimationFrame(() => {
        el.scrollIntoView({behavior: 'smooth', block: 'start'});
      });
    }
  });
});

document.addEventListener('change', (event) => {
  const target = event.target;
  if(!(target instanceof HTMLElement)) return;
  if(target.closest('#exportSection, #subtitleSection, #backgroundSection, #introPanel, #queueSection, #preflightPanel')){
    scheduleProjectSync();
  }
});
document.addEventListener('input', (event) => {
  const target = event.target;
  if(!(target instanceof HTMLElement)) return;
  if(target.closest('#exportSection, #subtitleSection, #backgroundSection, #introPanel, #queueSection, #preflightPanel')){
    scheduleProjectSync();
  }
});

window.addEventListener('beforeunload', (e) => {
  const active = captureActiveProject();
  if(active) syncProjectSnapshot(active, {immediate: true, beacon: true});
  if(!state.renderActive && !state.queueRendering) return;
  e.preventDefault();
  e.returnValue = '';
});

function pingDesktop(){
  if(!DESKTOP_MODE) return;
  fetch('/api/desktop-heartbeat', {method: 'POST', cache: 'no-store', keepalive: true}).catch(() => {});
}

function setupDesktopMode(){
  if(!DESKTOP_MODE) return;
  document.body.classList.add('desktop-mode');
  pingDesktop();
  setInterval(pingDesktop, 10000);
  document.addEventListener('visibilitychange', () => {
    if(!document.hidden) pingDesktop();
  });
}

function setupUiPerformanceGuards(){
  document.body.classList.add('ui-performance-steady');
  const animatedRegions = [
    previewMedia?.closest('.subtitle-preview'),
    introPanel,
    ctaPreviewStage,
    musicLibraryShelf,
  ].filter(Boolean);
  if(!('IntersectionObserver' in window)) return;
  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      entry.target.classList.toggle('performance-paused', !entry.isIntersecting);
      entry.target.querySelectorAll('video').forEach(video => {
        if(entry.isIntersecting) video.play().catch(() => {});
        else video.pause();
      });
    });
  }, {rootMargin: '160px 0px'});
  animatedRegions.forEach(region => observer.observe(region));
}

document.addEventListener('visibilitychange', () => {
  if(!document.hidden) return;
  const active = captureActiveProject();
  if(active) syncProjectSnapshot(active, {immediate: true, beacon: true});
});

setupDrag(videoTimeline, 'videos');
setupDrag(audioTimeline, 'audios');
if(backgroundTimeline) setupDrag(backgroundTimeline, 'backgroundTracks');
applyThemeMode();
runEditorIntro();
applyUiMode();
applySidebarState();
setupDesktopMode();
setupUiPerformanceGuards();
applyPresetToControls();
applyIntroPresetToControls();
refreshBackgroundMusicUi();
refreshFinalOutputUi();
loadRuntimeConfig();
loadCtaAssets();
warmBackendCache();
async function fetchDropzoneStatus() {
  try {
    const res = await fetch('/api/dropzone/status');
    if (!res.ok) return;
    const data = await res.json();
    updateDropzoneUI(data);
  } catch (err) {
    // silent
  }
}

function updateDropzoneUI(data) {
  const el = $('#dropzoneStatusBar');
  if (!el || !data) return;
  const count = data.discovered_folders || 0;
  const desc = el.querySelector('.dropzone-desc');
  if (desc) {
    if (count > 0) {
      desc.innerHTML = `Solte pastas com mídia em <code>DROPZONE/</code> — <strong>${count} projeto(s) autônomo(s) detectado(s)</strong>.`;
    } else {
      desc.innerHTML = `Solte pastas com mídia em <code>DROPZONE/</code> para renderização 100% autônoma.`;
    }
  }
}

async function triggerDropzoneScan() {
  const scanBtn = $('#dropzoneScanBtn');
  if (scanBtn) {
    scanBtn.disabled = true;
    scanBtn.textContent = 'Escaneando...';
  }
  try {
    const res = await fetch('/api/dropzone/scan_now', { method: 'POST' });
    if (res.ok) {
      const data = await res.json();
      updateDropzoneUI(data);
      if (typeof fetchQueueStatus === 'function') fetchQueueStatus();
      if (typeof refreshQueueProjects === 'function') refreshQueueProjects();
    }
  } catch (e) {
    // silent
  } finally {
    if (scanBtn) {
      scanBtn.disabled = false;
      scanBtn.textContent = 'Escanear agora';
    }
  }
}

const dropzoneScanBtn = $('#dropzoneScanBtn');
if (dropzoneScanBtn) {
  dropzoneScanBtn.addEventListener('click', triggerDropzoneScan);
}

const colorGradeSelect = $('#colorGradeSelect');
if (colorGradeSelect) {
  colorGradeSelect.addEventListener('change', () => {
    const active = captureActiveProject();
    if (active) syncProjectSnapshot(active);
  });
}

fetchDropzoneStatus();
setInterval(fetchDropzoneStatus, 10000);
loadPresetMusicStatus();
loadSfxPreviewMap();
loadSemanticModelStatus();
checkHealth();
refreshRenderGallery();
initializeProjectQueue().then(resumeActiveJob);


