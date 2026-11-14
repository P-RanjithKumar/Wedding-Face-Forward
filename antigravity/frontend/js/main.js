/**
 * AURA — Frontend Application v3.0 (by DARK intelligence)
 * Premium Dark Mode Desktop UI
 * Handles enrollment flow, gallery display, and API interactions
 */

// ============================================================
// API Service
// ============================================================
const API = {
    baseUrl: '/api',

    async enroll(formData) {
        const response = await fetch(`${this.baseUrl}/enroll`, {
            method: 'POST',
            body: formData,
        });
        return response.json();
    },

    async getStats() {
        try {
            const response = await fetch(`${this.baseUrl}/stats`);
            if (!response.ok) throw new Error('Stats not available');
            return response.json();
        } catch (error) {
            console.warn('Could not fetch stats:', error);
            return null;
        }
    },

    // Gallery calls need the guest's person_id and the private gallery_token
    // returned by /api/enroll; the server only shows that guest's photos.
    _galleryUrl(user, endpoint, params) {
        const query = new URLSearchParams({ token: user.gallery_token || '', ...params });
        return `${this.baseUrl}/gallery/${encodeURIComponent(user.person_id)}/${endpoint}?${query}`;
    },

    async getPhotos(user, category = 'solo') {
        const response = await fetch(this._galleryUrl(user, 'photos', { category }));
        if (!response.ok) throw new Error(`Gallery request failed (${response.status})`);
        return response.json();
    },

    getPhotoUrl(user, photoPath) {
        return this._galleryUrl(user, 'photo', { path: photoPath });
    },

    getThumbnailUrl(user, photoPath) {
        return this._galleryUrl(user, 'thumbnail', { path: photoPath });
    }
};


// ============================================================
// SVG Icons (Lucide-style inline)
// ============================================================
const Icons = {
    check: `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" fill="none" stroke="currentColor"><polyline points="20 6 9 17 4 12"/></svg>`,
    x: `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" fill="none" stroke="currentColor"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>`,
    info: `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" fill="none" stroke="currentColor"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/></svg>`,
    alertCircle: `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" fill="none" stroke="currentColor"><circle cx="12" cy="12" r="10"/><line x1="12" x2="12" y1="8" y2="12"/><line x1="12" x2="12.01" y1="16" y2="16"/></svg>`,
};


// ============================================================
// State Management
// ============================================================
const State = {
    currentStep: 1,
    selfieFile: null,
    enrolledUser: null,
    currentGalleryTab: 'solo',
    galleryPhotos: { solo: [], group: [] },
    currentPhotoIndex: 0,
    videoStream: null,

    reset() {
        this.currentStep = 1;
        this.selfieFile = null;
        this.stopVideoStream();
    },

    stopVideoStream() {
        if (this.videoStream) {
            this.videoStream.getTracks().forEach(track => track.stop());
            this.videoStream = null;
        }
    }
};


