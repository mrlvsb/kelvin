<script setup lang="ts">
/**
 * Component shows full edit task page, used for editing existing pages and creating new ones
 */

import { ref, watch, onMounted, toRaw } from 'vue';

import { semester as semesterSvelte, user as userSvelte } from '../../global.js';
import { fs, openedFiles as openedFilesSvelte } from '../../fs.js';
import VueModal from '../../components/VueModal.vue';
import { task_types } from '../../taskTypes';
import Manager from './FileManager.vue';
import SyncLoader from '../../components/SyncLoader.vue';
import TimeRange from './TimeRange.vue';
import { useReadableSvelteStore } from '../../utilities/useSvelteStoreInVue';
import { User, Semester, FileEntry } from '../../utilities/SvelteStoreTypes';
import AutoCompleteTaskPath from './AutoCompleteTaskPath.vue';
import { fetch } from '../../api';

const semester = useReadableSvelteStore<Semester>(semesterSvelte);
const user = useReadableSvelteStore<User>(userSvelte);
const openedFiles = useReadableSvelteStore<Record<string, FileEntry>>(openedFilesSvelte);

interface EditParams {
  id: number;
  subject?: never;
}

interface AddParams {
  subject: string;
  id?: never;
}

//parameters are based on page role - create new / edit
type RouteParams = EditParams | AddParams;

const props = defineProps<{ params: RouteParams }>();

interface Class {
  assigned: Date;
  assignment_id: number;
  code: string;
  deadline: Date;
  hard_deadline: boolean;
  id: number;
  max_points: number;
  teacher: string;
  timeslot: string;
  week_offset: number;
}

interface Task {
  id?: number;
  subject_abbr: string;
  path: string;
  classes: Class[];
  files?: Record<string, FileEntry>;
  files_uri?: string;
  errors?: Array<string>;
  task_link?: string;
  plagcheck_link?: string;
  plagiarism_key?: string;
  type: string;
  can_delete?: boolean;
}

let task = ref<Task | null>(null);
let syncPathWithTitle = ref(false);
let taskLink = ref('');
let deleteModal = ref(false);

const syncing = ref<boolean>(false);
let errors = ref<Array<string>>([]);
let savedPath = ref('');

let showAllClasses = ref<boolean>(false);

let shownClasses = ref<Array<Class>>([]);

function isClassVisible(cls: Class): boolean {
  return cls.teacher === user.value.username || cls.assignment_id > 0 || showAllClasses.value;
}

watch(task, (newTask) => {
  if (newTask) {
    shownClasses.value = newTask.classes.filter(isClassVisible).sort((a, b) => {
      function key(cls: Class): boolean {
        return cls.teacher === user.value.username || cls.assignment_id !== undefined;
      }

      return Number(key(b)) - Number(key(a));
    });
  }
});

watch(task, (newTask) => {
  if (newTask) {
    const clazz = newTask.classes.find((clazz) => clazz.assignment_id >= 1);
    if (clazz) {
      taskLink.value = `/task/${clazz.assignment_id}/${user.value.username}/`;
    } else {
      taskLink.value = newTask.task_link;
    }
  }
});

/**
 * Redirect user to given URL
 */
function redirectToUrl(url: string): void {
  window.location.href = url;
}

/**
 * Used when we want to create new task
 */
async function prepareCreatingTask(): Promise<void> {
  const res = await fetch('/api/subject/' + props.params.subject);
  const json = await res.json();

  const current_path = [props.params.subject, semester.value['abbr'], user.value.username].join(
    '/'
  );

  task.value = {
    classes: json['classes'],
    path: current_path,
    subject_abbr: props.params.subject,
    type: 'homework'
  };

  fs.createFile('readme.md', '# Task Title');
  await fs.open('readme.md');
}

/**
 * Load existing task
 * @param id task id
 * @param redirectTo we can load task from EditTask page, then we need to reload to reflect id in URL
 */
async function loadTask(id: number, redirectTo: boolean = true): Promise<void> {
  const req = await fetch('/api/tasks/' + id);
  task.value = await req.json();
  savedPath.value = task.value['path'];
  fs.setRoot(task.value.files, task.value.files_uri);
  await fs.open('readme.md');

  if (redirectTo) redirectToUrl('/task/edit/' + task.value.id);
}

