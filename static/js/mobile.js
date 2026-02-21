/* ============================================
   MOBILE-FIRST FUNCTIONALITY
   Enhanced for optimal mobile experience
   ============================================ */

// Haptic Feedback Helper Function
function triggerHaptic(duration = 10) {
    if (window.navigator && window.navigator.vibrate) {
        window.navigator.vibrate(duration);
    }
}

// Initialize Mobile Features
document.addEventListener('DOMContentLoaded', () => {
    initBottomNav();
    initMobileOptimizations();
    initTouchGestures();
    initScrollOptimizations();
    initMobileMenu(); // <-- ADD THIS LINE
});
// ============ MOBILE NAVIGATION MENU ============
function initMobileMenu() {
    const toggleBtn = document.getElementById('mobile-menu');
    const mobileMenuContent = document.getElementById('mobile-menu-content');
    const toggleIcon = toggleBtn ? toggleBtn.querySelector('i') : null;

    if (!toggleBtn || !mobileMenuContent) return;

    // Toggle menu open/close
    toggleBtn.addEventListener('click', (e) => {
        e.stopPropagation(); // Prevent document click from immediately closing it
        const isHidden = mobileMenuContent.classList.contains('hidden');
        
        if (isHidden) {
            // Open menu
            mobileMenuContent.classList.remove('hidden');
            mobileMenuContent.classList.add('active');
            if (toggleIcon) {
                toggleIcon.classList.remove('fa-bars');
                toggleIcon.classList.add('fa-times');
            }
            // Optional: prevent background scrolling when menu is open
            document.body.style.overflow = 'hidden'; 
        } else {
            // Close menu
            closeMobileMenu();
        }
    });

    // Close menu function
    function closeMobileMenu() {
        mobileMenuContent.classList.add('hidden');
        mobileMenuContent.classList.remove('active');
        if (toggleIcon) {
            toggleIcon.classList.remove('fa-times');
            toggleIcon.classList.add('fa-bars');
        }
        document.body.style.overflow = 'auto'; // Restore scrolling
    }

    // Close menu when clicking anywhere outside of it
    document.addEventListener('click', (e) => {
        if (!mobileMenuContent.classList.contains('hidden') && 
            !mobileMenuContent.contains(e.target) && 
            e.target !== toggleBtn) {
            closeMobileMenu();
        }
    });

    // Close menu when clicking a link inside the menu
    const menuLinks = mobileMenuContent.querySelectorAll('a');
    menuLinks.forEach(link => {
        link.addEventListener('click', () => {
            closeMobileMenu();
        });
    });
}

// ============ BOTTOM NAVIGATION ============
function initBottomNav() {
    const bottomNav = document.querySelector('.bottom-nav-bar');
    if (!bottomNav) return;

    function updateBottomNav() {
        if (window.innerWidth < 768) {
            bottomNav.classList.add('active');
        } else {
            bottomNav.classList.remove('active');
        }
    }

    // Set active nav item based on current page
    const currentPath = window.location.pathname;
    const navItems = document.querySelectorAll('.bottom-nav-item');

    navItems.forEach((item) => {
        const href = item.getAttribute('href');
        
        // Regular button active state
        if (href && href !== 'javascript:void(0);') {
            if (href === currentPath || (currentPath === '/filter' && href === '/filter')) {
                item.classList.add('active');
            }
        }
        
        // Add touch feedback
        item.addEventListener('touchstart', () => {
            item.style.opacity = '0.7';
        });
        
        item.addEventListener('touchend', () => {
            item.style.opacity = '1';
        });
    });

    updateBottomNav();
    window.addEventListener('resize', updateBottomNav);
}

// ============ MOBILE OPTIMIZATIONS ============
function initMobileOptimizations() {
    // Prevent double-tap zoom on interactive elements
    const interactiveElements = document.querySelectorAll('button, a, input, select, .filter-chip, .poster-card');
    interactiveElements.forEach(el => {
        el.style.touchAction = 'manipulation';
    });

    // Add active state to clickable elements
    const clickableElements = document.querySelectorAll('.poster-card, .filter-chip, button, a');
    clickableElements.forEach(el => {
        el.addEventListener('touchstart', function() {
            this.classList.add('touching');
            triggerHaptic(10);
        });
        
        el.addEventListener('touchend', function() {
            this.classList.remove('touching');
        });
        
        el.addEventListener('touchcancel', function() {
            this.classList.remove('touching');
        });
    });
    
    // Optimize images for mobile
    if ('loading' in HTMLImageElement.prototype) {
        const images = document.querySelectorAll('img[loading="lazy"]');
        images.forEach(img => {
            img.loading = 'lazy';
        });
    }
}

