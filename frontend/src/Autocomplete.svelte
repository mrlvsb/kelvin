<script>
import { createEventDispatcher, onMount } from 'svelte';
import CopyToClipboard from './CopyToClipboard.svelte';
import { user } from './global.js';
import { clickOutside } from './utils.js';
const dispatch = createEventDispatcher();

export let value;
export let onChange = () => {};

let items = [];
let selectedId = null;
let focused = false;
let highlight_row = -1;

onMount(async () => {
  let res = await fetch('api/task-list?sort=asc');
  res = await res.json();
  items = res['tasks'];
});

// https://stackoverflow.com/a/6969486/1107768
function escapeRegExp(string) {
  return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); // $& means the whole matched string
}

function keyup(e) {
  if (e.keyCode == 13 && highlight_row >= 0) {
    focused = false;
    selectedId = filtered[highlight_row].id;
    value = filtered[highlight_row].path;
    e.target.blur();
  } else if (e.keyCode == 38 && highlight_row >= 0) {
    highlight_row = Math.max(0, highlight_row - 1);
  } else if (e.keyCode == 40) {
    highlight_row = Math.min(filtered.length - 1, highlight_row + 1);
  }
}

$: filtered = filtered = items.filter(
  (i) =>
    i['path'].toLowerCase().includes(value.toLowerCase()) &&
    i['path'].toLowerCase() != value.toLowerCase()
);

$: if (selectedId) {
  onChange(selectedId);
}
</script>

<div class="form-control" use:clickOutside on:click_outside={() => (focused = false)}>
  <div class="input-group mb-1">
    <input
      bind:value
      class="form-control"
      required
      placeholder="Task directory"
      on:focus={() => (focused = true)}
      on:click={() => dispatch('click')}
      on:keyup={keyup} />
    <span class="btn btn-sm btn-outline-secondary">
      <CopyToClipboard
        content={`${$user.username.toLowerCase()}@kelvin.cs.vsb.cz:/srv/kelvin/kelvin/tasks/${value}`}
        title="Copy path for scp/rsync to the clipboard">path</CopyToClipboard>
    </span>
    <span class="btn btn-sm btn-outline-secondary">
      <CopyToClipboard
        content={`ssh -t ${$user.username.toLowerCase()}@kelvin.cs.vsb.cz 'cd /srv/kelvin/kelvin/tasks/${value} && exec bash'`}
        title="Copy ssh command to the clipboard">ssh</CopyToClipboard>
    </span>
  </div>

  {#if filtered.length && focused}
    <ul>
      {#each filtered as item, i}
        <li
          on:click={() => {
            value = item.path;
            selectedId = item.id;
          }}
          class:highlight={highlight_row == i}>
          {@html item.path.replace(
            new RegExp('(' + escapeRegExp(value) + ')', 'gi'),
            '<strong>$1</strong>'
          )}
        </li>
      {/each}
    </ul>
  {/if}
</div>

<style>
.form-control {
  padding-bottom: 0;
}
input {
  width: 100%;
  padding-bottom: 0;
  padding-top: 0;
  outline: 0;
  border: 0;
}

ul {
  background: white;
  border: 1px solid rgb(206, 212, 218);
  max-height: 200px;
  overflow-y: auto;
  list-style: none;
  padding-left: 0;
  position: absolute;
  width: 100%;
  z-index: 3;
}

li:hover,
li.highlight {
  background: #5bc0de;
  cursor: pointer;
}
</style>
