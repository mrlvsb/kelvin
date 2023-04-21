<script>
  import {fetch} from './api.js'
  import { createEventDispatcher } from 'svelte';

  const dispatch = createEventDispatcher();

  export let class_id;
  export let student_id;

  let removeError = '';

  async function removeStudent() {
    try {
    let req = await fetch(`/api/classes/${class_id}/remove_students`, {
      method: "DELETE",
      body: JSON.stringify({ username: student_id }),
    });
    let res = await req.text(); // get response body as text
    let resJson = JSON.parse(res); // parse response manually
    if (resJson) {
      if (resJson["success"] === true) {
        
        dispatch("remove");
        alert(resJson["username"] + " " + resJson["lastname"]+ " " + resJson["firstname"] + " was successfully removed from class.");
        location.reload()
      } else {
        removeError = resJson["error"] || "Unknown error";
        dispatch("remove");
      }
    }
  } catch (err) {
    alert("We are sorry, but you do not have permission to remove a student from class.");
  }
  }
</script>

<button class="p-0 btn btn-link" on:click= {removeStudent} title="Remove {student_id} from class">
  <span style="color:red;text-align:center;" class="iconify" data-icon="ri:delete-bin-line"></span>
</button>
{#if removeError}
  <span class="text-danger">{removeError}</span>
{/if}
