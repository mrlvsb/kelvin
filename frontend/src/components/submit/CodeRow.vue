<script lang="ts" setup>
import { computed, ref } from 'vue';
import CommentForm from './CommentForm.vue';
import Comment from './Comment.vue';
import { user } from '../../global';
import SuggestedComment from './SuggestedComment.vue';
import { useSvelteStore } from '../../utilities/useSvelteStore';
import type { Comment as TaskComment } from '../../types/TaskDetail';

const props = withDefaults(
  defineProps<{
    line?: string;
    lineNumber: number;
    comments?: TaskComment[];
    showAddingForm?: boolean;
    selected?: boolean;
    scroll?: boolean;
  }>(),
  {
    line: '',
    comments: () => [],
    showAddingForm: false,
    selected: false,
    scroll: false
  }
);

const emit = defineEmits([
  'showCommentForm',
  'saveComment',
  'setNotification',
  'resolveSuggestion'
]);

const addingInProgress = ref(false);
const currentUser = useSvelteStore(user, null);

const commentRole = computed(() => (currentUser.value?.teacher ? 'teacher' : 'student'));

const addNewComment = (text: string) => {
  if (text === '') {
    emit('showCommentForm', -1);
    return;
  }

  addingInProgress.value = true;

  emit('saveComment', {
    line: props.lineNumber,
    text,
    success: () => {
      emit('showCommentForm', -1);
      addingInProgress.value = false;
    }
  });
};
</script>

<template>
  <tr class="linecode" :class="{ selected }" :data-line="lineNumber">
    <td class="text-end align-baseline me-2">
      <span
        style="cursor: pointer"
        @click="emit('showCommentForm', showAddingForm ? -1 : lineNumber)"
      >
        <b>+</b>
      </span>
    </td>

    <td>
      <pre v-html="line"></pre>

      <template v-for="comment in comments || []" :key="comment.id">
        <SuggestedComment
          v-if="comment.type === 'ai-review'"
          v-bind="comment"
          @resolve-suggestion="emit('resolveSuggestion', $event)"
        />

        <Comment
          v-else
          v-bind="comment"
          @save-comment="emit('saveComment', $event)"
          @set-notification="emit('setNotification', $event)"
        />
      </template>

      <div v-if="showAddingForm" class="comment" :class="commentRole">
        <CommentForm :disabled="addingInProgress" @save="addNewComment" />
      </div>
    </td>
  </tr>
</template>

<style scoped>
span,
td,
pre {
  padding: 0;
  margin: 0;
  line-height: normal;
}

tr td:first-of-type {
  user-select: none;
  font-size: 0.87em;
  cursor: row-resize;
}

tr td:first-of-type span {
  visibility: hidden;
}

tr:hover td:first-of-type span {
  visibility: visible;
}

tr.linecode {
  counter-increment: my-sec-counter;
}
tr.linecode td:first-of-type::before {
  content: counter(my-sec-counter);
}
tr.linecode td:last-of-type {
  width: 100%;
}

:global(.comment) {
  padding: 5px;
  word-break: break-word;
  border: 2px solid var(--bs-body-color);
  border-radius: 5px;
  max-width: 980px;
  margin-bottom: 1px;
  filter: opacity(0.8);
}
:global(.comment p) {
  margin-bottom: 4px;
  white-space: pre-line;
}
:global(.comment ul, .comment ol) {
  padding-left: 20px;
}
:global(.comment p:last-of-type:first-of-type) {
  display: inline;
}
:global(.comment p:last-of-type) {
  margin-bottom: 0;
}

/* Light style comments */
:global(html[data-bs-theme='light'] .comment.teacher) {
  background: #ffff1ed9;
}
:global(html[data-bs-theme='light'] .comment.teacher.comment-read) {
  background: #ffff1e49;
}
:global(html[data-bs-theme='light'] .comment.student) {
  background: #71f740;
}
:global(html[data-bs-theme='light'] .comment.student.comment-read) {
  background: #71f74050;
}
:global(html[data-bs-theme='light'] .comment.automated) {
  background: #7db4e4;
}
:global(html[data-bs-theme='light'] .comment.ai-review) {
  background: #ffb3b3;
}

/* Dark style comments */
:global(html[data-bs-theme='dark'] .comment) {
  --bs-code-color: #0021ff;
  color: #000000;
}
:global(html[data-bs-theme='dark'] .comment.teacher) {
  background: #ffff2e;
}
:global(html[data-bs-theme='dark'] .comment.teacher.comment-read) {
  background: #c0c035;
}
:global(html[data-bs-theme='dark'] .comment.student) {
  background: #4eff0e;
}
:global(html[data-bs-theme='dark'] .comment.student.comment-read) {
  background: #66ec36;
}
:global(html[data-bs-theme='dark'] .comment.automated) {
  background: #1b96ff;
}
:global(html[data-bs-theme='dark'] .comment.ai-review) {
  background: #ff6f6f;
}

.selected {
  background: #ffff9349;
}
</style>