// ============================================================
// DOM Elements
// ============================================================
const Elements = {
    navbar: document.getElementById('navbar'),
    statPhotos: document.getElementById('stat-photos'),
    statGuests: document.getElementById('stat-guests'),
    statFaces: document.getElementById('stat-faces'),
    enrollForm: document.getElementById('enrollForm'),
    cameraArea: document.getElementById('cameraArea'),
    cameraView: document.getElementById('cameraView'),
    videoWrapper: document.getElementById('videoWrapper'),
    cameraStream: document.getElementById('cameraStream'),
    captureCanvas: document.getElementById('captureCanvas'),
    captureBtn: document.getElementById('captureBtn'),
    retakeBtn: document.getElementById('retakeBtn'),
    previewContent: document.getElementById('previewContent'),
    selfiePreview: document.getElementById('selfiePreview'),
    cameraActions: document.getElementById('cameraActions'),
    retakeActions: document.getElementById('retakeActions'),
    cameraUnavailable: document.getElementById('cameraUnavailable'),
    cameraUnavailableText: document.getElementById('cameraUnavailableText'),
    uploadFallback: document.getElementById('uploadFallback'),
    uploadBtnText: document.getElementById('uploadBtnText'),
    selfieFileInput: document.getElementById('selfieFileInput'),
    retryCameraBtn: document.getElementById('retryCameraBtn'),
    step1: document.getElementById('step-1'),
    step2: document.getElementById('step-2'),
    userName: document.getElementById('userName'),
    countryCode: document.getElementById('countryCode'),
    userPhone: document.getElementById('userPhone'),
    userEmail: document.getElementById('userEmail'),
    consent: document.getElementById('consent'),
    prevBtn: document.getElementById('prevBtn'),
    nextBtn: document.getElementById('nextBtn'),
    submitBtn: document.getElementById('submitBtn'),
    progressSteps: document.querySelectorAll('.progress-step'),
    resultsModal: document.getElementById('resultsModal'),
    modalBackdrop: document.getElementById('modalBackdrop'),
    modalClose: document.getElementById('modalClose'),
    resultSuccess: document.getElementById('resultSuccess'),
    resultError: document.getElementById('resultError'),
    matchMessage: document.getElementById('matchMessage'),
    soloCount: document.getElementById('soloCount'),
    groupCount: document.getElementById('groupCount'),
    galleryPreview: document.getElementById('galleryPreview'),
    viewGalleryBtn: document.getElementById('viewGalleryBtn'),
    errorMessage: document.getElementById('errorMessage'),
    tryAgainBtn: document.getElementById('tryAgainBtn'),
    gallerySection: document.getElementById('gallerySection'),
    backToHome: document.getElementById('backToHome'),
    galleryUserName: document.getElementById('galleryUserName'),
    galleryGrid: document.getElementById('galleryGrid'),
    galleryEmpty: document.getElementById('galleryEmpty'),
    tabBtns: document.querySelectorAll('.tab-btn'),
    tabSoloCount: document.getElementById('tabSoloCount'),
    tabGroupCount: document.getElementById('tabGroupCount'),
    lightbox: document.getElementById('lightbox'),
    lightboxClose: document.getElementById('lightboxClose'),
    lightboxPrev: document.getElementById('lightboxPrev'),
    lightboxNext: document.getElementById('lightboxNext'),
    lightboxImage: document.getElementById('lightboxImage'),
    lightboxCounter: document.getElementById('lightboxCounter'),
    downloadBtn: document.getElementById('downloadBtn'),
    heroSection: document.getElementById('hero'),
    featuresSection: document.getElementById('features'),
    enrollSection: document.getElementById('enroll'),
};


// ============================================================
// Initialization
// ============================================================
function init() {
    setupEventListeners();
    openGalleryFromLink();
    setupAnimations();
    animateStatsOnLoad();
}


// ============================================================
// Event Listeners
// ============================================================
function setupEventListeners() {
    // Navbar scroll effect
    window.addEventListener('scroll', handleScroll, { passive: true });

    // Camera actions
    if (Elements.captureBtn) Elements.captureBtn.addEventListener('click', capturePhoto);
    if (Elements.retakeBtn) Elements.retakeBtn.addEventListener('click', retakePhoto);
    if (Elements.selfieFileInput) Elements.selfieFileInput.addEventListener('change', handleSelfieFile);
    if (Elements.retryCameraBtn) Elements.retryCameraBtn.addEventListener('click', startCamera);

    // Start camera on step 1
    // Don't ask for the camera when the page was opened from a gallery link
    if (State.currentStep === 1 && !hasGalleryLink()) startCamera();

    // Form navigation
    if (Elements.prevBtn) Elements.prevBtn.addEventListener('click', goToPrevStep);
    if (Elements.nextBtn) Elements.nextBtn.addEventListener('click', goToNextStep);

    // Form submission
    if (Elements.enrollForm) Elements.enrollForm.addEventListener('submit', handleSubmit);

    // Modal
    if (Elements.modalClose) Elements.modalClose.addEventListener('click', closeModal);
    if (Elements.modalBackdrop) Elements.modalBackdrop.addEventListener('click', closeModal);
    if (Elements.tryAgainBtn) Elements.tryAgainBtn.addEventListener('click', handleTryAgain);
    if (Elements.viewGalleryBtn) Elements.viewGalleryBtn.addEventListener('click', openGallery);

    // Gallery
    if (Elements.backToHome) {
        Elements.backToHome.addEventListener('click', (e) => {
            e.preventDefault();
            closeGallery();
        });
    }

    if (Elements.tabBtns) {
        Elements.tabBtns.forEach(btn => {
            btn.addEventListener('click', () => switchTab(btn.dataset.tab));
        });
    }

    // Lightbox
    if (Elements.lightboxClose) Elements.lightboxClose.addEventListener('click', closeLightbox);
    if (Elements.lightboxPrev) Elements.lightboxPrev.addEventListener('click', () => navigateLightbox(-1));
    if (Elements.lightboxNext) Elements.lightboxNext.addEventListener('click', () => navigateLightbox(1));
    if (Elements.lightbox) {
        Elements.lightbox.addEventListener('click', (e) => {
            if (e.target === Elements.lightbox) closeLightbox();
        });
    }

    // Keyboard navigation
    document.addEventListener('keydown', handleKeydown);
}


