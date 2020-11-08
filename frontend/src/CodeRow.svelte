<style>
  span, td, pre {
    padding: 0;
    margin: 0;
    line-height: normal;
  }
  
  tr td:first-of-type {
    text-align: right;
    color: #7e7e7e;
    user-select: none;
    font-size: 87.5%;
    padding-right: 15px;
    vertical-align: top;
  }
  
  tr td:first-of-type span {
    padding-left: 4px;
    font-weight: bold;
    color: black;
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
    border: 2px solid #000000;
    border-radius: 5px;
    max-width: 1000px;
    margin-bottom: 1px;
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
  :global(.comment.teacher) {
    background: #FFFF1ED9;
  }
  :global(.comment.teacher.comment-read) {
    background: #FFFF1E49;
  }
  :global(.comment.student) {
    background: #71F740;
  }
  :global(.comment.student.comment-read) {
    background: #71F74050;
  }
  :global(.comment.automated) {
    background: #7DB4E4;
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

<tr class="linecode">
  <td>
    <span on:click={() => dispatch('showCommentForm', showAddingForm ? -1 : lineNumber)} style="cursor: pointer">+</span>
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
