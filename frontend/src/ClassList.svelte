<script>
  import {onMount} from 'svelte';
  import {fetch} from './api.js'
  import ClassDetail from './ClassDetail.svelte'

  let classes = [];
  onMount(async () => {
    classes = await refetch();
  });

  async function refetch() {
    let req = await fetch('/api/classes');
    let res = await req.json();
    return res['classes'];
  }
</script>

{#each classes as clazz}
  <ClassDetail clazz={clazz} on:update={async () => classes = await refetch()} />
{/each}