// ============================================================
// Scroll-driven Animations
// ============================================================
function setupAnimations() {
    setupRevealAnimations();
    setupFeatureCardAnimations();
}

function setupRevealAnimations() {
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('visible');
            }
        });
    }, { threshold: 0.1 });

    document.querySelectorAll('.reveal-text, .hero-subtitle, .hero-actions').forEach(el => {
        observer.observe(el);
    });
}

function setupFeatureCardAnimations() {
    const observer = new IntersectionObserver((entries) => {
        entries.forEach((entry, index) => {
            if (entry.isIntersecting) {
                entry.target.style.transitionDelay = `${index * 100}ms`;
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
            }
        });
    }, { threshold: 0.15 });

    document.querySelectorAll('.feature-card').forEach(card => {
        card.style.opacity = '0';
        card.style.transform = 'translateY(20px)';
        card.style.transition = 'opacity 0.5s cubic-bezier(0.16, 1, 0.3, 1), transform 0.5s cubic-bezier(0.16, 1, 0.3, 1)';
        observer.observe(card);
    });
}


// ============================================================
// Navbar
// ============================================================
function handleScroll() {
    const scrolled = window.scrollY > 10;
    if (Elements.navbar) {
        Elements.navbar.classList.toggle('scrolled', scrolled);
    }
}


// ============================================================
// Stats
// ============================================================
async function loadStats() {
    const stats = await API.getStats();
    if (stats) {
        if (Elements.statPhotos) animateNumber(Elements.statPhotos, stats.total_photos || 0);
        if (Elements.statGuests) animateNumber(Elements.statGuests, stats.total_enrolled || 0);
        if (Elements.statFaces) animateNumber(Elements.statFaces, stats.total_faces || 0);
    }
}

function animateNumber(element, target) {
    const duration = 1800;
    const startTime = performance.now();

    function update(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const easeOut = 1 - Math.pow(1 - progress, 3);
        const current = Math.round(target * easeOut);

        element.textContent = current.toLocaleString();

        if (progress < 1) {
            requestAnimationFrame(update);
        }
    }

    requestAnimationFrame(update);
}

function animateStatsOnLoad() {
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                loadStats();
                observer.disconnect();
            }
        });
    }, { threshold: 0.5 });

    const statsContainer = document.querySelector('.hero-stats');
    if (statsContainer) {
        observer.observe(statsContainer);
    }
}


// ============================================================
// Camera Capture
// ============================================================
// Two ways to get a selfie:
//  1. Live camera (getUserMedia). Browsers only allow it on https:// or
//     localhost, so it usually does NOT work on guests' phones that open
//     http://<laptop-ip>:8000 on the venue Wi-Fi.
//  2. "Take / choose a photo" file input with capture="user". Works over
//     plain http:// and opens the phone's front camera directly.
// If (1) is unavailable or denied, the page switches to (2) as the main action.

