<script lang="ts" setup>
import { computed, ref } from 'vue';
import CommentForm from './CommentForm.vue';
import StarRating from '../StarRating.vue';
import { safeMarkdown } from '../../markdown.js';
import { user } from '../../global.js';
import { hideComments, HideCommentsState } from '../../stores';
import { useSvelteStore } from '../../utilities/useSvelteStore';
import { getFromAPI } from '../../utilities/api';
import { Comment } from '../../types/TaskDetail';
import { toastApi } from '../../utilities/toast';

const props = withDefaults(
  defineProps<{
    comment: Comment;
    summary?: boolean;
  }>(),
  {
    summary: false
  }
);

const emit = defineEmits(['resolveSuggestion']);

const editing = ref(false);
const sending = ref(false);
const committedRating = ref(props.comment.meta?.review?.rating ?? 0);

const currentUser = useSvelteStore(user, null);
const hideCommentsValue = useSvelteStore(hideComments, HideCommentsState.NONE);

const showComment = computed(() => {
  return !(
    hideCommentsValue.value === HideCommentsState.AUTOMATED ||
    hideCommentsValue.value === HideCommentsState.ALL
  );
});

type SuggestionRequestOptions = {
  method: 'POST' | 'DELETE' | 'PATCH';
  body?: unknown;
};

const resolveSuggestion = async <T,>(
  url: string,
  options: SuggestionRequestOptions,
  onFinish: (() => void) | null = null
): Promise<{ data?: T; error?: string }> => {
  try {
    const data = await getFromAPI<T>(url, options.method, options.body);

    if (data === undefined) {
      return { error: 'Unexpected error occurred. Please try again.' };
    }

    return { data };
  } catch (error) {
    console.error(error);
    return { error: 'Unexpected error occurred. Please try again later.' };
  } finally {
    if (onFinish) {
      onFinish();
    }
  }
};

const handleAccept = async () => {
  sending.value = true;
  const suggestionId = props.comment.meta?.review?.id;

  const { data, error } = await resolveSuggestion<Comment>(
    `/api/v2/llm/suggestions/${suggestionId}`,
    {
      method: 'POST'
    },
    () => {
      sending.value = false;
    }
  );

  if (error) {
    toastApi.error(error);
    return;
  }

  if (data) {
    emit('resolveSuggestion', {
      id: suggestionId,
      comment: data
    });

    toastApi.success('Suggestion accepted successfully.');
  } else {
    toastApi.error('Unexpected error occurred. Please try again later.');
  }
};

const handleReject = async () => {
  sending.value = true;
  const suggestionId = props.comment.meta?.review?.id;

  const { error } = await resolveSuggestion<{ status: string }>(
    `/api/v2/llm/suggestions/${suggestionId}`,
    {
      method: 'DELETE'
    },
    () => {
      sending.value = false;
    }
  );

  if (error) {
    toastApi.error(error);
    return;
  }

  emit('resolveSuggestion', {
    id: suggestionId,
    comment: null
  });

  toastApi.success('Suggestion rejected successfully.');
};

const handleEdit = () => {
  editing.value = true;
};

const handleSave = async (text: string) => {
  sending.value = true;
  const suggestionId = props.comment.meta?.review?.id;

  const { data, error } = await resolveSuggestion<Comment>(
    `/api/v2/llm/suggestions/${suggestionId}`,
    {
      method: 'PATCH',
      body: {
        modified_text: text
      }
    },
    () => {
      sending.value = false;
      editing.value = false;
    }
  );

  if (error) {
    toastApi.error(error);
    return;
  }

  if (data) {
    emit('resolveSuggestion', {
      id: suggestionId,
      comment: data
    });

    toastApi.success('Suggestion accepted successfully.');
  } else {
    toastApi.error('Unexpected error occurred. Please try again later.');
  }
};

const handleRating = async (rating: number) => {
  sending.value = true;
  const suggestionId = props.comment.meta?.review?.id;

  const previousRating = committedRating.value;
  committedRating.value = rating;

  const { error } = await resolveSuggestion<{ status: string }>(
    `/api/v2/llm/suggestions/${suggestionId}/rate`,
    {
      method: 'POST',
      body: {
        commentId: suggestionId,
        rating
      }
    },
    () => {
      sending.value = false;
    }
  );

  if (error) {
    toastApi.error(error);
    committedRating.value = previousRating;
    return;
  }

  toastApi.success('Rating submitted successfully.');
};
</script>

<template>
  <div class="suggested-comment" v-bind="$attrs">
    <div v-if="showComment && currentUser?.teacher" class="comment ai-review">
      <div class="comment-header">
        <strong>{{ comment.author }}</strong>

        <div v-if="currentUser?.teacher && !editing" class="comment-actions">
          <button
            v-if="summary === true"
            title="Dismiss"
            class="icon-button"
            :disabled="sending"
            @click.prevent="handleReject"
          >
            <span class="iconify" data-icon="cil-x"></span>
          </button>

          <template v-else>
            <button
              title="Turn into a student-visible comment"
              class="icon-button"
              :disabled="sending"
              @click.prevent="handleAccept"
            >
              <span class="iconify" data-icon="cil-check"></span>
            </button>

            <button
              title="Edit"
              class="icon-button"
              :disabled="sending"
              @click.prevent="handleEdit"
            >
              <span class="iconify" data-icon="cil-pencil"></span>
            </button>

            <button
              title="Reject"
              class="icon-button"
              :disabled="sending"
              @click.prevent="handleReject"
            >
              <span class="iconify" data-icon="cil-x"></span>
            </button>
          </template>

          <StarRating
            :committed-rating="committedRating"
            :disabled="sending"
            @rate="handleRating"
          />
        </div>
      </div>

      <!-- eslint-disable vue/no-v-html -->
      <div v-if="!editing" class="comment-text" v-html="safeMarkdown(comment.text || '')" />
      <!-- eslint-enable -->
      <CommentForm v-else :comment="comment.text || ''" :disabled="sending" @save="handleSave" />
    </div>
  </div>
</template>

<style scoped>
.comment-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.comment-actions {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.icon-button {
  cursor: pointer;
  border: none;
  background: none;
  font-size: 1rem;
  line-height: 1;
  padding: 0.2rem;
  border-radius: 4px;
  transition: color 0.2s;
}

.icon-button:hover {
  color: black;
}
</style>
