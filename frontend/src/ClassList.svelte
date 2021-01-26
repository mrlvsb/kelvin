<script>
  import {onMount} from 'svelte';
  import {fetch} from './api.js'
  import ClassDetail from './ClassDetail.svelte'
  import {querystring, link} from 'svelte-spa-router'
  import SyncLoader from './SyncLoader.svelte'


  let classes = null;
  let selectedSubject = null;

  onMount(async () => {
    classes = await refetch();
  });

  async function refetch() {
    let req = await fetch('/api/classes');
    let res = await req.json();
    return res['classes'].map(c => {
      c.assignments = c.assignments.map(assignment => {
        assignment.assigned = new Date(assignment.assigned);
        if(assignment.deadline) {
          assignment.deadline = new Date(assignment.deadline);
        }
        return assignment;
      });
      return c;
    });
  }

  $: {
    const q = Object.fromEntries(new URLSearchParams($querystring));
    if(q['subject']) {
      selectedSubject = q['subject'];
    }
  }
</script>

<div class="container-fluid">
{#if !classes}
  <div class="d-flex justify-content-center">
    <SyncLoader />
  </div>
{:else}
  <div class="d-flex">
    <div>
      {#each [...new Set(classes.map(c => c.subject_abbr))] as subject}
        <a class="mr-2" class:font-weight-bold={selectedSubject == subject} href="/?subject={subject}" use:link>{subject}</a>
      {/each}
    </div>

    <div class="ml-auto">
      <a href="/admin/common/class/add/">Add class</a>
    </div>
  </div>

  {#each classes.filter(c => c.subject_abbr == selectedSubject || selectedSubject == null) as clazz}
    <ClassDetail clazz={clazz} on:update={async () => classes = await refetch()} />
  {/each}
{/if}
</div>
