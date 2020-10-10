<script>
  export let shown = false;
  let left;
  let top;
  let btnEl;

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

  function toggle() {
    left = btnEl.offsetLeft;
    top = btnEl.offsetTop + btnEl.clientHeight; 
    shown = !shown;
  }
</script>
<style>
.dropdown-menu {
  max-height: 400px;
  overflow-y: auto;
}
</style>

<button class="btn btn-sm btn-primary dropdown-toggle" on:click|preventDefault={toggle} bind:this={btnEl}></button>
<div class="dropdown-menu" class:show={shown} style="left: {left}px; top: {top}px;" use:clickOutside>
  <slot></slot>
</div>
