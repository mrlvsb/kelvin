<script setup>
import { computed, onMounted, ref, watch } from 'vue';
import CodeRow from './CodeRow.vue';
import hljs from 'highlight.js/lib/core';

const props = defineProps({
  code: {
    type: String,
    required: true
  },
  comments: {
    type: Object,
    default: () => ({})
  },
  selectedRows: {
    type: Object,
    default: null
  },
  path: {
    type: String,
    required: true
  }
});

const emit = defineEmits(['setNotification', 'resolveSuggestion', 'saveComment']);

const addingCommentToLine = ref(-1);
const highlightedLines = ref([]);
const selecting = ref(0);
const userSelected = ref(false);
const commentsByLine = computed(() => props.comments || {});

const updateHighlightedLines = () => {
  const container = document.createElement('div');
  container.innerHTML = hljs.highlightAuto(props.code).value;

  container.querySelectorAll('.hljs-comment').forEach((el) => {
    if (el.innerText.indexOf('\n') >= 0) {
      let prev = el;

      for (const line of el.innerText.split('\n')) {
        const e = document.createElement('span');
        e.classList.add('hljs-comment');
        e.innerText = line;
        el.parentNode.insertBefore(e, prev.nextSibling);
        prev = el.parentNode.insertBefore(document.createTextNode('\n'), e.nextSibling);
      }

      el.remove();
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

const mousedown = (event) => {
  if (event.target.tagName === 'SPAN') {
    return;
  }

  userSelected.value = true;
  const td = event.target.closest('tr td:first-of-type');

  if (td) {
    selecting.value = td.closest('tr').rowIndex + 1;
    updateSelection(selecting.value);
  }
};

const mouseover = (event) => {
  const td = event.target.closest('tr td:first-of-type');

  if (td && selecting.value >= 1) {
    updateSelection(td.closest('tr').rowIndex + 1);
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
