<script setup lang="ts">
import { ref, computed } from 'vue';
import AddStudentsToClass from './AddStudentsToClass.vue';
import Markdown from '../components/Markdown.vue';
import AssignmentPoints from './AssignmentPoints.vue';
import TaskFilter from './TaskFilter.vue';
import CopyToClipboard from '../components/CopyToClipboard.vue';
import TimeAgo from '../components/TimeAgo.vue';
import { type Assignment, type Class, type StudentIdentity } from './frontendtypes';
import { type User } from '../utilities/global';
import { localStorageStore } from '../utilities/storage';
import { getFromAPI } from '../utilities/api';
import { task_types } from '../taskTypes';

const { clazz, user } = defineProps<{
  clazz: Class;
  user: User;
}>();

const emit = defineEmits<{ (e: 'update'): void }>();

const showStudentsList = ref(clazz.students.length < 50);
const showAddStudents = ref(clazz.students.length === 0);
const showFullNames = localStorageStore<boolean>('classDetail/showFullNames', false);
const showSummary = ref(false);
const taskType = ref<string | null>(null);
const reevaluateLoading = ref(false);

const now = () => new Date();

const activeTaskList = computed(() =>
  clazz.assignments.filter((a) => taskType.value === null || a.task_type === taskType.value)
);
const activeQuizList = computed(() =>
  taskType.value === null || taskType.value === 'quiz' ? clazz.quizzes : []
);

const totalMaxPoints = computed(() =>
  [...activeTaskList.value, ...activeQuizList.value].reduce((sum, t) => sum + t.max_points, 0)
);

const isNumeric = (v: number | null | undefined) =>
  v !== null && v !== undefined && !isNaN(Number(v));

async function handleUpdate() {
  showAddStudents.value = false;
  emit('update');
}

async function reevaluateAssignment(assignment: Assignment) {
  reevaluateLoading.value = true;
  const submitIds = Object.values(assignment.students)
    .map((s) => s.accepted_submit_id)
    .filter((id) => id);

  for (const submitId of submitIds) {
    await getFromAPI('/reevaluate/' + submitId);
  }
  reevaluateLoading.value = false;
}

const studentPoints = (student: StudentIdentity) => {
  const taskPoints = activeTaskList.value
    .map((a) => a.students[student.username])
    .filter((r) => r && r.submits !== 0 && isNumeric(r.assigned_points))
    .reduce((acc, r) => acc + Number(r.assigned_points), 0);

  const quizPoints = activeQuizList.value
    .map((q) => q.students[student.username])
    .filter((r) => r && isNumeric(r.score))
    .reduce((acc, r) => acc + Number(r.score), 0);

  return (taskPoints + quizPoints).toFixed(2);
};

function totalTaskPoints(index: number): string {
  let points = 0;
  for (const info of Object.values(activeTaskList.value[index].students)) {
    if (isNumeric(info.assigned_points)) {
      points += Math.max(0, Number(info.assigned_points));
    }
  }
  return points.toFixed(2);
}

function totalQuizPoints(index: number): string {
  let points = 0;
  for (const student of clazz.students) {
    const result = activeQuizList.value[index].students[student.username];
    if (result && isNumeric(result.score)) {
      points += Math.max(0, Number(result.score));
    }
  }
  return points.toFixed(2);
}

function createTaskSummary(index: number): string {
  const assignment = activeTaskList.value[index];
  const maxPoints = isNaN(assignment.max_points) ? 0 : assignment.max_points;
  const totalMaximumPoints = maxPoints * clazz.students.length;

  let assignmentPoints = 0;
  let gradedStudents = 0;
  for (const info of Object.values(assignment.students)) {
    if (isNumeric(info.points)) {
      assignmentPoints += Math.max(0, Number(info.points));
      gradedStudents += 1;
    }
  }

  const average = gradedStudents > 0 ? (assignmentPoints / gradedStudents).toFixed(2) : 'N/A';

  return (
    `Graded ${gradedStudents}/${clazz.students.length} student(s)\n` +
    `Total points: ${assignmentPoints.toFixed(2)}/${totalMaximumPoints}\n` +
    `Average points: ${average}`
  );
}

function createTaskTypeSummary(): string {
  const parts = [`Total: ${activeTaskList.value.reduce((sum, t) => sum + t.max_points, 0)} pts`];

  for (const { key, value } of task_types) {
    const totalPoints = activeTaskList.value
      .filter((a) => a.task_type === key)
      .reduce((sum, t) => sum + t.max_points, 0);

    if (totalPoints > 0) {
      parts.push(`${key === null ? 'None' : value}: ${totalPoints} pts`);
    }
  }

  return parts.length > 0
    ? `Task Summary: \n${parts.join('\n')}`
    : 'Task Summary - No tasks assigned';
}

const iso = (date: string | Date) => new Date(date).toISOString();
const local = (date: string | Date) => new Date(date).toLocaleString('cs');
</script>

