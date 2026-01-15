<script lang="ts" setup>
import { ref, watch } from 'vue';
import Editor from '../Editor.vue';

const props = defineProps({
  comment: {
    type: String,
    default: ''
  },
  disabled: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits(['save']);

const localComment = ref(props.comment);

watch(
  () => props.comment,
  (value) => {
    localComment.value = value;
  }
);

const submit = () => {
  if (!props.disabled) {
    emit('save', localComment.value);
  }
};
</script>

<template>
  <Editor
    v-model:value="localComment"
    filename="comment.md"
    :disabled="disabled"
    :wrap="true"
    :autofocus="true"
    :extra-keys="{ 'Ctrl-Enter': submit }"
  />
  <button class="btn btn-sm btn-primary mt-1" :disabled="disabled" @click.prevent="submit">
    Add comment
  </button>
</template>
