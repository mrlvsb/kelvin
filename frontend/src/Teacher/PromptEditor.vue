<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { getFromAPI, getDataWithCSRF } from '../utilities/api';
import { toastApi } from '../utilities/toast';
import Editor from '../components/Editor.vue';
import VueModal from '../components/VueModal.vue';

type Prompt = {
  id: number;
  name: string;
  description: string;
  version: number;
  text: string;
  created_at: string | null;
  updated_at: string | null;
  default: boolean;
  is_deleted: boolean;
  author_username: string | null;
  author_full_name: string | null;
  updated_by_username: string | null;
  updated_by_full_name: string | null;
};

const props = defineProps<{
  isSuperAdmin: boolean;
  username: string;
}>();

const API = '/api/v2/llm/prompt';

const prompts = ref<Prompt[]>([]);
const selectedPrompt = ref<Prompt | null>(null);
const versionsForName = ref<string | null>(null);
const versions = ref<Prompt[]>([]);
const selectedVersionId = ref<number | null>(null);
const showDeleted = ref(false);
const loading = ref(false);
const saving = ref(false);

const editName = ref('');
const editDescription = ref('');
const editText = ref('');

const isCreating = ref(false);

const showDeleteModal = ref(false);
const promptToDelete = ref<Prompt | null>(null);

// Ownership: teacher owns selected prompt, or is superadmin
const isOwner = computed(() => {
  if (isCreating.value) return true;
  if (!selectedPrompt.value) return false;
  if (props.isSuperAdmin) return true;
  return selectedPrompt.value.author_username === props.username;
});

const isLatestVersion = computed(() => {
  if (!selectedPrompt.value) return true;
  if (versionsForName.value !== selectedPrompt.value.name) return true;
  if (versions.value.length === 0) return true;
  return selectedPrompt.value.id === versions.value[0]?.id;
});

const canEdit = computed(() => {
  if (isCreating.value) return true;
  if (!selectedPrompt.value) return false;
  if (!isOwner.value) return false;
  return isLatestVersion.value;
});

const canDelete = computed(() => {
  if (!selectedPrompt.value) return false;
  if (selectedPrompt.value.default) return false;
  if (selectedPrompt.value.is_deleted) return false;
  if (!isOwner.value) return false;
  return true;
});

const myPrompts = computed(() => prompts.value.filter((p) => p.author_username === props.username));

const otherPrompts = computed(() =>
  prompts.value.filter((p) => p.author_username !== props.username)
);

async function loadPrompts() {
  loading.value = true;
  const params = new URLSearchParams();

  if (showDeleted.value) {
    params.append('show_deleted', 'true');
  }

  const data = await getFromAPI<Prompt[]>(`${API}/?${params.toString()}`);
  if (data) {
    prompts.value = data;

    if (selectedPrompt.value) {
      const refreshed = data.find((p) => p.name === selectedPrompt.value!.name);

      if (refreshed) {
        selectedPrompt.value = {
          ...selectedPrompt.value,
          default: refreshed.default,
          is_deleted: refreshed.is_deleted
        };
      }
    }
  }

  loading.value = false;
}

async function loadVersions(promptName: string) {
  const data = await getFromAPI<Prompt[]>(`${API}/name/${encodeURIComponent(promptName)}/versions`);

  if (data) {
    versions.value = data;
    versionsForName.value = promptName;
  }
}

function selectPrompt(prompt: Prompt) {
  versions.value = [];
  versionsForName.value = null;
  selectedPrompt.value = prompt;
  isCreating.value = false;
  editName.value = prompt.name;
  editDescription.value = prompt.description;
  editText.value = prompt.text;
  selectedVersionId.value = prompt.id;
  loadVersions(prompt.name);
}

function switchVersion() {
  const version = versions.value.find((v) => v.id === selectedVersionId.value);

  if (version) {
    selectedPrompt.value = version;
    editName.value = version.name;
    editDescription.value = version.description;
    editText.value = version.text;
  }
}

function startCreate() {
  isCreating.value = true;
  selectedPrompt.value = null;
  selectedVersionId.value = null;
  versions.value = [];
  versionsForName.value = null;
  editName.value = '';
  editDescription.value = '';
  editText.value = '';
}

