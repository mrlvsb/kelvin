<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue';
import uppie from 'uppie';
import { csrfToken } from '../api';
import VueModal from './VueModal.vue';
import { toastApi } from '../utilities/toast';

withDefaults(
  defineProps<{
    cooldown?: number | string;
  }>(),
  {
    cooldown: 0
  }
);

const MAXIMUM_FILE_SHOWN = 20;
const SUBMITTED_TOAST_KEY = 'KELVIN_SUBMITTED_TOAST';

const filesQuestion = ref<string[]>([]);
const uploadFormData = ref<FormData | null>(null);
const dropping = ref(false);
const progress = ref<number | null>(null);
const error = ref<string | null>(null);

let dragLeaveTimer: number | undefined;

const uploadFileList = computed(() => filesQuestion.value.slice(0, MAXIMUM_FILE_SHOWN));
const uploadFileRest = computed(() => Math.max(0, filesQuestion.value.length - MAXIMUM_FILE_SHOWN));

const readSubmittedToast = () => {
  const stored = localStorage.getItem(SUBMITTED_TOAST_KEY);
  return stored ? Boolean(JSON.parse(stored)) : false;
};

const setSubmittedToast = (value: boolean) => {
  localStorage.setItem(SUBMITTED_TOAST_KEY, JSON.stringify(value));
};

const clearFormData = () => {
  uploadFormData.value = null;
  filesQuestion.value = [];
};

const parseErrorMessage = (xhr: XMLHttpRequest) => {
  const fallback = `Upload failed (HTTP ${xhr.status}).\nTry again or use the upload button.`;

  const responseText = xhr.responseText;
  if (!responseText) {
    return fallback;
  }

  try {
    const parsed = JSON.parse(responseText) as { error?: unknown; message?: unknown };

    if (typeof parsed.error === 'string' && parsed.error.trim().length > 0) {
      return parsed.error;
    }

    if (typeof parsed.message === 'string' && parsed.message.trim().length > 0) {
      return parsed.message;
    }

    return fallback;
  } catch {
    return fallback;
  }
};

const upload = (formData: FormData) => {
  progress.value = 0;
  error.value = null;

  const xhr = new XMLHttpRequest();
  xhr.responseType = 'text';

  xhr.upload.addEventListener('progress', (event) => {
    if (event.lengthComputable) {
      progress.value = Math.round((event.loaded * 100) / event.total);
    }
  });

  xhr.addEventListener('loadend', () => {
    if (xhr.status >= 200 && xhr.status < 300 && xhr.responseURL) {
      setSubmittedToast(true);
      window.location.href = `${xhr.responseURL}#result`;
      return;
    }

    error.value = parseErrorMessage(xhr);
    progress.value = null;
  });

  xhr.addEventListener('error', () => {
    error.value = 'Network error.\nCheck your connection and try again.';
    progress.value = null;
  });

  xhr.open('POST', window.location.href);
  xhr.setRequestHeader('X-CSRFToken', csrfToken());
  xhr.setRequestHeader('Accept', 'application/json');
  xhr.send(formData);
};

const acceptUpload = () => {
  if (!uploadFormData.value) {
    return;
  }

  upload(uploadFormData.value);
  clearFormData();
};

const dismiss = () => {
  if (error.value === null) {
    return;
  }

  error.value = null;
  dropping.value = false;
  progress.value = null;
};

const dragstop = () => {
  if (dragLeaveTimer) {
    window.clearTimeout(dragLeaveTimer);
  }

  dragLeaveTimer = window.setTimeout(() => {
    dropping.value = false;
  }, 300);
};

const isInternalDrag = (event: DragEvent) => {
  if (event.dataTransfer?.types) {
    for (const type of event.dataTransfer.types) {
      // Kelvin-internal-drag is used to mark drag events that originate from within
      if (type === 'text/kelvin-internal-drag') {
        return true;
      }
    }
  }

  return false;
};

