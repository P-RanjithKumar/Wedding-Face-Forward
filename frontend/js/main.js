/**
 * Wedding Face Forward - Frontend Application
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

    async getPhotos(personName, category = 'solo') {
        const response = await fetch(`${this.baseUrl}/photos/${encodeURIComponent(personName)}?category=${category}`);
        return response.json();
    },

    getPhotoUrl(photoPath) {
        return `${this.baseUrl}/photo?path=${encodeURIComponent(photoPath)}`;
    },

    getThumbnailUrl(photoPath) {
        return `${this.baseUrl}/thumbnail?path=${encodeURIComponent(photoPath)}`;
    }
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
    // Navbar
    navbar: document.getElementById('navbar'),

    // Stats
    statPhotos: document.getElementById('stat-photos'),
    statGuests: document.getElementById('stat-guests'),
    statFaces: document.getElementById('stat-faces'),

    // Form elements
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

    // Form steps
    step1: document.getElementById('step-1'),
    step2: document.getElementById('step-2'),

    // Form inputs
    userName: document.getElementById('userName'),
    countryCode: document.getElementById('countryCode'),
    userPhone: document.getElementById('userPhone'),
    userEmail: document.getElementById('userEmail'),
    consent: document.getElementById('consent'),

    // Buttons
    prevBtn: document.getElementById('prevBtn'),
    nextBtn: document.getElementById('nextBtn'),
    submitBtn: document.getElementById('submitBtn'),

    // Progress
    progressSteps: document.querySelectorAll('.progress-step'),

    // Modal
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

    // Gallery
    gallerySection: document.getElementById('gallerySection'),
    backToHome: document.getElementById('backToHome'),
    galleryUserName: document.getElementById('galleryUserName'),
    galleryGrid: document.getElementById('galleryGrid'),
    galleryEmpty: document.getElementById('galleryEmpty'),
    tabBtns: document.querySelectorAll('.tab-btn'),
    tabSoloCount: document.getElementById('tabSoloCount'),
    tabGroupCount: document.getElementById('tabGroupCount'),

    // Lightbox
    lightbox: document.getElementById('lightbox'),
    lightboxClose: document.getElementById('lightboxClose'),
    lightboxPrev: document.getElementById('lightboxPrev'),
    lightboxNext: document.getElementById('lightboxNext'),
    lightboxImage: document.getElementById('lightboxImage'),
    lightboxCounter: document.getElementById('lightboxCounter'),
    downloadBtn: document.getElementById('downloadBtn'),

    // Sections
    heroSection: document.getElementById('hero'),
    featuresSection: document.getElementById('features'),
    enrollSection: document.getElementById('enroll'),
};


// ============================================================
// Initialization
// ============================================================
function init() {
    setupEventListeners();
    setupAnimations();
    animateStatsOnLoad();
}


// ============================================================
// Event Listeners
// ============================================================
function setupEventListeners() {
    // Navbar scroll effect
    window.addEventListener('scroll', handleScroll);

    // Camera actions
    if (Elements.captureBtn) Elements.captureBtn.addEventListener('click', capturePhoto);
    if (Elements.retakeBtn) Elements.retakeBtn.addEventListener('click', retakePhoto);

    // Initial camera check when Page loads - if on step 1, start camera
    if (State.currentStep === 1) startCamera();

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
// Animations (New)
// ============================================================
function setupAnimations() {
    setupMagneticElements();
    setupRevealAnimations();
}

function setupMagneticElements() {
    const magnetics = document.querySelectorAll('.nav-link-cta, .btn, .nav-logo');

    magnetics.forEach(el => {
        el.addEventListener('mousemove', (e) => {
            const rect = el.getBoundingClientRect();
            const x = e.clientX - rect.left - rect.width / 2;
            const y = e.clientY - rect.top - rect.height / 2;

            // Lerp effect
            el.style.transform = `translate(${x * 0.2}px, ${y * 0.2}px)`;
            el.style.transition = 'transform 0.1s ease-out';
        });

        el.addEventListener('mouseleave', () => {
            el.style.transform = 'translate(0, 0)';
            el.style.transition = 'transform 0.5s cubic-bezier(0.34, 1.56, 0.64, 1)'; // Spring back
        });
    });
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


// ============================================================
// Navbar
// ============================================================
function handleScroll() {
    const scrolled = window.scrollY > 20;
    Elements.navbar.style.background = scrolled
        ? 'rgba(245, 243, 240, 0.9)'
        : 'rgba(245, 243, 240, 0.7)';

    Elements.navbar.style.boxShadow = scrolled
        ? 'var(--shadow-sm)'
        : 'none';
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
    const duration = 2000;
    const start = 0;
    const startTime = performance.now();

    function update(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);

        // Ease out cubic
        const easeOut = 1 - Math.pow(1 - progress, 3);
        const current = Math.round(start + (target - start) * easeOut);

        element.textContent = current.toLocaleString();

        if (progress < 1) {
            requestAnimationFrame(update);
        }
    }

    requestAnimationFrame(update);
}

function animateStatsOnLoad() {
    // Animate stats when they come into view
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
async function startCamera() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        showToast('Your browser does not support camera access. Please use a modern browser or HTTPS.', 'error');
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

        State.videoStream = stream;
        if (Elements.cameraStream) {
            Elements.cameraStream.srcObject = stream;
            Elements.cameraStream.onloadedmetadata = () => {
                Elements.cameraStream.play();
            };
        }

        // Show camera UI, hide preview
        if (Elements.videoWrapper) Elements.videoWrapper.classList.remove('hidden');
        if (Elements.cameraActions) Elements.cameraActions.classList.remove('hidden');
        if (Elements.previewContent) Elements.previewContent.classList.add('hidden');
        if (Elements.retakeActions) Elements.retakeActions.classList.add('hidden');
        if (Elements.cameraView) Elements.cameraView.classList.remove('captured');

    } catch (error) {
        console.error('Camera access error:', error);
        showToast('Could not access camera. Please ensure permissions are granted.', 'error');

        // Fallback or show instructions
        if (Elements.cameraActions) {
            Elements.cameraActions.innerHTML = `
                <p class="error-text">Camera access is required for enrollment.</p>
                <button type="button" class="btn btn-outline btn-sm" onclick="startCamera()">Retry Camera</button>
            `;
        }
    }
}

function capturePhoto() {
    const video = Elements.cameraStream;
    const canvas = Elements.captureCanvas;

    if (!video || !canvas) return;

    // Set canvas dimensions to match video
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;

    const ctx = canvas.getContext('2d');

    // Mirror the capture to match the mirrored preview
    ctx.translate(canvas.width, 0);
    ctx.scale(-1, 1);

    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    // Convert canvas to Blob
    canvas.toBlob((blob) => {
        const file = new File([blob], "selfie.jpg", { type: "image/jpeg" });
        State.selfieFile = file;

        // Show preview
        if (Elements.selfiePreview) Elements.selfiePreview.src = canvas.toDataURL('image/jpeg');
        if (Elements.previewContent) Elements.previewContent.classList.remove('hidden');
        if (Elements.videoWrapper) Elements.videoWrapper.classList.add('hidden');
        if (Elements.cameraActions) Elements.cameraActions.classList.add('hidden');
        if (Elements.retakeActions) Elements.retakeActions.classList.remove('hidden');
        if (Elements.cameraView) Elements.cameraView.classList.add('captured');

        // Stop the stream to save energy/resource
        State.stopVideoStream();

        showToast('Selfie captured!', 'success');
    }, 'image/jpeg', 0.9);
}

function retakePhoto() {
    State.selfieFile = null;
    startCamera();
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

    // Update step visibility
    if (Elements.step1) Elements.step1.classList.toggle('active', step === 1);
    if (Elements.step2) Elements.step2.classList.toggle('active', step === 2);

    // Update progress indicator
    if (Elements.progressSteps) {
        Elements.progressSteps.forEach((el, index) => {
            el.classList.toggle('active', index + 1 <= step);
            el.classList.toggle('completed', index + 1 < step);
        });
    }

    // Update buttons
    if (Elements.prevBtn) Elements.prevBtn.classList.toggle('hidden', step === 1);
    if (Elements.nextBtn) Elements.nextBtn.classList.toggle('hidden', step === 2);
    if (Elements.submitBtn) Elements.submitBtn.classList.toggle('hidden', step !== 2);

    // Handle camera lifecycle during transitions
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

    // Show loading state
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
        // Reset loading state
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

    // Load preview photos
    loadPreviewPhotos(result.person_name);

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

    // Reset preview and camera UI
    if (Elements.previewContent) Elements.previewContent.classList.add('hidden');
    if (Elements.videoWrapper) Elements.videoWrapper.classList.remove('hidden');
    if (Elements.cameraActions) Elements.cameraActions.classList.remove('hidden');
    if (Elements.retakeActions) Elements.retakeActions.classList.add('hidden');
    if (Elements.cameraView) Elements.cameraView.classList.remove('captured');

    // Restart camera
    startCamera();

    // Reset form
    if (Elements.enrollForm) Elements.enrollForm.reset();
}

async function loadPreviewPhotos(personName) {
    try {
        const photos = await API.getPhotos(personName, 'solo');
        const preview = photos.slice(0, 3);

        if (Elements.galleryPreview) {
            Elements.galleryPreview.innerHTML = preview.map(photo => `
              <img src="${API.getThumbnailUrl(photo.path)}" alt="Photo preview" loading="lazy">
            `).join('');

            if (preview.length === 0) {
                Elements.galleryPreview.innerHTML = '<p style="color: var(--text-tertiary);">Photos are being processed...</p>';
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

    // Hide other sections
    if (Elements.heroSection) Elements.heroSection.classList.add('hidden');
    if (Elements.featuresSection) Elements.featuresSection.classList.add('hidden');
    if (Elements.enrollSection) Elements.enrollSection.classList.add('hidden');
    const footer = document.querySelector('.footer');
    if (footer) footer.classList.add('hidden');

    // Show gallery
    if (Elements.gallerySection) Elements.gallerySection.classList.remove('hidden');
    if (Elements.galleryUserName) Elements.galleryUserName.textContent = State.enrolledUser.person_name;

    // Load photos
    loadGalleryPhotos();

    window.scrollTo(0, 0);
}

function closeGallery() {
    if (Elements.gallerySection) Elements.gallerySection.classList.add('hidden');
    if (Elements.heroSection) Elements.heroSection.classList.remove('hidden');
    if (Elements.featuresSection) Elements.featuresSection.classList.remove('hidden');
    if (Elements.enrollSection) Elements.enrollSection.classList.remove('hidden');
    const footer = document.querySelector('.footer');
    if (footer) footer.classList.remove('hidden');

    window.scrollTo(0, 0);
}

async function loadGalleryPhotos() {
    if (!State.enrolledUser) return;

    try {
        // Load solo photos
        const soloPhotos = await API.getPhotos(State.enrolledUser.person_name, 'solo');
        State.galleryPhotos.solo = soloPhotos;
        if (Elements.tabSoloCount) Elements.tabSoloCount.textContent = soloPhotos.length;

        // Load group photos
        const groupPhotos = await API.getPhotos(State.enrolledUser.person_name, 'group');
        State.galleryPhotos.group = groupPhotos;
        if (Elements.tabGroupCount) Elements.tabGroupCount.textContent = groupPhotos.length;

        // Render current tab
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
          <img src="${API.getThumbnailUrl(photo.path)}" alt="Photo" loading="lazy">
          <div class="photo-overlay">
            <span>View Full</span>
          </div>
        </div>
      `).join('');

        // Add click handlers
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

    if (Elements.lightboxImage) Elements.lightboxImage.src = API.getPhotoUrl(photo.path);
    if (Elements.lightboxCounter) Elements.lightboxCounter.textContent = `${State.currentPhotoIndex + 1} / ${photos.length}`;

    if (Elements.downloadBtn) {
        Elements.downloadBtn.href = API.getPhotoUrl(photo.path);
        Elements.downloadBtn.download = photo.filename || 'photo.jpg';
    }
}


// ============================================================
// Keyboard Navigation
// ============================================================
function handleKeydown(e) {
    // Lightbox navigation
    if (Elements.lightbox && !Elements.lightbox.classList.contains('hidden')) {
        if (e.key === 'Escape') closeLightbox();
        if (e.key === 'ArrowLeft') navigateLightbox(-1);
        if (e.key === 'ArrowRight') navigateLightbox(1);
        return;
    }

    // Modal escape
    if (Elements.resultsModal && !Elements.resultsModal.classList.contains('hidden')) {
        if (e.key === 'Escape') closeModal();
        return;
    }
}


// ============================================================
// Toast Notifications
// ============================================================
function showToast(message, type = 'info') {
    // Create toast element
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
    <span class="toast-icon">${type === 'error' ? '❌' : type === 'success' ? '✅' : 'ℹ️'}</span>
    <span class="toast-message">${message}</span>
  `;

    // Add styles
    Object.assign(toast.style, {
        position: 'fixed',
        bottom: '24px',
        right: '24px',
        padding: '16px 24px',
        background: type === 'error' ? 'rgba(239, 68, 68, 0.9)' : 'rgba(139, 92, 246, 0.9)',
        color: 'white',
        borderRadius: '12px',
        display: 'flex',
        alignItems: 'center',
        gap: '12px',
        fontSize: '14px',
        fontWeight: '500',
        boxShadow: '0 4px 20px rgba(0,0,0,0.3)',
        zIndex: '9999',
        animation: 'slideIn 0.3s ease',
    });

    // Add animation styles
    const style = document.createElement('style');
    style.textContent = `
    @keyframes slideIn {
      from { transform: translateX(100%); opacity: 0; }
      to { transform: translateX(0); opacity: 1; }
    }
    @keyframes slideOut {
      from { transform: translateX(0); opacity: 1; }
      to { transform: translateX(100%); opacity: 0; }
    }
  `;
    document.head.appendChild(style);

    document.body.appendChild(toast);

    // Remove after delay
    setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s ease forwards';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}


// ============================================================
// Start Application
// ============================================================
document.addEventListener('DOMContentLoaded', init);
