<script setup lang="ts">
/**
 * This component provides import of classes of students from Edison
 * into Kelvin using the INBUS API.
 *
 * It is only available to teachers, and it is accessible from the main page
 * next to class selection drop down menu.
 */
import { computed, ref } from 'vue';

import { csrfToken } from '../api.js';
import { ConcreteActivity, InbusSubjectVersion } from './inbusdto';

interface KelvinSubject {
  name: string;
  abbr: string;
}

interface Semester {
  pk: number;
  year: number;
  winter: boolean;
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

let busy = ref<boolean>(false);

const semesters = await loadSemesters();
// Semester ID
const semester = ref(semesters.length > 0 ? semesters[semesters.length - 1].pk : null);

const subjects_kelvin = await loadKelvinSubjects();

// Subject abbreviation
const subject_kelvin_selected = ref(
    subjects_kelvin.length > 0 ? subjects_kelvin[0].abbr : null
);

const subjects_inbus_filtered = await loadInbusSubjects(subjects_kelvin);
let subject_inbus_schedule = ref<ConcreteActivity[] | null>(null);

let classes_to_import = ref([]);
let result = ref<Result | null>(null);

let canImport = computed(() => {
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

async function loadKelvinSubjects(): Promise<KelvinSubject[]> {
    const res = await fetch('/api/subjects/all', {});
    const subjects_kelvin_resp = await res.json();

    const subjects_kelvin: KelvinSubject[] = subjects_kelvin_resp.subjects;
    subjects_kelvin.sort((a, b) => {
        const name_a = a.name.toUpperCase();
        const name_b = b.name.toUpperCase();
        if (name_a < name_b) {
            return -1;
        }
        if (name_a > name_b) {
            return 1;
        }
        return 0;
    });
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
  const semesters = semesters_data.map((sm) => ({
    pk: sm.pk,
    year: sm.year,
    winter: sm.winter,
    display: String(sm.year) + (sm.winter ? 'W' : 'S')
  }));

  return semesters;
}

async function loadSemesters() {
  const request = assembleRequest('/api/semesters');
  const res = await fetch(request, {});

  const semesters_data = await res.json();
  return parseSemesters(semesters_data['semesters']);
}

async function loadScheduleForSubjectVersionId(subject_index: number) {
  subject_inbus_schedule.value = null;
  const request = assembleRequest(
    '/api/inbus/schedule/subject/version/' +
      subjects_inbus_filtered.value[subject_index].subjectVersionId
  );
  let res = await fetch(request, {});
  subject_inbus_schedule.value = await res.json();
}

async function importActivities() {
  busy.value = true;
  const req = {
    semester_id: semester.value,
    subject_abbr: subject_kelvin_selected.value,
    activities: classes_to_import.value
  };

  //console.log(req);

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

function onInbusSubjectSelected(event: Event) {
  loadScheduleForSubjectVersionId(event.target.value);
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
          {{ ca.teacherFullNames }}
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
