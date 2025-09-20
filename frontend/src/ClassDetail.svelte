<script>
import { link } from 'svelte-spa-router';
import { fetch } from './api.js';

import CopyToClipboard from './CopyToClipboard.svelte';
import TimeAgo from './TimeAgo.svelte';
import { localStorageStore } from './utils.js';
import { user } from './global.js';
import AddStudentsToClass from './AddStudentsToClass.svelte';
import Markdown from './Markdown.svelte';
import AssignmentPoints from './AssignmentPoints.svelte';
import TaskFilter from './TaskFilter.svelte';
import { task_types } from './taskTypes.js';

export let clazz;
export let showStudentsList = clazz['students'].length < 50;
let task_type = null;

let activeTaskList = [];
let activeQuizList = [];
let showAddStudents = clazz.students.length == 0;

let reevaluateLoading = false;
async function reevaluateAssignment(assignment) {
  reevaluateLoading = true;
  const submit_ids = Object.values(assignment.students)
    .map((stud) => stud['accepted_submit_id'])
    .filter((id) => id);

  for (const submit_id of submit_ids) {
    await fetch('/reevaluate/' + submit_id);
  }
  reevaluateLoading = false;
}

$: {
  activeTaskList = clazz.assignments.filter(
    (as) => task_type === null || as.task_type === task_type
  );
}

$: {
  activeQuizList = task_type === null ? clazz.quizzes : [];
}

function studentPoints(activeTaskList, activeQuizList, student) {
  return (
    activeTaskList
      .map((i) => i.students[student.username])
      .filter(
        (result) => result && result.submits != 0 && !isNaN(parseFloat(result.assigned_points))
      )
      .map((result) => parseFloat(result.assigned_points))
      .reduce((acc, val) => acc + val, 0) +
    activeQuizList
      .map((i) => i.students[student.username])
      .filter((result) => result && !isNaN(parseFloat(result.score)))
      .map((result) => parseFloat(result.score))
      .reduce((acc, val) => acc + val, 0)
  ).toFixed(2);
}

function totalTaskPoints(activeTaskList, assignment_index) {
  let assignmentPoints = 0;

  Object.entries(activeTaskList[assignment_index].students).forEach(([name, info]) => {
    if (!isNaN(info.assigned_points)) {
      assignmentPoints += Math.max(0, info.assigned_points);
    }
  });

  return assignmentPoints;
}

function totalQuizPoints(clazz, quiz_index) {
  let quizPoints = 0;

  for (let i = 0; i < clazz.students.length; i++) {
    const student = clazz.students[i];
    if (!isNaN(clazz.quizzes[quiz_index].students[student.username].score)) {
      quizPoints += Math.max(0, clazz.quizzes[quiz_index].students[student.username].score);
    }
  }

  return quizPoints;
}

function createTaskSummary(activeTaskList, clazz, assignment_index) {
  let maxPoints = activeTaskList[assignment_index].max_points;
  if (isNaN(maxPoints)) {
    maxPoints = 0;
  }

  let totalMaximumPoints = maxPoints * clazz.students.length;
  let assignmentPoints = 0;
  let gradedStudents = 0;

  Object.entries(activeTaskList[assignment_index].students).forEach(([name, info]) => {
    if (!isNaN(info.points) && info.points !== null) {
      assignmentPoints += Math.max(0, info.points);
      gradedStudents += 1;
    }
  });

  let average = 'N/A';
  if (gradedStudents > 0) {
    average = (assignmentPoints / gradedStudents).toFixed(2);
  }

  return `Graded ${gradedStudents}/${clazz.students.length} student(s)
Total points: ${assignmentPoints.toFixed(2)}/${totalMaximumPoints}
Average points: ${average}`;
}

function createTaskTypeSummary(activeTaskList) {
  let summaryParts = [];
  summaryParts.push(`Total: ${activeTaskList.reduce((sum, task) => sum + task.max_points, 0)} pts`);
  task_types.forEach(({ key, value }) => {
    const totalPoints = activeTaskList
      .filter((asg) => asg.task_type === key)
      .reduce((sum, task) => sum + task.max_points, 0);

    if (totalPoints > 0) {
      summaryParts.push(`${key === null ? 'None' : value}: ${totalPoints} pts`);
    }
  });

  return summaryParts.length > 0
    ? `Task Summary: \n${summaryParts.join('\n')}`
    : 'Task Summary - No tasks assigned';
}

let showFullNames = localStorageStore('classDetail/showFullNames', false);
let showSummary = false;
</script>

