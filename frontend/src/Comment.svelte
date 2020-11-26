<script>
    import CommentForm from './CommentForm.svelte'
    import { createEventDispatcher } from 'svelte';
    import marked from 'marked'
    import hljs from 'highlight.js/lib/core'
    import DOMPurify from 'dompurify';
    import { user } from './global';

    marked.setOptions({
      highlight: function(code, lang) {
        if(lang) {
          try {
            return hljs.highlight(lang, code).value;
          } catch (err) {
            if(typeof(Sentry) !== 'undefined') {
              Sentry.captureException(err);
            }
          }
        }
        return hljs.highlightAuto(code).value;
      },
      breaks: true,
    });

    export let author;
    export let author_id = null;
    export let text;
    export let type;
    export let id;
    export let can_edit;
    export let url = null;
    export let unread = null;
    export let notification_id = null;

    const dispatch = createEventDispatcher();

    const sanitizeOpts = {
      ALLOWED_TAGS: [
        'img', 'p', 'b', 'strong', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'a', 'i', 'ul', 'ol', 'li', 'pre', 'code', 'a', 'br', 'span'
      ],
      ALLOWED_ATTR: [
        'href', 'src', 'class',
      ]
    };

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
      {@html DOMPurify.sanitize(marked(text), sanitizeOpts)}
    {/if}
  {:else}
    <CommentForm comment={text} on:save={updateComment} disabled={sending} />
  {/if}
</div>
