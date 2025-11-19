<script setup lang="ts">
import { ref, computed } from 'vue';
import AddStudentsToClass from './AddStudentsToClass.vue';
import Markdown from '../components/Markdown.vue';
import AssignmentPoints from './AssignmentPoints.vue';
import { type Class, type StudentIdentity } from './frontendtypes';

const { clazz } = defineProps<{
  clazz: Class;
}>();

const showStudentsList = ref(clazz.students.length < 50);
const showAddStudents = ref(clazz.students.length === 0);
const showFullTaskNames = ref(false);
const showSummary = ref(false);
const user = ref({ is_staff: true }); // FIXME: Get user from /api/info
const emit = defineEmits<{ (e: 'update'): void }>();

async function handleUpdate() {
  showAddStudents.value = false;
  emit('update');
}

const totalMaxPoints = computed(() =>
  clazz.assignments.reduce((sum, task) => sum + task.max_points, 0)
);

const studentPoints = (student: StudentIdentity) => {
  return clazz.assignments
    .map((i) => i.students[student.username])
    .filter(
      (result) => result && result.submits !== 0 && !isNaN(parseFloat(result.assigned_points))
    )
    .map((result) => parseFloat(result.assigned_points))
    .reduce((acc, val) => acc + val, 0)
    .toFixed(2);
};

/*
export default {
  name: 'ClassDetail',
  components: {AssignmentPoints}, //{ AddStudentsToClass, Markdown },
  props: {
    clazz: {
      type: Object as PropType<typeof Class>,
      required: true
    }
  },
  setup(props) {
    const showStudentsList = ref(props.clazz.students.length < 50);
    const showAddStudents = ref(props.clazz.students.length === 0);
    const showFullTaskNames = ref(false);
    const showSummary = ref(false);
    const user = ref({ is_staff: true });

    const totalMaxPoints = computed(() =>
      props.clazz.assignments.reduce((sum, task) => sum + task.max_points, 0)
    );

    const studentPoints = (student: typeof Student) => {
      return props.clazz.assignments
        .map((i) => i.students[student.username])
        .filter(
          (result) => result && result.submits !== 0 && !isNaN(parseFloat(result.assigned_points))
        )
        .map((result) => parseFloat(result.assigned_points))
        .reduce((acc, val) => acc + val, 0)
        .toFixed(2);
    };

    return {
      showStudentsList,
      showAddStudents,
      showFullTaskNames,
      showSummary,
      user,
      studentPoints,
      totalMaxPoints
    };
  }
};
*/
</script>

<template>
  <div class="card mb-2" style="position: initial">
    <div class="card-header p-0">
      <div class="float-end p-2" style="display: flex; align-items: center">
        <a :href="`/task/add/${clazz.subject_abbr}`" title="Assign new task">
          <span class="iconify" data-icon="bx:bx-calendar-plus"></span>
        </a>
        <button
          class="p-0 btn btn-link"
          title="Add user to class"
          @click="showAddStudents = !showAddStudents"
        >
          <span class="iconify" data-icon="ant-design:user-add-outlined"></span>
        </button>
        <a :href="`${clazz.csv_link}`" title="Download CSV with results for all tasks">
          <span class="iconify" data-icon="la:file-csv-solid"></span>
        </a>
        <button
          class="p-0 btn btn-link"
          title="Show full task names"
          @click="showFullTaskNames = !showFullTaskNames"
        >
          <span v-if="showFullTaskNames"><span class="iconify" data-icon="la:eye"></span></span>
          <span v-else><span class="iconify" data-icon="la:eye-slash"></span></span>
        </button>
        <a
          v-if="user.is_staff"
          :href="`/admin/common/class/${clazz.id}/change`"
          title="Edit class in Admin"
        >
          <span class="iconify" data-icon="clarity:edit-solid"></span>
        </a>
      </div>
      <button class="btn" @click="showStudentsList = !showStudentsList">
        {{ clazz.subject_abbr }} {{ clazz.timeslot }} {{ clazz.code }} {{ clazz.teacher_username }}
        <span class="text-muted d-none d-md-inline">({{ clazz.students.length }} students)</span>
      </button>
    </div>
    <div v-if="showStudentsList || showAddStudents">
      <div class="card-body p-1">
        <AddStudentsToClass v-if="showAddStudents" :class-id="clazz.id" @update="handleUpdate" />
        <div v-if="showStudentsList">
          <button v-if="clazz.summary" class="p-0 btn btn-link" @click="showSummary = !showSummary">
            {{ showSummary ? 'Hide' : 'Show' }} class summary
          </button>
          <Markdown v-if="showSummary" :content="clazz.summary" />
          <div style="overflow: auto">
            <table class="table table-sm table-hover table-striped">
              <thead>
                <tr>
                  <th>Login</th>
                  <th>Student</th>
                  <th v-for="(assignment, index) in clazz.assignments" :key="index">
                    <a
                      :href="`${assignment.task_link}`"
                      :class="{
                        'text-muted': assignment.assigned > new Date(),
                        'text-success': assignment.deadline > new Date()
                      }"
                    >
                      {{ showFullTaskNames ? assignment.short_name : `#${index + 1}` }}
                      <span v-if="assignment.max_points > 0"> ({{ assignment.max_points }}b)</span>
                    </a>
                  </th>
                  <th>Total ({{ totalMaxPoints }} pts)</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="student in clazz.students" :key="student.username">
                  <td>
                    <a :href="`/student/${student.username}`" target="_blank">{{
                      student.username
                    }}</a>
                  </td>
                  <td>{{ student.last_name }} {{ student.first_name }}</td>
                  <td v-for="(assignment, i) in clazz.assignments" :key="i">
                    <AssignmentPoints
                      :submit_id="assignment.students[student.username]?.accepted_submit_id"
                      :submits="assignment.students[student.username]?.submits"
                      :link="assignment.students[student.username]?.link"
                      :login="student.username"
                      :task="assignment.name"
                      :color="assignment.students[student.username]?.color"
                      :assigned_points="assignment.students[student.username]?.assigned_points"
                    />
                  </td>
                  <td>{{ studentPoints(student) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p v-if="clazz.students.length === 0" class="text-center">No student added yet.</p>
        </div>
      </div>
    </div>
  </div>
</template>

<style>
td,
th {
  white-space: nowrap;
  width: 1%;
}
tr th:last-of-type,
td:last-of-type {
  width: 100%;
  text-align: right;
}
tr td:not(:nth-of-type(1)):not(:nth-of-type(2)):not(:last-child) {
  text-align: center;
}

.card-body {
  overflow-x: auto;
}

.spin {
  animation-name: spin;
  animation-duration: 2000ms;
  animation-iteration-count: infinite;
  animation-timing-function: linear;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.more-content {
  display: none;
  text-align: left;
}

.more-hover:hover .more-content {
  position: absolute;
  display: block;
  font-weight: normal;
}
</style>
