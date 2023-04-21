<script>
    import CommentForm from './CommentForm.svelte'
    import { createEventDispatcher } from 'svelte';
    import { user } from './global';
    import { safeMarkdown } from './markdown.js'

    export let author;
    export let author_id = null;
    export let text;
    export let type;
    export let id;
    export let can_edit;
    export let url = null;
    export let unread = null;

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

    function handleNotification() {
      dispatch('setNotification', {
        comment_id: id,
        unread: !unread,
      })
    }
</script>

  <div style="display: flex; flex-direction: row;">
    <div class="comment comment-{unread ? 'unread' : 'read'} {type}" on:dblclick={() => editing = can_edit}>
      <strong>{author}</strong>:
      {#if !editing}
        {#if type == 'automated'}
          {text}
          {#if url}
            <a href="{url}">
              <span class="iconify" data-icon="entypo:help"></span>
            </a>
          {/if}
        {:else if $user}
          {#if unread && type != 'automated' && author_id != $user.id}
            <button class="btn p-0 float-right" on:click|preventDefault={handleNotification} style="line-height: normal">
              <span class="iconify" data-icon="cil-check"></span>
            </button>
          {/if}
          {@html safeMarkdown(text)}
        {/if}
      {:else}
        <CommentForm comment={text} on:save={updateComment} disabled={sending} />
      {/if}
    </div>
  </div> 