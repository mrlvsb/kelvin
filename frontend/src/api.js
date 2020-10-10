export function fetch(url, options) {
  options = options || {};
  options.headers = options.headers || {};
  options.headers['X-CSRFToken'] = document.querySelector('meta[name=csrf-token]').getAttribute('content');
  return window.fetch(url, options);
}
