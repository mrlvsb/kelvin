<script>
import SyncLoader from './SyncLoader.svelte';

export let submitid;
let job_status = '';
let message = '';

async function update() {
  const res = await fetch(`/submit/${submitid}/pipeline`);
  const json = await res.json();

  if (json.finished) {
    document.location.reload();
  } else {
    job_status = json['status'];
    message = json['message'];
    setTimeout(update, 1000);
  }
}

update();
</script>

{#if job_status == 'failed'}
  <h2 class="text-danger text-center"><b>Evaluation failed - please contact your teacher.</b></h2>

  <pre>{message}</pre>
{:else}
  <div class="main">
    Your submit is being processed, please wait.<br />
    Your submit has been uploaded to Kelvin, it won't be lost if you close the browser.<br />
    {job_status}
    <div class="d-flex justify-content-center">
      <SyncLoader />
    </div>
  </div>
{/if}

<style>
div.main {
  font-size: 1.5rem;
  font-weight: bold;
  text-align: center;
}
</style>
