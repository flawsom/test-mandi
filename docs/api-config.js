/**
 * MandiIQ API Configuration
 * Dynamic API base URL detection for local dev, GitHub Pages, and Render
 * 
 * Include this in all HTML pages via:
 *   <script src="api-config.js"></script>
 */
const API_CONFIG = {
  /**
   * Auto-detect API base URL based on current host
   */
  get baseUrl() {
    const hostname = window.location.hostname;
    const isLocal = hostname === 'localhost' || hostname === '127.0.0.1';
    const isGitHub = hostname.includes('github.io') || hostname.includes('github');

    if (isLocal) {
      return 'http://127.0.0.1:18765';
    }
    if (isGitHub) {
      return 'https://mandiiq-api.onrender.com';
    }
    // Render / production
    return 'https://mandiiq-api.onrender.com';
  },

  /**
   * Dashboard URL
   */
  get dashboardUrl() {
    return 'https://mandiiq.streamlit.app';
  },

  /**
   * GitHub Pages docs URL
   */
  get docsUrl() {
    const hostname = window.location.hostname;
    if (hostname === 'localhost' || hostname === '127.0.0.1') {
      return '/docs';
    }
    return 'https://flawsom.github.io/MandiIQ/docs';
  },

  /**
   * Landing page URL
   */
  get landingUrl() {
    const hostname = window.location.hostname;
    if (hostname === 'localhost' || hostname === '127.0.0.1') {
      return '/landing/index.html';
    }
    return 'https://flawsom.github.io/MandiIQ';
  },

  /**
   * Utility: build absolute URL from path
   * @param {string} path - e.g. '/health'
   */
  url(path) {
    return `${this.baseUrl}${path}`;
  },

  endpoints: {
    health: '/health',
    freshness: '/freshness',
    pipeline: '/pipeline.mmd',
    prices: '/prices',
    forecast: '/forecast',
    rdd: '/rdd',
  },
};
