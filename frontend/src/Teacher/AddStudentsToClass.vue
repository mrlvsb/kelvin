<script setup lang="ts">
import { ref, defineProps, defineEmits } from 'vue';
import { getDataWithCSRF } from '../utilities/api';

const props = defineProps({
  classId: {
    type: [String, Number],
    required: true
  }
});

const emit = defineEmits(['update']);

const textarea = ref('');
const processing = ref(false);
const addStudentError = ref('');

function pasteLogins(event) {
  const paste = (event.clipboardData || window.clipboardData).getData('text').toUpperCase();
  const logins = Array.from(paste.matchAll(/\b([A-Z]{3}[0-9]{2,4})\b/g)).map((m) => m[1]);
  if (logins.length) {
    event.preventDefault();
    logins.sort();
    textarea.value = [...new Set(logins)].join('\n');
  }
}

async function addStudents() {
  addStudentError.value = '';
  const logins = textarea.value
    .split('\n')
    .map((login) => login.trim())
    .filter((login) => login.length);

  if (!logins.length) return;

  processing.value = true;

  try {
    const url = `/api/classes/${props.classId}/add_students`;

    const res = await getDataWithCSRF<{
      not_found: string[];
      success: boolean;
      error?: string;
    }>(url, 'POST', { username: logins });

    if (res) {
      if (res['not_found']?.length) {
        addStudentError.value = 'Not found users left in textarea.';
        textarea.value = res['not_found'].join('\n');
        emit('update');
      } else if (res['success'] === true) {
        textarea.value = '';
        console.log('Successfully added a student!');
        emit('update');
      } else {
        addStudentError.value = res['error'] || 'Unknown error';
      }
    }
  } catch (err) {
    addStudentError.value = 'Error: ' + err;
  }

  processing.value = false;
}
</script>

<template>
  <form class="p-0 mb-2" @submit.prevent="addStudents">
    <textarea
      v-model="textarea"
      class="form-control mb-1"
      rows="20"
      :disabled="processing"
      placeholder="Add student logins to this class
May contain surrounding text or HTML"
      @paste="pasteLogins"
    />
    <button class="btn btn-primary" type="submit" :disabled="processing">
      <template v-if="!processing">Add</template>
      <template v-else>
        <div class="spinner-border spinner-border-sm"></div>
      </template>
    </button>
  </form>
  <span v-if="addStudentError" class="text-danger">{{ addStudentError }}</span>
</template>