// ============ TOUCH GESTURES ============
function initTouchGestures() {
    // CSS Scroll Snap handles horizontal carousel scrolling natively
    // No manual JS needed - native browser scrolling is optimized and smoother
}

// ============ SCROLL OPTIMIZATIONS ============
function initScrollOptimizations() {
    // Hide/show bottom nav on scroll
    let lastScrollTop = 0;
    const bottomNav = document.querySelector('.bottom-nav-bar');
    const scrollThreshold = 10;
    
    if (bottomNav && window.innerWidth < 768) {
        window.addEventListener('scroll', () => {
            const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
            
            if (Math.abs(scrollTop - lastScrollTop) < scrollThreshold) {
                return;
            }
            
            if (scrollTop > lastScrollTop && scrollTop > 100) {
                // Scrolling down
                bottomNav.style.transform = 'translateY(100%)';
                bottomNav.style.transition = 'transform 0.3s ease';
            } else {
                // Scrolling up
                bottomNav.style.transform = 'translateY(0)';
            }
            
            lastScrollTop = scrollTop;
        }, { passive: true });
    }

    // Lazy load optimization
    if ('IntersectionObserver' in window) {
        const imageObserver = new IntersectionObserver((entries, observer) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const img = entry.target;
                    if (img.dataset.src) {
                        img.src = img.dataset.src;
                        img.removeAttribute('data-src');
                    }
                    observer.unobserve(img);
                }
            });
        }, {
            rootMargin: '50px 0px',
            threshold: 0.01
        });

        const lazyImages = document.querySelectorAll('img[data-src]');
        lazyImages.forEach(img => imageObserver.observe(img));
    }

    // Scroll to top on page nav
    const scrollToTop = () => {
        window.scrollTo({
            top: 0,
            behavior: 'smooth'
        });
    };

    // Add scroll to top on logo tap
    const logo = document.querySelector('.nav-logo a');
    if (logo) {
        logo.addEventListener('click', (e) => {
            if (window.location.pathname === '/') {
                e.preventDefault();
                scrollToTop();
            }
        });
    }
}

// ============ FILTER DRAWER ============
class MobileFilterDrawer {
    constructor() {
        this.drawer = document.getElementById('filtersSidebar');
        this.overlay = document.getElementById('filtersOverlay');
        this.toggleBtn = document.getElementById('sidebarToggle');
        this.closeBtn = document.getElementById('sidebarClose');

        if (!this.drawer) return;

        this.setupEventListeners();
    }

    setupEventListeners() {
        this.toggleBtn?.addEventListener('click', () => this.open());
        this.closeBtn?.addEventListener('click', () => this.close());
        this.overlay?.addEventListener('click', () => this.close());

        // Close on Escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.drawer.style.display === 'block') {
                this.close();
            }
        });

        // Close when clicking form button (apply filters)
        const submitBtn = this.drawer.querySelector('button[type="submit"]');
        submitBtn?.addEventListener('click', () => {
            setTimeout(() => this.close(), 100);
        });
    }

    open() {
        if (window.innerWidth >= 768) return; // Don't open on desktop

        this.drawer.style.display = 'block';
        this.overlay.style.display = 'block';
        document.body.style.overflow = 'hidden';
    }

    close() {
        this.drawer.classList.add('closing');
        setTimeout(() => {
            this.drawer.style.display = 'none';
            this.drawer.classList.remove('closing');
            this.overlay.style.display = 'none';
            document.body.style.overflow = 'auto';
        }, 300);
    }
}

// Initialize filter drawer
new MobileFilterDrawer();

// ============ SAFE AREA PADDING ============
function updateSafeAreaPadding() {
    const viewportMeta = document.querySelector('meta[name="viewport"]');
    if (viewportMeta) {
        // Mobile devices handle their own safe area
        const navBar = document.querySelector('.bottom-nav-bar');
        if (navBar && window.innerWidth < 768) {
            // Already handled by padding-bottom: env(safe-area-inset-bottom)
        }
    }
}

updateSafeAreaPadding();
window.addEventListener('orientationchange', updateSafeAreaPadding);

// ============ TOUCH FEEDBACK ============
document.addEventListener('touchstart', (e) => {
    const target = e.target.closest('button, .filter-chip, .poster-card, a');
    if (target) {
        target.style.opacity = '0.8';
    }
});

document.addEventListener('touchend', (e) => {
    const target = e.target.closest('button, .filter-chip, .poster-card, a');
    if (target) {
        target.style.opacity = '1';
    }
});
