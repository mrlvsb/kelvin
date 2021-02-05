<script>
  import {link} from 'svelte-spa-router'
  import {fetch} from './api.js'
  import {user} from './global.js'
  import CopyToClipboard from './CopyToClipboard.svelte'
  import TimeAgo from './TimeAgo.svelte'
  import {localStorageStore} from './utils.js'
  import AddStudentsToClass from './AddStudentsToClass.svelte'
  import Markdown from './Markdown.svelte'

  import { createEventDispatcher } from 'svelte';
  const dispatch = createEventDispatcher();

  export let clazz;
  export let showStudentsList = clazz['students'].length < 50; 

  let showAddStudents = clazz.students.length == 0;

  let reevaluateLoading = false;
  async function reevaluateAssignment(assignment) {
    reevaluateLoading = true;
    const submit_ids = Object.values(assignment.students)
      .map(stud => stud['accepted_submit_id'])
      .filter(id => id);

    for(const submit_id of submit_ids) {
      await fetch('/reevaluate/' + submit_id);
    }
    reevaluateLoading = false;
  }

  function studentPoints(clazz, student) {
      return clazz.assignments
          .map(i => i.students[student.username])
          .filter(result => result && result.submits != 0 && !isNaN(parseFloat(result.assigned_points)))
          .map(result => parseFloat(result.assigned_points))
          .reduce((acc, val) => acc + val, 0);
  }

  let showFullTaskNames = localStorageStore('classDetail/showFullTaskNames', false);
  let showSummary = false;
</script>

<style>
td, th {
  white-space: nowrap;
  width: 1%;
}
tr th:last-of-type,td:last-of-type {
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
    transform:rotate(0deg);
  }
  to {
    transform:rotate(360deg);
  }
}

.more-content {
  display: none;
  text-align: left;
}

.more-hover {
  position: relative;
}

.more-hover:hover .more-content {
  position: absolute;
  display: block;
  background: white;
  padding: 3px;
  border: 1px solid #dee2e6;
  font-weight: normal;
  z-index: 10;
}

</style>

<div class="card mb-2" style="position: initial">
  <div class="card-header p-0">
      <div class="float-right p-2" style="display: flex; align-items: center;">
        <a href="/task/add/{clazz.subject_abbr}" use:link title="Assign new task">
          <span class="iconify" data-icon="bx:bx-calendar-plus"></span>
        </a>
        <button class="p-0 btn btn-link"
                on:click={() => showAddStudents = !showAddStudents}
                title="Add user to class">
          <span class="iconify" data-icon="ant-design:user-add-outlined"></span>
        </button>
        <a href="{clazz.csv_link}" title="Download CSV with results for all task">
          <span class="iconify" data-icon="la:file-csv-solid"></span>
        </a>
        <button class="p-0 btn btn-link"
                on:click={() => $showFullTaskNames = !$showFullTaskNames}
                title="Show full task names">
          {#if $showFullTaskNames }
            <span><span class="iconify" data-icon="la:eye"></span></span>
          {:else}
            <span><span class="iconify" data-icon="la:eye-slash"></span></span>
          {/if}
        </button>
      </div>
      <button class="btn" on:click={() => showStudentsList = !showStudentsList}>
          {clazz.subject_abbr} {clazz.timeslot} {clazz.code} {clazz.teacher_username}
          <span class="text-muted">({clazz.students.length} students)</span>
      </button>
  </div>
  <div> 
  {#if showStudentsList || showAddStudents}
    <div class="card-body">
      {#if showAddStudents}
        <AddStudentsToClass class_id={clazz.id} on:update />
      {/if}

      {#if showStudentsList}
        {#if clazz.summary }
          <button class="p-0 btn btn-link"
                    on:click={() => showSummary = !showSummary}>{showSummary ? "Skrýt" : "Zobrazit"} informace o cvičení</button>
          {#if showSummary }
            <Markdown content={clazz.summary} />
          {:else}
          {/if}
        {/if}
        <table class="table table-sm table-hover">
          <thead>
            <tr>
              <th>
                Login<!--
                --><CopyToClipboard content={clazz.students.map(s => s.username).join('\n')} title='Copy logins to clipboard'>
                  <span class="iconify" data-icon="clarity:clipboard-line"></span>
                </CopyToClipboard><!--
                --><CopyToClipboard content={clazz.students.map(s => s.username + '@vsb.cz').join('\n')} title='Copy emails to clipboard'>
                  <span class="iconify" data-icon="ic:round-alternate-email"></span>
                </CopyToClipboard>
              </th>
              <th>Student</th>
              {#each clazz.assignments as assignment, index}
              <th class="more-hover">
                <a href="/task/{ $user.username }/{ assignment.assignment_id }" 
                   class:text-muted={assignment.assigned > new Date()}
                   class:text-success={assignment.deadline > new Date()}>
                  { $showFullTaskNames ? assignment.short_name : `#${index+1}` }{#if assignment.max_points > 0}&nbsp;({ assignment.max_points }b){/if}
                </a>
                <div class="more-content">
                  {assignment.name}
                  <a href="/task/edit/{assignment.task_id}" use:link title="Edit"><span class="iconify" data-icon="clarity:edit-solid"></span></a>
                  <div style="display: flex; align-items: center;">
                    <a href="{assignment.moss_link}" title="Send to MOSS"><span class="iconify" data-icon="bx:bx-check-double"></span></a>
                    <a href="{assignment.sources_link}" title="Download all source codes"><span class="iconify" data-icon="fe:download" data-inline="false"></span></a>
                    <a href="{assignment.csv_link}" title="Download CSV with results"><span class="iconify" data-icon="la:file-csv-solid"></span></a>
                    <a href="/assignment/show/{assignment.assignment_id}" title="Show all source codes"><span class="iconify" data-icon="bx-bx-code-alt"></span></a>
                    <button class="btn btn-link p-0" class:spin={reevaluateLoading} title='Reevaluate latest submits' on:click={() => reevaluateAssignment(assignment)}>
                      <span class="iconify" data-icon="bx:bx-refresh"></span>
                    </button>
                    <a href="/statistics/assignment/{assignment.assignment_id}" title="Show assignment stats"><span class="iconify" data-icon="bx-bx-bar-chart-alt-2"></span></a>
                  </div>
                  <dl>
                    <dt>Assigned</dt>
                    <dd>
                      {assignment.assigned.toLocaleString('cs')}{#if assignment.assigned > new Date()}, <TimeAgo datetime={assignment.assigned} />{/if}
                    </dd>

                    {#if assignment.deadline}
                    <dt>Deadline</dt>
                    <dd>
                      {assignment.deadline.toLocaleString('cs')}{#if assignment.deadline > new Date()}, <TimeAgo datetime={assignment.deadline} />{/if}
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
              <th>Celkem</th>
            </tr>
          </thead>

          <tbody>
          {#each clazz.students as student}
          <tr>
            <td>{ student.username }</td>
            <td>{ student.last_name } { student.first_name }</td>
            {#each clazz.assignments.map(i => i.students[student.username]) as result}
              <td>
                {#if result.submits != 0}
                  <a href={result.link} style="color: {result.color}">
                    { isNaN(parseFloat(result.assigned_points)) ? '?' : result.assigned_points}
                  </a>
                {/if}
              </td>
            {/each}
            <td>{studentPoints(clazz, student)}</td>
          </tr>
          {/each}
          </tbody>
        </table>
        {#if clazz.students.length == 0}
          <p class="text-center">
            No student added yet.
          </p>
        {/if}
      {/if}
    </div>
    {/if}
  </div>
</div>
