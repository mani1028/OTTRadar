/**
 * OPTIMIZATIONS.JS
 * Handles: Lazy loading, infinite scroll, skeleton loading, trailer modal
 */

class MovieOptimizations {
    constructor() {
        this.currentPage = 1;
        this.isLoading = false;
        this.hasMore = true;
        this.currentCategory = null;
        this.initLazyLoading();
        this.initInfiniteScroll();
        this.initTrailerModal();
    }

    // ===== URL SLUG GENERATOR (SEO-FRIENDLY) =====
    slugify(title) {
        return title
            .toLowerCase()
            .replace(/[^\w\s-]/g, '')
            .replace(/[-\s]+/g, '-')
            .replace(/^-+|-+$/g, '');
    }

    // ===== LAZY LOADING IMAGES =====
    initLazyLoading() {
        if ('IntersectionObserver' in window) {
            const imageObserver = new IntersectionObserver((entries, observer) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        const img = entry.target;
                        img.src = img.dataset.src;
                        img.classList.remove('lazy');
                        observer.unobserve(img);
                    }
                });
            }, {
                rootMargin: '50px'
            });

            // Observe all lazy images
            document.querySelectorAll('img[data-src]').forEach(img => {
                imageObserver.observe(img);
            });
        } else {
            // Fallback for browsers without IntersectionObserver
            document.querySelectorAll('img[data-src]').forEach(img => {
                img.src = img.dataset.src;
            });
        }
    }

    // ===== INFINITE SCROLL =====
    initInfiniteScroll() {
        if (!('IntersectionObserver' in window)) return;

        const sentinel = document.getElementById('infinite-scroll-sentinel');
        if (!sentinel) return;

        const scrollObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting && this.hasMore && !this.isLoading) {
                    this.loadMoreMovies();
                }
            });
        });

        scrollObserver.observe(sentinel);
    }

    loadMoreMovies() {
        if (this.isLoading || !this.hasMore) return;

        this.isLoading = true;
        this.currentPage++;

        // Determine the endpoint based on current page
        const query = new URLSearchParams(window.location.search);
        const searchQuery = query.get('q');
        
        if (searchQuery) {
            // Search API
            this.fetchAndAppendMovies(`/api/search?q=${encodeURIComponent(searchQuery)}&page=${this.currentPage}`);
        } else if (this.currentCategory) {
            // Category API
            this.fetchAndAppendMovies(`/api/movies/${this.currentCategory}?page=${this.currentPage}`);
        }
    }

    fetchAndAppendMovies(url) {
        // Show skeleton loaders
        this.showSkeletonLoaders(6);

        fetch(url)
            .then(response => response.json())
            .then(data => {
                this.removeSkeletonLoaders();
                
                if (data.results && data.results.length > 0) {
                    this.appendMoviesToGrid(data.results);
                    this.hasMore = data.has_more || false;
                } else {
                    this.hasMore = false;
                }
                
                this.isLoading = false;
            })
            .catch(error => {
                console.error('Error loading more movies:', error);
                this.removeSkeletonLoaders();
                this.isLoading = false;
            });
    }

    appendMoviesToGrid(movies) {
        const grid = document.querySelector('.movie-grid');
        if (!grid) return;

        movies.forEach(movie => {
            const card = this.createMovieCard(movie);
            grid.appendChild(card);
        });

        // Re-initialize lazy loading for new images
        this.initLazyLoading();
    }

    createMovieCard(movie) {
        const a = document.createElement('a');
        a.href = `/movie/${this.slugify(movie.title)}`;
        a.className = 'poster-card';

        const posterWrapper = document.createElement('div');
        posterWrapper.className = 'poster-wrapper';

        if (movie.poster) {
            const img = document.createElement('img');
            img.src = '/static/images/placeholder.jpg'; // Placeholder
            img.dataset.src = movie.poster;
            img.alt = movie.title;
            img.loading = 'lazy';
            img.className = 'lazy';
            img.onerror = () => {
                img.closest('.poster-wrapper').classList.add('image-error');
            };
            posterWrapper.appendChild(img);
        } else {
            const fallback = document.createElement('div');
            fallback.className = 'poster-fallback';
            fallback.innerHTML = '<i class="fas fa-film"></i>';
            posterWrapper.appendChild(fallback);
        }

        // Rating badge
        if (movie.rating) {
            const ratingBadge = document.createElement('div');
            ratingBadge.className = 'rating-badge';
            ratingBadge.textContent = `⭐ ${movie.rating.toFixed(1)}`;
            posterWrapper.appendChild(ratingBadge);
        }

        // OTT badges (max 2)
        if (movie.ott_platforms && Object.keys(movie.ott_platforms).length > 0) {
            const badges = document.createElement('div');
            badges.className = 'platform-badges';
            let count = 0;
            
            const ottMap = {
                'netflix': 'N',
                'prime': 'P',
                'amazon': 'P',
                'hotstar': 'H',
                'jiocinema': 'J'
            };

            for (const [platform, data] of Object.entries(movie.ott_platforms)) {
                if (count >= 2) break;
                const badgeChar = ottMap[platform.toLowerCase()] || platform.charAt(0).toUpperCase();
                const badge = document.createElement('div');
                badge.className = `platform-badge ${platform.toLowerCase()}`;
                badge.textContent = badgeChar;
                badge.title = `Available on ${platform}`;
                badges.appendChild(badge);
                count++;
            }
            posterWrapper.appendChild(badges);
        }

        a.appendChild(posterWrapper);

        // Title
        const title = document.createElement('h3');
        title.className = 'poster-title';
        title.textContent = movie.title;
        a.appendChild(title);

        return a;
    }

    // ===== SKELETON LOADERS =====
    showSkeletonLoaders(count = 6) {
        const grid = document.querySelector('.movie-grid');
        if (!grid) return;

        for (let i = 0; i < count; i++) {
            const skeleton = document.createElement('div');
            skeleton.className = 'poster-card skeleton-loader';
            skeleton.innerHTML = `
                <div class="poster-wrapper loading-skeleton"></div>
                <div class="poster-title loading-skeleton" style="height: 20px; margin-top: 8px;"></div>
            `;
            grid.appendChild(skeleton);
        }
    }

    removeSkeletonLoaders() {
        const grid = document.querySelector('.movie-grid');
        if (!grid) return;

        grid.querySelectorAll('.skeleton-loader').forEach(skeleton => {
            skeleton.remove();
        });
    }

    // ===== TRAILER MODAL =====
    initTrailerModal() {
        // Create modal if it doesn't exist
        if (!document.getElementById('trailer-modal')) {
            this.createTrailerModal();
        }

        // Add click listeners to trailer buttons
        this.attachTrailerListeners();
    }

    createTrailerModal() {
        const modal = document.createElement('div');
        modal.id = 'trailer-modal';
        modal.className = 'modal';
        modal.innerHTML = `
            <div class="modal-content">
                <span class="modal-close">&times;</span>
                <div class="modal-body">
                    <div id="trailer-container" style="position: relative; width: 100%; padding-bottom: 56.25%; height: 0; overflow: hidden; border-radius: 12px;">
                        <iframe id="trailer-iframe" 
                                style="position: absolute; top: 0; left: 0; width: 100%; height: 100%;" 
                                frameborder="0" 
                                allowfullscreen 
                                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture">
                        </iframe>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(modal);

        // Close button
        modal.querySelector('.modal-close').addEventListener('click', () => {
            this.closeTrailerModal();
        });

        // Close on outside click
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                this.closeTrailerModal();
            }
        });

        // Close on Escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.closeTrailerModal();
            }
        });
    }

    attachTrailerListeners() {
        // Look for trailer buttons with data-trailer attribute
        document.querySelectorAll('[data-trailer]').forEach(button => {
            button.addEventListener('click', (e) => {
                e.preventDefault();
                const trailerId = button.dataset.trailer;
                this.openTrailerModal(trailerId);
            });
        });

        // Also look for hero trailer buttons with youtube_trailer_id
        document.querySelectorAll('.hero-trailer-btn').forEach(button => {
            button.addEventListener('click', (e) => {
                e.preventDefault();
                const trailerId = button.dataset.youtubeId || button.dataset.trailer;
                if (trailerId) {
                    this.openTrailerModal(trailerId);
                } else {
                    alert('Trailer not available for this movie');
                }
            });
        });
    }

    openTrailerModal(trailerId) {
        const modal = document.getElementById('trailer-modal');
        const iframe = document.getElementById('trailer-iframe');
        if (!modal || !iframe) return;

        // Handle both YouTube IDs and full URLs
        let youtubeId = trailerId;
        if (trailerId.includes('youtube.com') || trailerId.includes('youtu.be')) {
            youtubeId = this.extractYouTubeId(trailerId);
        }

        if (!youtubeId) {
            alert('Trailer not available');
            return;
        }

        iframe.src = `https://www.youtube.com/embed/${youtubeId}?autoplay=1`;
        modal.classList.add('active');
        document.body.style.overflow = 'hidden';
    }

    closeTrailerModal() {
        const modal = document.getElementById('trailer-modal');
        if (!modal) return;

        modal.classList.remove('active');
        document.getElementById('trailer-iframe').src = '';
        document.body.style.overflow = '';
    }

    extractYouTubeId(url) {
        const patterns = [
            /(?:youtube\.com\/watch\?v=|youtu\.be\/)([^&\n?#]+)/,
            /^([a-zA-Z0-9_-]{11})$/
        ];

        for (const pattern of patterns) {
            const match = url.match(pattern);
            if (match && match[1]) {
                return match[1];
            }
        }
        return null;
    }

    // ===== UTILITY: Set current category =====
    setCurrentCategory(category) {
        this.currentCategory = category;
        this.currentPage = 1;
        this.hasMore = true;
    }
}

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    window.movieOptimizations = new MovieOptimizations();
});
