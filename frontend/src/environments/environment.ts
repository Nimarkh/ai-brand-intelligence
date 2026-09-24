export const environment = {
  // Same-origin `/api/v1` for both development (proxy.conf.js) and production
  // (nginx reverse proxy). Never put secrets or absolute backend hostnames here —
  // frontend build variables are public in the browser bundle.
  apiBaseUrl: '/api/v1',
};
