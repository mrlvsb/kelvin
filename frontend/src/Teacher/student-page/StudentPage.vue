<script setup lang="ts">
/**
 * This component displays information about a student.
 * It is only available to teachers, and it is accessible through links from various parts
 * of Kelvin.
 */
import EventList from './EventList.vue';

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
    <div><a :href="`/submits/${props.student.login}`">List of submits</a></div>
    <div class="mt-4">
      <h2>Event log</h2>
      <EventList :login="props.student.login" />
    </div>
  </div>
</template>

<style scoped lang="scss"></style>