const MAX_SELFIE_EDGE = 1600;   // px; phone photos are shrunk before upload

function setCameraMode(mode, message) {
    // mode: 'live' | 'unavailable' | 'preview'
    const live = mode === 'live';
    const preview = mode === 'preview';
    const unavailable = mode === 'unavailable';

    State.cameraMode = mode;
    if (Elements.videoWrapper) Elements.videoWrapper.classList.toggle('hidden', !live);
    if (Elements.cameraActions) Elements.cameraActions.classList.toggle('hidden', !live);
    if (Elements.previewContent) Elements.previewContent.classList.toggle('hidden', !preview);
    if (Elements.retakeActions) Elements.retakeActions.classList.toggle('hidden', !preview);
    if (Elements.cameraView) Elements.cameraView.classList.toggle('captured', preview);
    if (Elements.cameraUnavailable) Elements.cameraUnavailable.classList.toggle('hidden', !unavailable);
    if (Elements.uploadFallback) {
        Elements.uploadFallback.classList.toggle('hidden', preview);
        Elements.uploadFallback.classList.toggle('is-primary', unavailable);
    }
    if (Elements.uploadBtnText) {
        Elements.uploadBtnText.textContent = unavailable ? 'Take a selfie' : 'Or take / choose a photo';
    }
    if (unavailable && message && Elements.cameraUnavailableText) {
        Elements.cameraUnavailableText.textContent = message;
    }
}

async function startCamera() {
    if (Elements.retryCameraBtn) Elements.retryCameraBtn.classList.add('hidden');

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        // Typical on phones over http:// — not an error for the guest.
        State.cameraSupported = false;
        setCameraMode('unavailable', "Tap the button below to take a selfie with your phone's camera.");
        return;
    }

    try {
        const stream = await navigator.mediaDevices.getUserMedia({
            video: {
                facingMode: 'user',
                width: { ideal: 1280 },
                height: { ideal: 720 }
            },
            audio: false
        });

        State.cameraSupported = true;
        State.videoStream = stream;
        if (Elements.cameraStream) {
            Elements.cameraStream.srcObject = stream;
            Elements.cameraStream.onloadedmetadata = () => {
                Elements.cameraStream.play();
            };
        }
        setCameraMode('live');

    } catch (error) {
        console.error('Camera access error:', error);
        State.cameraSupported = false;
        setCameraMode('unavailable', "We couldn't open the camera here. Tap the button below to take a selfie instead.");
        if (Elements.retryCameraBtn) Elements.retryCameraBtn.classList.remove('hidden');
    }
}

function showSelfiePreview(file, previewUrl) {
    State.selfieFile = file;
    if (Elements.selfiePreview) Elements.selfiePreview.src = previewUrl;
    setCameraMode('preview');
    State.stopVideoStream();
}

function capturePhoto() {
    const video = Elements.cameraStream;
    const canvas = Elements.captureCanvas;

    if (!video || !canvas || !video.videoWidth) return;

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;

    const ctx = canvas.getContext('2d');
    ctx.translate(canvas.width, 0);
    ctx.scale(-1, 1);
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    canvas.toBlob((blob) => {
        const file = new File([blob], "selfie.jpg", { type: "image/jpeg" });
        showSelfiePreview(file, canvas.toDataURL('image/jpeg'));
        showToast('Selfie captured successfully', 'success');
    }, 'image/jpeg', 0.9);
}

