<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { getFromAPI } from '../utilities/api';
import { loadInfo } from '../utilities/global';
import { type ClassesByTeacher } from './frontendtypes';

const router = useRouter();
const route = useRoute();

const emit = defineEmits<{
  (
    e: 'filterChange',
    filter: { semester: string; subject: string; teacher: string; class: string }
  ): void;
}>();

const semesters = ref<ClassesByTeacher>({});
const sem_sorted = ref<string[]>([]);
const teachers = ref<string[]>([]);
const allTeachers = ref<string[]>([]);
const classes = ref<string[]>([]);
const allClasses = ref<string[]>([]);

const semester = ref('');
const subject = ref('');
const teacher = ref('');
const clazz = ref('');

const isLoading = ref(true);

const [user] = await loadInfo(true);

async function load() {
  const res = await getFromAPI<{ semesters: ClassesByTeacher }>('/api/classes/all');
  semesters.value = res.semesters;

  sem_sorted.value = sorted(Object.keys(semesters.value), compareSemester);
  const allTeachersSet = new Set<string>();
  const allClassesSet = new Set<string>();
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

  // Initialize from route query params
  semester.value =
    (route.query.semester as string) || sem_sorted.value[sem_sorted.value.length - 1] || '';
  subject.value = (route.query.subject as string) || '';
  teacher.value = (route.query.teacher as string) || '';
  clazz.value = (route.query.class as string) || '';

  isLoading.value = false;
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

// Update URL when filters change
watch([semester, subject, teacher, clazz], () => {
  if (isLoading.value) return;

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

  router.replace({ path: '/', query: Object.fromEntries(params.entries()) }).catch(() => {});

  // Emit filter change to parent
  emit('filterChange', {
    semester: semester.value,
    subject: subject.value,
    teacher: teacher.value,
    class: clazz.value
  });
});

// Update available options when semester/subject/teacher change
watch([semester, subject, teacher], () => {
  if (isLoading.value) return;

  const sem = semesters.value[semester.value];

  if (!sem) {
    teachers.value = allTeachers.value;
    classes.value = allClasses.value;
    return;
  }

  // Reset subject if it doesn't exist in selected semester
  if (subject.value && !sem[subject.value]) {
    subject.value = '';
    return;
  }

  // Reset teacher if it doesn't exist for selected subject
  if (subject.value && teacher.value && !sem[subject.value]?.hasOwnProperty(teacher.value)) {
    teacher.value = '';
  }

  // Update available teachers and classes based on selection
  if (semester.value && subject.value && sem?.[subject.value]) {
    teachers.value = sorted(Object.keys(sem[subject.value]));

    if (teacher.value && sem[subject.value][teacher.value]) {
      classes.value = sem[subject.value][teacher.value];
    } else {
      const merged: string[] = [];
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
