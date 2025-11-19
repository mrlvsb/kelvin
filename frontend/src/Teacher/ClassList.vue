<script setup lang="ts">
import { onMounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import { getFromAPI } from '../utilities/api';
import ClassDetail from './ClassDetail.vue';
import ClassFilter from './ClassFilter.vue';

import { type Class } from './frontendtypes';
import { loadInfo } from '../utilities/global';

const route = useRoute();
const classes = ref<Class[]>([]);
const isLoading = ref(false);

interface FilterParams {
  semester: string;
  subject: string | null;
  teacher: string;
  class: string | null;
}

const [user, semester] = await loadInfo(true);

const filter = ref<FilterParams>({
  semester: (route.query.semester as string) || semester.value.abbr,
  subject: (route.query.subject as string) || null,
  teacher: (route.query.teacher as string) || user.value.username,
  class: (route.query.class as string) || null
});

async function loadClasses() {
  isLoading.value = true;
  const params = new URLSearchParams(
    Object.fromEntries(Object.entries(filter.value).filter(([, v]) => v))
  ).toString();

  const req = await getFromAPI<{ classes: Class[] }>('/api/classes?' + params);

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

  isLoading.value = false;
}

function handleFilterChange(newFilter: FilterParams) {
  filter.value = newFilter;
  loadClasses();
}

// Watch route query changes
watch(
  () => route.query,
  (newQuery) => {
    filter.value = {
      semester: (newQuery.semester as string) || semester.value.abbr,
      subject: (newQuery.subject as string) || null,
      teacher: (newQuery.teacher as string) || user.value.username,
      class: (newQuery.class as string) || null
    };
    loadClasses();
  }
);

onMounted(() => {
  loadClasses();
});
</script>

<template>
  <div class="container-fluid p-1">
    <div class="d-flex mb-1">
      <ClassFilter @filter-change="handleFilterChange" />
    </div>
    <div class="classes" :class="{ loading: isLoading }">
      <div class="classes-inner">
        <ClassDetail
          v-for="clazz in classes"
          :key="clazz.id"
          :clazz="clazz"
          @update="loadClasses"
        />
        <p v-if="!isLoading && classes.length === 0" class="alert alert-info">
          No class found, try different filter.
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.loading .classes-inner {
  opacity: 0.5;
  pointer-events: none;
}
</style>
