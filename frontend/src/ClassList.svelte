<script>
  import {onMount} from 'svelte';
  import {fetch} from './api.js'
  import ClassDetail from './ClassDetail.svelte'

  let classes = null;
  let selectedSubject = null;

  onMount(async () => {
    classes = await refetch();
  });

  async function refetch() {
    let req = await fetch('/api/classes');
    let res = await req.json();
    return res['classes'];
  }
</script>

{#if !classes}
  Loading...
{:else}
  {#each [...new Set(classes.map(c => c.subject_abbr))] as subject}
    <button class="btn btn-link p-0 pr-2" class:font-weight-bold={selectedSubject == subject} on:click={() => selectedSubject = subject}>{subject}</button>
  {/each}

  {#each classes.filter(c => c.subject_abbr == selectedSubject || selectedSubject == null) as clazz}
    <ClassDetail clazz={clazz} on:update={async () => classes = await refetch()} />
  {/each}
{/if}
