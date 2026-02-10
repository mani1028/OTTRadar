"""OTT link builder utilities used by enrichment scripts."""

OTT_SEARCH_URLS = {
    'netflix': 'https://www.netflix.com/search?q={query}',
    'prime': 'https://www.primevideo.com/search/ref=atv_nb_sr?phrase={query}',
    'amazon': 'https://www.primevideo.com/search/ref=atv_nb_sr?phrase={query}',
    'hotstar': 'https://www.hotstar.com/in/search?q={query}',
    'disney': 'https://www.hotstar.com/in/search?q={query}',
    'jiocinema': 'https://www.jiocinema.com/search/{query}',
    'zee5': 'https://www.zee5.com/search?q={query}',
    'sony_liv': 'https://www.sonyliv.com/search?query={query}',
    'mx_player': 'https://www.mxplayer.in/search/{query}',
    'voot': 'https://www.voot.com/search?q={query}',
    'apple': 'https://tv.apple.com/search?term={query}',
    'youtube': 'https://www.youtube.com/results?search_query={query}',
    'airtel': 'https://www.airtelxstream.in/search?query={query}'
}


DISPLAY_NAMES = {
    'netflix': 'Netflix',
    'prime': 'Prime Video',
    'amazon': 'Prime Video',
    'hotstar': 'Hotstar',
    'disney': 'Disney+',
    'jiocinema': 'JioCinema',
    'zee5': 'ZEE5',
    'sony_liv': 'SonyLIV',
    'mx_player': 'MX Player',
    'voot': 'Voot',
    'apple': 'Apple TV',
    'youtube': 'YouTube',
    'airtel': 'Airtel Xstream'
}


def get_platform_display_name(platform_key):
    """Return a friendly display name for a platform key."""
    if not platform_key:
        return ''
    return DISPLAY_NAMES.get(platform_key.lower(), platform_key.replace('_', ' ').title())