<template>
  <div class="card mb-2" style="position: initial">
    <div class="card-header p-0">
      <div class="float-end p-2" style="display: flex; align-items: center">
        <a :href="`/task/add/${clazz.subject_abbr}`" title="Assign new task">
          <span class="iconify" data-icon="bx:bx-calendar-plus"></span>
        </a>
        <button
          class="p-0 btn btn-link"
          title="Add user to class"
          @click="showAddStudents = !showAddStudents"
        >
          <span class="iconify" data-icon="ant-design:user-add-outlined"></span>
        </button>
        <a :href="`${clazz.csv_link}`" title="Download CSV with results for all tasks">
          <span class="iconify" data-icon="la:file-csv-solid"></span>
        </a>
        <button
          class="p-0 btn btn-link"
          title="Show full task names"
          @click="showFullNames = !showFullNames"
        >
          <span v-if="showFullNames"><span class="iconify" data-icon="la:eye"></span></span>
          <span v-else><span class="iconify" data-icon="la:eye-slash"></span></span>
        </button>
        <a
          v-if="user.is_staff"
          :href="`/admin/common/class/${clazz.id}/change`"
          title="Edit class in Admin"
        >
          <span class="iconify" data-icon="clarity:edit-solid"></span>
        </a>
      </div>
      <button class="float-start btn" @click="showStudentsList = !showStudentsList">
        {{ clazz.subject_abbr }}
        <template v-if="clazz.room">{{ clazz.room }}</template>
        {{ clazz.timeslot }} {{ clazz.code }} {{ clazz.teacher_username }}
        <span class="text-muted d-none d-md-inline">({{ clazz.students.length }} students)</span>
      </button>
      <div class="float-start">
        <TaskFilter v-model:task-type="taskType" />
      </div>
    </div>

    <div v-if="showStudentsList || showAddStudents">
      <div class="card-body p-1">
        <AddStudentsToClass v-if="showAddStudents" :class-id="clazz.id" @update="handleUpdate" />

        <div v-if="showStudentsList">
          <button v-if="clazz.summary" class="p-0 btn btn-link" @click="showSummary = !showSummary">
            {{ showSummary ? 'Hide' : 'Show' }} class summary
          </button>
          <Markdown v-if="showSummary" :content="clazz.summary" />

          <div style="overflow: auto">
            <table class="table table-sm table-hover table-striped">
              <thead>
                <tr>
                  <th>
                    Login<span class="d-none d-md-inline"
                      ><CopyToClipboard
                        :content="clazz.students.map((s) => s.username).join('\n')"
                        title="Copy logins to clipboard"
                      >
                        <span
                          class="iconify"
                          data-icon="clarity:clipboard-line"
                        ></span> </CopyToClipboard
                      ><CopyToClipboard
                        :content="clazz.students.map((s) => `${s.username}@vsb.cz`).join('\n')"
                        title="Copy emails to clipboard"
                      >
                        <span class="iconify" data-icon="ic:round-alternate-email"></span>
                      </CopyToClipboard>
                    </span>
                  </th>
                  <th>Student</th>

                  <th
                    v-for="assignment in activeTaskList"
                    :key="`t${assignment.assignment_id}`"
                    class="more-hover"
                  >
                    <a
                      :href="assignment.task_link"
                      :class="{
                        'text-muted': assignment.assigned > now(),
                        'text-success': assignment.deadline > now()
                      }"
                    >
                      {{
                        showFullNames
                          ? assignment.short_name
                          : `#T${clazz.assignments.indexOf(assignment) + 1}`
                      }}<template v-if="assignment.max_points > 0">
                        ({{ assignment.max_points }}b)</template
                      >
                    </a>
                    <div class="more-content border shadow rounded bg-body p-1">
                      {{ assignment.name }}
                      <a :href="`/task/edit/${assignment.task_id}`" title="Edit"
                        ><span class="iconify" data-icon="clarity:edit-solid"></span
                      ></a>
                      <div style="display: flex; align-items: center">
                        <a :href="assignment.plagcheck_link" title="Plagiarism check"
                          ><span class="iconify" data-icon="bx:bx-check-double"></span
                        ></a>
                        <a :href="assignment.sources_link" title="Download all source codes"
                          ><span class="iconify" data-icon="fe:download" data-inline="false"></span
                        ></a>
                        <a :href="assignment.csv_link" title="Download CSV with results"
                          ><span class="iconify" data-icon="la:file-csv-solid"></span
                        ></a>
                        <a
                          :href="`/assignment/show/${assignment.assignment_id}`"
                          title="Show all source codes"
                          ><span class="iconify" data-icon="bx-bx-code-alt"></span
                        ></a>
                        <button
                          class="btn btn-link p-0"
                          :class="{ spin: reevaluateLoading }"
                          title="Reevaluate latest submits"
                          @click="reevaluateAssignment(assignment)"
                        >
                          <span class="iconify" data-icon="bx:bx-refresh"></span>
                        </button>
                        <a
                          :href="`/statistics/assignment/${assignment.assignment_id}`"
                          title="Show assignment stats"
                          ><span class="iconify" data-icon="bx-bx-bar-chart-alt-2"></span
                        ></a>
                      </div>
                      <dl>
                        <dt>Assigned</dt>
                        <dd>
                          {{ local(assignment.assigned)
                          }}<template v-if="assignment.assigned > now()"
                            >, <TimeAgo :datetime="iso(assignment.assigned)"
                          /></template>
                        </dd>

                        <template v-if="assignment.deadline">
                          <dt>Deadline</dt>
                          <dd>
                            {{ local(assignment.deadline)
                            }}<template v-if="assignment.deadline > now()"
                              >, <TimeAgo :datetime="iso(assignment.deadline)"
                            /></template>
                          </dd>
                        </template>

                        <template v-if="assignment.max_points">
                          <dt>Max points</dt>
                          <dd>{{ assignment.max_points }}</dd>
                        </template>
                      </dl>
                    </div>
                  </th>

                  <th
                    v-for="(quiz, index) in activeQuizList"
                    :key="`q${quiz.assigned_id}`"
                    class="more-hover"
                  >
                    <a
                      :href="quiz.quiz_link"
                      :class="{
                        'text-muted': quiz.assigned > now(),
                        'text-success': quiz.deadline > now()
                      }"
                    >
                      {{ showFullNames ? quiz.name_lower : `#Q${index + 1}`
                      }}<template v-if="quiz.max_points > 0"> ({{ quiz.max_points }}b)</template>
                    </a>
                    <div class="more-content border shadow rounded bg-body p-1">
                      {{ quiz.name }}
                      <a :href="quiz.quiz_edit_link" title="Edit"
                        ><span class="iconify" data-icon="clarity:edit-solid"></span
                      ></a>
                      <dl>
                        <dt>Assigned</dt>
                        <dd>
                          {{ local(quiz.assigned)
                          }}<template v-if="quiz.assigned > now()"
                            >, <TimeAgo :datetime="iso(quiz.assigned)"
                          /></template>
                        </dd>

                        <template v-if="quiz.deadline">
                          <dt>Deadline</dt>
                          <dd>
                            {{ local(quiz.deadline)
                            }}<template v-if="quiz.deadline > now()"
                              >, <TimeAgo :datetime="iso(quiz.deadline)"
                            /></template>
                          </dd>
                        </template>

                        <template v-if="quiz.max_points">
                          <dt>Max points</dt>
                          <dd>{{ quiz.max_points }}</dd>
                        </template>
                      </dl>
                    </div>
                  </th>

                  <th class="more-hover" :title="taskType === null ? createTaskTypeSummary() : ''">
                    Total ({{ totalMaxPoints }} pts)
                  </th>
                </tr>
              </thead>

              <tbody>
                <tr v-for="student in clazz.students" :key="student.username">
                  <td>
                    <a :href="`/student/${student.username}`" target="_blank">{{
                      student.username
                    }}</a>
                  </td>
                  <td>{{ student.last_name }} {{ student.first_name }}</td>

                  <td
                    v-for="(assignment, i) in activeTaskList"
                    :key="`t${assignment.assignment_id}`"
                  >
                    <AssignmentPoints
                      :submit_id="assignment.students[student.username]?.accepted_submit_id"
                      :submits="assignment.students[student.username]?.submits"
                      :link="assignment.students[student.username]?.link"
                      :login="student.username"
                      :task="activeTaskList[i].name"
                      :color="assignment.students[student.username]?.color"
                      :assigned_points="assignment.students[student.username]?.assigned_points"
                      :has_final_submit="assignment.students[student.username]?.has_final_submit"
                    />
                  </td>

                  <td v-for="quiz in activeQuizList" :key="`q${quiz.assigned_id}`">
                    <a
                      v-if="quiz.students[student.username]?.score != null"
                      :href="quiz.students[student.username]?.scoring_link"
                      :style="{ color: quiz.students[student.username]?.color }"
                      >{{ quiz.students[student.username]?.score }}</a
                    >
                  </td>

                  <td>{{ studentPoints(student) }}</td>
                </tr>

                <tr>
                  <td></td>
                  <td></td>
                  <td
                    v-for="(assignment, k) in activeTaskList"
                    :key="`t${assignment.assignment_id}`"
                    :title="createTaskSummary(k)"
                  >
                    {{ totalTaskPoints(k) }}
                  </td>
                  <td v-for="(quiz, k) in activeQuizList" :key="`q${quiz.assigned_id}`">
                    {{ totalQuizPoints(k) }}
                  </td>
                  <td></td>
                </tr>
              </tbody>
            </table>
          </div>
          <p v-if="clazz.students.length === 0" class="text-center">No student added yet.</p>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
td,
th {
  white-space: nowrap;
  width: 1%;
}
tr th:last-of-type,
td:last-of-type {
  width: 100%;
  text-align: right;
}
tr td:not(:nth-of-type(1)):not(:nth-of-type(2)):not(:last-child) {
  text-align: center;
}

.card-body {
  overflow-x: auto;
}

.spin {
  animation-name: spin;
  animation-duration: 2000ms;
  animation-iteration-count: infinite;
  animation-timing-function: linear;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.more-content {
  display: none;
  text-align: left;
}

.more-hover:hover .more-content {
  position: absolute;
  display: block;
  font-weight: normal;
  z-index: 3;
}
</style>
