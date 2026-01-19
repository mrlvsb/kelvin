<script lang="ts" setup>
import { computed, ref } from 'vue';
import CommentForm from './CommentForm.vue';
import StarRating from '../StarRating.vue';
import { safeMarkdown } from '../../markdown.js';
import { user } from '../../global.js';
import { hideComments, HideCommentsState } from '../../stores';
import { useSvelteStore } from '../../utilities/useSvelteStore';
import { fetch as apiFetch } from '../../api.js';
import Toast from 'bootstrap/js/dist/toast';
import { Comment } from '../../types/TaskDetail';

const props = withDefaults(defineProps<Comment & { summary?: boolean }>(), {
  summary: false
});

const emit = defineEmits(['resolveSuggestion']);

const toast = ref(null);
const editing = ref(false);
const sending = ref(false);
const committedRating = ref(props.meta.review.rating ?? 0);

const currentUser = useSvelteStore(user, null);
const hideCommentsValue = useSvelteStore(hideComments, HideCommentsState.NONE);

const showComment = computed(() => {
  return !(
    hideCommentsValue.value === HideCommentsState.AUTOMATED ||
    hideCommentsValue.value === HideCommentsState.ALL
  );
});

// TODO: Implement global toast notification system and remove this local one
const showToast = (message, status = 'success') => {
  if (!toast.value) {
    return;
  }

  toast.value.querySelector('.toast-body').textContent = message;

  let bgColor = 'bg-success';
  let textColor = 'text-white';

  if (status === 'error') {
    bgColor = 'bg-danger';
  } else if (status === 'warning') {
    bgColor = 'bg-warning';
    textColor = 'text-dark';
  }

  toast.value.className = `toast align-items-center ${textColor} ${bgColor} border-0`;
  new Toast(toast.value).show();
};

type SuggestionRequestOptions = {
  method: 'POST' | 'DELETE' | 'PATCH';
  headers: Record<string, string>;
  body?: string;
};

const resolveSuggestion = async <T,>(
  url: string,
  options: SuggestionRequestOptions,
  onFinish: (() => void) | null = null
): Promise<{ data?: T; error?: string }> => {
  try {
    const response = await apiFetch(url, options);

    if (!response.ok) {
      const errorData = await response.json().catch(() => null);

      return {
        error: errorData?.detail || 'Unexpected error occurred. Please try again.'
      };
    }

    const data = (await response.json().catch(() => null)) as T | null;
    if (data === null) {
      return {
        error: 'Unexpected error occurred. Please try again.'
      };
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
  const suggestionId = props.meta.review.id;

  const { data, error } = await resolveSuggestion<Comment>(
    `/api/v2/llm/suggestions/${suggestionId}`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      }
    },
    () => {
      sending.value = false;
    }
  );

  if (error) {
    showToast(error, 'warning');
    return;
  }

  if (data) {
    emit('resolveSuggestion', {
      id: suggestionId,
      comment: data
    });
  } else {
    showToast('Unexpected error occurred. Please try again later.', 'error');
  }
};

const handleReject = async () => {
  sending.value = true;
  const suggestionId = props.meta.review.id;

  const { error } = await resolveSuggestion<{ status: string }>(
    `/api/v2/llm/suggestions/${suggestionId}`,
    {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json'
      }
    },
    () => {
      sending.value = false;
    }
  );

  if (error) {
    showToast(error, 'warning');
    return;
  }

  emit('resolveSuggestion', {
    id: suggestionId,
    comment: null
  });
};

const handleEdit = () => {
  editing.value = true;
};

const handleSave = async (text: string) => {
  sending.value = true;
  const suggestionId = props.meta.review.id;

  const { data, error } = await resolveSuggestion<Comment>(
    `/api/v2/llm/suggestions/${suggestionId}`,
    {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        modified_text: text
      })
    },
    () => {
      sending.value = false;
      editing.value = false;
    }
  );

  if (error) {
    showToast(error, 'warning');
    return;
  }

  if (data) {
    emit('resolveSuggestion', {
      id: suggestionId,
      comment: data
    });
  } else {
    showToast('Unexpected error occurred. Please try again later.', 'error');
  }
};

const handleRating = async (rating: number) => {
  sending.value = true;
  const suggestionId = props.meta.review.id;

  const previousRating = committedRating.value;
  committedRating.value = rating;

  const { error } = await resolveSuggestion<{ status: string }>(
    `/api/v2/llm/suggestions/${suggestionId}/rate`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        commentId: suggestionId,
        rating
      })
    },
    () => {
      sending.value = false;
    }
  );

  if (error) {
    showToast(error, 'warning');
    committedRating.value = previousRating;
  }
};
</script>

<template>
  <div class="suggested-comment" v-bind="$attrs">
    <div class="position-fixed top-0 end-0 mt-5 me-3">
      <div
        ref="toast"
        class="toast align-items-center text-white bg-success border-0"
        role="alert"
        aria-live="assertive"
        aria-atomic="true"
      >
        <div class="d-flex">
          <div class="toast-body">Unexpected error occurred. Please try again later.</div>

          <button
            type="button"
            class="btn-close btn-close-dark me-2 m-auto"
            data-bs-dismiss="toast"
            aria-label="Close"
          />
        </div>
      </div>
    </div>

    <div v-if="showComment && currentUser?.teacher" class="comment ai-review">
      <div class="comment-header">
        <strong>{{ author }}</strong>

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

      <div v-if="!editing" class="comment-text" v-html="safeMarkdown(text)"></div>
      <CommentForm v-else :comment="text" :disabled="sending" @save="handleSave" />
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
