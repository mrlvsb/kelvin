<script>
import CommentForm from './CommentForm.svelte';
import { safeMarkdown } from './markdown.js';
import { user } from './global.js';
import { hideComments, HideCommentsState } from './stores';
import { createEventDispatcher, onMount } from 'svelte';
import Toast from 'bootstrap/js/dist/toast';

export let id;
export let author;
export let text;
export let meta;
export let files;
export let rating;
export let summary = false;

let toast = null;

if (rating === undefined) {
  rating = 0;
}

const dispatch = createEventDispatcher();

let editing = false;
let sending = false;
let processed = false;

async function handleAccept() {
  sending = true;
  const suggestionId = meta.review.id;

  const res = await fetch(`/api/v2/llm/suggestions/${suggestionId}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    }
  });

  const json = await res.json();

  if (!res.ok) {
    showToast(json.detail, 'warning');
    return;
  }

  dispatch('resolveSuggestion', {
    id: suggestionId,
    comment: json
  });

  processed = true;
  sending = false;
}

async function handleReject() {
  sending = true;
  const suggestionId = meta.review.id;

  const res = await fetch(`/api/v2/llm/suggestions/${suggestionId}`, {
    method: 'DELETE',
    headers: {
      'Content-Type': 'application/json'
    }
  });

  const json = await res.json();

  if (!res.ok) {
    showToast(json.detail, 'warning');
    return;
  }

  processed = true;
  sending = false;
}

// Modification, first edit, then save

function handleEdit() {
  editing = true;
}

async function handleSave(event) {
  sending = true;
  const suggestionId = meta.review.id;

  const res = await fetch(`/api/v2/llm/suggestions/${suggestionId}`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      modified_text: event.detail
    })
  });

  const json = await res.json();

  if (!res.ok) {
    showToast(json.detail, 'warning');
    editing = false;
    return;
  }

  dispatch('resolveSuggestion', {
    id: suggestionId,
    comment: json
  });

  processed = true;
  sending = false;
  editing = false;
}

function showToast(message, status = 'success') {
  if (toast) {
    toast.querySelector('.toast-body').textContent = message;

    let bg_color = 'bg-success';
    let text_color = 'text-white';

    if (status === 'error') {
      bg_color = 'bg-danger';
    } else if (status === 'warning') {
      bg_color = 'bg-warning';
      text_color = 'text-dark';
    }

    // Update toast color based on status
    toast.className = `toast align-items-center ${text_color} ${bg_color} border-0`;

    new Toast(toast).show();
  }
}
</script>

<div class="position-fixed top-0 end-0 mt-5 me-3">
  <div
    class="toast align-items-center text-white bg-success border-0"
    role="alert"
    aria-live="assertive"
    aria-atomic="true"
    bind:this={toast}>
    <div class="d-flex">
      <div class="toast-body">Unexpected error occurred. Please try again later.</div>

      <button
        type="button"
        class="btn-close btn-close-dark me-2 m-auto"
        data-bs-dismiss="toast"
        aria-label="Close" />
    </div>
  </div>
</div>

{#if !($hideComments === HideCommentsState.AUTOMATED || $hideComments === HideCommentsState.ALL)}
  {#if $user?.teacher && !processed}
    <div class="comment ai-review">
      <div class="comment-header">
        <strong>{author}</strong>

        {#if $user?.teacher && !editing}
          <div class="comment-actions">
            {#if summary === true}
              <button title="Dismiss" class="icon-button" on:click|preventDefault={handleReject}>
                <span class="iconify" data-icon="cil-x"></span>
              </button>
            {:else}
              <button
                title="Turn into a student-visible comment"
                class="icon-button"
                on:click|preventDefault={handleAccept}>
                <span class="iconify" data-icon="cil-check"></span>
              </button>
              <button title="Edit" class="icon-button" on:click|preventDefault={handleEdit}>
                <span class="iconify" data-icon="cil-pencil"></span>
              </button>
              <button title="Reject" class="icon-button" on:click|preventDefault={handleReject}>
                <span class="iconify" data-icon="cil-x"></span>
              </button>
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
