<script setup lang="ts">
import { ref, computed } from 'vue';
import { getDataWithCSRF, getFromAPI } from '../utilities/api';

type ClassName = string;

interface Teacher {
  [login: string]: ClassName[];
}

interface ClassesByTeacher {
  [abbrev: string]: Teacher;
}

interface Classes {
  [semester: string]: ClassesByTeacher[];
}

interface StudentSubmit {
  student: string; // login
  submits: number;
  submits_with_assigned_pts: number;
  first_submit_date: string;
  last_submit_date: string;
  points: number | null;
  max_points: number | null;
  assigned_points: number | null;
  accepted_submit_num: number;
  accepted_submit_id: number;
  link: string;
}

interface Assignment {
  task_id: number;
  task_link: string;
  assignment_id: number;
  name: string;
  short_name: string;
  plagcheck_link: string;
  sources_link: string;
  csv_link: string;
  assigned: string;
  deadline: string;
  max_points: number;
  students: StudentSubmit[];
}

interface Student {
  username: string;
  first_name: string;
  last_name: string;
}

interface Class {
  id: number;
  teacher_username: string;
  timeslot: string;
  code: string;
  subject_abbr: string;
  csv_link: string;
  assignments: Assignment[];
  summary: string;
  students: Student[];
}

interface Transfer {
  submit_id: number;
  before: string;
  after: string;
}

interface AssignmentRequest {
    src_assignment_id: number;
    dst_assignment_id: number;
}

interface TransferRequest {
  src_class: number;
  dst_class: number;
  student: string;
  assignments: AssignmentRequest[];
}

const semester = ref(null);
const subject = ref(null);
const teacher = ref(null);
const clazz = ref(null);
const student = ref(null);
const target_class = ref(null);
const assignments = ref<AssignmentRequest[]>([]);
const busy = ref(false);
const data = await loadClasses();
const classes = ref<Class[] | null>(null);
const result = ref<Transfer[] | null>(null);

const notAssignedCount = computed(
  () => assignments.value.filter((t) => !t.dst_assignment_id).length
);
const uniqueAssignments = computed(() => true);
const canTransfer = computed(
  () =>
    assignments.value.length &&
    notAssignedCount.value === 0 &&
    uniqueAssignments.value &&
    !busy.value
);

async function onSubjectChanged() {
  teacher.value = null;
  clazz.value = null;
  student.value = null;
  target_class.value = null;
  assignments.value = [];

  const res = await getFromAPI<{ classes: Class[] }>(
    `/api/classes?semester=${semester.value}&subject=${subject.value}`
  );
  if (res) {
    classes.value = res.classes;
  }
}

async function loadClasses() : Promise<Classes> {
  return await getFromAPI<Classes>('/api/classes/all');
}

function target_changed() {
  const target = classes.value.find((c) => c.code === target_class.value).assignments;
  let index = 0;
  assignments.value = classes.value
    .find((c) => c.code === clazz.value)
    .assignments.map((t) => ({
      src_assignment_id: t.assignment_id,
      dst_assignment_id: index < target.length ? target[index++].assignment_id : null
    }));
}

async function transfer() {
  busy.value = true;
  const req: TransferRequest = {
    student: student.value,
    src_class: classes.value.find((c) => c.code === clazz.value).id,
    dst_class: classes.value.find((c) => c.code === target_class.value).id,
    assignments: assignments.value
  };

  const res = await getDataWithCSRF<{
    transfers: Transfer[];
  }>('/api/transfer_students', 'POST', req);

  result.value = res.transfers;
  busy.value = false;
}
</script>

<template>
  <div v-if="data">
    <select v-model="semester">
      <option v-for="item in Object.keys(data.semesters)" :key="item" :value="item">
        {{ item }}
      </option>
    </select>

    <select v-if="semester" v-model="subject" @change="onSubjectChanged">
      <option v-for="item in Object.keys(data.semesters[semester])" :key="item" :value="item">
        {{ item }}
      </option>
    </select>

    <select v-if="subject" v-model="teacher">
      <option
        v-for="item in Object.keys(data.semesters[semester][subject])"
        :key="item"
        :value="item"
      >
        {{ item }}
      </option>
    </select>

    <select v-if="teacher && classes" v-model="clazz">
      <option
        v-for="item in classes.filter((c) => c.teacher_username === teacher)"
        :key="item.code"
        :value="item.code"
      >
        {{ item.timeslot }} {{ item.code }}
      </option>
    </select>

    <select v-if="clazz" v-model="student">
      <option
        v-for="item in classes.find((c) => c.code === clazz).students"
        :key="item.username"
        :value="item.username"
      >
        {{ item.username }} {{ item.first_name }} {{ item.last_name }}
      </option>
    </select>

    <select v-if="student" v-model="target_class" @change="target_changed">
      <option v-for="item in classes" :key="item.code" :value="item.code">
        {{ item.teacher_username }} {{ item.timeslot }} {{ item.code }}
      </option>
    </select>

    <table class="table table-hover table-stripped table-sm">
      <tbody>
        <tr v-for="assignment in assignments" :key="assignment.src_assignment_id">
          <td>{{ assignment.name }}</td>
          <td>{{ assignment.assigned_points }}</td>
          <td>
            <select v-if="target_class" v-model="assignment.dst_assignment_id">
              <option
                v-for="target in classes.find((c) => c.code === target_class).assignments"
                :key="target.assignment_id"
                :value="target.assignment_id"
              >
                {{ target.name }}
              </option>
            </select>
          </td>
        </tr>
      </tbody>
    </table>

    <table v-if="result" class="table table-sm table-hover table-striped">
      <tbody>
        <tr v-for="item in result" :key="item.submit_id">
          <td>{{ item.submit_id }}</td>
          <td>{{ item.before }}</td>
          <td>{{ item.after }}</td>
        </tr>
      </tbody>
    </table>

    <button
      class="btn"
      :class="canTransfer ? 'btn-success' : 'btn-danger'"
      :disabled="!canTransfer"
      @click="transfer"
    >
      {{ busy ? 'Transferring...' : 'Transfer' }}
      <span v-if="!canTransfer"
        >(
        <span v-if="assignments.length">
          <span v-if="notAssignedCount > 0">{{ notAssignedCount }} tasks need to be assigned</span>
          <span v-else>Tasks on the right side need to be unique.</span>
        </span>
        <span v-else>Missing target class</span>
        )</span
      >
    </button>
  </div>
</template>
