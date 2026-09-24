/**
 * Dev-server proxy for /api.
 * Host `npm start` uses 127.0.0.1:8000.
 * Docker Compose sets API_PROXY_TARGET=http://backend:8000 so the frontend
 * container reaches the backend service instead of itself.
 */
const target = process.env.API_PROXY_TARGET || 'http://127.0.0.1:8000';

module.exports = {
  '/api': {
    target,
    secure: false,
    changeOrigin: true,
  },
};
