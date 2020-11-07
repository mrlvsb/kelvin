<script>
  import SubmitSource from "./SubmitSource.svelte";
  import SyncLoader from "./SyncLoader.svelte";
  import CopyToClipboard from './CopyToClipboard.svelte'
  import {fetch} from './api.js'
  import CommentForm from './CommentForm.svelte'
  import Comment from './Comment.svelte'

  export let url;
  let sources = null;
  let summaryComments = [];

  async function addNewComment(comment) {
    const res = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(comment)
      });

      return await res.json();
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
  }

  async function saveComment(evt) {
    if(evt.detail.id === undefined) {
      const json = await addNewComment({
        text: evt.detail.text,
        source: evt.detail.source,
        line: evt.detail.line,
      });

      sources = sources.map(source => {
        if(source.path === evt.detail.source) {
          (source.comments[evt.detail.line - 1] = source.comments[evt.detail.line - 1] || []).push(json);
        }
        return source;
      });
    } else {
      await updateComment(evt.detail.id, evt.detail.text);
      
      sources = sources.map(source => {
        if(evt.detail.text == '') {
          source.comments = Object.fromEntries(Object.entries(source.comments).map(([lineNum, comments]) => {
            return [lineNum, comments.filter(comment => comment.id !== evt.detail.id)];
          }));
        } else {
          source.comments = Object.fromEntries(Object.entries(source.comments).map(([lineNum, comments]) => {
            return [lineNum, comments.map(comment => {
              if(comment.id === evt.detail.id) {
                  comment.text = evt.detail.text;
              }
              return comment;
            })];
          }));
        }
        return source;
      });
    }
    
    if(evt.detail.success) {
      evt.detail.success();
    }
  }

  async function addSummaryComment(evt) {
    const res = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        text: evt.detail
      })
    });

    summaryComments = [...summaryComments, await res.json()];
  }

  async function updateSummaryComment(evt) {
    await updateComment(evt.detail.id, evt.detail.text);

    summaryComments = summaryComments.map(c => {
      if(c.id === evt.detail.id) {
        if(evt.detail.text === '') {
          return null;
        }
        c.text = evt.detail.text;
      }
      return c;
    }).filter(c => c !== null);

    if(evt.detail.success) {
      evt.detail.success();
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
  
  {#each summaryComments as comment}
    <Comment {...comment} on:saveComment={updateSummaryComment} />
  {/each}

  <CommentForm on:save={addSummaryComment} />

  {#each sources as source}
    <h2>
      {source.path}{#if source.type == 'source'}<CopyToClipboard content={() => source.content} title='Copy the source code to the clipboard'><span class="iconify" data-icon="clarity:copy-to-clipboard-line" style="height: 20px"></span></CopyToClipboard>{/if}
    </h2>
    {#if source.type == 'source'}
      <SubmitSource
        code={source.content}
        comments={source.comments}
        on:saveComment={(evt) => {evt.detail.source = source.path; saveComment(evt)}} />
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
