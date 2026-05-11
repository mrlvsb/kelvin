<script lang="ts" setup>
import { computed, ref } from 'vue';
import CommentForm from './CommentForm.vue';
import { user } from '../../global';
import { safeMarkdown } from '../../markdown';
import { hideComments, HideCommentsState } from '../../stores';
import { useSvelteStore } from '../../utilities/useSvelteStore';
import { Comment } from '../../types/TaskDetail';

const props = defineProps<{
  comment: Comment;
}>();

const emit = defineEmits(['saveComment', 'setNotification']);

const editing = ref(false);
const sending = ref(false);

const currentUser = useSvelteStore(user, null);
const currentHideComments = useSvelteStore(hideComments, HideCommentsState.NONE);

const showComment = computed(() => {
  return (
    currentHideComments.value !== HideCommentsState.ALL &&
    !(
      currentHideComments.value === HideCommentsState.AUTOMATED &&
      props.comment.type === 'automated'
    )
  );
});

const updateComment = (text: string) => {
  sending.value = true;

  emit('saveComment', {
    id: props.comment.id,
    text,
    success: () => {
      editing.value = false;
      sending.value = false;
    }
  });
};

const handleNotification = () => {
  emit('setNotification', {
    comment_id: props.comment.id,
    unread: !props.comment.unread
  });
};
</script>

<template>
  <div v-if="showComment" style="display: flex; flex-direction: row">
    <div
      class="comment"
      :class="[`comment-${comment.unread ? 'unread' : 'read'}`, comment.type]"
      @dblclick="editing = comment.can_edit"
    >
      <strong>{{ comment.author }}: </strong>

      <template v-if="!editing">
        <template v-if="comment.type === 'automated'">
          {{ comment.text }}
          <a v-if="comment.meta && comment.meta.url" :href="comment.meta.url">
            <span class="iconify" data-icon="entypo:help"></span>
          </a>
        </template>

        <template v-else-if="currentUser">
          <button
            v-if="comment.unread && comment.author_id !== currentUser.id"
            class="btn p-0 float-end"
            style="line-height: normal"
            @click.prevent="handleNotification"
          >
            <span class="iconify" data-icon="cil-check"></span>
          </button>

          <!-- eslint-disable vue/no-v-html -->
          <span v-html="safeMarkdown(comment.text || '')" />
          <!-- eslint-enable -->
        </template>
      </template>

      <CommentForm v-else :comment="comment.text || ''" :disabled="sending" @save="updateComment" />
    </div>
  </div>
</template>
