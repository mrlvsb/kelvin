<script>
import { onDestroy, onMount } from 'svelte';
import { fetch } from './api';

export let selected_classrooms = [];
export let onDuplicateClick;

let all_classrooms = [];

onMount(async () => {
  const req = await fetch('/api/classrooms-list/');
  all_classrooms = await req.json();
});

$: if (selected_classrooms) {
  all_classrooms = all_classrooms.map((i) => {
    i.selected = selected_classrooms.includes(i.id);
    return i;
  });
}

let search = '';
let showDropdown = false;

function toggleItem(item) {
  item.selected = !item.selected;
  if (item.selected) {
    selected_classrooms.push(item.id);
  } else {
    const idx = selected_classrooms.indexOf(item.id);
    if (idx > -1) {
      selected_classrooms.splice(idx, 1);
    }
  }
  all_classrooms = [...all_classrooms];
  selected_classrooms = [...selected_classrooms];
}

$: sortedClassroomList = all_classrooms
  .filter((i) => i.name.toLowerCase().includes(search.toLowerCase()))
  .sort((a, b) => {
    if (a.selected && !b.selected) return -1;
    if (!a.selected && b.selected) return 1;

    return a.name.localeCompare(b.name);
  });

$: selectedCount = all_classrooms.filter((i) => i.selected).length;

function toggleDropdown() {
  showDropdown = !showDropdown;
  if (showDropdown) {
    document.addEventListener('click', handleClickOutside);
  } else {
    document.removeEventListener('click', handleClickOutside);
  }
}

let outsideClick;
function handleClickOutside(event) {
  if (outsideClick && !outsideClick.contains(event.target)) {
    showDropdown = false;
    document.removeEventListener('click', handleClickOutside);
  }
}

onDestroy(() => {
  document.removeEventListener('click', handleClickOutside);
});
</script>

<div class="dropdown" style="position: relative;" bind:this={outsideClick}>
  <div class="input-group">
    <input
      type="button"
      value={selectedCount > 0 ? `${selectedCount} classroom(s) selected` : 'Select classrooms'}
      class="btn btn-sm btn-primary"
      on:click={toggleDropdown} />
    <button
      class="btn btn-sm btn-secondary"
      title="Set assigned classroom list to all visible classes"
      on:click|preventDefault={() => onDuplicateClick(selected_classrooms)}>
      <span class="iconify" data-icon="mdi:content-duplicate"></span>
    </button>
  </div>

  {#if showDropdown}
    <div
      class="card p-3 mt-2"
      style="position: absolute; z-index: 1000; width: 250px; max-height: 300px; overflow-y: auto;">
      <input type="text" placeholder="Search..." bind:value={search} class="form-control mb-2" />

      {#each sortedClassroomList as classroom (classroom.id)}
        <div class="form-check">
          <input
            type="checkbox"
            class="form-check-input"
            id={'classroom' + classroom.id}
            checked={classroom.selected}
            on:change={() => toggleItem(classroom)} />
          <label class="form-check-label" for={'classroom' + classroom.id}>{classroom.name}</label>
        </div>
      {/each}

      {#if sortedClassroomList.length === 0}
        <small class="text-black">No classrooms found</small>
      {/if}
    </div>
  {/if}
</div>

<style>
.dropdown .card {
  background: white;
  border: 1px solid #ddd;
  border-radius: 0.25rem;
  color: black;
}
</style>
