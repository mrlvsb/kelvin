<script>
import { onMount } from 'svelte';
import { csrfToken } from './api.js';
import uppie from 'uppie';
import { localStorageStore } from './utils.js';
import Toast from 'bootstrap/js/dist/toast';
import Modal from './Modal.svelte';

export let cooldown = 0;

let filesQuestion = [];
let uploadFormData = null;
let dropping = false;
let dragLeaveTimer = null;
let progress = null;
let error = false;
let lastSubmitDate = localStorageStore('KELVIN_LAST_SUBMIT_DATE', 0);
let submittedToast = localStorageStore('KELVIN_SUBMITTED_TOAST', false);
let toast = null;
let remainingMS = -1;
let queued = null;

function upload(formData) {
  progress = 0;
  const xhr = new XMLHttpRequest();
  xhr.upload.addEventListener(
    'progress',
    (e) => {
      if (e.lengthComputable) {
        progress = Math.round((e.loaded * 100) / e.total);
      }
    },
    false
  );
  xhr.addEventListener('loadend', () => {
    if (xhr.status == 200 && xhr.responseURL) {
      $lastSubmitDate = new Date();
      $submittedToast = true;
      document.location.href = xhr.responseURL + '#result';
    } else {
      error = true;
    }
  });
  xhr.open('POST', document.location.href);
  xhr.setRequestHeader('X-CSRFToken', csrfToken());
  xhr.send(formData);
}

uppie()(window, { name: 'solution' }, async (event, formData, files) => {
  if (files.length && uploadFormData === null) {
    formData.append('paths', files.join('\n'));
    if (remainingMS <= 0) {
      uploadFormData = formData;
      filesQuestion = files;
    } else {
      queued = formData;
    }
  }
});

function acceptUpload() {
  upload(uploadFormData);
  clearFormData();
}

function clearFormData() {
  uploadFormData = null;
  filesQuestion = [];
}

function dragstop() {
  if (dragLeaveTimer) {
    clearInterval(dragLeaveTimer);
  }
  dragLeaveTimer = setTimeout(() => (dropping = false), 300);
}

function dragstart(e) {
  if (dragLeaveTimer) {
    clearInterval(dragLeaveTimer);
  }

  function hasFiles() {
    if (e.dataTransfer.types) {
      for (const t of e.dataTransfer.types) {
        if (t == 'Files') {
          return true;
        }
      }
    }
    return false;
  }

  if (uploadFormData === null && hasFiles() && !dropping) {
    dropping = true;
  }
}

function dismiss() {
  if (!error && !queued) {
    return;
  }

  error = false;
  dropping = false;
  progress = null;
  queued = null;
}

const btn = document.getElementById('upload-choose');
btn.onchange = function () {
  $lastSubmitDate = new Date();
  $submittedToast = true;
  this.form.submit();
};
const btnText = btn.nextElementSibling;

function update() {
  try {
    const target = new Date();
    target.setUTCMilliseconds(target.getUTCMilliseconds() - cooldown * 1000);
    remainingMS = new Date($lastSubmitDate) - target;
  } catch (e) {}

  if (remainingMS <= 0) {
    btn.removeAttribute('disabled');
    btnText.classList.remove('disabled');
    btnText.innerText = 'Upload';

    if (queued) {
      const formData = queued;
      console.log(queued);
      upload(formData);
    }
    return;
  }

  btn.setAttribute('disabled', 'disabled');
  btnText.classList.add('disabled');
  btnText.innerText = 'next upload in ' + Math.ceil(remainingMS / 1000) + ' seconds';
  setTimeout(update, 1000);
}

const MAXIMUM_FILE_SHOWN = 20;

function uploadFileList() {
  return filesQuestion.slice(0, MAXIMUM_FILE_SHOWN);
}
function uploadFileRest() {
  return Math.max(0, filesQuestion.length - MAXIMUM_FILE_SHOWN);
}

onMount(async () => {
  if ($submittedToast) {
    $submittedToast = false;
    new Toast(toast).show();
  }
});

update();
</script>

<svelte:window
  on:dragleave={dragstop}
  on:drop={dragstop}
  on:dragenter={dragstart}
  on:dragover={dragstart} />

<div
  class="dropzone"
  class:dropping
  class:uploading={progress != null}
  class:queued
  class:error
  on:click={dismiss}>
  {#if error}
    <span class="text-danger">
      Upload failed.<br />
      Try again or use the upload button.
    </span>
  {:else if queued}
    uploading in {Math.ceil(remainingMS / 1000)} seconds...
  {:else if progress != null}
    {progress}%
  {:else}
    <span
      ><span class="iconify" data-icon="ic:baseline-file-upload" data-inline="false"></span></span>
  {/if}
</div>

<Modal
  open={uploadFormData !== null}
  onClosed={(proceed) => (proceed ? acceptUpload() : clearFormData())}
  title="Submit source code">
  <p>
    <strong>Do you really want to submit these files?</strong>
  </p>
  <ul>
    {#each uploadFileList() as file}
      <li>{file}</li>
    {/each}
  </ul>
  {#if uploadFileRest() > 0}
    <span>and {uploadFileRest()} other file(s).</span>
  {/if}
</Modal>

<div class="position-fixed top-0 end-0 mt-5 me-3">
  <div
    class="toast align-items-center text-white bg-success border-0"
    role="alert"
    aria-live="assertive"
    aria-atomic="true"
    bind:this={toast}>
    <div class="d-flex">
      <div class="toast-body">The files have been submitted successfully.</div>
      <button
        type="button"
        class="btn-close btn-close-white me-2 m-auto"
        data-bs-dismiss="toast"
        aria-label="Close" />
    </div>
  </div>
</div>

<style>
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