// Shrink a phone photo to MAX_SELFIE_EDGE as JPEG. Returns null if the
// browser can't decode it (e.g. HEIC on some browsers); the original file
// is uploaded then, since the server can read HEIC.
function shrinkImage(file) {
    return new Promise((resolve) => {
        const url = URL.createObjectURL(file);
        const img = new Image();
        img.onload = () => {
            const scale = Math.min(1, MAX_SELFIE_EDGE / Math.max(img.naturalWidth, img.naturalHeight));
            const canvas = document.createElement('canvas');
            canvas.width = Math.round(img.naturalWidth * scale);
            canvas.height = Math.round(img.naturalHeight * scale);
            canvas.getContext('2d').drawImage(img, 0, 0, canvas.width, canvas.height);
            URL.revokeObjectURL(url);
            canvas.toBlob((blob) => {
                if (!blob) return resolve(null);
                resolve({
                    file: new File([blob], 'selfie.jpg', { type: 'image/jpeg' }),
                    previewUrl: canvas.toDataURL('image/jpeg', 0.8),
                });
            }, 'image/jpeg', 0.9);
        };
        img.onerror = () => { URL.revokeObjectURL(url); resolve(null); };
        img.src = url;
    });
}

async function handleSelfieFile(e) {
    const file = e.target.files && e.target.files[0];
    e.target.value = '';   // allow choosing the same file again later
    if (!file) return;

    if (file.type && !file.type.startsWith('image/')) {
        showToast('Please choose a photo', 'error');
        return;
    }

    const shrunk = await shrinkImage(file);
    if (shrunk) {
        showSelfiePreview(shrunk.file, shrunk.previewUrl);
    } else if (file.size <= 15 * 1024 * 1024) {
        showSelfiePreview(file, URL.createObjectURL(file));
    } else {
        showToast('That photo is too large. Please take a new selfie.', 'error');
        return;
    }
    showToast('Photo added', 'success');
}

function retakePhoto() {
    State.selfieFile = null;
    if (State.cameraSupported === false) {
        // No live camera: go straight back to the phone camera / picker
        setCameraMode('unavailable');
        if (Elements.selfieFileInput) Elements.selfieFileInput.click();
    } else {
        startCamera();
    }
}


// ============================================================
// Form Navigation
// ============================================================
function goToNextStep() {
    if (State.currentStep === 1) {
        if (!State.selfieFile) {
            showToast('Please capture a selfie first', 'error');
            return;
        }
        showStep(2);
    }
}

function goToPrevStep() {
    if (State.currentStep === 2) {
        showStep(1);
    }
}

function showStep(step) {
    State.currentStep = step;

    if (Elements.step1) Elements.step1.classList.toggle('active', step === 1);
    if (Elements.step2) Elements.step2.classList.toggle('active', step === 2);

    if (Elements.progressSteps) {
        Elements.progressSteps.forEach((el, index) => {
            el.classList.toggle('active', index + 1 <= step);
            el.classList.toggle('completed', index + 1 < step);
        });
    }

    if (Elements.prevBtn) Elements.prevBtn.classList.toggle('hidden', step === 1);
    if (Elements.nextBtn) Elements.nextBtn.classList.toggle('hidden', step === 2);
    if (Elements.submitBtn) Elements.submitBtn.classList.toggle('hidden', step !== 2);

    if (step === 1 && !State.selfieFile) {
        startCamera();
    } else {
        State.stopVideoStream();
    }
}


// ============================================================
// Form Submission
// ============================================================
async function handleSubmit(e) {
    e.preventDefault();

    if (!State.selfieFile) {
        showToast('Please capture a selfie first', 'error');
        return;
    }

    if (!Elements.userName.value.trim()) {
        showToast('Please enter your name', 'error');
        Elements.userName.focus();
        return;
    }

    if (!Elements.consent.checked) {
        showToast('Please accept the consent terms', 'error');
        return;
    }

    if (!Elements.userPhone.value.trim()) {
        showToast('Please enter your phone number', 'error');
        Elements.userPhone.focus();
        return;
    }

    const btnText = Elements.submitBtn.querySelector('.btn-text');
    const btnLoading = Elements.submitBtn.querySelector('.btn-loading');
    if (btnText) btnText.classList.add('hidden');
    if (btnLoading) btnLoading.classList.remove('hidden');
    Elements.submitBtn.disabled = true;

    try {
        const formData = new FormData();
        formData.append('selfie', State.selfieFile);
        formData.append('name', Elements.userName.value.trim());

        const fullPhone = Elements.countryCode.value.trim() + Elements.userPhone.value.trim();
        formData.append('phone', fullPhone);
        formData.append('email', Elements.userEmail.value.trim());
        formData.append('consent', Elements.consent.checked);

        const result = await API.enroll(formData);

        if (result.success) {
            showSuccessModal(result);
        } else {
            showErrorModal(result.message);
        }
    } catch (error) {
        console.error('Enrollment error:', error);
        showErrorModal('An error occurred. Please try again.');
    } finally {
        if (btnText) btnText.classList.remove('hidden');
        if (btnLoading) btnLoading.classList.add('hidden');
        Elements.submitBtn.disabled = false;
    }
}


