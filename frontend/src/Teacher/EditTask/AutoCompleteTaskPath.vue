<script setup lang="ts">
/**
 * Component displays an input field that autocomplete path based on subject and username.
 * It also allows user to copy entered path in SSH/RSYNC format to clipboard.
 */

import { user as userSvelte } from '../../global.js';
import { clickOutside } from '../../utilities/clickOutside';
import { User } from '../../utilities/SvelteStoreTypes';
import { useReadableSvelteStore } from '../../utilities/useSvelteStoreInVue';
import { defineModel, onMounted, computed, ref, watch, defineEmits } from 'vue';
import CopyToClipboard from './CopyToClipboard.vue';

/**
 * @prop {string}                     subject  - subject code used to get autocomplete hints
 * @prop {(task_id: number) => void}  onChange - function called once user select item from list
 */
let { subject, onChange } = defineProps<{
  subject: string;
  onChange: (task_id: number) => void;
}>();

const vClickOutside = clickOutside;

const clickEmit = defineEmits<{
  (e: 'click'): void;
}>();

/**
 * @model
 * @type string
 * Model is variable containing actual path
 */
const path = defineModel<string>();

interface TaskList {
  id: number;
  title: string;
  path: string;
  subject: string;
  date: Date;
  link: string;
}

const user = useReadableSvelteStore<User>(userSvelte);

const items = ref<TaskList[]>([]);
const selectedId = ref<number | null>(null);
let focused = ref<boolean>(false);
const highlighted_row = ref<number>(-1);

const filtered = computed(() =>
  items.value.filter(
    (i) =>
      i['path'].toLowerCase().includes(path.value.toLowerCase()) &&
      i['path'].toLowerCase() != path.value.toLowerCase()
  )
);

onMounted(async () => {
  // Load last 100 tasks of the given subject.
  // Hopefully they will contain some useful paths to autocomplete :)
  let res = await fetch(`/api/task-list/${subject}?sort=desc`);
  res = await res.json();
  items.value = res['tasks'];
});

// https://stackoverflow.com/a/6969486/1107768
function escapeRegExp(string: string): string {
  return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); // $& means the whole matched string
}

function keyup(e: KeyboardEvent) {
  if (e.key == 'Enter' && highlighted_row.value >= 0) {
    focused.value = false;
    selectedId.value = filtered.value[highlighted_row.value].id;
    path.value = filtered.value[highlighted_row.value].path;

    let input: HTMLInputElement = e.target as HTMLInputElement;
    input.blur();
  } else if (e.key == 'ArrowUp' && highlighted_row.value >= 0) {
    highlighted_row.value = Math.max(0, highlighted_row.value - 1);
  } else if (e.key == 'ArrowDown') {
    highlighted_row.value = Math.min(filtered.value.length - 1, highlighted_row.value + 1);
  }
}

watch(selectedId, () => {
  if (selectedId.value) onChange(selectedId.value);
});
</script>

<template>
  <div v-click-outside="() => (focused = false)" class="form-control">
    <div class="input-group mb-1">
      <input
        v-model="path"
        class="form-control"
        required
        placeholder="Task directory"
        @focus="focused = true"
        @click="() => clickEmit('click')"
        @keyup="keyup"
      />
      <span class="btn btn-sm btn-outline-secondary">
        <CopyToClipboard
          :content="`${user.username.toLowerCase()}@kelvin.cs.vsb.cz:/srv/kelvin/kelvin/tasks/${path}`"
          title="Copy path for scp/rsync to the clipboard"
          >path</CopyToClipboard
        >
      </span>
      <span class="btn btn-sm btn-outline-secondary">
        <CopyToClipboard
          :content="`ssh -t ${user.username.toLowerCase()}@kelvin.cs.vsb.cz 'cd /srv/kelvin/kelvin/tasks/${path} && exec bash'`"
          title="Copy ssh command to the clipboard"
          >ssh</CopyToClipboard
        >
      </span>
    </div>

    <ul v-if="filtered.length && focused">
      <li
        v-for="(item, i) in filtered"
        :key="i"
        :class="{ highlight: highlighted_row == i }"
        @click="
          () => {
            path = item.path;
            selectedId = item.id;
          }
        "
        v-html="
          item.path.replace(new RegExp('(' + escapeRegExp(path) + ')', 'gi'), '<strong>$1</strong>')
        "
      ></li>
    </ul>
  </div>
</template>

<style scoped>
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
