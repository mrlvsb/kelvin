<script lang="ts" setup>
import type { CommentCounts } from '../../types/TaskDetail';

const props = withDefaults(
  defineProps<{
    counts?: CommentCounts | null;
    size?: 'sm' | 'md';
  }>(),
  {
    counts: null,
    size: 'sm'
  }
);
</script>

<template>
  <span
    v-if="props.counts?.user || props.counts?.automated"
    class="comment-badges"
    :class="`comment-badges--${props.size}`"
  >
    <span v-if="props.counts?.user" class="badge bg-secondary" title="Student/teacher comments">
      {{ props.counts.user }}
    </span>

    <span v-if="props.counts?.automated" class="badge bg-primary" title="Automation comments">
      {{ props.counts.automated }}
    </span>
  </span>
</template>

<style scoped>
.comment-badges {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-left: 6px;
}

.comment-badges .badge {
  font-size: 0.6em;
  line-height: 1;
}

.comment-badges .badge:hover {
  text-decoration: none;
}

.comment-badges--sm .badge {
  padding: 4px 6px;
}

.comment-badges--md .badge {
  padding: 5px 10px;
}
</style>
