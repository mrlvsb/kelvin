<script>
  import 'bootstrap/js/dist/dropdown';
  import 'bootstrap/js/dist/button';

  const htmlData = document.querySelector("html").dataset;
  let curTheme = "auto";
  const icons = {
    "auto": "bi-circle-half",
    "light": "bi-sun",
    "dark": "bi-moon-stars",
  }

  function detectTheme() {
    const colorScheme = window.matchMedia("(prefers-color-scheme: light)");
    htmlData.bsTheme = colorScheme.matches ? "light" : "dark";
  }

  function selectTheme(event) {
    curTheme = event.srcElement.dataset.theme;
    if (curTheme == "auto") {
      localStorage.removeItem("color-theme"); 
      detectTheme();
      window.matchMedia("(prefers-color-scheme: light)").addEventListener("change", detectTheme);
      return;
    }
    // theme is manually selected
    window.matchMedia("(prefers-color-scheme: light)").removeEventListener("change", detectTheme);
    localStorage.setItem("color-theme", curTheme);
    htmlData.bsTheme = curTheme;
  }


  if (localStorage.getItem("color-theme") === null) {
    detectTheme();
    window.matchMedia("(prefers-color-scheme: light)").addEventListener("change", detectTheme);
  } else {
    htmlData.bsTheme = curTheme = localStorage.getItem("color-theme");
  }
</script>

<li class="nav-item dropdown">
  <button class="btn btn-link nav-link dropdown-toggle" href="#" type="button" data-bs-toggle="dropdown" aria-expanded="false">
    <i class="bi {icons[curTheme] === undefined ? "bi-circle-half" : icons[curTheme]}"></i>
  </button>
  <ul class="dropdown-menu dropdown-menu-end">
    <li><button on:click={selectTheme} class="d-flex dropdown-item" class:active={curTheme == "auto"} data-theme="auto">
      <i class="me-1 bi bi-circle-half"></i>Auto<i class="opacity ms-auto bi bi-check2" hidden={curTheme != "auto"}></i>
    </button></li>
    <li><button on:click={selectTheme} class="d-flex dropdown-item" class:active={curTheme == "light"} data-theme="light">
      <i class="me-1 bi bi-sun"></i>Light mode<i class="opacity ms-auto bi bi-check2" hidden={curTheme != "light"}></i>
    </button></li>
    <li><button on:click={selectTheme} class="d-flex dropdown-item" class:active={curTheme == "dark"} data-theme="dark">
      <i class="me-1 bi bi-moon-stars"></i>Dark mode<i class="opacity ms-auto bi bi-check2" hidden={curTheme != "dark"}></i>
    </button></li>
  </ul>
</li>

<style>
  .opacity {
    opacity: 85%;
  }
</style>
