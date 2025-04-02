<script>
import { task_types } from './taskTypes.js';

export let task_type = null;

function setTaskType(type) {
  task_type = type;
}
</script>

<div class="ms-auto">
  <div class="input-group">
    {#each task_types as { key, value }}
      <button
        type="button"
        class="btn btn-dark {key == task_type ? 'active' : ''}"
        on:click={() => setTaskType(key)}
        on:change>{value}</button>
    {/each}
  </div>
</div>
