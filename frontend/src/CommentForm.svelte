<script>
    import { createEventDispatcher } from 'svelte';
    export let comment = '';
    export let disabled = false;

    const dispatch = createEventDispatcher();

  function keydown(evt) {
    if (evt.ctrlKey && evt.keyCode == 13) {
      submit();
    }
  }

  function submit() {
    dispatch('save', comment);
  }
</script>

<textarea class="form-control mb-1" rows=4 on:keydown={keydown} bind:value={comment} {disabled}></textarea>
<button class="btn btn-sm btn-primary" on:click|preventDefault={submit} {disabled}>Add the comment</button>
