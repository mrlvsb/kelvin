<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue';
import { fetch } from "../api.js";

const semester = ref(null);
const subject = ref(null);
const teacher = ref(null);
const clazz = ref(null);
const student = ref(null);
const target_class = ref(null);
const assignments = ref([]);
const busy = ref(false);
const data = await loadClasses();
const classes = ref( null );
const result = ref(null);

const notAssignedCount = computed(() => assignments.value.filter(t => !t.dst_assignment_id).length);
const uniqueAssignments = computed(() => true); // Adjust logic if necessary
const canTransfer = computed(() => assignments.value.length && notAssignedCount.value === 0 && uniqueAssignments.value && !busy.value);

watch(teacher, () => {
  loadClass();
});

async function loadClasses() {
  const res = await fetch("/api/classes/all");
  return await res.json();
  //data.value = await res.json();
}

async function loadClass() {
  const res = await fetch(`/api/classes?semester=${semester.value}&subject=${subject.value}`);
  classes.value = (await res.json()).classes;
  //return (await res.json()).classes;
}

function target_changed() {
  const target = classes.value.find(c => c.code === target_class.value).assignments;
  let index = 0;
  assignments.value = classes.value.find(c => c.code === clazz.value).assignments.map(t => ({
    name: t.name,
    assigned_points: t.students[student.value]?.assigned_points || "",
    src_assignment_id: t.assignment_id,
    dst_assignment_id: index < target.length ? target[index++].assignment_id : null
  }));
}

async function transfer() {
  busy.value = true;
  const req = {
    student: student.value,
    src_class: classes.value.find(c => c.code === clazz.value).id,
    dst_class: classes.value.find(c => c.code === target_class.value).id,
    assignments: assignments.value
  };
  const res = await fetch("/api/transfer_students", {
    method: "POST",
    body: JSON.stringify(req)
  });
  result.value = (await res.json()).transfers;
  busy.value = false;
}

//onMounted(() => {
//  loadClasses();
//});
</script>

<template>
  <div v-if="data">
    <select v-model="semester">
      <option v-for="item in Object.keys(data.semesters)" :key="item" :value="item">{{ item }}</option>
    </select>

    <select v-model="subject" v-if="semester">
      <option v-for="item in Object.keys(data.semesters[semester])" :key="item" :value="item">{{ item }}</option>
    </select>

    <select v-model="teacher" v-if="subject">
      <option v-for="item in Object.keys(data.semesters[semester][subject])" :key="item" :value="item">{{ item }}</option>
    </select>

    <select v-model="clazz" v-if="teacher && classes">
      <option v-for="item in classes.filter(c => c.teacher_username === teacher)" :key="item.code" :value="item.code">
        {{ item.timeslot }} {{ item.code }}
      </option>
    </select>

    <select v-model="student" v-if="clazz">
      <option v-for="item in classes.find(c => c.code === clazz).students" :key="item.username" :value="item.username">
        {{ item.username }} {{ item.first_name }} {{ item.last_name }}
      </option>
    </select>

    <select v-model="target_class" @change="target_changed" v-if="student">
      <option v-for="item in classes" :key="item.code" :value="item.code">
        {{ item.teacher_username }} {{ item.timeslot }} {{ item.code }}
      </option>
    </select>

    <table class="table table-hover table-stripped table-sm">
      <tbody>
        <tr v-for="assignment in assignments" :key="assignment.src_assignment_id">
          <td>{{ assignment.name }}</td>
          <td>{{ assignment.assigned_points }}</td>
          <td>
            <select v-model="assignment.dst_assignment_id" v-if="target_class">
              <option v-for="target in classes.find(c => c.code === target_class).assignments" :key="target.assignment_id" :value="target.assignment_id">
                {{ target.name }}
              </option>
            </select>
          </td>
        </tr>
      </tbody>
    </table>

    <table v-if="result" class="table table-sm table-hover table-striped">
      <tbody>
        <tr v-for="item in result" :key="item.submit_id">
          <td>{{ item.submit_id }}</td>
          <td>{{ item.before }}</td>
          <td>{{ item.after }}</td>
        </tr>
      </tbody>
    </table>

    <button
      class="btn"
      :class="canTransfer ? 'btn-success' : 'btn-danger'"
      @click="transfer"
      :disabled="!canTransfer">
      {{ busy ? 'Transferring...' : 'Transfer' }}
      <span v-if="!canTransfer">(
        <span v-if="assignments.length">
          <span v-if="notAssignedCount > 0">{{ notAssignedCount }} tasks need to be assigned</span>
          <span v-else>Tasks on the right side need to be unique.</span>
        </span>
        <span v-else>Missing target class</span>
      )</span>
    </button>
  </div>
</template>