function clonePrompt(prompt: Prompt) {
  isCreating.value = true;
  selectedPrompt.value = null;
  selectedVersionId.value = null;
  versions.value = [];
  versionsForName.value = null;
  editName.value = prompt.name + ' (copy)';
  editDescription.value = prompt.description;
  editText.value = prompt.text;
}

async function savePrompt() {
  saving.value = true;

  if (!editName.value.trim()) {
    toastApi.warning('Name is required.');
    saving.value = false;
    return;
  }

  if (!editText.value.trim()) {
    toastApi.warning('Prompt text is required.');
    saving.value = false;
    return;
  }

  if (isCreating.value) {
    const result = await getDataWithCSRF<Prompt>(
      `${API}/`,
      'POST',
      {
        name: editName.value.trim(),
        description: editDescription.value,
        text: editText.value
      },
      { 'Content-Type': 'application/json' }
    );

    if (result) {
      toastApi.success('Prompt created successfully.');
      isCreating.value = false;
      await loadPrompts();
      selectPrompt(result);
    } else {
      toastApi.error('Failed to create prompt. A prompt with this name may already exist.');
    }
  } else if (selectedPrompt.value) {
    const result = await getDataWithCSRF<Prompt>(
      `${API}/${encodeURIComponent(selectedPrompt.value.name)}`,
      'PUT',
      {
        name: editName.value.trim(),
        description: editDescription.value,
        text: editText.value
      },
      { 'Content-Type': 'application/json' }
    );

    if (result) {
      toastApi.success(`Prompt saved as version ${result.version}.`);
      await loadPrompts();
      selectPrompt(result);
    } else {
      toastApi.error('Failed to update prompt.');
    }
  }

  saving.value = false;
}

function confirmDelete(prompt: Prompt) {
  promptToDelete.value = prompt;
  showDeleteModal.value = true;
}

async function handleDeleteModalClose(proceed: boolean) {
  showDeleteModal.value = false;

  if (proceed && promptToDelete.value) {
    await deletePrompt(promptToDelete.value);
  }

  promptToDelete.value = null;
}

async function deletePrompt(prompt: Prompt) {
  const result = await getDataWithCSRF<{ status: string }>(
    `${API}/${encodeURIComponent(prompt.name)}`,
    'DELETE'
  );

  if (result) {
    toastApi.success('Prompt deleted.');
    selectedPrompt.value = null;
    isCreating.value = false;
    versions.value = [];
    versionsForName.value = null;
    await loadPrompts();
  } else {
    toastApi.error('Failed to delete prompt.');
  }
}

async function restorePrompt(prompt: Prompt) {
  const result = await getDataWithCSRF<{ status: string }>(
    `${API}/${encodeURIComponent(prompt.name)}/restore`,
    'PATCH'
  );

  if (result) {
    toastApi.success('Prompt restored.');
    await loadPrompts();
  } else {
    toastApi.error('Failed to restore prompt.');
  }
}

async function setDefault(prompt: Prompt) {
  if (prompt.default) return;

  const result = await getDataWithCSRF<Prompt>(
    `${API}/${encodeURIComponent(prompt.name)}/toggle-default`,
    'PATCH'
  );

  if (result) {
    await loadPrompts();
  } else {
    toastApi.error('Failed to set default prompt.');
  }
}

function formatDate(date: string | null): string {
  if (!date) return '-';
  return new Date(date).toLocaleString();
}

onMounted(() => {
  loadPrompts();
});
</script>

