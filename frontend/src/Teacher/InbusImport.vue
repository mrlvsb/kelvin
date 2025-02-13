<script setup lang="ts">
/**
 * This component provides import of classes of students from Edison
 * into Kelvin using the INBUS API.
 *
 * It is only available to teachers, and it is accessible from the main page
 * next to class selection drop down menu.
 */
import { computed, ref } from 'vue';

import { csrfToken } from '../utilities/api';
import { ConcreteActivity, InbusSubjectVersion } from './inbusdto';

interface KelvinSubject {
  name: string;
  abbr: string;
}

interface Semester {
  pk: number;
  year: number;
  winter: boolean;
  inbus_semester_id: number;
}

interface ImportResult {
  login: string;
  firstname: string;
  lastname: string;
  created: boolean;
}

interface Result {
  users: ImportResult[];
  count: number;
  error?: string;
}

interface Teacher {
  username: string;
  full_name: string;
  last_name: string;
}

interface ImportRequest {
  semester_id: number;
  subject_abbr: string;
  activities: number[];
  activities_to_teacher: { [key: number]: string };
}

const busy = ref<boolean>(false);

const semesters = await loadSemesters();
// Semester ID
const semester = ref<number | null>(
  semesters.length > 0 ? semesters[semesters.length - 1].pk : null
);

const subjects_kelvin = await loadKelvinSubjects();

// Subject abbreviation
const subject_kelvin_selected = ref<string | null>(
  subjects_kelvin.length > 0 ? subjects_kelvin[0].abbr : null
);

const subjects_inbus_filtered = await loadInbusSubjects(subjects_kelvin);
const subject_inbus_schedule = ref<ConcreteActivity[] | null>(null);

const teachers = await loadTeachers();
const activities_to_teacher_selected = ref({});

const classes_to_import = ref([]);
const result = ref<Result | null>(null);

const canImport = computed(() => {
  return (
    classes_to_import.value.length && !busy.value && subject_kelvin_selected.value && semester.value
  );
});

function assembleRequest(url: string): Request {
  const headers: Headers = new Headers();

  headers.set('Content-Type', 'application/json');
  headers.set('Accept', 'application/json');

  const request: Request = new Request(url, {
    method: 'GET',
    headers: headers
  });

  return request;
}

function svcc2num(svcc: string): number {
  const [dept_code, version] = svcc.split('/');
  const [dept, code] = dept_code.split('-');

  const svcc_str = dept + code + version;
  const svcc_num = Number(svcc_str);

  return svcc_num;
}

function sortCollection<T>(collection: T[], key: string) {
  collection.sort((a, b) => {
    const name_a = a[key].toUpperCase();
    const name_b = b[key].toUpperCase();
    if (name_a < name_b) {
      return -1;
    }
    if (name_a > name_b) {
      return 1;
    }
    return 0;
  });
}

async function loadKelvinSubjects(): Promise<KelvinSubject[]> {
  const res = await fetch('/api/subjects/all', {});
  const subjects_kelvin_resp = await res.json();

  const subjects_kelvin: KelvinSubject[] = subjects_kelvin_resp.subjects;
  sortCollection(subjects_kelvin, 'name');

  return subjects_kelvin;
}

async function loadInbusSubjects(kelvin_subjects: KelvinSubject[]): Promise<InbusSubjectVersion[]> {
  const res = await fetch('/api/inbus/subject_versions', {});

  const subjects_inbus: InbusSubjectVersion[] = await res.json();
  const subject_kelvin_abbrs = kelvin_subjects.map((s) => s.abbr);

  const subjects_inbus_filtered = subjects_inbus.filter((subject_inbus) =>
    subject_kelvin_abbrs.includes(subject_inbus.subject.abbrev)
  );
  subjects_inbus_filtered.sort(
    (a, b) => svcc2num(a.subjectVersionCompleteCode) - svcc2num(b.subjectVersionCompleteCode)
  );

  return subjects_inbus_filtered;
}

function parseSemesters(semesters_data: Semester[]) {
  return semesters_data.map((sm) => ({
    pk: sm.pk,
    year: sm.year,
    winter: sm.winter,
    inbus_semester_id: sm.inbus_semester_id,
    display: String(sm.year) + (sm.winter ? 'W' : 'S')
  }));
}

async function loadSemesters() {
  const request = assembleRequest('/api/semesters');
  const res = await fetch(request, {});

  const semesters_data = await res.json();
  return parseSemesters(semesters_data['semesters']);
}

async function loadScheduleForSubjectVersionId(subject_index: number) {
  subject_inbus_schedule.value = null;
  activities_to_teacher_selected.value = {};

  const versionId = subjects_inbus_filtered[subject_index].subjectVersionId;
  const inbusSemesterId = semesters.find((item) => item.pk === semester.value).inbus_semester_id;
  const request = assembleRequest(
    `/api/inbus/schedule/subject/version/${versionId}/${inbusSemesterId}`
  );
  const res = await fetch(request, {});
  subject_inbus_schedule.value = await res.json();
}

async function loadTeachers(): Promise<Teacher[]> {
  const request = assembleRequest('/api/teachers/all');
  const res = await fetch(request, {});
  const teachers_data = await res.json();
  const teachers: Teacher[] = teachers_data['teachers'];

  sortCollection(teachers, 'last_name');

  return teachers;
}

function classesWithoutTeacher() {
  const classes_without_teacher: number[] = [];
  for (const clazz of subject_inbus_schedule.value) {
    if (!clazz.teacherFullNames) {
      classes_without_teacher.push(clazz.concreteActivityId);
    }
  }

  return classes_without_teacher;
}

