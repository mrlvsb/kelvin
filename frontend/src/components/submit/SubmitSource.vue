<script lang="ts" setup>
import { computed, onMounted, ref, watch } from 'vue';
import CodeRow from './CodeRow.vue';
import hljs from 'highlight.js/lib/core';
import type { Comment } from '../../types/TaskDetail';

const props = withDefaults(
  defineProps<{
    code: string;
    comments?: Record<string, Comment[]>;
    selectedRows?: { from: number; to: number } | null;
    path: string;
  }>(),
  {
    comments: () => ({}),
    selectedRows: null
  }
);

const emit = defineEmits(['setNotification', 'resolveSuggestion', 'saveComment']);

const addingCommentToLine = ref(-1);
const highlightedLines = ref<string[]>([]);
const selecting = ref(0);
const userSelected = ref(false);
const commentsByLine = computed(() => props.comments || {});

const updateHighlightedLines = () => {
  const container = document.createElement('div');
  container.innerHTML = hljs.highlightAuto(props.code).value;

  container.querySelectorAll('.hljs-comment').forEach((el) => {
    const commentNode = el as HTMLElement;

    if (commentNode.innerText.indexOf('\n') >= 0) {
      const parent = commentNode.parentNode;
      if (!parent) {
        return;
      }

      let prev: Node = commentNode;

      for (const line of commentNode.innerText.split('\n')) {
        const e = document.createElement('span');
        e.classList.add('hljs-comment');
        e.innerText = line;
        parent.insertBefore(e, prev.nextSibling);
        prev = parent.insertBefore(document.createTextNode('\n'), e.nextSibling);
      }

      commentNode.remove();
    }
  });

  highlightedLines.value = container.innerHTML.split('\n');
};

onMounted(updateHighlightedLines);
watch(() => props.code, updateHighlightedLines);

const updateSelection = (to) => {
  let from = selecting.value;
  if (from > to) {
    [from, to] = [to, from];
  }

  document.location.hash = `#src;${props.path}:${from}${to !== from ? '-' + to : ''}`;
};

const mousedown = (event: MouseEvent) => {
  const target = event.target as HTMLElement | null;

  if (target?.tagName === 'SPAN') {
    return;
  }

  userSelected.value = true;
  const td = target?.closest('tr td:first-of-type') as HTMLTableCellElement | null;

  if (td) {
    const row = td.closest('tr') as HTMLTableRowElement | null;
    if (row) {
      selecting.value = row.rowIndex + 1;
    }

    updateSelection(selecting.value);
  }
};

const mouseover = (event: MouseEvent) => {
  const target = event.target as HTMLElement | null;
  const td = target?.closest('tr td:first-of-type') as HTMLTableCellElement | null;

  if (td && selecting.value >= 1) {
    const row = td.closest('tr') as HTMLTableRowElement | null;

    if (row) {
      updateSelection(row.rowIndex + 1);
    }
  }
};
</script>

<template>
  <table :data-path="path" @mousedown="mousedown" @mouseover="mouseover" @mouseup="selecting = 0">
    <CodeRow
      v-for="(line, index) in highlightedLines"
      :key="index"
      :line="line"
      :line-number="index + 1"
      :comments="commentsByLine[index]"
      :show-adding-form="addingCommentToLine === index + 1"
      :selected="selectedRows && index + 1 >= selectedRows.from && index + 1 <= selectedRows.to"
      :scroll="selectedRows && !userSelected && index + 1 === selectedRows.from"
      @show-comment-form="addingCommentToLine = $event"
      @set-notification="emit('setNotification', $event)"
      @resolve-suggestion="emit('resolveSuggestion', $event)"
      @save-comment="emit('saveComment', $event)"
    />
  </table>
</template>
