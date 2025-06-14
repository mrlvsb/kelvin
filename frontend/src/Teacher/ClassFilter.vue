<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue';
//import { useRouter } from 'vue-router';
import { getFromAPI } from '../utilities/api';
//import { user } from './global.js';
import { user } from '../utilities/global';
import { type ClassesByTeacher } from './frontendtypes';

//const user = ref({ username: 'GAU01', is_staff: true, is_superuser: true }); // FIXME: Get user from /api/info

//const router = useRouter();

const semesters = ref({});
const teachers = ref([]);
const allTeachers = ref([]);
const classes = ref([]);
const allClasses = ref([]);

const semester = ref('');
const subject = ref('');
const teacher = ref('');
const clazz = ref('');

async function load() {
  const res = await getFromAPI<{ semesters: ClassesByTeacher }>('/api/classes/all');
  //const json = await res.json();
  semesters.value = res.semesters; //json.semesters;

  const allTeachersSet = new Set();
  const allClassesSet = new Set();
  for (const sem in semesters.value) {
    for (const subj in semesters.value[sem]) {
      for (const t in semesters.value[sem][subj]) {
        allTeachersSet.add(t);
        for (const c of semesters.value[sem][subj][t]) {
          allClassesSet.add(c);
        }
      }
    }
  }
  allTeachers.value = [...allTeachersSet];
  allClasses.value = [...allClassesSet];
}

function resetClass() {
  clazz.value = '';
}

function fillTeacher() {
  if (
    subject.value &&
    semesters.value[semester.value]?.[subject.value]?.hasOwnProperty(user.value.username)
  ) {
    teacher.value = user.value.username;
  }
  resetClass();
}

function sorted(items, compareFn?) {
  return [...items].sort(compareFn);
}

function compareSemester(a, b) {
  const yearA = Number(a.substring(0, 4));
  const yearB = Number(b.substring(0, 4));
  if (yearA < yearB) return -1;
  if (yearA > yearB) return 1;
  return a[4] === 'W' ? -1 : 1;
}

watch([semester, subject, teacher, clazz], () => {
  const params = new URLSearchParams(
    Object.fromEntries(
      Object.entries({
        semester: semester.value,
        subject: subject.value,
        teacher: teacher.value,
        class: clazz.value
      }).filter(([, v]) => v)
    )
  );
  //router.push({ path: '/', query: Object.fromEntries(params.entries()) });
});

watch([semester, subject, teacher], () => {
  const sem = semesters.value[semester.value];
  if (!sem) return;

  if (subject.value && !sem[subject.value]) {
    subject.value = '';
  } else if (subject.value && teacher.value && !sem[subject.value]?.hasOwnProperty(teacher.value)) {
    teacher.value = '';
  }

  if (semester.value && subject.value && sem?.[subject.value]) {
    teachers.value = Object.keys(sem[subject.value]);
    if (teacher.value && sem[subject.value][teacher.value]) {
      classes.value = sem[subject.value][teacher.value];
    } else {
      const merged = [];
      for (const t in sem[subject.value]) {
        merged.push(...sem[subject.value][t]);
      }
      classes.value = merged;
    }
  } else {
    teachers.value = allTeachers.value;
    classes.value = allClasses.value;
  }
});

onMounted(load);
</script>

<template>
  <div class="ms-auto">
    <div class="input-group">
      <select v-model="semester" class="form-select form-select-sm" @change="resetClass">
        <option value="">Semester</option>
        <option v-for="s in sorted(Object.keys(semesters), compareSemester)" :key="s">
          {{ s }}
        </option>
      </select>

      <select
        v-model="subject"
        class="form-select form-select-sm"
        :disabled="!semester"
        @change="fillTeacher"
      >
        <option value="">Subject</option>
        <option v-for="subj in sorted(Object.keys(semesters[semester] || {}))" :key="subj">
          {{ subj }}
        </option>
      </select>

      <select
        v-if="user.is_superuser"
        v-model="teacher"
        class="form-select form-select-sm"
        @change="resetClass"
      >
        <option value="">Teacher</option>
        <option v-for="t in sorted(teachers)" :key="t">
          {{ t }}
        </option>
      </select>

      <select v-model="clazz" class="form-select form-select-sm" :disabled="!(semester && subject)">
        <option value="">Class</option>
        <option v-for="c in classes" :key="c">
          {{ c }}
        </option>
      </select>
    </div>
  </div>
</template>