const dragstart = (event: DragEvent) => {
  if (dragLeaveTimer) {
    window.clearTimeout(dragLeaveTimer);
  }

  if (isInternalDrag(event)) {
    return;
  }

  const hasFiles = () => {
    if (event.dataTransfer?.types) {
      for (const type of event.dataTransfer.types) {
        if (type === 'Files') {
          return true;
        }
      }
    }
    return false;
  };

  if (uploadFormData.value === null && hasFiles() && !dropping.value) {
    dropping.value = true;
  }
};

const setupUploadInput = () => {
  const input = document.getElementById('upload-choose') as HTMLInputElement | null;
  if (!input) {
    return;
  }

  const handleChange = () => {
    if (!input.files?.length) {
      return;
    }

    const formData = new FormData();
    const fileNames: string[] = [];

    for (const file of Array.from(input.files)) {
      formData.append('solution', file);
      fileNames.push(file.name);
    }

    formData.append('paths', fileNames.join('\n'));
    upload(formData);
  };

  input.addEventListener('change', handleChange);

  return () => {
    input.removeEventListener('change', handleChange);
  };
};

const setupDragAndDrop = () => {
  // Use uppie so folders dropped from the file manager are expanded.
  uppie()(window, { name: 'solution' }, (_event: Event, formData: FormData, files: string[]) => {
    const event = _event as DragEvent;
    if (isInternalDrag(event)) {
      return;
    }

    if (!files.length || uploadFormData.value !== null) {
      return;
    }

    formData.append('paths', files.join('\n'));
    uploadFormData.value = formData;
    filesQuestion.value = files;
  });

  window.addEventListener('dragleave', dragstop);
  window.addEventListener('drop', dragstop);
  window.addEventListener('dragenter', dragstart);
  window.addEventListener('dragover', dragstart);

  return () => {
    window.removeEventListener('dragleave', dragstop);
    window.removeEventListener('drop', dragstop);
    window.removeEventListener('dragenter', dragstart);
    window.removeEventListener('dragover', dragstart);
  };
};

let removeInputListener: (() => void) | undefined;
let removeDragListeners: (() => void) | undefined;

onMounted(() => {
  removeInputListener = setupUploadInput();
  removeDragListeners = setupDragAndDrop();

  if (readSubmittedToast()) {
    setSubmittedToast(false);
    toastApi.success('The files have been submitted successfully.');
  }
});

onUnmounted(() => {
  removeInputListener?.();
  removeDragListeners?.();

  if (dragLeaveTimer) {
    window.clearTimeout(dragLeaveTimer);
  }
});
</script>

<template>
  <div
    class="dropzone"
    :class="{
      dropping,
      uploading: progress !== null,
      error: error !== null
    }"
    @click="dismiss"
  >
    <span v-if="error !== null" class="text-danger" style="white-space: pre-line">
      {{ error }}
    </span>

    <span v-else-if="progress !== null">{{ progress }}%</span>

    <span v-else>
      <span class="iconify" data-icon="ic:baseline-file-upload" data-inline="false"></span>
    </span>
  </div>

  <VueModal
    :open="uploadFormData !== null"
    title="Submit source code"
    :on-closed="(proceed: boolean) => (proceed ? acceptUpload() : clearFormData())"
  >
    <p>
      <strong>Do you really want to submit these files?</strong>
    </p>
    <ul>
      <li v-for="file in uploadFileList" :key="file">{{ file }}</li>
    </ul>
    <span v-if="uploadFileRest > 0">and {{ uploadFileRest }} other file(s).</span>
  </VueModal>
</template>

<style scoped>
.dropzone {
  position: fixed;
  z-index: 10;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  transition: background-color 100ms;
  visibility: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10rem;
  text-align: center;
}

.dropzone.uploading:not(.dropzone.error) {
  cursor: wait;
}

.dropzone.dropping,
.dropzone.uploading,
.dropzone.error {
  visibility: visible;
  background: #007bff50;
}

.dropzone.error {
  background: #f5c6cbcc;
  font-size: 3rem;
}
</style>
