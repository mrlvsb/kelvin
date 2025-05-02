<script setup lang="ts">
/**
 * This component allows assigning a quiz to classes.
 * It is only available for teachers.
 */
import { computed, ref } from 'vue';
import VueDatePicker from '@vuepic/vue-datepicker';
import { toast, updateGlobalOptions } from 'vue3-toastify';
import '@vuepic/vue-datepicker/dist/main.css';
import 'vue3-toastify/dist/index.css';
import { getDataWithCSRF } from '../utilities/api';

const { assignments, quiz_id, teacher } = defineProps<{
  assignments: string;
  quiz_id: number;
  teacher: string;
}>();

const quizDeletable = defineModel<boolean>();

type AssignmentClass = {
  id: number;
  name: string;
  teacher: string;
  code: string;
  timeslot: string;
  duration: number | null;
  deadline: string | null;
  assigned: string | null;
  assigned_id: number | null;
  visible: boolean;
  publish_results: boolean | null;
  deletable: boolean;
};

type AssignmentClassProperty = 'assigned' | 'deadline' | 'duration';

/**
 * Check if the class is missing properties to assign a quiz.
 * @param clazz AssignmentClass to be checked
 */
const isMissingPropertyToAssign = (clazz: AssignmentClass) => {
  return !clazz.assigned || !clazz.deadline || !clazz.duration;
};

updateGlobalOptions({
  multiple: false,
  theme: 'auto',
  autoClose: 2000,
  transition: 'slide',
  dangerouslyHTMLString: true
});

const isCollapsed = ref<boolean>(true);
const selectedTeacher = ref<string>(teacher);
const assignmentsData = ref<AssignmentClass[]>(JSON.parse(assignments) satisfies AssignmentClass[]);
const teacherNames = ref<string[]>([
  ...new Set(assignmentsData.value.map((c) => c.teacher)),
  'All'
]);

/**
 * Send assignments to the server
 */
const saveAssignments = async () => {
  const data = await getDataWithCSRF<{
    message: string;
    quiz_deletable: boolean;
    assignments: AssignmentClass[];
  }>(`/api/quiz/${quiz_id}/assignments`, 'POST', { assignments: assignmentsData.value });

  if (data) {
    toast.success(data.message);
    quizDeletable.value = data.quiz_deletable;
    assignmentsData.value = data.assignments;
  } else {
    toast.error('Failed to save assignments');
  }
};

/**
 * Set the same values for all classes
 * @param target AssignmentClass to be copied from
 */
const setToAllClasses = async (target: AssignmentClass) => {
  const properties = ['assigned', 'deadline', 'duration', 'publish_results'];

  properties.forEach((property) => {
    assignmentsData.value
      .filter((c) => c.visible)
      .forEach((clazz) => {
        clazz[property] = target[property];
      });
  });
};

/**
 * Set the same value for all classes by property
 * @param target AssignmentClass to be copied from
 * @param property AssignmentClass property to be copied from the target
 */
const setToAllClassesByProperty = async (
  target: AssignmentClass,
  property: AssignmentClassProperty
) => {
  const properties = ['assigned', 'deadline', 'duration'];

  const propertyIndex = properties.indexOf(property);

  assignmentsData.value
    .filter((c) => c.visible)
    .forEach((clazz) => {
      let canAssign = true;

      for (let i = 0; i < propertyIndex; i++) {
        if (!clazz[properties[i]]) {
          canAssign = false;
          break;
        }
      }

      if (canAssign) {
        clazz[property as string] = target[property];
      }
    });
};

/**
 * Delete assignment values
 * @param clazz AssignmentClass that values have to be deleted
 */
const deleteAssignmentValues = async (clazz: AssignmentClass) => {
  clazz.assigned = null;
  clazz.deadline = null;
  clazz.duration = null;
  clazz.publish_results = null;
};

/**
 * Set publish results for all possible assignments
 */
const setPublishToAllClasses = async () => {
  assignmentsData.value
    .filter((c) => c.visible)
    .forEach((clazz) => {
      if (!isMissingPropertyToAssign(clazz)) {
        clazz.publish_results = true;
      }
    });
};

const visibleClasses = computed(() => {
  if (selectedTeacher.value === 'All') {
    return assignmentsData.value;
  } else {
    return assignmentsData.value.filter((clazz) => clazz.teacher === selectedTeacher.value);
  }
});
</script>

