<script>
import { fetch } from './api.js';
import { createEventDispatcher } from 'svelte';

const dispatch = createEventDispatcher();

export let class_id;

let addStudentError = [];
let textarea = '';
let processing = false;

function pasteLogins(event) {
  const paste = (event.clipboardData || window.clipboardData).getData('text').toUpperCase();

  const logins = Array.from(paste.matchAll(/\b([A-Z]{3}[0-9]{2,4})\b/g)).map((m) => m[1]);
  if (logins.length) {
    event.preventDefault();
    logins.sort();
    textarea = [...new Set(logins)].join('\n');
  }
}

async function addStudents() {
  addStudentError = [];
  const logins = textarea
    .split('\n')
    .map((login) => login.replace(/^\s+|\s+$/g, ''))
    .filter((login) => login.length);

  if (!logins.length) {
    return;
  }

  processing = true;

  try {
    let req = await fetch(`/api/classes/${class_id}/add_students`, {
      method: 'POST',
      body: JSON.stringify({ username: logins })
    });
    let res = await req.json();
    if (res) {
      if (res['not_found'].length) {
        addStudentError =
          'Not found users left in textarea. Already assigned students are separated by a newline';
        textarea = res['not_found'].filter((x) => !res['already_assigned'].includes(x)).join('\n');
        textarea += '\n\n';
        textarea += res['already_assigned'].join('\n');
        dispatch('update');
      } else if (res['success'] === true) {
        textarea = '';
        dispatch('update');
      } else {
        addStudentError = res['error'] || 'Unknown error';
      }
    }
  } catch (err) {
    addStudentError = 'Error: ' + err;
  }

  processing = false;
}
</script>

<form class="p-0 mb-2">
  <textarea
    disabled={processing}
    on:paste={pasteLogins}
    bind:value={textarea}
    class="form-control mb-1"
    rows="20"
    placeholder="Add student logins to this class
May contain surrounding text or HTML" />
  <button class="btn btn-primary" on:click|preventDefault={addStudents} disabled={processing}>
    {#if !processing}
      Add
    {:else}
      <div class="spinner-border spinner-border-sm"></div>
    {/if}
  </button>
</form>
{#if addStudentError}
  <span class="text-danger">{addStudentError}</span>
{/if}
