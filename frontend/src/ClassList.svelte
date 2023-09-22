<script>
  import {onMount} from 'svelte';
  import {fetch} from './api.js'
  import ClassDetail from './ClassDetail.svelte'
  import {querystring, link} from 'svelte-spa-router'
  import SyncLoader from './SyncLoader.svelte'
  import ClassFilter from './ClassFilter.svelte'
  import {semester, user} from './global.js'

  let classes = null;
  let loading = true;

  let filter = {
        semester: $semester.abbr,
        subject: null,
        teacher: $user.username,
        class: null,
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
    loading = true;

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
    loading = false;
  }

  $: {
      if($querystring.length) {
        filter = Object.fromEntries(new URLSearchParams($querystring));
      }
      refetch();
  }
</script>

<style>
  .loading-animation {
    visibility: hidden;
    position: absolute;
    width: 100%;
    pointer-events: none;
    z-index: 2;
  }

  .loading {
    position: relative;
  }

  .loading .loading-animation {
    visibility: visible;
  }

  .loading .classes-inner {
    opacity: 0.5;
    pointer-events: none;
  }
</style>

<div class="container-fluid p-1">
  <div class="d-flex mb-1">
        <ClassFilter
            semester={filter.semester}
            subject={filter.subject}
            teacher={filter.teacher}
            clazz={filter.class} />

        <a class="btn btn-sm p-1" href="/#/import" title="Bulk import students from EDISON">
          <span class="iconify" data-icon="mdi:calendar-import"></span>
        </a>

        {#if $user.is_staff}
        <a class="btn btn-sm p-1" href="/admin/common/class/add/" title="Add class">
          <span class="iconify" data-icon="ant-design:plus-outlined"></span>
        </a>
        {/if}
  </div>

  <div class="classes" class:loading>
    <div class="d-flex justify-content-center loading-animation">
      <SyncLoader />
    </div>

    <div class="classes-inner">
      {#if classes && classes.length}
        {#each classes as clazz (clazz.id)}
          <ClassDetail clazz={clazz} on:update={async () => {prevParams = null; await refetch();}} />
        {/each}
      {:else if classes !== null}
        <p class="alert alert-info">No class found, try different filter.</p>
      {/if}
    </div>
  </div>
</div>
