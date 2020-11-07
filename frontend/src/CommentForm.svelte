<style>
:global(.comment .CodeMirror) {
  height: 100px;
}
</style>

<script>
    import { createEventDispatcher } from 'svelte';
    import Editor from './Editor.svelte'
    export let comment = '';
    export let disabled = false;

    const dispatch = createEventDispatcher();

  function submit() {
    dispatch('save', comment);
  }
</script>

<Editor bind:value={comment} filename="comment.md" {disabled} autofocus extraKeys={{'Ctrl-Enter': submit}} /> 
<button class="btn btn-sm btn-primary mt-1" on:click|preventDefault={submit} {disabled}>Add comment</button>
