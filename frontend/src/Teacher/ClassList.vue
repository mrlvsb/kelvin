<script setup lang="ts">
import { onMounted } from 'vue';
import { ref } from 'vue';
import { getFromAPI } from '../utilities/api';

import ClassDetail from './ClassDetail.vue';

import { type Class } from './frontendtypes';

const classes = ref<Class[]>([]);

interface FilterParams {
  semester: string;
  subject: string | null;
  teacher: string;
  class: string | null;
}

const filter: FilterParams = {
  semester: '2024S', //semester.abbr
  subject: null,
  teacher: 'GAU01', //user.username
  class: null
};

let prevParams;

async function refetch(): Promise<Class[]> {
  const params = new URLSearchParams(
    Object.fromEntries(Object.entries(filter).filter(([_, v]) => v))
  ).toString();
  if (prevParams === params) {
    return;
  }
  prevParams = params;

  const req = await getFromAPI<{ classes: Class[] }>(
    `/api/classes?semester=${filter.semester}&teacher=${filter.teacher}`
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

onMounted(() => {
  refetch();
});
</script>

<template>
  <div class="container-fluid p-1">
    <div class="d-flex mb-1"></div>
    <div class="classes">
      <div class="classes-inner">
        <ClassDetail v-for="clazz in classes" :key="clazz.id" :clazz="clazz" />
      </div>
    </div>
  </div>
</template>

<style scoped></style>
