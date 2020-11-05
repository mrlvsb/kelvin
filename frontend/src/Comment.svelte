<script>
    import CommentForm from './CommentForm.svelte'
    import { createEventDispatcher } from 'svelte';
    import marked from 'marked'
    import hljs from 'highlight.js/lib/core'
    import DOMPurify from 'dompurify';

    marked.setOptions({
      highlight: function(code, lang) {
        if(lang) {
          return hljs.highlight(lang, code).value;
        }
        return hljs.highlightAuto(code).value;
      },
      breaks: true,
    });

    function sanitize(string) {
      const map = {
          '&': '&amp;',
          '<': '&lt;',
          '>': '&gt;',
          '"': '&quot;',
          "'": '&#x27;',
          "/": '&#x2F;',
      };
      const reg = /[&<>"'/]/ig;
      return string.replace(reg, (match)=>(map[match]));
    }


    export let author;
    export let text;
    export let type;
    export let id;
    export let can_edit;
    export let url = null;

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
  <strong>{author}</strong>: 
  {#if !editing}
    {#if type == 'automated'}
      {text}
      {#if url}
        <a href="{url}">
          <span class="iconify" data-icon="entypo:help"></span>
        </a>
      {/if}
    {:else}
      {@html DOMPurify.sanitize(marked(sanitize(text)))}
    {/if}
  {:else}
    <CommentForm comment={text} on:save={updateComment} disabled={sending} />
  {/if}
</div>
