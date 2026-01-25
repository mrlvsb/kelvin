<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue';
import uppie from 'uppie';
import { csrfToken } from '../api';
import VueModal from './VueModal.vue';
import { toastApi } from '../utilities/toast';

const props = withDefaults(
  defineProps<{
    cooldown?: number | string;
  }>(),
  {
    cooldown: 0
  }
);

const MAXIMUM_FILE_SHOWN = 20;
const LAST_SUBMIT_KEY = 'KELVIN_LAST_SUBMIT_DATE';
const SUBMITTED_TOAST_KEY = 'KELVIN_SUBMITTED_TOAST';

const filesQuestion = ref<string[]>([]);
const uploadFormData = ref<FormData | null>(null);
const dropping = ref(false);
const progress = ref<number | null>(null);
const error = ref(false);
const remainingMS = ref(-1);
const queued = ref<FormData | null>(null);
const fileInput = ref<HTMLInputElement | null>(null);
const fileInputLabel = ref<HTMLElement | null>(null);

const cooldownSeconds = computed(() => Number(props.cooldown ?? 0) || 0);

let dragLeaveTimer: number | undefined;
let cooldownTimer: number | undefined;

const uploadFileList = computed(() => filesQuestion.value.slice(0, MAXIMUM_FILE_SHOWN));
const uploadFileRest = computed(() => Math.max(0, filesQuestion.value.length - MAXIMUM_FILE_SHOWN));

const readStoredDate = () => {
  const stored = localStorage.getItem(LAST_SUBMIT_KEY);
  if (!stored) {
    return new Date(0);
  }

  try {
    const parsed = JSON.parse(stored) as string | number;
    return new Date(parsed);
  } catch {
    return new Date(stored);
  }
};

const setStoredDate = (date: Date) => {
  localStorage.setItem(LAST_SUBMIT_KEY, date.toISOString());
};

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

const upload = (formData: FormData) => {
  progress.value = 0;

  const xhr = new XMLHttpRequest();
  xhr.upload.addEventListener('progress', (event) => {
    if (event.lengthComputable) {
      progress.value = Math.round((event.loaded * 100) / event.total);
    }
  });

  xhr.addEventListener('loadend', () => {
    if (xhr.status === 200 && xhr.responseURL) {
      setStoredDate(new Date());
      setSubmittedToast(true);
      window.location.href = `${xhr.responseURL}#result`;
      return;
    }

    error.value = true;
  });

  xhr.open('POST', window.location.href);
  xhr.setRequestHeader('X-CSRFToken', csrfToken());
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
  if (!error.value && !queued.value) {
    return;
  }

  error.value = false;
  dropping.value = false;
  progress.value = null;
  queued.value = null;
};

const dragstop = () => {
  if (dragLeaveTimer) {
    window.clearTimeout(dragLeaveTimer);
  }

  dragLeaveTimer = window.setTimeout(() => {
    dropping.value = false;
  }, 300);
};

const dragstart = (event: DragEvent) => {
  if (dragLeaveTimer) {
    window.clearTimeout(dragLeaveTimer);
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

const updateCooldown = () => {
  const target = new Date();
  target.setUTCMilliseconds(target.getUTCMilliseconds() - cooldownSeconds.value * 1000);
  remainingMS.value = readStoredDate().getTime() - target.getTime();

  if (!fileInput.value || !fileInputLabel.value) {
    return;
  }

  if (remainingMS.value <= 0) {
    fileInput.value.removeAttribute('disabled');
    fileInputLabel.value.classList.remove('disabled');
    fileInputLabel.value.innerText = 'Upload';

    if (queued.value) {
      const pending = queued.value;
      queued.value = null;
      upload(pending);
    }

    return;
  }

  fileInput.value.setAttribute('disabled', 'disabled');
  fileInputLabel.value.classList.add('disabled');
  fileInputLabel.value.innerText = `next upload in ${Math.ceil(remainingMS.value / 1000)} seconds`;

  cooldownTimer = window.setTimeout(updateCooldown, 1000);
};

const setupUploadInput = () => {
  const input = document.getElementById('upload-choose') as HTMLInputElement | null;
  if (!input) {
    return;
  }

  fileInput.value = input;
  fileInputLabel.value = input.nextElementSibling as HTMLElement | null;

  const handleChange = () => {
    setStoredDate(new Date());
    setSubmittedToast(true);
    input.form?.submit();
  };

  input.addEventListener('change', handleChange);

  return () => {
    input.removeEventListener('change', handleChange);
  };
};

const setupDragAndDrop = () => {
  // Use uppie so folders dropped from the file manager are expanded.
  uppie()(window, { name: 'solution' }, (_event: Event, formData: FormData, files: string[]) => {
    if (!files.length || uploadFormData.value !== null) {
      return;
    }

    formData.append('paths', files.join('\n'));
    if (remainingMS.value <= 0) {
      uploadFormData.value = formData;
      filesQuestion.value = files;
      return;
    }

    queued.value = formData;
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

  updateCooldown();
});

onUnmounted(() => {
  removeInputListener?.();
  removeDragListeners?.();

  if (cooldownTimer) {
    window.clearTimeout(cooldownTimer);
  }

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
      queued: queued !== null,
      error
    }"
    @click="dismiss"
  >
    <span v-if="error" class="text-danger">
      Upload failed.<br />
      Try again or use the upload button.
    </span>

    <span v-else-if="queued !== null">
      uploading in {{ Math.ceil(remainingMS / 1000) }} seconds...
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
.dropzone.queued {
  visibility: visible;
  background: #007bff50;
}

.dropzone.queued {
  font-size: 3rem;
}

.dropzone.error {
  background: #f5c6cbcc;
  font-size: 3rem;
}
</style>
