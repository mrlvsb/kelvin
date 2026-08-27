<script setup lang="ts">
import { onMounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import { getFromAPI } from '../utilities/api';
import ClassDetail from './ClassDetail.vue';
import ClassFilter from './ClassFilter.vue';
import SyncLoader from '../components/SyncLoader.vue';

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

// This is the root of the class-list component tree: /api/info is fetched here
// once and handed to ClassFilter / ClassDetail via props.
const { user, semester } = await loadInfo();

const filter = ref<FilterParams>({
  semester: (route.query.semester as string) || semester.abbr,
  subject: (route.query.subject as string) || null,
  teacher: (route.query.teacher as string) || user.username,
  class: (route.query.class as string) || null
});

// Last query string we actually fetched, so overlapping reactive triggers
// (onMounted, the route-query watch, and ClassFilter's filter-change event) that
// resolve to the same filter don't each fire a request.
let prevParams: string | undefined;

async function loadClasses() {
  const params = new URLSearchParams(
    Object.fromEntries(Object.entries(filter.value).filter(([, v]) => v))
  ).toString();

  if (params === prevParams) {
    return;
  }
  prevParams = params;
  isLoading.value = true;

  const req = await getFromAPI<{ classes: Class[] }>('/api/classes?' + params);

  classes.value = (req?.classes ?? []).map((c) => {
    c.assignments = c.assignments.map((assignment) => {
      assignment.assigned = new Date(assignment.assigned);
      if (assignment.deadline) {
        assignment.deadline = new Date(assignment.deadline);
      }
      return assignment;
    });
    c.quizzes = (c.quizzes ?? []).map((quiz) => {
      quiz.assigned = new Date(quiz.assigned);
      if (quiz.deadline) {
        quiz.deadline = new Date(quiz.deadline);
      }
      return quiz;
    });
    return c;
  });

  isLoading.value = false;
}

function handleFilterChange(newFilter: FilterParams) {
  filter.value = newFilter;
  loadClasses();
}

// A class changed (e.g. students added) — force a refetch even though the filter
// is unchanged.
function reloadClasses() {
  prevParams = undefined;
  loadClasses();
}

// Watch route query changes
watch(
  () => route.query,
  (newQuery) => {
    filter.value = {
      semester: (newQuery.semester as string) || semester.abbr,
      subject: (newQuery.subject as string) || null,
      teacher: (newQuery.teacher as string) || user.username,
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
      <ClassFilter :user="user" @filter-change="handleFilterChange" />

      <a class="btn btn-sm p-1" href="/import/inbus" title="Bulk import students from EDISON">
        <span class="iconify" data-icon="mdi:calendar-import"></span>
      </a>

      <a
        v-if="user.is_staff"
        class="btn btn-sm p-1"
        href="/admin/common/class/add/"
        title="Add class"
      >
        <span class="iconify" data-icon="ant-design:plus-outlined"></span>
      </a>
    </div>
    <div class="classes" :class="{ loading: isLoading }">
      <div class="d-flex justify-content-center loading-animation">
        <SyncLoader />
      </div>

      <div class="classes-inner">
        <ClassDetail
          v-for="clazz in classes"
          :key="clazz.id"
          :clazz="clazz"
          :user="user"
          @update="reloadClasses"
        />
        <p v-if="!isLoading && classes.length === 0" class="alert alert-info">
          No class found, try different filter.
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.loading-animation {
  visibility: hidden;
  position: absolute;
  width: 100%;
  pointer-events: none;
  z-index: 2;
}

.classes.loading {
  position: relative;
}

.loading .loading-animation {
  visibility: visible;
}

.loading .classes-inner {
  opacity: 0.5;
  pointer-events: none;
}
</style>