<div class="card mb-2" style="position: initial">
  <div class="card-header p-0">
    <div class="float-end p-2" style="display: flex; align-items: center;">
      <a href="/task/add/{clazz.subject_abbr}" use:link title="Assign new task">
        <span class="iconify" data-icon="bx:bx-calendar-plus"></span>
      </a>
      <button
        class="p-0 btn btn-link"
        on:click={() => (showAddStudents = !showAddStudents)}
        title="Add user to class">
        <span class="iconify" data-icon="ant-design:user-add-outlined"></span>
      </button>
      <a href={clazz.csv_link} title="Download CSV with results for all task">
        <span class="iconify" data-icon="la:file-csv-solid"></span>
      </a>
      <button
        class="p-0 btn btn-link"
        on:click={() => ($showFullNames = !$showFullNames)}
        title="Show full task names">
        {#if $showFullNames}
          <span><span class="iconify" data-icon="la:eye"></span></span>
        {:else}
          <span><span class="iconify" data-icon="la:eye-slash"></span></span>
        {/if}
      </button>
      {#if $user.is_staff}
        <a href="/admin/common/class/{clazz.id}/change" title="Edit class in Admin">
          <span class="iconify" data-icon="clarity:edit-solid"></span>
        </a>
      {/if}
    </div>
    <button class="float-start btn" on:click={() => (showStudentsList = !showStudentsList)}>
      {clazz.subject_abbr}
      {clazz.timeslot}
      {clazz.code}
      {clazz.teacher_username}
      <span class="text-muted d-none d-md-inline">({clazz.students.length} students)</span>
    </button>
    <div class="float-start">
      <TaskFilter bind:task_type />
    </div>
  </div>
  <div>
    {#if showStudentsList || showAddStudents}
      <div class="card-body p-1">
        {#if showAddStudents}
          <AddStudentsToClass class_id={clazz.id} on:update />
        {/if}

        {#if showStudentsList}
          {#if clazz.summary}
            <button class="p-0 btn btn-link" on:click={() => (showSummary = !showSummary)}
              >{showSummary ? 'Hide' : 'Show'} class summary</button>
            {#if showSummary}
              <Markdown content={clazz.summary} />
            {/if}
          {/if}
          <div style="overflow: auto">
            <table class="table table-sm table-hover table-striped">
              <thead>
                <tr>
                  <th>
                    Login<span class="d-none d-md-inline"
                      ><!--
                  --><CopyToClipboard
                        content={clazz.students.map((s) => s.username).join('\n')}
                        title="Copy logins to clipboard">
                        <span class="iconify" data-icon="clarity:clipboard-line"></span>
                      </CopyToClipboard><!--
                  --><CopyToClipboard
                        content={clazz.students.map((s) => s.username + '@vsb.cz').join('\n')}
                        title="Copy emails to clipboard">
                        <span class="iconify" data-icon="ic:round-alternate-email"></span>
                      </CopyToClipboard></span>
                  </th>
                  <th>Student</th>
                  {#each activeTaskList as assignment, index}
                    <th class="more-hover">
                      <a
                        href={assignment.task_link}
                        class:text-muted={assignment.assigned > new Date()}
                        class:text-success={assignment.deadline > new Date()}>
                        {$showFullNames
                          ? assignment.short_name
                          : `#T${clazz.assignments.indexOf(assignment) + 1}`}{#if assignment.max_points > 0}&nbsp;({assignment.max_points}b){/if}
                      </a>
                      <div class="more-content border shadow rounded bg-body p-1">
                        {assignment.name}
                        <a href="/#/task/edit/{assignment.task_id}" title="Edit"
                          ><span class="iconify" data-icon="clarity:edit-solid"></span></a>
                        <div style="display: flex; align-items: center;">
                          <a href={assignment.plagcheck_link} title="Plagiarism check"
                            ><span class="iconify" data-icon="bx:bx-check-double"></span></a>
                          <a href={assignment.sources_link} title="Download all source codes"
                            ><span class="iconify" data-icon="fe:download" data-inline="false"
                            ></span
                            ></a>
                          <a href={assignment.csv_link} title="Download CSV with results"
                            ><span class="iconify" data-icon="la:file-csv-solid"></span></a>
                          <a
                            href="/assignment/show/{assignment.assignment_id}"
                            title="Show all source codes"
                            ><span class="iconify" data-icon="bx-bx-code-alt"></span></a>
                          <button
                            class="btn btn-link p-0"
                            class:spin={reevaluateLoading}
                            title="Reevaluate latest submits"
                            on:click={() => reevaluateAssignment(assignment)}>
                            <span class="iconify" data-icon="bx:bx-refresh"></span>
                          </button>
                          <a
                            href="/statistics/assignment/{assignment.assignment_id}"
                            title="Show assignment stats"
                            ><span class="iconify" data-icon="bx-bx-bar-chart-alt-2"></span></a>
                        </div>
                        <dl>
                          <dt>Assigned</dt>
                          <dd>
                            {assignment.assigned.toLocaleString(
                              'cs'
                            )}{#if assignment.assigned > new Date()}, <TimeAgo
                                datetime={assignment.assigned} />{/if}
                          </dd>

                          {#if assignment.deadline}
                            <dt>Deadline</dt>
                            <dd>
                              {assignment.deadline.toLocaleString(
                                'cs'
                              )}{#if assignment.deadline > new Date()}, <TimeAgo
                                  datetime={assignment.deadline} />{/if}
                            </dd>
                          {/if}

                          {#if assignment.max_points}
                            <dt>Max points</dt>
                            <dd>
                              {assignment.max_points}
                            </dd>
                          {/if}
                        </dl>
                      </div>
                    </th>
                  {/each}
                  {#each activeQuizList as quiz, index}
                    <th class="more-hover">
                      <a
                        href={quiz.quiz_link}
                        class:text-muted={quiz.assigned > new Date()}
                        class:text-success={quiz.deadline > new Date()}>
                        {$showFullNames
                          ? quiz.name_lower
                          : `#Q${index + 1}`}{#if quiz.max_points > 0}&nbsp;({quiz.max_points}b){/if}
                      </a>
                      <div class="more-content border shadow rounded bg-body p-1">
                        {quiz.name}
                        <a href={quiz.quiz_edit_link} title="Edit"
                          ><span class="iconify" data-icon="clarity:edit-solid"></span></a>
                        <dl>
                          <dt>Assigned</dt>
                          <dd>
                            {quiz.assigned.toLocaleString('cs')}{#if quiz.assigned > new Date()}, <TimeAgo
                                datetime={quiz.assigned} />{/if}
                          </dd>

                          {#if quiz.deadline}
                            <dt>Deadline</dt>
                            <dd>
                              {quiz.deadline.toLocaleString('cs')}{#if quiz.deadline > new Date()}, <TimeAgo
                                  datetime={quiz.deadline} />{/if}
                            </dd>
                          {/if}
                          {#if quiz.max_points}
                            <dt>Max points</dt>
                            <dd>
                              {quiz.max_points}
                            </dd>
                          {/if}
                        </dl>
                      </div>
                    </th>
                  {/each}
                  <th
                    class="more-hover"
                    title={task_type === null ? createTaskTypeSummary(activeTaskList) : ''}>
                    Total ({activeTaskList
                      .concat(activeQuizList)
                      .reduce((sum, task) => sum + task.max_points, 0)} pts)
                  </th>
                </tr>
              </thead>

              <tbody>
                {#each clazz.students as student}
                  <tr>
                    <td
                      ><a href="/student/{student.username}" target="_blank">{student.username}</a
                      ></td>
                    <td>{student.last_name} {student.first_name}</td>
                    {#each activeTaskList.map((i) => i.students[student.username]) as result, i}
                      <td>
                        <AssignmentPoints
                          submit_id={result.accepted_submit_id}
                          submits={result.submits}
                          link={result.link}
                          login={student.username}
                          task={clazz.assignments[i].name}
                          color={result.color}
                          assigned_points={result.assigned_points} />
                      </td>
                    {/each}
                    {#each activeQuizList.map((i) => i.students[student.username]) as result, i}
                      <td>
                        {#if result.score != null}<a
                            href={result.scoring_link}
                            style="color: {result.color};">{result.score}</a
                          >{/if}
                      </td>
                    {/each}
                    <td>{studentPoints(activeTaskList, activeQuizList, student)}</td>
                  </tr>
                {/each}
                <tr>
                  <td></td>
                  <td></td>
                  {#each activeTaskList as assignment, k}
                    <td title={createTaskSummary(activeTaskList, clazz, k)}
                      >{totalTaskPoints(activeTaskList, k).toFixed(2)}</td>
                  {/each}
                  {#each activeQuizList as _, k}
                    <td>{totalQuizPoints(clazz, k).toFixed(2)}</td>
                  {/each}
                  <td></td>
                </tr>
              </tbody>
            </table>
          </div>
          {#if clazz.students.length == 0}
            <p class="text-center">No student added yet.</p>
          {/if}
        {/if}
      </div>
    {/if}
  </div>
</div>

<style>
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
