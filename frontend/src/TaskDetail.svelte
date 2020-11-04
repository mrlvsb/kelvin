<script>
  import { onMount } from "svelte";
  import SubmitSource from "./SubmitSource.svelte";
  import SyncLoader from "./SyncLoader.svelte";
  import CopyToClipboard from './CopyToClipboard.svelte'
  import {fetch} from './api.js'

  export let url;
  let sources = [];

  async function saveComment(evt) {
    if(evt.detail.id === undefined) {
      const res = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          text: evt.detail.text,
          source: evt.detail.source,
          line: evt.detail.line,
        })
      });

      const json = await res.json();
      sources.find(s => s.path === evt.detail.source).lines[evt.detail.line - 1].comments.push(json);
    } else {
      const res = await fetch(url, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          id: evt.detail.id,
          text: evt.detail.text,
        })
      });

      for(let source of sources) {
        for(let line of source.lines) {
          for(const commentIdx in line.comments) {
            if(line.comments[commentIdx].id === evt.detail.id) {
              if(evt.detail.text == '') {
                line.comments.splice(commentIdx, 1);
              } else {
                line.comments[commentIdx].text = evt.detail.text;
              }
            }
          }
        }
      }
    }
    
    sources = sources;
    if(evt.detail.success) {
      evt.detail.success();
    }
  }

  async function load() {
    const res = await fetch(url);
    sources = await res.json();
  }

  load();
</script>

<style>
  video,
  img {
    max-width: 100%;
  }
</style>

{#each sources as source}
  <h2>
    {source.path}{#if source.type == 'source'}<CopyToClipboard content={() => source.content} title='Copy the source code to the clipboard'><span class="iconify" data-icon="clarity:copy-to-clipboard-line" style="height: 20px"></span></CopyToClipboard>{/if}
  </h2>
  {#if source.type == 'source'}
    <SubmitSource
      code={source.content}
      comments={source.lines.map((i) => i.comments)}
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

<!--
  {#await sources}
  <div class="d-flex justify-content-center">
    <SyncLoader />
  </div>
{:then sources}
{:catch}
  <p class="alert alert-danger">Failed to load the submit's source code.</p>
{/await}
-->
