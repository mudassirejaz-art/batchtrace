/**
 * Small marketing-site bootstrap: leave the existing src/main.tsx and
 * src/App.tsx completely unchanged for the authenticated application.
 * This file is the only Vite HTML entrypoint after the guarded install.
 */
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

if (window.location.pathname === '/') {
  // The public page is isolated from the dashboard's global CSS/reset.
  document.body.style.margin = '0';
  void import('./batchtrace/landing/Landing').then(({ Landing }) => {
    const container = document.getElementById('root');
    if (!container) {
      throw new Error('BatchTrace landing mount point #root not found');
    }
    createRoot(container).render(
      <StrictMode>
        <Landing />
      </StrictMode>,
    );
  });
} else {
  // Original startup code handles /app, authentication, dashboard and all
  // other existing routes without any modification or new provider context.
  void import('./main');
}