function isRequestValid(req) {
  const classes_without_teacher = classesWithoutTeacher();

  for (const activity of req.activities) {
    if (classes_without_teacher.includes(activity)) {
      if (!req.activities_to_teacher.hasOwnProperty(activity)) {
        return false;
      }
    }
  }

  return true;
}

function getCorrespondingActivityRepr(activity_id: number) {
  for (const ca of subject_inbus_schedule.value) {
    if (ca.concreteActivityId === activity_id) {
      return `${ca.educationTypeAbbrev}/${ca.order}, ${ca.subjectVersionCompleteCode}`;
    }
  }
}

function classesWithoutSelectedTeacher(req: ImportRequest) {
  const classes_without_selected_teacher: string[] = [];
  const classes_without_teacher = classesWithoutTeacher();

  for (const activity_id of req.activities) {
    if (classes_without_teacher.includes(activity_id)) {
      if (!req.activities_to_teacher.hasOwnProperty(activity_id)) {
        classes_without_selected_teacher.push(getCorrespondingActivityRepr(activity_id));
      }
    }
  }

  return classes_without_selected_teacher;
}

async function importActivities() {
  busy.value = true;
  const req: ImportRequest = {
    semester_id: semester.value,
    subject_abbr: subject_kelvin_selected.value,
    activities: classes_to_import.value,
    activities_to_teacher: activities_to_teacher_selected.value
  };

  if (!isRequestValid(req)) {
    const classes_without_selected_teacher = classesWithoutSelectedTeacher(req);
    const err_msg =
      classes_without_selected_teacher.length > 1
        ? `Selected classes to import (${classes_without_selected_teacher.join(', ')}) don't have assigned teacher. Please, select ones.`
        : `Selected class to import (${classes_without_selected_teacher}) doesn't have assigned teacher. Please, select one.`;
    result.value = { users: [], count: 0, error: err_msg };
    busy.value = false;

    return;
  }

  const res = await fetch('/api/import/activities', {
    method: 'POST',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      'X-CSRFToken': csrfToken()
    },
    body: JSON.stringify(req)
  });

  result.value = await res.json();
  busy.value = false;
}

function onInbusSubjectSelected(event) {
  const value: string = event.target.value;
  if (value !== '') {
    loadScheduleForSubjectVersionId(Number.parseInt(value));
  } else {
    subject_inbus_schedule.value = null;
  }
}

function onTeacherSelected(event) {
  const value: string = event.target.value;
  const [activity_id, teacher_username] = value.split(',');
  console.log(value);

  activities_to_teacher_selected.value[parseInt(activity_id)] = teacher_username;
}
</script>

<template>
  <select v-model="semester">
    <option v-for="item in semesters" :key="item.pk" :value="item.pk">{{ item.display }}</option>
  </select>

  <select v-model="subject_kelvin_selected">
    <option v-for="item in subjects_kelvin" :key="item.abbr" :value="item.abbr">
      {{ item.abbr }} - {{ item.name }}
    </option>
  </select>

  <select @change="onInbusSubjectSelected">
    <option value="">Select Edison subject</option>
    <option v-for="(item, index) in subjects_inbus_filtered" :key="index" :value="index">
      {{ item.subjectVersionCompleteCode }} - {{ item.subject.abbrev }} - {{ item.subject.title }}
    </option>
  </select>

  <table v-if="subject_inbus_schedule" class="table table-hover table-stripped table-sm">
    <tbody>
      <tr v-for="ca in subject_inbus_schedule" :key="ca.concreteActivityId">
        <td>
          <label>
            <input
              v-model="classes_to_import"
              type="checkbox"
              :value="ca.concreteActivityId"
              name="classesToImport"
            />
            {{ ca.educationTypeAbbrev }}
          </label>
        </td>

        <td>{{ ca.educationTypeAbbrev }}/{{ ca.order }}, {{ ca.subjectVersionCompleteCode }}</td>

        <td>
          <span v-if="ca.teacherFullNames">{{ ca.teacherFullNames }}</span>
          <span v-else>
            <select @change="onTeacherSelected">
              <option value="">Select teacher</option>
              <option
                v-for="teacher in teachers"
                :key="teacher.username"
                :value="`${ca.concreteActivityId},${teacher.username}`"
              >
                {{ teacher.username }} - {{ teacher.full_name }}
              </option>
            </select>
          </span>
        </td>

        <td>
          {{ ca.weekDayAbbrev }}
        </td>

        <td>
          {{ ca.beginTime }}
        </td>

        <td>
          {{ ca.endTime }}
        </td>
      </tr>
    </tbody>
  </table>

  <button
    class="btn"
    :class="{ 'btn-success': canImport, 'btn-danger': !canImport }"
    :disabled="!canImport"
    @click="importActivities"
  >
    <span v-if="busy">Importing...</span>
    <span v-else>Import</span>
  </button>

  <div>
    <div v-if="result">
      <div v-if="result.error" class="alert alert-danger" role="alert">
        {{ result.error }}
      </div>
      <div v-else>
        <table class="table table-sm table-hover table-striped">
          <thead>
            <tr>
              <th>Login</th>
              <th>First name</th>
              <th>Last name</th>
              <th>User created</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in result.users" :key="item.login">
              <td>{{ item.login }}</td>
              <td>{{ item.firstname }}</td>
              <td>{{ item.lastname }}</td>
              <td>{{ item.created }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<style scoped></style>
