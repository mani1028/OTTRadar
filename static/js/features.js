// ===== OTT Radar Premium Features =====

// 1. Watchlist Quick Add
document.addEventListener('DOMContentLoaded', function() {
    // Watchlist buttons
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
            }
        });
    });
    
    // Check if items in watchlist and update button state
    document.querySelectorAll('.watchlist-btn').forEach(btn => {
        const tmdbId = btn.dataset.tmdbId;
        if (localStorage.getItem(`watchlist_${tmdbId}`)) {
            btn.style.background = 'var(--accent-hover)';
            btn.innerHTML = '<i class="fas fa-check"></i>';
        }
    });
});

// 2. Filter Persistence (for Discover page)
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
    },
    
    restoreFilters: function() {
        const filters = this.getFilters();
        if (!filters) return;
        
        // Restore language filters
        if (filters.lang && filters.lang.length > 0) {
            document.querySelectorAll('select[name="lang"] option').forEach(opt => {
                opt.selected = filters.lang.includes(opt.value);
            });
        }
        
        // Restore platform filters
        if (filters.platform && filters.platform.length > 0) {
            document.querySelectorAll('select[name="platform"] option').forEach(opt => {
                opt.selected = filters.platform.includes(opt.value);
            });
        }
        
        // Restore rating
        if (filters.min_rating) {
            const ratingInput = document.querySelector('input[name="min_rating"]');
            if (ratingInput) ratingInput.value = filters.min_rating;
        }
        
        // Restore year range
        if (filters.year_from) {
            const yearFromInput = document.querySelector('input[name="year_from"]');
            if (yearFromInput) yearFromInput.value = filters.year_from;
        }
        
        if (filters.year_to) {
            const yearToInput = document.querySelector('input[name="year_to"]');
            if (yearToInput) yearToInput.value = filters.year_to;
        }
        
        // Restore checkboxes
        if (filters.free_only) {
            const freeCheckbox = document.querySelector('input[name="free_only"]');
            if (freeCheckbox) freeCheckbox.checked = true;
        }
        
        if (filters.dubbed) {
            const dubbedCheckbox = document.querySelector('input[name="dubbed"]');
            if (dubbedCheckbox) dubbedCheckbox.checked = true;
        }
    },
    
    setupAutoSave: function() {
        const filterForm = document.querySelector('.filters-sidebar-form');
        if (!filterForm) return;
        
        filterForm.addEventListener('change', () => {
            this.captureAndSave();
        });
    },
    
    captureAndSave: function() {
        const filters = {
            lang: Array.from(document.querySelectorAll('select[name="lang"] option:checked')).map(o => o.value),
            platform: Array.from(document.querySelectorAll('select[name="platform"] option:checked')).map(o => o.value),
            min_rating: document.querySelector('input[name="min_rating"]')?.value,
            year_from: document.querySelector('input[name="year_from"]')?.value,
            year_to: document.querySelector('input[name="year_to"]')?.value,
            free_only: document.querySelector('input[name="free_only"]')?.checked,
            dubbed: document.querySelector('input[name="dubbed"]')?.checked
        };
        
        this.saveFilters(filters);
    }
};

// Initialize filter persistence on Discover page
document.addEventListener('DOMContentLoaded', function() {
    if (document.querySelector('.discover-page') || document.querySelector('.filters-sidebar')) {
        FilterPersistence.restoreFilters();
        FilterPersistence.setupAutoSave();
    }
});

// 3. Infinite Scroll / Load More
const InfiniteScroll = {
    page: 1,
    isLoading: false,
    hasMore: true,
    
    init: function() {
        const loadMoreBtn = document.getElementById('loadMoreBtn');
        if (loadMoreBtn) {
            loadMoreBtn.addEventListener('click', () => this.loadMore());
        }
    },
    
    loadMore: function() {
        if (this.isLoading || !this.hasMore) return;
        
        this.isLoading = true;
        this.page++;
        
        // Get current filters from URL or form
        const params = new URLSearchParams(window.location.search);
        params.set('page', this.page);
        
        fetch(`?${params.toString()}`)
            .then(response => response.text())
            .then(html => {
                // Parse and extract movie grid
                const parser = new DOMParser();
                const doc = parser.parseFromString(html, 'text/html');
                const newMovies = doc.querySelectorAll('.movie-grid .movie-card, .movie-grid .poster-card');
                
                if (newMovies.length === 0) {
                    this.hasMore = false;
                    document.getElementById('loadMoreBtn').textContent = 'No more movies';
                    return;
                }
                
                // Append to existing grid
                const grid = document.querySelector('.movie-grid');
                newMovies.forEach(movie => {
                    grid.appendChild(movie.cloneNode(true));
                });
                
                this.isLoading = false;
            });
    }
};

// Initialize infinite scroll
document.addEventListener('DOMContentLoaded', function() {
    InfiniteScroll.init();
});

// 4. Keyboard Shortcuts (Power User Features)
const KeyboardShortcuts = {
    init: function() {
        document.addEventListener('keydown', (e) => {
            // / → Focus search
            if (e.key === '/') {
                e.preventDefault();
                const searchInput = document.querySelector('.search-input-discover, input[placeholder*="Search"]');
                if (searchInput) searchInput.focus();
            }
            
            // f → Open filters
            if (e.key === 'f' && !e.ctrlKey && !e.metaKey) {
                const filterToggle = document.getElementById('sidebarToggle');
                if (filterToggle) filterToggle.click();
            }
            
            // Escape → Close filters
            if (e.key === 'Escape') {
                const filtersSidebar = document.getElementById('filtersSidebar');
                if (filtersSidebar && filtersSidebar.style.display !== 'none') {
                    filtersSidebar.style.display = 'none';
                }
            }
        });
    }
};

document.addEventListener('DOMContentLoaded', () => KeyboardShortcuts.init());
