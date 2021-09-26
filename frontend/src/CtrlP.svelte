<svelte:window on:keydown={keydown} />

<script>
    import fuzzysort from 'fuzzysort'

    let shown = false;
    let results = [];
    let query = '';
    let selected = 0;

    const normalize = s => s.normalize('NFD').replace(/[\u0300-\u036f]/g, '');

    $: filtered = fuzzysort.go(normalize(query), results, {keys: ['normalized'], limit: 20})
      .map(r => {
          return {
            url: r.obj.url,
            highlight: fuzzysort.highlight({...r, ...r[0], target: r.obj.text}, '<strong>', '</strong>')
          }
      });


    async function load() {
      const res = await fetch('/api/search');
      const json = await res.json();
      results = json['results'].map(item => ({
        text: item.text,
        normalized: normalize(item.text),
        url: item.url,
        owned: item.owned,
      }));
    }
    load();

    function go(index) {
      document.location.href = filtered[index].url;
      shown = false;
    }

    function keydown(e) {
      if(e.ctrlKey && e.code == 'KeyP') {
          shown = true;
          selected = 0;
          query = '';
          e.preventDefault();
      } else if(shown) {
        if(e.code == 'Enter') {
          go(selected);
        } else if(e.code == 'ArrowDown') {
          selected++;
        } else if(e.code == 'ArrowUp') {
          selected--;
        } else if(e.code == 'Escape') {
          shown = false;
        }
      }
    }
</script>

<style>
div.ctrlp {
  position: fixed;
  top: 0px;
  left: 0px;
  z-index: 2;
  width: 100%;
}
ul {
  background: #ffffff;
  list-style: none;
  padding: 0;
}
ul li {
  padding-left: 4px;
}
</style>

{#if shown}
  <div class="ctrlp">
    <input type="text" class="form-control form-control-xs" bind:value={query} autofocus>
    <ul>
      {#each filtered as result, row}
        <li class:bg-info={row == selected} class:text-white={row == selected} on:click={() => go(row)}>
          {@html result.highlight}
        </li>
      {/each}
    </ul>
  </div>
{/if}
