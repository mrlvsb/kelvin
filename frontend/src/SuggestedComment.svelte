<script>
import CommentForm from './CommentForm.svelte';
import { safeMarkdown } from './markdown.js';
import { user } from './global.js';
import { hideComments, HideCommentsState } from './stores';
import { createEventDispatcher } from 'svelte';

export let id;
export let author;
export let text;
export let meta;
export let files;
export let rating;
export let summary = false;

if (rating === undefined) {
  rating = 0;
}

const dispatch = createEventDispatcher();

let editing = false;
let sending = false;
let processed = false;
let hoverRating = 0;

async function handleAccept() {
  sending = true;
  const suggestionId = meta.review.id;

  const res = await fetch(`/api/v2/llm/suggestions/resolve/${suggestionId}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    }
  });

  const json = await res.json();

  dispatch('resolveSuggestion', {
    id: suggestionId,
    comment: json
  });

  processed = true;
  sending = false;
}

async function handleDeny() {
  sending = true;
  const suggestionId = meta.review.id;

  await fetch(`/api/v2/llm/suggestions/resolve/${suggestionId}`, {
    method: 'DELETE',
    headers: {
      'Content-Type': 'application/json'
    }
  });

  processed = true;
  sending = false;
}

function handleEdit() {
  editing = true;
}

async function handleSave(event) {
  sending = true;
  const suggestionId = meta.review.id;

  const res = await fetch(`/api/v2/llm/suggestions/resolve/${suggestionId}`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      modified_text: event.detail
    })
  });

  const json = await res.json();

  dispatch('resolveSuggestion', {
    id: suggestionId,
    comment: json
  });

  processed = true;
  sending = false;
  editing = false;
}

async function handleDismiss() {
  sending = true;
  const suggestionId = meta.review.id;

  await fetch(`/api/v2/llm/suggestions/dismiss/${suggestionId}`, {
    method: 'DELETE',
    headers: {
      'Content-Type': 'application/json'
    }
  });

  processed = true;
  sending = false;
}
</script>

{#if !(($hideComments === HideCommentsState.AUTOMATED && meta?.type === 'ai-review') || $hideComments === HideCommentsState.ALL)}
  {#if $user?.teacher && meta?.review?.state === 'PENDING' && !processed}
    <div class="comment ai-review">
      <div class="comment-header">
        <strong>{author}</strong>

        {#if $user?.teacher && !editing}
          <div class="comment-actions">
            {#if meta?.review?.state === 'PENDING'}
              {#if summary === true}
                <button title="Accept" class="icon-button" on:click|preventDefault={handleDismiss}>
                  <span class="iconify" data-icon="cil-check"></span>
                </button>
              {:else}
                <button title="Accept" class="icon-button" on:click|preventDefault={handleAccept}>
                  <span class="iconify" data-icon="cil-check"></span>
                </button>
                <button title="Edit" class="icon-button" on:click|preventDefault={handleEdit}>
                  <span class="iconify" data-icon="cil-pencil"></span>
                </button>
                <button title="Decline" class="icon-button" on:click|preventDefault={handleDeny}>
                  <span class="iconify" data-icon="cil-x"></span>
                </button>
              {/if}
            {/if}
          </div>
        {/if}
      </div>

      {#if !editing}
        <div class="comment-text">
          {@html safeMarkdown(text)}
        </div>
      {:else}
        <CommentForm comment={text} on:save={handleSave} disabled={sending} />
      {/if}
    </div>
  {/if}
{/if}

<style>
.comment-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.comment-actions {
  display: flex;
  gap: 0.4rem;
}

.icon-button {
  cursor: pointer;
  border: none;
  background: none;
  font-size: 1rem;
  line-height: 1;
  padding: 0.2rem;
  border-radius: 4px;
  transition: color 0.2s;
}

.icon-button:hover {
  color: black;
}
</style>
