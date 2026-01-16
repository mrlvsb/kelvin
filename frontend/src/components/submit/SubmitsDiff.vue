<script lang="ts" setup>
import { ref, watch } from 'vue';
import TimeAgo from '../TimeAgo.vue';
import type { Submit } from '../../types/TaskDetail';

declare global {
  interface Window {
    Diff2Html: {
      html: (
        diff: string,
        options: {
          matching: string;
          outputFormat: string;
          drawFileList: boolean;
        }
      ) => string;
    };
  }
}

const props = withDefaults(
  defineProps<{
    submits?: Submit[];
    current_submit: number;
    deadline: number | string | Date;
  }>(),
  {
    submits: () => []
  }
);

const a = ref(1);
const b = ref(props.current_submit);
const diffHtmlOutput = ref('');

const formatInfo = (submit: Submit) => {
  let result = '';

  if (submit.points !== null) {
    result += `${submit.points} point${submit.points !== 1 ? 's' : ''}`;
  }

  if (submit.comments > 0) {
    if (submit.points != null) {
      result += ', ';
    }

    result += `${submit.comments} comment${submit.comments !== 1 ? 's' : ''}`;
  }

  return ` (${result})`;
};

watch(
  () => props.current_submit,
  (value) => {
    if (value != null) {
      a.value = Math.max(value - 1, 1);
      b.value = value;
    }
  },
  { immediate: true }
);

watch(
  [a, b],
  () => {
    if (a.value === b.value) {
      diffHtmlOutput.value = '';
      return;
    }

    fetch(`../${a.value}-${b.value}.diff`)
      .then((result) => result.text())
      .then((diff) => {
        diffHtmlOutput.value = window.Diff2Html.html(diff, {
          matching: 'lines',
          outputFormat: 'side-by-side',
          drawFileList: false
        });
      });
  },
  { immediate: true }
);
</script>

<template>
  <ul>
    <li v-for="submit in submits" :key="submit.num">
      <input v-model="a" type="radio" :value="submit.num" />
      <input v-model="b" type="radio" :value="submit.num" :disabled="submit.num <= a" />

      <a :href="`../${submit.num}#src`">
        <strong>#{{ submit.num }}</strong>
      </a>

      <strong v-if="submit.submitted > deadline" class="text-danger">
        <TimeAgo
          :datetime="String(submit.submitted)"
          :rel="String(deadline)"
          suffix="after the deadline"
        />
      </strong>

      <template v-else>
        {{ new Date(submit.submitted).toLocaleString('cs') }}
      </template>

      <template v-if="submit.ip_address"> (from {{ submit.ip_address }}) </template>

      <span v-if="submit.points != null || submit.comments > 0" class="text-muted">
        {{ formatInfo(submit) }}
      </span>
    </li>

    <div class="code-diff" v-html="diffHtmlOutput"></div>
  </ul>
</template>

<style scoped>
ul {
  list-style: none;
  padding-left: 0;
}

li > * {
  margin-right: 8px;
}
</style>
