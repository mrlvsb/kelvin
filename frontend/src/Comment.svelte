<script>
    import CommentForm from './CommentForm.svelte'
    import { createEventDispatcher } from 'svelte';


    export let author;
    export let text;
    export let type;
    export let id;
    export let can_edit;

    const dispatch = createEventDispatcher();

    let editing = false;
    let sending = false;
  
    function updateComment(evt) {
      sending = true;
      dispatch('saveComment', {
        id: id,
        text: evt.detail,
        success: () => editing = sending = false,
      })
    }

</script>

<div class="comment {type}" on:dblclick={() => editing = can_edit}>
  <strong>{author}</strong>: {#if !editing}{text}{:else}<CommentForm comment={text} on:save={updateComment} disabled={sending} />{/if}
</div>
