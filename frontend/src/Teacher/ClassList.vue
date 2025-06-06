<script setup lang="ts">
import { onMounted } from 'vue';
import { ref } from 'vue';
import { getFromAPI } from '../utilities/api';
import { user, semester } from '../utilities/global';
import ClassDetail from './ClassDetail.vue';
import ClassFilter from './ClassFilter.vue';

import { type Class } from './frontendtypes';

const classes = ref<Class[]>([]);

interface FilterParams {
  semester: string;
  subject: string | null;
  teacher: string;
  class: string | null;
}

const filter: FilterParams = {
  semester: semester.value.abbr, //semester.abbr
  subject: null,
  teacher: user.value.username, //user.username
  class: null
};

let prevParams;

async function loadClasses() {
  const req = await getFromAPI<{ classes: Class[] }>(
    //`/api/classes?semester=${filter.semester}&subject=${filter.subject}&teacher=${filter.teacher}`
    '/api/classes?' + prevParams
  );

  classes.value = req.classes.map((c) => {
    c.assignments = c.assignments.map((assignment) => {
      assignment.assigned = new Date(assignment.assigned);
      if (assignment.deadline) {
        assignment.deadline = new Date(assignment.deadline);
      }
      return assignment;
    });
    return c;
  });
}

async function refetch(): Promise<Class[]> {
  const params = new URLSearchParams(
    Object.fromEntries(Object.entries(filter).filter(([_, v]) => v))
  ).toString();
  if (prevParams === params) {
    return;
  }
  prevParams = params;

  await loadClasses();
}

onMounted(() => {
  refetch();
});
</script>

<template>
  <div class="container-fluid p-1">
    <div class="d-flex mb-1">
      <ClassFilter
        :semester="filter.semester"
        :subject="filter.subject"
        :teacher="filter.teacher"
        :clazz="filter.class"
      />
    </div>
    <div class="classes">
      <div class="classes-inner">
        <ClassDetail
          v-for="clazz in classes"
          :key="clazz.id"
          :clazz="clazz"
          @update="loadClasses"
        />
      </div>
    </div>
  </div>
</template>

<style scoped></style>
