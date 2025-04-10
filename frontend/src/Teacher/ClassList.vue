<script setup lang="ts">
import { onMounted } from 'vue';
import { ref } from 'vue';
import { getFromAPI } from '../utilities/api';

import ClassDetail from './ClassDetail.vue';

let classes = ref(Array<Class>());

let filter = {
  semester: '2024S', //semester.abbr,
  subject: null,
  teacher: 'GAU01', //user.username,
  class: null
};

interface Assignment {
  task_id: number;
  task_link: string; // URL
  assignment_id: number;
  name: string;
  short_name: string;
  moss_link: string; // URL
  sources_link: string; // URL
  csv_link: string; // URL
  assigned: string; // datetime
  deadline: string; // datetime
  max_points: number;
}

interface Student {
  student: string; // login
  submits: number;
  submits_with_assigned_pts: number;
  first_submit_date: string; // datetime
  last_submit_date: string; // datetime
  points: null;
  max_points: null;
  assigned_points: number;
  accepted_submit_num: number;
  accepted_submit_id: number;
  color: string;
  link: string; // URL
}

interface Class {
  id: number;
  teacher_username: string;
  timeslot: string;
  code: string;
  subject_abbr: string;
  csv_link: string; // URL
  assignments: Assignment[];
  summary: string;
  students: Student[];
}

let prevParams;

async function refetch(): Promise<Class[]> {
  const params = new URLSearchParams(
    Object.fromEntries(Object.entries(filter).filter(([_, v]) => v))
  ).toString();
  if (prevParams === params) {
    return;
  }
  prevParams = params;

  const req = await getFromAPI<Class[]>(
    `/api/classes?semester=${filter.semester}&teacher=${filter.teacher}`
  );

  classes.value = req['classes'].map((c) => {
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
        <ClassDetail v-for="clazz in classes" :clazz="clazz" />
      </div>
    </div>
  </div>
</template>

<style scoped></style>
