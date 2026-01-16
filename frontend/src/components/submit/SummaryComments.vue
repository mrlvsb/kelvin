<script lang="ts" setup>
import { ref } from 'vue';
import CommentForm from './CommentForm.vue';
import Comment from './Comment.vue';
import SuggestedComment from './SuggestedComment.vue';
import type { Comment as TaskComment } from '../../types/TaskDetail';

withDefaults(
  defineProps<{
    summaryComments?: TaskComment[];
  }>(),
  {
    summaryComments: () => []
  }
);

const emit = defineEmits(['saveComment', 'setNotification', 'resolveSuggestion']);

const showForm = ref(false);

const addComment = (text: string) => {
  emit('saveComment', {
    text,
    success: () => {
      showForm.value = false;
    }
  });
};
</script>

<template>
  <template v-for="comment in summaryComments" :key="comment.id">
    <SuggestedComment
      v-if="comment.type === 'ai-review'"
      v-bind="comment"
      :summary="true"
      @resolve-suggestion="emit('resolveSuggestion', $event)"
    />

    <Comment
      v-else
      v-bind="comment"
      @save-comment="emit('saveComment', $event)"
      @set-notification="emit('setNotification', $event)"
    />
  </template>

  <div v-if="showForm">
    <CommentForm @save="addComment" />
  </div>

  <button v-else class="btn p-0" @click="showForm = !showForm">
    <span
      class="iconify"
      data-icon="bx:bx-comment-add"
      data-inline="false"
      data-flip="vertical"
      data-height="20"
      title="Add new comment"
    ></span>
  </button>
</template>

<style scoped>
div :global(.CodeMirror) {
  height: 100px;
}

button {
  line-height: normal;
  margin-top: -10px;
}
</style>
