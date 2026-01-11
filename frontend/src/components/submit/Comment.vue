<script setup>
import { computed, ref } from 'vue';
import CommentForm from './CommentForm.vue';
import { user } from '../../global';
import { safeMarkdown } from '../../markdown.js';
import { HideCommentsState, hideComments } from '../../stores';
import { useSvelteStore } from '../../utilities/useSvelteStore.js';

const props = defineProps({
  author: {
    type: String,
    default: ''
  },
  author_id: {
    type: Number,
    default: null
  },
  text: {
    type: String,
    default: ''
  },
  type: {
    type: String,
    default: ''
  },
  id: {
    type: Number,
    default: null
  },
  can_edit: {
    type: Boolean,
    default: false
  },
  unread: {
    type: Boolean,
    default: null
  },
  notification_id: {
    type: Number,
    default: null
  },
  meta: {
    type: Object,
    default: null
  }
});

const emit = defineEmits(['saveComment', 'setNotification']);

const editing = ref(false);
const sending = ref(false);

const currentUser = useSvelteStore(user, null);
const currentHideComments = useSvelteStore(hideComments, HideCommentsState.NONE);

const showComment = computed(() => {
  return (currentHideComments.value !== HideCommentsState.ALL)
    && !(currentHideComments.value === HideCommentsState.AUTOMATED && props.type === 'automated');
});

const updateComment = (text) => {
  sending.value = true;

  emit('saveComment', {
    id: props.id,
    text,
    success: () => {
      editing.value = false;
      sending.value = false;
    }
  });
};

const handleNotification = () => {
  emit('setNotification', {
    comment_id: props.id,
    unread: !props.unread
  });
};
</script>

<template>
  <div v-if="showComment" style="display: flex; flex-direction: row;">
    <div
      class="comment"
      :class="[`comment-${unread ? 'unread' : 'read'}`, type]"
      @dblclick="editing = can_edit"
    >
      <strong>{{ author }}: </strong>

      <template v-if="!editing">
        <template v-if="type === 'automated'">
          {{ text }}
          <a v-if="meta && meta.url" :href="meta.url">
            <span class="iconify" data-icon="entypo:help"></span>
          </a>
        </template>

        <template v-else-if="currentUser">
          <button
            v-if="unread && author_id !== currentUser.id"
            class="btn p-0 float-end"
            style="line-height: normal"
            @click.prevent="handleNotification"
          >
            <span class="iconify" data-icon="cil-check"></span>
          </button>

          <span v-html="safeMarkdown(text)"></span>
        </template>
      </template>

      <CommentForm v-else :comment="text" :disabled="sending" @save="updateComment" />
    </div>
  </div>
</template>