onMounted(async () => {
  if (props.params.id) {
    await loadTask(props.params.id, false);
  } else {
    await prepareCreatingTask();
    syncPathWithTitle.value = true;
  }
});

function synchronizePathWithReadMeTitle(): void {
  const readme = openedFiles.value['/readme.md'];

  if (readme && task.value) {
    let parts = [props.params.subject, semester.value['abbr'], user.value.username];

    let classes = task.value['classes'].filter((c) => c.assigned);
    if (classes.length == 1) {
      parts.push(classes[0].timeslot);
    }

    const title = readme.content
      .split('\n')[0]
      .toLowerCase()
      .replace(/^\s*#\s*|\s*$/g, '')
      .replace(/( |\/|\\)/g, '_')
      .split('')
      .map((c) => {
        const map = {
          ě: 'e',
          š: 's',
          č: 'c',
          ř: 'r',
          ž: 'z',
          ý: 'y',
          á: 'a',
          í: 'i',
          é: 'e',
          ú: 'u',
          ů: 'u',
          ǒ: 'o',
          ó: 'p'
        };
        return map[c] ? map[c] : c;
      })
      .join('');

    if (title) {
      parts.push(title);
    }

    task.value.path = parts.join('/');
  }
}

watch(syncPathWithTitle, (newSyncPathWithTitle) => {
  if (newSyncPathWithTitle) {
    synchronizePathWithReadMeTitle();
  }
});

watch(openedFiles, () => {
  if (syncPathWithTitle.value) {
    synchronizePathWithReadMeTitle();
  }
});

async function save(): Promise<void> {
  syncing.value = true;

  console.log(task.value);

  const res = await fetch('/api/tasks/' + (task.value.id ? task.value.id : ''), {
    method: 'POST',
    body: JSON.stringify(toRaw(task.value))
  });

  const json = await res.json();
  errors.value = json['errors'];
  if (errors.value.length == 0) {
    task.value['classes'] = json['classes'];
    savedPath.value = json['path'];
    task.value['can_delete'] = json['can_delete'];
    fs.setEndpointUrl(json.files_uri);

    await openedFilesSvelte.save();

    if (!task.value.id) {
      redirectToUrl('/task/edit/' + json.id);
    }
  }
  syncing.value = false;
}

onMounted(() => {
  window.addEventListener('keydown', (evt) => {
    if (evt.ctrlKey && evt.key == 's') {
      save();
      evt.preventDefault();
    }
  });
});

function setAssignedDateToVisible(assigned: Date): void {
  task.value.classes = task.value.classes.map((cl) => {
    if (isClassVisible(cl)) cl.assigned = assigned;
    return cl;
  });
}

function setDeadlineToAssigned(deadline: Date): void {
  task.value.classes = task.value.classes.map((cl) => {
    if (cl.assigned) cl.deadline = deadline;
    return cl;
  });
}

function assignPointsToAll(max_pts: number): void {
  task.value.classes = task.value.classes.map((cl) => {
    if (cl.assigned) {
      cl.max_points = max_pts;
    }
    return cl;
  });
}

function assignHardDeadlineToAll(hard_deadline: boolean): void {
  task.value.classes = task.value.classes.map((cl) => {
    if (cl.assigned) cl.hard_deadline = hard_deadline;
    return cl;
  });
}

function assignSameToAll(templateClass: Class): void {
  task.value.classes = task.value.classes.map((cl) => {
    if (isClassVisible(cl)) {
      cl.max_points = templateClass.max_points;
      cl.assigned = templateClass.assigned;
      cl.deadline = templateClass.deadline;
      cl.hard_deadline = templateClass.hard_deadline;
    }
    return cl;
  });
}

function setRelativeDeadlineToAssigned(assigned: Date, deadline: Date): void {
  const diff = Number(new Date(deadline)) - Number(new Date(assigned));
  task.value.classes = task.value.classes.map((cl) => {
    if (cl.assigned) {
      cl.deadline = new Date(new Date(cl.assigned).getTime() + diff);
    }
    return cl;
  });
}

async function duplicateTask(): Promise<void> {
  let res = await fetch(`/api/tasks/${task.value.id}/duplicate`, {
    method: 'POST'
  });

  let json = await res.json();
  redirectToUrl('/task/edit/' + json.id);
  await loadTask(json.id);
}

async function deleteTask(proceed: boolean): Promise<void> {
  deleteModal.value = false;
  if (proceed) {
    const res = await fetch(`/api/tasks/${task.value.id}`, {
      method: 'DELETE'
    });

    const json = await res.json();

    if (json['errors']) {
      errors.value = json['errors'];
    } else {
      errors.value = [];
      redirectToUrl('/task/add/' + task.value.subject_abbr);
      fs.setRoot([], undefined);
      await prepareCreatingTask();
    }
  }
}
</script>

<template>
  <div v-if="task != null" class="container-fluid">
    <div style="position: relative">
      <div v-if="syncing" style="position: absolute; top: 50%; left: 50%; z-index: 1">
        <SyncLoader />
      </div>
      <div>
        <div v-if="errors && errors.length" class="alert alert-danger">
          <ul v-for="error in errors" :key="error" class="m-0">
            <li style="white-space: pre-line">{{ error }}</li>
          </ul>
        </div>

        <div class="input-group mb-1">
          <AutoCompleteTaskPath
            v-model="task.path"
            :subject="task.subject_abbr"
            :on-change="loadTask"
            @click="syncPathWithTitle = false"
          />
          <template v-if="taskLink">
            <a
              class="btn btn-outline-info d-flex align-items-center"
              title="Plagiarism check"
              :href="task.plagcheck_link"
              target="_blank"
            >
              <span class="iconify" data-icon="bx:bx-check-double"></span>
            </a>
            <a
              class="btn btn-outline-info d-flex align-items-center"
              title="Show all source codes"
              :href="'/task/show/' + task.id"
              target="_blank"
            >
              <span class="iconify" data-icon="bx-bx-code-alt"></span>
            </a>
            <a
              class="btn btn-outline-info d-flex align-items-center"
              title="Show task stats"
              :href="'/statistics/task/' + task.id"
              target="_blank"
            >
              <span class="iconify" data-icon="bx-bx-bar-chart-alt-2"></span>
            </a>
            <button
              class="btn btn-outline-info d-flex align-items-center"
              title="Duplicate this task"
              @click="duplicateTask"
            >
              <span class="iconify" data-icon="ant-design:copy-outlined"></span>
            </button>
            <button class="btn btn-outline-info d-flex align-items-center" title="Open task">
              <a :href="taskLink" target="_blank"
                ><span class="iconify" data-icon="bx:bx-link-external"></span
              ></a>
            </button>
            <button
              class="btn btn-outline-danger d-flex align-items-center"
              :disabled="!task['can_delete']"
              @click="() => (deleteModal = true)"
            >
              <span class="iconify" data-icon="akar-icons:trash-can"></span>
            </button>
            <VueModal
              :open="deleteModal"
              :on-closed="deleteTask"
              proceed-button-label="Delete"
              title="Delete task"
            >
              Do you really want to delete the task with path <strong>{{ savedPath }}</strong
              >?
              <strong>Readme.md</strong>
              and all files will be <strong>DELETED!</strong>
            </VueModal>
          </template>
        </div>

        <div class="mb-2">
          <table class="table table-hover table-striped mb-0">
            <tbody>
              <tr
                v-for="(clazz, idx) in shownClasses"
                :key="clazz.id"
                :class="{ 'table-success': clazz.assigned }"
              >
                <td>
                  {{ clazz.timeslot }}
                  <span class="opacity-50">({{ clazz.code }})</span>
                </td>
                <td>{{ clazz.teacher }}</td>
                <td>
                  <div class="row">
                    <TimeRange
                      v-model:from-date="clazz.assigned"
                      v-model:to-date="clazz.deadline"
                      :on-to-relative-click="setRelativeDeadlineToAssigned"
                      :on-to-duplicate-click="setDeadlineToAssigned"
                      :on-from-duplicate-click="setAssignedDateToVisible"
                      :semester-begin-date="semester.begin"
                      :time-offset-in-week="clazz.week_offset"
                    />
                    <div
                      v-if="clazz.deadline"
                      class="col-2"
                      title="Forbids students to make submissions after the deadline has passed."
                    >
                      <div class="input-group input-group-sm">
                        <input
                          :id="'hardDeadline_' + idx"
                          v-model="clazz.hard_deadline"
                          class="form-check-input checkbox-md"
                          type="checkbox"
                        />
                        <label class="form-check-label check_box_label" :for="'hardDeadline_' + idx"
                          >Hard Deadline</label
                        >
                        <button
                          class="btn btn-sm btn-secondary"
                          title="Copy hard deadline setting to all classes"
                          @click.prevent="assignHardDeadlineToAll(clazz.hard_deadline)"
                        >
                          <span class="iconify" data-icon="mdi:content-duplicate"></span>
                        </button>
                      </div>
                    </div>
                    <div class="col-2">
                      <div class="input-group">
                        <input
                          v-model="clazz.max_points"
                          class="form-control form-control-sm"
                          type="number"
                          min="0"
                          step="1"
                          :disabled="!clazz.assigned"
                          placeholder="Max points"
                        />
                        <button
                          class="btn btn-sm btn-secondary"
                          :disabled="!clazz.assigned"
                          title="Set points to all assigned classes"
                          @click.prevent="assignPointsToAll(clazz.max_points)"
                        >
                          <span class="iconify" data-icon="mdi:content-duplicate"></span>
                        </button>
                      </div>
                    </div>
                  </div>
                </td>
                <td>
                  <button
                    class="btn btn-sm p-0"
                    title="Set same assigned date, deadline, deadline type and points to all visible classes"
                    @click="() => assignSameToAll(clazz)"
                  >
                    <span class="iconify" data-icon="mdi:content-duplicate"></span>
                  </button>
                  <button
                    class="btn-close"
                    :disabled="!(clazz.assigned || clazz.deadline)"
                    aria-label="Unassign class"
                    @click="
                      () => {
                        clazz.assigned = null;
                        clazz.deadline = null;
                        clazz.max_points = null;
                      }
                    "
                  ></button>
                </td>
              </tr>
            </tbody>
          </table>
          <button
            v-if="task && (task.classes.length > shownClasses.length || showAllClasses)"
            class="btn p-0"
            @click.prevent="showAllClasses = !showAllClasses"
          >
            <span class="iconify" data-icon="la:eye"></span> Show all classes
          </button>
        </div>

        <div class="row">
          <div class="col">
            <div
              class="input-group mb-3"
              title="All tasks with the same plagiarism key will be checked together"
            >
              <span class="input-group-text">Plagiarism key:</span>
              <input
                v-model="task.plagiarism_key"
                class="form-control"
                type="text"
                maxlength="255"
              />
            </div>
          </div>
          <div class="col">
            <div class="input-group mb-3">
              <span class="input-group-text">Task type:</span>
              <select v-model="task.type" class="form-control form-control-sm">
                <option v-if="task.type === null" :value="null">None</option>

                <template v-for="type in task_types" :key="type.key">
                  <option v-if="type.key !== null" :value="type.key">
                    {{ type.value }}
                  </option>
                </template>
              </select>
            </div>
          </div>
        </div>

        <div class="mb-1">
          <Manager :taskid="task.id" />
        </div>

        <button class="btn btn-primary" @click.prevent="save">Save</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
td:not(:nth-of-type(3)) {
  vertical-align: middle;
  width: 1%;
  white-space: nowrap;
}

.btn > a,
.btn > a:visited,
.btn > a:hover,
.btn > a:active {
  color: inherit;
}

.check_box_label {
  background-color: var(--bs-body-bg);
  color: var(--bs-body-color);
  padding: 0.25rem 0.5rem;
}

.form-check-input.checkbox-md {
  height: 2rem;
  margin-top: 0;
  background-color: #0d6efd;
  width: 1.5rem;
}
</style>
