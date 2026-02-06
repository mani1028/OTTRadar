/**
 * OTT RADAR - MAIN BUNDLE
 * Consolidated JavaScript for optimal performance
 * Combines: app.js, features.js, mobile.js, optimizations.js
 * Plus: Haptic Feedback for native-like mobile experience
 */

(function() {
    'use strict';

    // ============================================
    // HAPTIC FEEDBACK SYSTEM
    // ============================================
    const HapticFeedback = {
        /**
         * Trigger haptic feedback on supported devices
         * @param {string} style - 'light', 'medium', 'heavy', or 'selection'
         */
        vibrate(style = 'light') {
            if (!navigator.vibrate) return;
            
            const patterns = {
                light: 10,
                medium: 20,
                heavy: 30,
                selection: [5, 10],
                success: [10, 50, 10]
            };
            
            navigator.vibrate(patterns[style] || patterns.light);
        },

        /**
         * Add haptic feedback to specific actions
         */
        init() {
            // Watchlist actions
            document.addEventListener('click', (e) => {
                const watchlistBtn = e.target.closest('.watchlist-btn, [data-action="watchlist"]');
                if (watchlistBtn) {
                    this.vibrate('medium');
                }

                // Trailer button clicks
                const trailerBtn = e.target.closest('.trailer-btn, [data-action="trailer"]');
                if (trailerBtn) {
                    this.vibrate('light');
                }

                // Filter chip selections
                const filterChip = e.target.closest('.filter-chip');
                if (filterChip) {
                    this.vibrate('selection');
                }

                // Bottom nav taps
                const bottomNavItem = e.target.closest('.bottom-nav-item');
                if (bottomNavItem) {
                    this.vibrate('light');
                }
            });
        }
    };

    // ============================================
    // MOBILE MENU TOGGLE
    // ============================================
    function initMobileMenu() {
        const mobileMenuBtn = document.getElementById('mobile-menu');
        const mobileMenu = document.getElementById('mobile-menu-content');

        if (mobileMenuBtn && mobileMenu) {
            mobileMenuBtn.addEventListener('click', () => {
                mobileMenu.classList.toggle('hidden');
                mobileMenu.classList.toggle('active');
                
                const icon = mobileMenuBtn.querySelector('i');
                if (mobileMenu.classList.contains('active')) {
                    icon.classList.remove('fa-bars');
                    icon.classList.add('fa-times');
                } else {
                    icon.classList.remove('fa-times');
                    icon.classList.add('fa-bars');
                }
            });
        }
    }

    // ============================================
    // WATCHLIST QUICK ADD
    // ============================================
    function initWatchlist() {
        document.querySelectorAll('.watchlist-btn').forEach(btn => {
            btn.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                
                const tmdbId = this.dataset.tmdbId;
                const isAdded = localStorage.getItem(`watchlist_${tmdbId}`);
                
                if (isAdded) {
                    localStorage.removeItem(`watchlist_${tmdbId}`);
                    this.style.background = 'var(--accent-primary)';
                    this.innerHTML = '<i class="fas fa-plus"></i>';
                } else {
                    localStorage.setItem(`watchlist_${tmdbId}`, JSON.stringify({
                        tmdbId: tmdbId,
                        addedAt: new Date().toISOString()
                    }));
                    this.style.background = 'var(--accent-hover)';
                    this.innerHTML = '<i class="fas fa-check"></i>';
                    HapticFeedback.vibrate('success');
                }
            });
        });
        
        // Update button states on load
        document.querySelectorAll('.watchlist-btn').forEach(btn => {
            const tmdbId = btn.dataset.tmdbId;
            if (localStorage.getItem(`watchlist_${tmdbId}`)) {
                btn.style.background = 'var(--accent-hover)';
                btn.innerHTML = '<i class="fas fa-check"></i>';
            }
        });
    }

    // ============================================
    // BOTTOM NAVIGATION
    // ============================================
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

        const currentPath = window.location.pathname;
        const navItems = document.querySelectorAll('.bottom-nav-item');

        navItems.forEach((item) => {
            const href = item.getAttribute('href');
            
            if (href && href !== 'javascript:void(0);') {
                if (href === currentPath || (currentPath === '/filter' && href === '/filter')) {
                    item.classList.add('active');
                }
            }
            
            item.addEventListener('touchstart', () => {
                item.style.opacity = '0.7';
            });
            
            item.addEventListener('touchend', () => {
                item.style.opacity = '1';
            });
        });

        updateBottomNav();
        window.addEventListener('resize', updateBottomNav);

        // Hide/show on scroll
        let lastScrollTop = 0;
        window.addEventListener('scroll', () => {
            const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
            
            if (Math.abs(scrollTop - lastScrollTop) < 10) return;
            
            if (scrollTop > lastScrollTop && scrollTop > 100) {
                bottomNav.style.transform = 'translateY(100%)';
                bottomNav.style.transition = 'transform 0.3s ease';
            } else {
                bottomNav.style.transform = 'translateY(0)';
            }
            
            lastScrollTop = scrollTop;
        }, { passive: true });
    }

    // ============================================
    // LAZY LOADING IMAGES
    // ============================================
    function initLazyLoading() {
        if ('IntersectionObserver' in window) {
            const imageObserver = new IntersectionObserver((entries, observer) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        const img = entry.target;
                        
                        // Main image lazy loading
                        if (img.dataset.src) {
                            img.src = img.dataset.src;
                            img.classList.remove('lazy');
                            img.classList.add('loaded');
                            observer.unobserve(img);
                        }
                        
                        // Handle poster images with blur-up effect
                        if (img.loading === 'lazy') {
                            img.classList.add('loaded');
                        }
                    }
                });
            }, {
                rootMargin: '50px',
                threshold: 0.01
            });

            document.querySelectorAll('img[data-src], img[loading="lazy"]').forEach(img => {
                imageObserver.observe(img);
            });
        }
    }

    // ============================================
    // TRAILER MODAL
    // ============================================
    function initTrailerModal() {
        const modals = document.querySelectorAll('.modal, .trailer-modal');
        
        document.addEventListener('click', (e) => {
            const trailerBtn = e.target.closest('.trailer-btn, [data-action="trailer"]');
            
            if (trailerBtn) {
                e.preventDefault();
                const youtubeId = trailerBtn.dataset.youtubeId;
                
                if (youtubeId) {
                    const modal = document.getElementById('trailerModal') || document.querySelector('.trailer-modal');
                    if (modal) {
                        const iframe = modal.querySelector('iframe');
                        if (iframe) {
                            iframe.src = `https://www.youtube.com/embed/${youtubeId}?autoplay=1`;
                        }
                        modal.classList.add('active', 'is-open');
                        document.body.style.overflow = 'hidden';
                    }
                }
            }
            
            // Close modal
            const closeBtn = e.target.closest('.modal-close, .trailer-modal__close');
            const modalBackdrop = e.target.classList.contains('modal') || e.target.classList.contains('trailer-modal__backdrop');
            
            if (closeBtn || modalBackdrop) {
                e.preventDefault();
                modals.forEach(modal => {
                    modal.classList.remove('active', 'is-open');
                    const iframe = modal.querySelector('iframe');
                    if (iframe) iframe.src = '';
                });
                document.body.style.overflow = '';
            }
        });
    }

    // ============================================
    // MOBILE OPTIMIZATIONS
    // ============================================
    function initMobileOptimizations() {
        // Prevent double-tap zoom
        const interactiveElements = document.querySelectorAll('button, a, input, select, .filter-chip, .poster-card');
        interactiveElements.forEach(el => {
            el.style.touchAction = 'manipulation';
        });

        // Add touch active states
        const clickableElements = document.querySelectorAll('.poster-card, .filter-chip, button, a');
        clickableElements.forEach(el => {
            el.addEventListener('touchstart', function() {
                this.classList.add('touching');
            }, { passive: true });
            
            el.addEventListener('touchend', function() {
                this.classList.remove('touching');
            }, { passive: true });
        });
    }

    // ============================================
    // FILTER PERSISTENCE
    // ============================================
    const FilterPersistence = {
        storageKey: 'ottRadarFilters',
        
        saveFilters: function(filters) {
            localStorage.setItem(this.storageKey, JSON.stringify(filters));
        },
        
        getFilters: function() {
            const saved = localStorage.getItem(this.storageKey);
            return saved ? JSON.parse(saved) : null;
        },
        
        clearFilters: function() {
            localStorage.removeItem(this.storageKey);
        }
    };

    // ============================================
    // INFINITE SCROLL
    // ============================================
    class InfiniteScroll {
        constructor() {
            this.currentPage = 1;
            this.isLoading = false;
            this.hasMore = true;
            this.init();
        }

        init() {
            if (!('IntersectionObserver' in window)) return;

            const sentinel = document.getElementById('infinite-scroll-sentinel');
            if (!sentinel) return;

            const scrollObserver = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting && this.hasMore && !this.isLoading) {
                        this.loadMore();
                    }
                });
            });

            scrollObserver.observe(sentinel);
        }

        loadMore() {
            // Implement based on page context
            console.log('Load more triggered');
        }
    }

    // ============================================
    // INITIALIZATION
    // ============================================
    document.addEventListener('DOMContentLoaded', () => {
        initMobileMenu();
        initWatchlist();
        initBottomNav();
        initLazyLoading();
        initTrailerModal();
        initMobileOptimizations();
        HapticFeedback.init();
        
        // Initialize infinite scroll if needed
        if (document.getElementById('infinite-scroll-sentinel')) {
            new InfiniteScroll();
        }
    });

    // Export for external use if needed
    window.OTTRadar = {
        HapticFeedback,
        FilterPersistence
    };

})();
