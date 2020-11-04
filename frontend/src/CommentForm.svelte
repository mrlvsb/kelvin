<style>
textarea {
  line-height: normal;
}
</style>

<script>
    import { createEventDispatcher } from 'svelte';
    export let comment = '';
    export let disabled = false;

    const dispatch = createEventDispatcher();

  function keydown(evt) {
    if (evt.ctrlKey && evt.keyCode == 13) {
      submit();
    } else if(evt.key == 'Tab') {
      evt.preventDefault();
      const start = this.selectionStart;
      const end = this.selectionEnd;
      this.value = this.value.substring(0, start) + "\t" + this.value.substring(end);
      this.selectionStart = this.selectionEnd = start + 1;
    }
  }

  function submit() {
    dispatch('save', comment);
  }
</script>

<textarea class="form-control mb-1" rows=4 on:keydown={keydown} bind:value={comment} {disabled}></textarea>
<button class="btn btn-sm btn-primary" on:click|preventDefault={submit} {disabled}>Add the comment</button>
