<script setup lang="ts">
/**
 * This component displays information about a student.
 * It is only available to teachers, and it is accessible through links from various parts
 * of Kelvin.
 */

type Student = {
  login: string;
  name: string;
};

const props = defineProps<{
  student: Student;
}>();
</script>

<template>
  <div>
    <div><b>Name</b>: {{ props.student.name }}</div>
    <div><b>Login</b>: {{ props.student.login }}</div>
    <div><a :href="'/submits/' + props.student.login">List of submits</a></div>
    <div>This page is in progress, it will be filled with more useful information later.</div>
  </div>
</template>
