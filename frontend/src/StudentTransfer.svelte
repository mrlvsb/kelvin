<script>
import { fetch } from './api.js';

let semester;
let subject;
let teacher;
let clazz;
let student;
let target_class;
let assignments = [];
let busy = false;

let data = null;
let classes = null;
let result = null;

$: notAssignedCount = assignments.filter((t) => !t.dst_assignment_id).length;
//$: uniqueAssignments = new Set(assignments.map(t => t.dst_assignment_id)).length == assignments.length;
$: uniqueAssignments = true;
$: canTransfer = assignments.length && notAssignedCount == 0 && uniqueAssignments && !busy;

async function loadClasses() {
  const res = await fetch('/api/classes/all');
  data = await res.json();
  semester = Object.keys(data.semesters)[Object.keys(data.semesters).length - 1];
}

async function loadClass() {
  let res = await fetch(`/api/classes?semester=${semester}&subject=${subject}`);
  classes = (await res.json())['classes'];
}

$: if (teacher) {
  loadClass();
}

function target_changed() {
  const target = classes.find((c) => c.code == target_class).assignments;

  let index = 0;
  assignments = classes
    .find((c) => c.code == clazz)
    .assignments.map((t) => {
      return {
        name: t.name,
        assigned_points: t.students[student]?.assigned_points || '',
        src_assignment_id: t.assignment_id,
        dst_assignment_id: index < target.length ? target[index++].assignment_id : null
      };
    });
}

async function transfer() {
  busy = true;
  const req = {
    student: student,
    src_class: classes.find((c) => c.code == clazz).id,
    dst_class: classes.find((c) => c.code == target_class).id,
    assignments: assignments
  };

  const res = await fetch('/api/transfer_students', {
    method: 'POST',
    body: JSON.stringify(req)
  });

  result = (await res.json()).transfers;
}

loadClasses();
</script>

{#if data}
  <select bind:value={semester}>
    {#each Object.keys(data.semesters) as item}
      <option value={item}>{item}</option>
    {/each}
  </select>

  <select bind:value={subject}>
    {#if semester}
      {#each Object.keys(data.semesters[semester]) as item}
        <option value={item}>{item}</option>
      {/each}
    {/if}
  </select>

  <select bind:value={teacher}>
    {#if subject}
      {#each Object.keys(data.semesters[semester][subject]) as item}
        <option value={item}>{item}</option>
      {/each}
    {/if}
  </select>

  <select bind:value={clazz}>
    {#if teacher && classes}
      {#each classes.filter((c) => c.teacher_username == teacher) as item}
        <option value={item.code}>{item.timeslot} {item.code}</option>
      {/each}
    {/if}
  </select>

  <select bind:value={student}>
    {#if clazz}
      {#each classes.find((c) => c.code == clazz).students as item}
        <option value={item.username}>{item.username} {item.first_name} {item.last_name}</option>
      {/each}
    {/if}
  </select>

  <select bind:value={target_class} on:change={target_changed}>
    {#if student}
      {#each classes as item}
        <option value={item.code}>{item.teacher_username} {item.timeslot} {item.code}</option>
      {/each}
    {/if}
  </select>

  <table class="table table-hover table-stripped table-sm">
    <tbody>
      {#each assignments as assignment}
        <tr>
          <td>
            {assignment.name}
          </td>

          <td>
            {assignment.assigned_points}
          </td>

          <td>
            <select bind:value={assignment.dst_assignment_id}>
              {#if target_class}
                {#each classes.find((c) => c.code == target_class).assignments as assignment}
                  <option value={assignment.assignment_id}>{assignment.name}</option>
                {/each}
              {/if}
            </select>
          </td>
        </tr>
      {/each}
    </tbody>
  </table>
{/if}

{#if result}
  <table class="table table-sm table-hover table-striped">
    <tbody>
      {#each result as item}
        <tr>
          <td>{item.submit_id}</td>
          <td>{item.before}</td>
          <td>{item.after}</td>
        </tr>
      {/each}
    </tbody>
  </table>
{:else}
  <button
    class="btn btn-success"
    on:click={transfer}
    disabled={!canTransfer}
    class:btn-danger={!canTransfer}>
    {#if busy}
      Transfering...
    {:else}
      Transfer
      {#if !canTransfer}
        (
        {#if assignments.length}
          {#if notAssignedCount > 0}
            {notAssignedCount} tasks needs to be assigned
          {:else}
            Tasks on the right side needs to be unique.
          {/if}
        {:else}
          missing target class
        {/if}
        )
      {/if}
    {/if}
  </button>
{/if}
