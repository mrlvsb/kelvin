<script>
import 'bootstrap/js/dist/dropdown';
import 'bootstrap/js/dist/button';
import { curTheme } from './utils';

let workingTheme = 'auto';
const htmlData = document.querySelector('html').dataset;
let autoInUse = false;
const icons = {
  auto: 'bi-circle-half',
  light: 'bi-sun',
  dark: 'bi-moon-stars'
};

function detectTheme() {
  const colorScheme = window.matchMedia('(prefers-color-scheme: light)');
  const theme = colorScheme.matches ? 'light' : 'dark';
  htmlData.bsTheme = theme;
  curTheme.set(theme);
}

function selectTheme(event) {
  workingTheme = event.srcElement.dataset.theme;
  if (workingTheme == 'auto') {
    localStorage.removeItem('color-theme');
    autoInUse = true;
    detectTheme();
    window.matchMedia('(prefers-color-scheme: light)').addEventListener('change', detectTheme);
    return;
  }
  // theme is manually selected
  curTheme.set(workingTheme);
  window.matchMedia('(prefers-color-scheme: light)').removeEventListener('change', detectTheme);
  localStorage.setItem('color-theme', workingTheme);
  htmlData.bsTheme = workingTheme;
}

if (localStorage.getItem('color-theme') === null) {
  detectTheme();
  window.matchMedia('(prefers-color-scheme: light)').addEventListener('change', detectTheme);
} else {
  workingTheme = htmlData.bsTheme = localStorage.getItem('color-theme');
  curTheme.set(htmlData.bsTheme);
}
</script>

<li class="nav-item dropdown">
  <button
    class="btn nav-link dropdown-toggle"
    href="#"
    type="button"
    data-bs-toggle="dropdown"
    aria-expanded="false"
    title="Change theme">
    <i class="bi {icons[workingTheme] === undefined ? 'bi-circle-half' : icons[workingTheme]}"></i>
    <span class="d-md-none ms-1">Change theme</span>
  </button>
  <ul class="dropdown-menu dropdown-menu-end shadow">
    <li>
      <button
        on:click={selectTheme}
        class="d-flex dropdown-item"
        class:active={workingTheme == 'auto'}
        data-theme="auto">
        <i class="me-1 bi bi-circle-half"></i>Auto<i
          class="opacity-75 ms-auto bi bi-check2"
          hidden={workingTheme != 'auto'}></i>
      </button>
    </li>
    <li>
      <button
        on:click={selectTheme}
        class="d-flex dropdown-item"
        class:active={workingTheme == 'light'}
        data-theme="light">
        <i class="me-1 bi bi-sun"></i>Light mode<i
          class="opacity-75 ms-auto bi bi-check2"
          hidden={workingTheme != 'light'}></i>
      </button>
    </li>
    <li>
      <button
        on:click={selectTheme}
        class="d-flex dropdown-item"
        class:active={workingTheme == 'dark'}
        data-theme="dark">
        <i class="me-1 bi bi-moon-stars"></i>Dark mode<i
          class="opacity-75 ms-auto bi bi-check2"
          hidden={workingTheme != 'dark'}></i>
      </button>
    </li>
  </ul>
</li>
