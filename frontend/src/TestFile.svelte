<script>
  import SyncLoader from "./SyncLoader.svelte";

  export let url;
  export let path;
  let folded = true;
  let fetched = false;
  let data = null;
  const maxInlineContentBytes = 64565;

  async function getRawFile() {
    if (!fetched) {
      const res = await fetch(url);
      fetched = true;
      if (res.ok && parseInt(res.headers.get("Content-Length")) <= maxInlineContentBytes) {
        data = await res.text();
      }
    }
  }
</script>

<div class="card mb-3">
  <div class="card-header d-flex align-items-center justify-content-between">
    <button class="btn" on:click={() => folded = !folded}>
      <h5>{ path }</h5>
    </button>
    <a href="{ url }">Raw content</a>
  </div>
    {#if !folded}
      <div class="card-body">
      {#await getRawFile()}
        <SyncLoader />
      {:then}
        {#if data == null}
          Content too large, show <a href="{ url }">raw content</a>.
        {:else}
          <pre>{ data }</pre>
        {/if}
      {/await}
    </div>
  {/if}
</div>
