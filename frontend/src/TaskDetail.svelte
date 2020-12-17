<script>
  import SubmitSource from "./SubmitSource.svelte";
  import SyncLoader from "./SyncLoader.svelte";
  import CopyToClipboard from './CopyToClipboard.svelte'
  import {fetch} from './api.js'
  import SummaryComments from './SummaryComments.svelte'
  import { user } from "./global";
  import { notifications } from './notifications.js'

  export let url;
  let sources = null;
  let summaryComments = [];

  function updateCommentProps(id, newProps) {
    function update(items) {
      return items.map(c => {
        if(c.id == id) {
          if(newProps === null) {
            return null;
          }
          return {...c, ...newProps};
        }
        return c;
      }).filter(c => c !== null);
    }

    sources = sources.map(source => {
      if(source.comments) {
        source.comments = Object.fromEntries(Object.entries(source.comments).map(([lineNum, comments]) => {
          return [lineNum, update(comments)];
        }));
      }
      return source;
    });

    summaryComments = update(summaryComments);
  }

  async function addNewComment(comment) {
    const res = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(comment)
    });

    const json = await res.json();
    if(!comment.source) {
      summaryComments = [
        ...await Promise.all(summaryComments.map(markCommentAsRead)),
        json
      ];
    } else {
      sources = await Promise.all(sources.map(async source => {
        if(source.path === comment.source) {
          let comments = await Promise.all((source.comments[comment.line - 1] || []).map(markCommentAsRead));
          source.comments[comment.line - 1] = [...comments, json];
        }
        return source;
      }));
    }

  }

  async function updateComment(id, text) {
    const res = await fetch(url, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        id: id,
        text: text,
      })
    });

    updateCommentProps(id, text === '' ? null : {text});
  }

  async function saveComment(comment) {
    if(comment.id) {
      await updateComment(comment.id, comment.text);
    } else {
      await addNewComment(comment);
    }
    if(comment.success) {
      comment.success();
    }
  }

  async function markCommentAsRead(comment) {
    if(comment.unread && comment.author_id !== $user.id && comment.notification_id) {
      await notifications.markRead(comment.notification_id);
      comment.unread = false;
    }
    return comment;
  }

  async function setNotification(evt) {
    async function walk(comments) {
      if(comments.filter(c => c.id === evt.detail.comment_id).length) {
        for(const comment of comments) {
          if(comment.unread && comment.author_id !== $user.id && comment.notification_id) {
            await notifications.markRead(comment.notification_id);
            updateCommentProps(comment.id, {unread: evt.detail.unread});
          }
        }
      }
    }

    await walk(summaryComments);
    for(const source of sources) {
      if(source.comments) {
        for(const comments of Object.values(source.comments)) {
          await walk(comments);
        }
      }
    }
  }

  async function load() {
    const res = await fetch(url);
    const json = await res.json();
    sources = json['sources'];
    summaryComments = json['summary_comments'];
  }
  load();
</script>

<style>
  video,
  img {
    max-width: 100%;
  }
</style>

{#if sources === null}
  <div class="d-flex justify-content-center">
    <SyncLoader />
  </div>
{:else}
  <SummaryComments {summaryComments} on:saveComment={evt => saveComment(evt.detail)} on:setNotification={setNotification} />

  {#each sources as source}
    <h2>
      {source.path}{#if source.type == 'source'}<CopyToClipboard content={() => source.content} title='Copy the source code to the clipboard'><span class="iconify" data-icon="clarity:copy-to-clipboard-line" style="height: 20px"></span></CopyToClipboard>{/if}
    </h2>
    {#if source.type == 'source' }
      {#if source.content_url }
        Content too large, show <a href="{ source.content_url }">raw content</a>.
      {:else}
        <SubmitSource
        code={source.content}
        comments={source.comments}
        on:setNotification={setNotification}
        on:saveComment={evt => saveComment({...evt.detail, source: source.path})} />
      {/if}
    {:else if source.type === 'img'}
      <img src={source.src} />
    {:else if source.type === 'video'}
      <video controls>
        {#each source.sources as src}
          <source {src} />
        {/each}
      </video>
    {:else}The preview cannot be shown.{/if}
  {/each}
{/if}
