document.addEventListener('DOMContentLoaded', () => {
        // Show popup for flash messages
        const alerts = document.querySelectorAll('.alert');
        alerts.forEach(alert => {
            if (alert.textContent.trim()) {
                // Create a popup div
                const popup = document.createElement('div');
                popup.className = 'popup-flash popup-' + alert.className.replace('alert-', '');
                popup.textContent = alert.textContent;
                document.body.appendChild(popup);
                setTimeout(() => {
                    popup.classList.add('show');
                }, 100);
                setTimeout(() => {
                    popup.classList.remove('show');
                    setTimeout(() => popup.remove(), 500);
                }, 3000);
            }
        });
    // Mobile Menu Toggle
    const mobileMenuBtn = document.getElementById('mobile-menu');
    const mobileMenu = document.getElementById('mobile-menu-content');

    if (mobileMenuBtn && mobileMenu) {
        mobileMenuBtn.addEventListener('click', () => {
            mobileMenu.classList.toggle('hidden');
            mobileMenu.classList.toggle('active');
            
            // Toggle icon between bars and times (X)
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
    
    // ===== INFINITE SCROLL FOR LARGE LISTS =====
    // Handles pagination for category pages (trending, new-on-ott, free, hidden-gems, upcoming)
    initInfiniteScroll();
        // ===== AJAX LIVE SEARCH FOR SEARCH PAGE =====
        const searchInput = document.getElementById('live-search-input');
        const searchResults = document.getElementById('live-search-results');
        if (searchInput && searchResults) {
            let debounceTimeout = null;
            searchInput.addEventListener('input', function() {
                const q = this.value.trim();
                if (debounceTimeout) clearTimeout(debounceTimeout);
                if (q.length < 2) {
                    searchResults.innerHTML = '';
                    return;
                }
                debounceTimeout = setTimeout(() => {
                    searchResults.innerHTML = '<div style="color:var(--text-secondary);padding:8px;">Searching...</div>';
                    fetch(`/api/search?q=${encodeURIComponent(q)}&limit=8`)
                        .then(res => res.json())
                        .then(data => {
                            if (!data.results || data.results.length === 0) {
                                searchResults.innerHTML = '<div style="color:var(--text-secondary);padding:8px;">No results found.</div>';
                                return;
                            }
                            searchResults.innerHTML = data.results.map(movie => `
                                <a href="/movie/${movie.tmdb_id}" style="display:flex;align-items:center;padding:8px 0;text-decoration:none;color:var(--text-primary);border-bottom:1px solid var(--border);">
                                    <img src="${movie.poster || movie.backdrop || '/static/images/platforms/default.png'}" alt="${movie.title}" style="width:40px;height:60px;object-fit:cover;border-radius:6px;margin-right:12px;">
                                    <div>
                                        <div style="font-weight:500;font-size:15px;">${movie.title}</div>
                                        <div style="font-size:13px;color:var(--text-secondary);">${movie.year || ''} ${movie.rating ? '★ ' + movie.rating.toFixed(1) : ''}</div>
                                    </div>
                                </a>
                            `).join('');
                        })
                        .catch(() => {
                            searchResults.innerHTML = '<div style="color:var(--text-secondary);padding:8px;">Error searching.</div>';
                        });
                }, 250);
            });
        }
});

/**
 * Initialize infinite scroll for paginated movie lists
 * Loads next page when user scrolls near bottom
 */
function initInfiniteScroll() {
    const container = document.getElementById('movies-container');
    if (!container) return; // Not a category/list page
    
    let currentPage = 1;
    let isLoading = false;
    let hasMore = true;
    let category = getCategory();
    
    if (!category) return; // Can't determine category
    
    // Intersection Observer for lazy loading
    const sentinel = document.createElement('div');
    sentinel.id = 'scroll-sentinel';
    container.parentElement.appendChild(sentinel);
    
    const options = {
        root: null,
        rootMargin: '200px', // Load 200px before reaching bottom
        threshold: 0
    };
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting && hasMore && !isLoading) {
                loadNextPage();
            }
        });
    }, options);
    
    observer.observe(sentinel);
    
    /**
     * Load next page of movies
     */
    async function loadNextPage() {
        if (isLoading || !hasMore) return;
        
        isLoading = true;
        currentPage++;
        
        try {
            const response = await fetch(
                `/api/movies/${category}?page=${currentPage}&limit=12`
            );
            
            if (!response.ok) {
                throw new Error('Failed to load movies');
            }
            
            const data = await response.json();
            
            if (!data.results || data.results.length === 0) {
                hasMore = false;
                return;
            }
            
            // Render new movies
            renderMovies(data.results, container);
            
            // Update has_more flag
            hasMore = data.has_more || false;
            
            if (!hasMore) {
                sentinel.style.display = 'none';
            }
        } catch (error) {
            console.error('Infinite scroll error:', error);
            hasMore = false;
        } finally {
            isLoading = false;
        }
    }
    
    /**
     * Render movies to container
     */
    function renderMovies(movies, container) {
        movies.forEach(movie => {
            const movieEl = createMovieElement(movie);
            container.appendChild(movieEl);
        });
    }
    
    /**
     * Create movie card element
     */
    function createMovieElement(movie) {
        const div = document.createElement('div');
        div.className = 'movie-card';
        div.innerHTML = `
            <a href="/movie/${movie.id}">
                <div class="poster-wrapper">
                    ${movie.poster ? 
                        `<img src="https://image.tmdb.org/t/p/w200${movie.poster}" alt="${movie.title}" loading="lazy">` :
                        `<div class="no-poster">No Poster</div>`
                    }
                    ${movie.youtube_trailer_id ? 
                        `<div class="trailer-badge">
                            <i class="fas fa-play"></i>
                        </div>` : ''
                    }
                </div>
                <div class="movie-info">
                    <h3>${movie.title}</h3>
                    ${movie.rating ? `<div class="rating">★ ${movie.rating.toFixed(1)}</div>` : ''}
                </div>
            </a>
        `;
        return div;
    }
    
    /**
     * Get category from page URL or meta tag
     */
    function getCategory() {
        // Try from meta tag
        const meta = document.querySelector('meta[name="category"]');
        if (meta) return meta.getAttribute('content');
        
        // Try from URL path
        const path = window.location.pathname;
        const match = path.match(/\/(trending|new-on-ott|free|hidden-gems|upcoming)/);
        return match ? match[1] : null;
    }
});

// Top modal search fallback logic
const watchButtons = document.querySelectorAll('.open-watch-modal');
watchButtons.forEach(btn => {
    btn.addEventListener('click', (e) => {
        const movieTitle = btn.dataset.title;
        const linkExists = btn.dataset.hasLink === 'true';

        if (!linkExists) {
            // Inform user about search fallback
            console.log(`No direct link for ${movieTitle}. Using search fallback.`);
            // Optionally update modal content here
        }
        // Logic to open your "Top Modal" remains here
    });
});