// ============================================================
// Modal
// ============================================================
function showSuccessModal(result) {
    State.enrolledUser = result;

    if (Elements.matchMessage) Elements.matchMessage.textContent = `Welcome, ${result.person_name}! Your photos are ready.`;
    if (Elements.soloCount) Elements.soloCount.textContent = result.solo_count || 0;
    if (Elements.groupCount) Elements.groupCount.textContent = result.group_count || 0;

    loadPreviewPhotos(result);

    if (Elements.resultSuccess) Elements.resultSuccess.classList.remove('hidden');
    if (Elements.resultError) Elements.resultError.classList.add('hidden');
    if (Elements.resultsModal) Elements.resultsModal.classList.remove('hidden');
    document.body.style.overflow = 'hidden';
}

function showErrorModal(message) {
    if (Elements.errorMessage) Elements.errorMessage.textContent = message;
    if (Elements.resultSuccess) Elements.resultSuccess.classList.add('hidden');
    if (Elements.resultError) Elements.resultError.classList.remove('hidden');
    if (Elements.resultsModal) Elements.resultsModal.classList.remove('hidden');
    document.body.style.overflow = 'hidden';
}

function closeModal() {
    if (Elements.resultsModal) Elements.resultsModal.classList.add('hidden');
    document.body.style.overflow = '';
}

function handleTryAgain() {
    closeModal();
    State.reset();
    showStep(1);

    if (Elements.previewContent) Elements.previewContent.classList.add('hidden');
    if (Elements.videoWrapper) Elements.videoWrapper.classList.remove('hidden');
    if (Elements.cameraActions) Elements.cameraActions.classList.remove('hidden');
    if (Elements.retakeActions) Elements.retakeActions.classList.add('hidden');
    if (Elements.cameraView) Elements.cameraView.classList.remove('captured');

    startCamera();

    if (Elements.enrollForm) Elements.enrollForm.reset();
}

async function loadPreviewPhotos(user) {
    try {
        const photos = await API.getPhotos(user, 'solo');
        const preview = photos.slice(0, 3);

        if (Elements.galleryPreview) {
            Elements.galleryPreview.innerHTML = preview.map(photo => `
              <img src="${API.getThumbnailUrl(user, photo.path)}" alt="Photo preview" loading="lazy">
            `).join('');

            if (preview.length === 0) {
                Elements.galleryPreview.innerHTML = '<p style="color: var(--text-tertiary); font-size: var(--text-sm);">Photos are being processed...</p>';
            }
        }
    } catch (error) {
        console.error('Could not load preview photos:', error);
    }
}


// ============================================================
// Gallery
// ============================================================
function openGallery(e) {
    e?.preventDefault();

    if (!State.enrolledUser) return;

    closeModal();

    if (Elements.heroSection) Elements.heroSection.classList.add('hidden');
    if (Elements.featuresSection) Elements.featuresSection.classList.add('hidden');
    if (Elements.enrollSection) Elements.enrollSection.classList.add('hidden');
    const footer = document.querySelector('.footer');
    if (footer) footer.classList.add('hidden');

    if (Elements.gallerySection) Elements.gallerySection.classList.remove('hidden');
    if (Elements.galleryUserName) Elements.galleryUserName.textContent = State.enrolledUser.person_name;

    loadGalleryPhotos();
    window.scrollTo(0, 0);
}

