import '@testing-library/jest-dom';

// Ensure frontend unit and integration tests run offline in demo mode
if (typeof window !== 'undefined' && window.localStorage) {
  window.localStorage.setItem('sparkrail_demo_mode', 'true');
}
