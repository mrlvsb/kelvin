<script>
    import CommentForm from './CommentForm.svelte'
    import Comment from './Comment.svelte'
    import { createEventDispatcher } from 'svelte';

    export let summaryComments;

    let showForm = false;

    const dispatch = createEventDispatcher();

    function addComment(evt) {
        dispatch('saveComment', {
            text: evt.detail,
            success: () => showForm = false,
        });
    }
</script>

<style>
div :global(.CodeMirror) {
    height: 100px;
}

button {
    line-height: normal;
    margin-top: -10px;
}
</style>

{#each summaryComments as comment}
    <Comment {...comment} on:saveComment on:setNotification />
{/each}

{#if showForm}
    <div>
        <CommentForm on:save={addComment} />
    </div>
{:else}
    <button class="btn p-0" on:click={() => showForm = !showForm}>
        <span class="iconify" data-icon="bx:bx-comment-add" data-inline="false" data-flip="vertical" data-height="20" title="Add new comment"></span>
    </button>
{/if}
