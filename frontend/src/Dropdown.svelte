<script>
  export let shown = false;

  function clickOutside(node) {
    const handleClick = event => {
      if (node && !event.defaultPrevented) {
        shown = false;
      }
    }

    document.addEventListener('click', handleClick, true);
    return {
      destroy() {
        document.removeEventListener('click', handleClick, true);
      }
    }
  }
</script>


<div class="dropdown" use:clickOutside>
  <button class="btn btn-secondary dropdown-toggle" on:click|preventDefault={() => shown = true}>
    <span class="iconify" data-icon="cil:clock"></span>
  </button>
  <div class="dropdown-menu" class:show={shown}>
    <slot></slot>
  </div>
</div>