// Direct gallery links (?g=<person id>&k=<private key>), shared from the
// desktop app's "Share Links" window as a WhatsApp fallback (2026-11-14).
function hasGalleryLink() {
    const params = new URLSearchParams(window.location.search);
    return params.has('g') && params.has('k');
}

async function openGalleryFromLink() {
    if (!hasGalleryLink()) return;
    const params = new URLSearchParams(window.location.search);
    const id = params.get('g');
    const key = params.get('k');
    try {
        const response = await fetch(
            `${API.baseUrl}/gallery/${encodeURIComponent(id)}/info?token=${encodeURIComponent(key)}`);
        if (!response.ok) throw new Error(`status ${response.status}`);
        const info = await response.json();
        State.enrolledUser = { person_id: info.person_id, person_name: info.person_name, gallery_token: key };
        State.openedFromLink = true;
        openGallery();
    } catch (error) {
        console.warn('Gallery link not valid:', error);
        showToast('This gallery link is not valid. Take a selfie below to find your photos.', 'error');
        startCamera();
    }
}

function closeGallery() {
    if (Elements.gallerySection) Elements.gallerySection.classList.add('hidden');
    if (Elements.heroSection) Elements.heroSection.classList.remove('hidden');
    if (Elements.featuresSection) Elements.featuresSection.classList.remove('hidden');
    if (Elements.enrollSection) Elements.enrollSection.classList.remove('hidden');
    const footer = document.querySelector('.footer');
    if (footer) footer.classList.remove('hidden');

    if (State.openedFromLink) {
        State.openedFromLink = false;
        if (!State.videoStream && !State.selfieFile) startCamera();
    }

    window.scrollTo(0, 0);
}

async function loadGalleryPhotos() {
    if (!State.enrolledUser) return;

    try {
        const soloPhotos = await API.getPhotos(State.enrolledUser, 'solo');
        State.galleryPhotos.solo = soloPhotos;
        if (Elements.tabSoloCount) Elements.tabSoloCount.textContent = soloPhotos.length;

        const groupPhotos = await API.getPhotos(State.enrolledUser, 'group');
        State.galleryPhotos.group = groupPhotos;
        if (Elements.tabGroupCount) Elements.tabGroupCount.textContent = groupPhotos.length;

        renderGallery();
    } catch (error) {
        console.error('Could not load gallery photos:', error);
        showToast('Could not load photos', 'error');
    }
}

function switchTab(tab) {
    State.currentGalleryTab = tab;

    if (Elements.tabBtns) {
        Elements.tabBtns.forEach(btn => {
            btn.classList.toggle('active', btn.dataset.tab === tab);
        });
    }

    renderGallery();
}

function renderGallery() {
    const photos = State.galleryPhotos[State.currentGalleryTab] || [];

    if (photos.length === 0) {
        if (Elements.galleryGrid) Elements.galleryGrid.innerHTML = '';
        if (Elements.galleryEmpty) Elements.galleryEmpty.classList.remove('hidden');
        return;
    }

    if (Elements.galleryEmpty) Elements.galleryEmpty.classList.add('hidden');

    if (Elements.galleryGrid) {
        Elements.galleryGrid.innerHTML = photos.map((photo, index) => `
        <div class="photo-card" data-index="${index}">
          <img src="${API.getThumbnailUrl(State.enrolledUser, photo.path)}" alt="Photo" loading="lazy">
          <div class="photo-overlay">
            <span>View Full</span>
          </div>
        </div>
      `).join('');

        Elements.galleryGrid.querySelectorAll('.photo-card').forEach(card => {
            card.addEventListener('click', () => {
                const index = parseInt(card.dataset.index);
                openLightbox(index);
            });
        });
    }
}


// ============================================================
// Lightbox
// ============================================================
function openLightbox(index) {
    State.currentPhotoIndex = index;
    updateLightbox();
    if (Elements.lightbox) Elements.lightbox.classList.remove('hidden');
    document.body.style.overflow = 'hidden';
}

