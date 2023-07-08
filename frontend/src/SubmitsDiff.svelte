<script>
    import TimeAgo from './TimeAgo.svelte'

    export let submits = [];
    export let current_submit;
    export let deadline;

    let a = Math.max(current_submit - 1, 1);
    let b = current_submit;

    let diffHtmlOutput = '';

    $: if(a != b) {
        fetch(`../${a}-${b}.diff`)
          .then((result) => result.text())
          .then((diff) => {
              diffHtmlOutput = Diff2Html.html(diff, {
                  matching: 'lines',
                  outputFormat: 'side-by-side',
                  drawFileList: false
              });
          });
    }
</script>

<style>
    ul {
        list-style: none;
        padding-left: 0;
    }
</style>

<ul>
    {#each submits as submit}
        <li>
            <input type="radio" bind:group={a} value="{submit.num}">
            <input type="radio" bind:group={b} value="{submit.num}" disabled={submit.num <= a}>
            <a href="../{submit.num}#src">
                <strong>#{submit.num}</strong>
            </a>
            {#if submit.submitted > deadline}
                <strong class="text-danger"><TimeAgo datetime={submit.submitted} rel={deadline} suffix='after the deadline' /></strong>
            {:else}
                {new Date(submit.submitted).toLocaleString('cs')}
            {/if}

            {#if submit.points != null}
                <span class="text-muted">({submit.points} points)</span>
            {/if}
        </li>
    {/each}
    <!-- TODO implement dark mode once diff2html adds it -->
    <div class="text-bg-light">
        {@html diffHtmlOutput}
    </div>
</ul>
