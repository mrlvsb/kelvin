<script>
import { fade } from 'svelte/transition';

export let content;
export let title = 'Copy to clipboard';

let tooltip;

function copy(e) {
    navigator.clipboard.writeText(content);

    let container = e.target.closest('.tooltip-container');
    tooltip = {
      left: container.offsetLeft + container.offsetWidth,
      top: container.offsetTop - 5,
    }

    setTimeout(() => tooltip = null, 500);
}
</script>

<style>
span {
  cursor: pointer;
}
</style>

<span style="position: relative">
  <span on:click={copy} title={title}  class='tooltip-container'>
    <slot></slot>
  </span>
  {#if tooltip}
  <div class="tooltip bs-tooltip-right show d-flex align-items-center" role="tooltip" style="left: {tooltip.left}px; top: {tooltip.top}px" out:fade={{duration: 200}}>
    <div class="arrow"></div>
    <div class="tooltip-inner">
      Copied!
    </div>
  </div>
  {/if}
</span>
