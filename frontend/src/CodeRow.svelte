<style>
  span, td, pre {
    padding: 0;
    margin: 0;
    line-height: normal;
  }
  
  tr td:first-of-type {
    user-select: none;
    font-size: .87em;
    cursor: row-resize;
  }
  
  tr td:first-of-type span {
    visibility: hidden;
  }
  
  tr:hover td:first-of-type span {
    visibility: visible;
  }
  
  tr.linecode {
    counter-increment: my-sec-counter;
  }
  tr.linecode td:first-of-type::before {
    content: counter(my-sec-counter);
  }
  tr.linecode td:last-of-type {
    width: 100%;
  }
  
  :global(.comment) {
    padding: 5px;
    word-break: break-word;
    border: 2px solid var(--bs-body-color);
    border-radius: 5px;
    max-width: 980px;
    margin-bottom: 1px;
    filter: opacity(.8);
  }
  :global(.comment p) {
    margin-bottom: 4px;
    white-space: pre-line;
  }
  :global(.comment ul, .comment ol) {
    padding-left: 20px;
  }
  :global(.comment p:last-of-type:first-of-type) {
    display: inline;
  }
  :global(.comment p:last-of-type) {
    margin-bottom: 0;
  }

  /* Light style comments */
  :global(html[data-bs-theme="light"] .comment.teacher) {
    background: #FFFF1ED9;
  }
  :global(html[data-bs-theme="light"] .comment.teacher.comment-read) {
      background: #FFFF1E49;
  }
  :global(html[data-bs-theme="light"] .comment.student) {
      background: #71F740;
  }
  :global(html[data-bs-theme="light"] .comment.student.comment-read) {
      background: #71F74050;
  }
  :global(html[data-bs-theme="light"] .comment.automated) {
      background: #7DB4E4;
  }

  /* Dark style comments */
  :global(html[data-bs-theme="dark"] .comment) {
      color: #FFFFFF;
  }
  :global(html[data-bs-theme="dark"] .comment.teacher) {
      background: #B3B32A;
  }
  :global(html[data-bs-theme="dark"] .comment.teacher.comment-read) {
      background: #FFFF1E49;
  }
  :global(html[data-bs-theme="dark"] .comment.student) {
      background: #2F8510;
  }
  :global(html[data-bs-theme="dark"] .comment.student.comment-read) {
      background: #2A4A1E;
  }
  :global(html[data-bs-theme="dark"] .comment.automated) {
      background: #083154;
  }

  .selected {
    background: #ffff9349;
  }
  
  </style>
  

<script>
  import { createEventDispatcher } from 'svelte'
  import CommentForm from './CommentForm.svelte'
  import Comment from './Comment.svelte'
  import {user} from './global.js'

  export let line;
  export let lineNumber;
  export let comments = [];
  export let showAddingForm = false;
  export let selected = false;
  export let scroll = false;

  let addingInProgress = false;

  const dispatch = createEventDispatcher();

  function addNewComment(evt) {
    if(evt.detail === '') {
      dispatch('showCommentForm', -1);
    } else {
      addingInProgress = true;
      dispatch('saveComment', {
        line: lineNumber,
        text: evt.detail,
        success: function() {
          dispatch('showCommentForm', -1);
          addingInProgress = false;
        },
      });
    }
  }
  
</script>

<tr class="linecode" class:selected={selected} data-line="{lineNumber}">
  <td class="text-end align-baseline me-2">
    <span on:click={() => dispatch('showCommentForm', showAddingForm ? -1 : lineNumber)} style="cursor: pointer"><b>+</b></span>
  </td>
  <td>
    <pre>{@html line}</pre>
    {#each comments||[] as comment}
      <Comment {...comment} on:saveComment on:setNotification />
    {/each}

    {#if showAddingForm}
      <div class="comment {$user.teacher ? 'teacher' : 'student'}">
        <CommentForm on:save={addNewComment} disabled={addingInProgress} />
      </div>
    {/if}
  </td>
</tr>
