<script lang="ts" setup>
import { computed, ref } from 'vue';

const props = withDefaults(
  defineProps<{
    committedRating: number;
    disabled?: boolean;
  }>(),
  {
    committedRating: 0,
    disabled: false
  }
);

const emit = defineEmits<{
  (event: 'rate', value: number): void;
}>();

const starIndexes: number[] = [1, 2, 3, 4, 5];
const hoverRating = ref<number | null>(null);

const displayRating = computed<number>(() => hoverRating.value ?? props.committedRating);

const getRatingFromPointer = (event: PointerEvent, starIndex: number) => {
  const target = event.currentTarget as HTMLElement | null;
  if (!target) {
    return Math.max(0, Math.min(10, starIndex * 2));
  }

  const rect = target.getBoundingClientRect();
  const offsetX = event.clientX - rect.left;
  const isHalf = offsetX <= rect.width / 2;

  return Math.max(0, Math.min(10, (starIndex - 1) * 2 + (isHalf ? 1 : 2)));
};

const getStarIconClass = (starIndex: number, rating: number) => {
  const starRating = rating - (starIndex - 1) * 2;

  if (starRating >= 2) return 'bi-star-fill';
  if (starRating === 1) return 'bi-star-half';
  return 'bi-star';
};

const handlePointerMove = (event: PointerEvent, starIndex: number) => {
  if (props.disabled) return;
  hoverRating.value = getRatingFromPointer(event, starIndex);
};

const handleClick = (event: PointerEvent, starIndex: number) => {
  if (props.disabled) return;
  const rating = getRatingFromPointer(event, starIndex);
  emit('rate', rating);
};

const handleLeave = () => {
  hoverRating.value = null;
};
</script>

<template>
  <div class="rating-container" @pointerleave="handleLeave" @blur="handleLeave">
    <button
      v-for="starIndex in starIndexes"
      :key="starIndex"
      type="button"
      class="rating-star"
      @pointermove="(event) => handlePointerMove(event, starIndex)"
      @click="(event) => handleClick(event as PointerEvent, starIndex)"
    >
      <i :class="['bi', getStarIconClass(starIndex, displayRating)]" />
    </button>
  </div>
</template>

<style scoped>
.rating-container {
  display: flex;
  align-items: center;
  gap: 0.2rem;
}

.rating-star {
  cursor: pointer;
  border: none;
  background: none;
  padding: 0;
  line-height: 1;
  color: var(--bs-warning);
  font-size: 1rem;
}

.rating-star .bi {
  display: inline-block;
}
</style>
