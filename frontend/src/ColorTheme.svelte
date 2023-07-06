<script>
  import 'bootstrap/js/dist/dropdown';
  import 'bootstrap/js/dist/button';
  import { curTheme } from "./utils";

  const htmlData = document.querySelector("html").dataset;
  let autoInUse = false;
  const icons = {
    "auto": "bi-circle-half",
    "light": "bi-sun",
    "dark": "bi-moon-stars",
  }

  function detectTheme() {
    const colorScheme = window.matchMedia("(prefers-color-scheme: light)");
    const theme = colorScheme.matches ? "light" : "dark";
    htmlData.bsTheme = theme;
    curTheme.set(theme);
  }

  function selectTheme(event) {
    const theme = event.srcElement.dataset.theme;
    if (theme == "auto") {
      localStorage.removeItem("color-theme"); 
      detectTheme();
      window.matchMedia("(prefers-color-scheme: light)").addEventListener("change", detectTheme);
      return;
    }
    // theme is manually selected
    curTheme.set(theme);
    window.matchMedia("(prefers-color-scheme: light)").removeEventListener("change", detectTheme);
    localStorage.setItem("color-theme", $curTheme);
    htmlData.bsTheme = $curTheme;
  }


  if (localStorage.getItem("color-theme") === null) {
    detectTheme();
    window.matchMedia("(prefers-color-scheme: light)").addEventListener("change", detectTheme);
  } else {
    htmlData.bsTheme = localStorage.getItem("color-theme");
    curTheme.set(htmlData.bsTheme);
  }
</script>

<li class="nav-item dropdown">
  <button class="btn btn-link nav-link dropdown-toggle" href="#" type="button" data-bs-toggle="dropdown" aria-expanded="false" title="Change theme">
    <i class="bi {icons[$curTheme] === undefined ? "bi-circle-half" : icons[$curTheme]}"></i>
    <span class="d-md-none ms-1">Change theme</span>
  </button>
  <ul class="dropdown-menu dropdown-menu-end shadow">
    <li><button on:click={selectTheme} class="d-flex dropdown-item" class:active={$curTheme == "auto"} data-theme="auto">
      <i class="me-1 bi bi-circle-half"></i>Auto<i class="opacity-75 ms-auto bi bi-check2" hidden={$curTheme != "auto"}></i>
    </button></li>
    <li><button on:click={selectTheme} class="d-flex dropdown-item" class:active={$curTheme == "light"} data-theme="light">
      <i class="me-1 bi bi-sun"></i>Light mode<i class="opacity-75 ms-auto bi bi-check2" hidden={$curTheme != "light"}></i>
    </button></li>
    <li><button on:click={selectTheme} class="d-flex dropdown-item" class:active={$curTheme == "dark"} data-theme="dark">
      <i class="me-1 bi bi-moon-stars"></i>Dark mode<i class="opacity-75 ms-auto bi bi-check2" hidden={$curTheme != "dark"}></i>
    </button></li>
  </ul>
</li>