<template>
  <div class="prompt-editor">
    <div class="row g-0" style="min-height: 50vh">
      <!-- Left panel: Prompt list -->
      <div class="col-md-4 col-lg-3 border-end">
        <div class="p-3">
          <div class="d-flex justify-content-between align-items-center mb-3">
            <h5 class="mb-0">Prompts</h5>

            <button class="btn btn-sm btn-primary" @click="startCreate">
              <i class="bi bi-plus-lg"></i> New
            </button>
          </div>

          <!-- Show deleted toggle -->
          <div class="form-check mb-3">
            <input
              id="showDeleted"
              v-model="showDeleted"
              class="form-check-input"
              type="checkbox"
              @change="loadPrompts"
            />
            <label class="form-check-label" for="showDeleted"> Show deleted </label>
          </div>

          <div v-if="loading" class="text-center py-3">
            <div class="spinner-border spinner-border-sm" role="status">
              <span class="visually-hidden">Loading...</span>
            </div>
          </div>

          <div v-else-if="prompts.length === 0" class="text-muted small py-2">
            No prompts found.
          </div>

          <template v-else>
            <!-- My prompts -->
            <div v-if="myPrompts.length > 0" class="mb-3">
              <div class="text-muted small fw-semibold text-uppercase mb-1">My Prompts</div>

              <div class="list-group">
                <button
                  v-for="prompt in myPrompts"
                  :key="prompt.id"
                  class="list-group-item list-group-item-action d-flex align-items-center py-2"
                  :class="{
                    active: selectedPrompt?.name === prompt.name && !isCreating,
                    'list-group-item-danger': prompt.is_deleted
                  }"
                  @click="selectPrompt(prompt)"
                >
                  <span class="text-truncate me-auto fw-semibold">{{ prompt.name }}</span>
                  <span class="badge bg-secondary ms-2">v{{ prompt.version }}</span>
                  <span v-if="prompt.default" class="badge bg-success ms-1">Default</span>
                  <span v-if="prompt.is_deleted" class="badge bg-danger ms-1">Deleted</span>
                </button>
              </div>
            </div>

            <!-- Other prompts -->
            <div v-if="otherPrompts.length > 0">
              <div class="text-muted small fw-semibold text-uppercase mb-1">Other Prompts</div>

              <div class="list-group">
                <button
                  v-for="prompt in otherPrompts"
                  :key="prompt.id"
                  class="list-group-item list-group-item-action d-flex align-items-center py-2"
                  :class="{
                    active: selectedPrompt?.name === prompt.name && !isCreating,
                    'list-group-item-danger': prompt.is_deleted
                  }"
                  @click="selectPrompt(prompt)"
                >
                  <span class="text-truncate me-auto fw-semibold">{{ prompt.name }}</span>
                  <span class="badge bg-secondary ms-2">v{{ prompt.version }}</span>
                  <span v-if="prompt.default" class="badge bg-success ms-1">Default</span>
                  <span v-if="prompt.is_deleted" class="badge bg-danger ms-1">Deleted</span>
                </button>
              </div>
            </div>
          </template>
        </div>
      </div>

      <!-- Right panel: Editor -->
      <div class="col-md-8 col-lg-9 d-flex flex-column">
        <div class="p-3 d-flex flex-column flex-grow-1">
          <!-- No selection state -->
          <div
            v-if="!selectedPrompt && !isCreating"
            class="d-flex align-items-center justify-content-center flex-grow-1"
          >
            <div class="text-center text-muted">
              <i class="bi bi-pencil-square" style="font-size: 3rem"></i>
              <p class="mt-2">Select a prompt from the list or create a new one.</p>
            </div>
          </div>

          <!-- Editor form -->
          <div v-else class="d-flex flex-column flex-grow-1">
            <div class="d-flex justify-content-between align-items-center mb-3">
              <h5 class="mb-0">
                {{ isCreating ? 'New Prompt' : `Edit: ${selectedPrompt?.name}` }}
              </h5>

              <div v-if="!isCreating && selectedPrompt" class="d-flex gap-2 align-items-center">
                <!-- Version selector -->
                <div class="d-flex align-items-center gap-1">
                  <label class="form-label mb-0 small">Version:</label>
                  <select
                    v-model="selectedVersionId"
                    class="form-select form-select-sm"
                    style="width: auto"
                    :disabled="versions.length <= 1"
                    @change="switchVersion"
                  >
                    <option v-if="versions.length === 0" :value="selectedPrompt.id">
                      v{{ selectedPrompt.version }} (latest)
                    </option>
                    <option v-for="v in versions" :key="v.id" :value="v.id">
                      v{{ v.version }}{{ v.id === versions[0]?.id ? ' (latest)' : '' }}
                    </option>
                  </select>
                </div>

                <!-- Clone as new prompt -->
                <button
                  class="btn btn-sm btn-outline-secondary"
                  title="Clone as new prompt"
                  @click="clonePrompt(selectedPrompt)"
                >
                  <i class="bi bi-files"></i>
                </button>

                <!-- Set as default (superadmin only) -->
                <button
                  v-if="isSuperAdmin"
                  class="btn btn-sm"
                  :class="selectedPrompt.default ? 'btn-warning' : 'btn-outline-warning'"
                  :title="selectedPrompt.default ? 'This is the default prompt' : 'Set as default'"
                  :disabled="selectedPrompt.default"
                  @click="setDefault(selectedPrompt)"
                >
                  <i class="bi" :class="selectedPrompt.default ? 'bi-star-fill' : 'bi-star'"></i>
                </button>

                <!-- Delete: always shown, disabled when not allowed -->
                <button
                  v-if="!selectedPrompt.is_deleted"
                  class="btn btn-sm btn-outline-danger"
                  :title="
                    !isOwner
                      ? 'You can only delete your own prompts'
                      : selectedPrompt.default
                        ? 'Cannot delete the default prompt'
                        : 'Delete prompt'
                  "
                  :disabled="!canDelete"
                  @click="confirmDelete(selectedPrompt)"
                >
                  <i class="bi bi-trash"></i>
                </button>

                <!-- Restore (superadmin only) -->
                <button
                  v-if="selectedPrompt.is_deleted && isOwner"
                  class="btn btn-sm btn-outline-success"
                  title="Restore prompt"
                  @click="restorePrompt(selectedPrompt)"
                >
                  <i class="bi bi-arrow-counterclockwise"></i> Restore
                </button>
              </div>
            </div>

            <!-- Metadata -->
            <div v-if="selectedPrompt && !isCreating" class="mb-3 small text-muted">
              <span v-if="selectedPrompt.author_full_name">
                Author: <strong>{{ selectedPrompt.author_full_name }}</strong>
              </span>

              <span v-if="selectedPrompt.created_at">
                &middot; Created: {{ formatDate(selectedPrompt.created_at) }}
              </span>

              <span v-if="selectedPrompt.updated_by_full_name">
                &middot; Updated by: <strong>{{ selectedPrompt.updated_by_full_name }}</strong>
              </span>

              <span v-if="selectedPrompt.updated_at">
                at {{ formatDate(selectedPrompt.updated_at) }}
              </span>
            </div>

            <!-- Not-owner notice -->
            <div v-if="!isOwner && !isCreating" class="alert alert-info small">
              <i class="bi bi-info-circle"></i>
              This prompt belongs to another user. You cannot edit it.
            </div>

            <!-- Not latest version warning -->
            <div
              v-if="isOwner && !isLatestVersion && !isCreating"
              class="alert alert-warning small"
            >
              <i class="bi bi-exclamation-triangle"></i>
              You are viewing an older version (v{{ selectedPrompt?.version }}). Switch to the
              latest version to make edits.
            </div>

            <!-- Form -->
            <div class="mb-3">
              <label class="form-label">Name</label>

              <input
                v-model="editName"
                type="text"
                class="form-control"
                :disabled="!canEdit"
                placeholder="Prompt name"
              />
            </div>

            <div class="mb-3">
              <label class="form-label">Description</label>

              <textarea
                v-model="editDescription"
                class="form-control"
                :disabled="!canEdit"
                rows="2"
                placeholder="Optional description"
              ></textarea>
            </div>

            <div class="mb-3 prompt-text-wrapper">
              <label class="form-label">Prompt Text</label>

              <Editor v-model="editText" filename="prompt.md" :disabled="!canEdit" :wrap="true" />
            </div>

            <div class="d-flex gap-2">
              <button class="btn btn-primary" :disabled="!canEdit || saving" @click="savePrompt">
                <span v-if="saving" class="spinner-border spinner-border-sm me-1"></span>
                {{ isCreating ? 'Create Prompt' : 'Save as New Version' }}
              </button>

              <button
                v-if="isCreating"
                class="btn btn-secondary"
                @click="
                  isCreating = false;
                  selectedPrompt = null;
                "
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Delete confirmation modal -->
    <VueModal
      :open="showDeleteModal"
      title="Delete Prompt"
      cancel-button-label="Cancel"
      proceed-button-label="Delete"
      :on-closed="handleDeleteModalClose"
    >
      <p>
        Are you sure you want to delete <strong>{{ promptToDelete?.name }}</strong
        >?
      </p>
      <p class="text-muted small">The prompt will be soft-deleted and can be restored later.</p>
    </VueModal>
  </div>
</template>

<style scoped>
.prompt-editor {
  border: 1px solid var(--bs-border-color);
  border-radius: 0.375rem;
  background: var(--bs-body-bg);
}

.list-group-item.active {
  z-index: 1;
}

/* 20 lines at ~18px line-height = 360px */
.prompt-text-wrapper :deep(.CodeMirror) {
  height: 360px;
}
</style>