function closeLightbox() {
    if (Elements.lightbox) Elements.lightbox.classList.add('hidden');
    document.body.style.overflow = '';
}

function navigateLightbox(direction) {
    const photos = State.galleryPhotos[State.currentGalleryTab] || [];
    State.currentPhotoIndex = (State.currentPhotoIndex + direction + photos.length) % photos.length;
    updateLightbox();
}

function updateLightbox() {
    const photos = State.galleryPhotos[State.currentGalleryTab] || [];
    const photo = photos[State.currentPhotoIndex];

    if (!photo) return;

    if (Elements.lightboxImage) Elements.lightboxImage.src = API.getPhotoUrl(State.enrolledUser, photo.path);
    if (Elements.lightboxCounter) Elements.lightboxCounter.textContent = `${State.currentPhotoIndex + 1} / ${photos.length}`;

    if (Elements.downloadBtn) {
        Elements.downloadBtn.href = API.getPhotoUrl(State.enrolledUser, photo.path);
        Elements.downloadBtn.download = photo.filename || 'photo.jpg';
    }
}


// ============================================================
// Keyboard Navigation
// ============================================================
function handleKeydown(e) {
    if (Elements.lightbox && !Elements.lightbox.classList.contains('hidden')) {
        if (e.key === 'Escape') closeLightbox();
        if (e.key === 'ArrowLeft') navigateLightbox(-1);
        if (e.key === 'ArrowRight') navigateLightbox(1);
        return;
    }

    if (Elements.resultsModal && !Elements.resultsModal.classList.contains('hidden')) {
        if (e.key === 'Escape') closeModal();
        return;
    }
}


// ============================================================
// Toast Notifications — Premium Dark Style
// ============================================================
function showToast(message, type = 'info') {
    // Remove existing toasts
    document.querySelectorAll('.toast-notification').forEach(t => t.remove());

    const toast = document.createElement('div');
    toast.className = `toast-notification toast-${type}`;

    const iconSvg = type === 'error' ? Icons.alertCircle
        : type === 'success' ? Icons.check
            : Icons.info;

    const bgColor = type === 'error'
        ? 'rgba(239, 68, 68, 0.15)'
        : type === 'success'
            ? 'rgba(34, 197, 94, 0.15)'
            : 'rgba(6, 182, 212, 0.15)';

    const borderColor = type === 'error'
        ? 'rgba(239, 68, 68, 0.3)'
        : type === 'success'
            ? 'rgba(34, 197, 94, 0.3)'
            : 'rgba(6, 182, 212, 0.3)';

    const textColor = type === 'error'
        ? '#FCA5A5'
        : type === 'success'
            ? '#86EFAC'
            : '#67E8F9';

    toast.innerHTML = `
        <span class="toast-icon-wrap">${iconSvg}</span>
        <span class="toast-msg">${message}</span>
    `;

    Object.assign(toast.style, {
        position: 'fixed',
        bottom: '24px',
        right: '24px',
        padding: '12px 20px',
        background: bgColor,
        backdropFilter: 'blur(24px)',
        WebkitBackdropFilter: 'blur(24px)',
        border: `1px solid ${borderColor}`,
        color: textColor,
        borderRadius: '10px',
        display: 'flex',
        alignItems: 'center',
        gap: '10px',
        fontSize: '14px',
        fontWeight: '500',
        fontFamily: "'DM Sans', sans-serif",
        boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
        zIndex: '9999',
        transform: 'translateX(100%)',
        opacity: '0',
        transition: 'transform 0.3s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.3s ease',
    });

    document.body.appendChild(toast);

    // Animate in
    requestAnimationFrame(() => {
        requestAnimationFrame(() => {
            toast.style.transform = 'translateX(0)';
            toast.style.opacity = '1';
        });
    });

    // Remove after delay
    setTimeout(() => {
        toast.style.transform = 'translateX(100%)';
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}


// ============================================================
// Start Application
// ============================================================
document.addEventListener('DOMContentLoaded', init);
