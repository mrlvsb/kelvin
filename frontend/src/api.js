export function fetch(url, options) {
  options = options || {};
  options.headers = options.headers || {};
  options.headers['X-CSRFToken'] = csrfToken();
  return window.fetch(url, options);
}

export function csrfToken() {
  return document.querySelector('meta[name=csrf-token]').getAttribute('content');
}
