<script>
  import {onMount} from 'svelte';
  import {fetch} from './api.js'
  import ClassDetail from './ClassDetail.svelte'
  import {querystring, link} from 'svelte-spa-router'
  import SyncLoader from './SyncLoader.svelte'
  import ClassFilter from './ClassFilter.svelte'
  import {semester, user} from './global.js'

  let classes = null;

  let filter = {
        semester: $semester.abbr,
        subject: null,
        teacher: $user.username,
  };

  onMount(async () => {
    await refetch();
  });

  let prevParams;
  async function refetch() {
    const params = new URLSearchParams(Object.fromEntries(Object.entries(filter).filter(([_, v]) => v))).toString();
    if(prevParams === params) {
        return;
    }
    prevParams = params;

    classes = null;

    const req = await fetch('/api/classes?' + params);
    const res = await req.json();
    classes = res['classes'].map(c => {
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
      if($querystring.length) {
        filter = Object.fromEntries(new URLSearchParams($querystring));
      }
      refetch();
  }
</script>

<div class="container-fluid">
  <div class="d-flex mb-1">
        <ClassFilter semester={filter.semester} subject={filter.subject} teacher={filter.teacher} />

        <a class="btn btn-sm" href="/admin/common/class/add/" title="Add class">
          <span class="iconify" data-icon="ant-design:plus-outlined"></span>
        </a>
  </div>

  {#if !classes}
    <div class="d-flex justify-content-center">
      <SyncLoader />
    </div>
  {:else}
    {#if classes.length}
      {#each classes as clazz}
        <ClassDetail clazz={clazz} on:update={async () => classes = await refetch()} />
      {/each}
    {:else}
      <p class="alert alert-info">No class found, try different filter.</p>
    {/if}
  {/if}
</div>
