<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { getFromAPI } from '../utilities/api';
import { user } from '../utilities/global';
import { type ClassesByTeacher } from './frontendtypes';

const router = useRouter();

const semesters = ref({});
const sem_sorted = ref<string[]>([]);
const teachers = ref([]);
const allTeachers = ref([]);
const classes = ref([]);
const allClasses = ref([]);

const semester = ref('');
const subject = ref('');
const teacher = ref('');
const clazz = ref('');

/*
const subjs = computed(() => {
  console.log('computed subject');
  const result = [];
  const sem = semesters.value?.[semester.value];
  if (sem) {
    for (const subj in sem) {
      if (Object.prototype.hasOwnProperty.call(sem[subj], user.value.username)) {
        result.push(subj);
      }
    }
  }
  return result;
});
*/

/*
watch([semesters], () => {
  subjs.value = [];
  const sem = semesters.value?.[semester.value];
  if (sem) {
    for (const subj in sem) {
      if (Object.prototype.hasOwnProperty.call(sem[subj], user.value.username)) {
        subjs.value.push(subj);
      }
    }
  }
});
*/

async function load() {
  const res = await getFromAPI<{ semesters: ClassesByTeacher }>('/api/classes/all');
  semesters.value = res.semesters;

  sem_sorted.value = sorted(Object.keys(semesters.value), compareSemester);
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

  //console.log('sem_sorted', sem_sorted.value);
  semester.value = sem_sorted.value[sem_sorted.value.length - 1];
  //console.log('semester', semester.value);
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

function sorted(items: string[], compareFn?: (a: string, b: string) => number): string[] {
  return [...items].sort(compareFn);
}

function compareSemester(a: string, b: string) {
  const yearA = Number(a.substring(0, 4));
  const yearB = Number(b.substring(0, 4));
  if (yearA < yearB) return -1;
  if (yearA > yearB) return 1;
  return a[4] === 'W' ? -1 : 1;
}

watch([semester, subject, teacher, clazz], () => {
  console.log('watch 1');
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
  router.push({ path: '/', query: Object.fromEntries(params.entries()) });
});

watch([semester, subject, teacher], () => {
  console.log('watch 2');
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