<template>
  <div class="col-12">
    <div class="card">
      <div class="card-header">
        <h5 class="card-title mb-0" style="cursor: pointer" @click="isCollapsed = !isCollapsed">
          Assign quiz <span class="iconify" data-icon="la:eye"></span>
        </h5>
      </div>
      <div :class="{ collapse: isCollapsed, show: !isCollapsed }">
        <div class="d-flex justify-content-end m-1">
          <button class="btn btn-secondary" @click="setPublishToAllClasses">
            Publish all results
          </button>
          <button class="btn btn-success ms-1" @click="saveAssignments">Save assignments</button>
        </div>
        <div class="d-flex m-1">
          <label for="teacher-select" class="form-label mt-2">Teacher</label>
          <select id="teacher-select" v-model="selectedTeacher" class="form-control mx-2">
            <option v-for="teacherName in teacherNames" :key="teacherName" :value="teacherName">
              {{ teacherName }}
            </option>
          </select>
        </div>
        <table id="assign" class="table m-0">
          <tbody>
            <tr
              v-for="clazz in visibleClasses"
              :key="clazz.id"
              class="col-12 p-2"
              :class="{ 'table-success': !isMissingPropertyToAssign(clazz) }"
              :style="{ display: clazz.visible ? 'table-row' : 'none' }"
            >
              <td>
                {{ clazz.timeslot }}
                <span class="opacity-50">({{ clazz.code }})</span>
              </td>
              <td>{{ clazz.teacher }}</td>
              <td>
                <div class="row col-12">
                  <div class="col-lg d-flex justify-content-start">
                    <VueDatePicker
                      v-model="clazz.assigned"
                      class="border-0"
                      placeholder="Active from"
                    />
                    <button
                      class="btn btn-sm btn-secondary"
                      title="Set active from to all assigned classes"
                      :disabled="!clazz.assigned"
                      @click="setToAllClassesByProperty(clazz, 'assigned')"
                    >
                      <span class="iconify" data-icon="mdi:content-duplicate"></span>
                    </button>
                  </div>
                  <div class="col-lg d-flex justify-content-start">
                    <VueDatePicker
                      v-model="clazz.deadline"
                      :disabled="!clazz.assigned"
                      placeholder="Deadline"
                    />
                    <button
                      class="btn btn-sm btn-secondary"
                      title="Set deadline to all assigned classes"
                      :disabled="!clazz.deadline"
                      @click="setToAllClassesByProperty(clazz, 'deadline')"
                    >
                      <span class="iconify" data-icon="mdi:content-duplicate"></span>
                    </button>
                  </div>
                  <div class="col-lg d-flex justify-content-start">
                    <input
                      v-model="clazz.duration"
                      placeholder="Duration (minutes)"
                      class="form-control"
                      type="number"
                      min="1"
                      step="1"
                      :disabled="!clazz.deadline || !clazz.assigned"
                    />
                    <button
                      class="btn btn-sm btn-secondary"
                      title="Set duration to all assigned classes"
                      :disabled="!clazz.duration"
                      @click="setToAllClassesByProperty(clazz, 'duration')"
                    >
                      <span class="iconify" data-icon="mdi:content-duplicate"></span>
                    </button>
                  </div>
                </div>
              </td>
              <td>
                <div class="form-check d-flex p-0">
                  <input
                    :id="'publish-results-input-' + clazz.id"
                    v-model="clazz.publish_results"
                    class="form-check-input"
                    type="checkbox"
                    :disabled="isMissingPropertyToAssign(clazz)"
                    :checked="clazz.publish_results"
                  />
                  <label :for="'publish-results-input-' + clazz.id" class="form-check-label"
                    >&nbsp;Publish results</label
                  >
                </div>
              </td>
              <td>
                <button
                  class="btn btn-secondary"
                  title="Set values to all assigned classes"
                  :disabled="isMissingPropertyToAssign(clazz)"
                  @click="setToAllClasses(clazz)"
                >
                  <span class="iconify" data-icon="mdi:content-duplicate"></span>
                </button>
              </td>
              <td>
                <button
                  class="btn-close"
                  aria-label="Unassign class"
                  :disabled="!clazz.deletable"
                  @click="deleteAssignmentValues(clazz)"
                ></button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<style scoped>
#assign:deep(td) {
  vertical-align: middle !important;
  padding: 2px 0 0 3px !important;
  margin: 0 !important;
}

#assign:deep(input) {
  font-family: -apple-system, blinkmacsystemfont, 'Segoe UI', roboto, oxygen, ubuntu, cantarell,
    'Open Sans', 'Helvetica Neue', sans-serif !important;
}

#assign:deep(input:disabled) {
  background-color: #f6f6f6 !important;
}

#assign:deep(input:disabled::-webkit-input-placeholder) {
  color: #6c757d !important;
}
</style>
