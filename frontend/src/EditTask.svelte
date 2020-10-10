<script>
  import Manager from './Manager.svelte';
  import AutoComplete from './Autocomplete.svelte';
  import TimeRange from './TimeRange.svelte'
  import {onMount} from 'svelte';
  import {push} from 'svelte-spa-router'
  import {semester, user} from './global.js'
  import {fetch} from './api.js'

  export let params = {}

  let openedFiles = {};
  let task = null;
  let openFile;
  let syncPathWithTitle = params.subject;

  onMount(async () => {
      if(params.id) {
        loadTask(params.id);
      } else {
          task = {
              'classes': [],
              'path': [params.subject, $semester['abbr'], $user.username].join('/'),
              'files': {
                  'readme.md': {
                    'type': 'file',
                    'content': '# task name\n',
                  },
              },
          };
      }
  });

  $: if(syncPathWithTitle) {
    const readme = openedFiles['readme.md'];
    if(readme) {
      const title = readme.split('\n')[0]
        .toLowerCase()
        .replace(/^\s*#\s*|\s*$/g, '')
        .replace(/( |\/|\\)/g, '_')
        .split('')
        .map(c => {
            const map = { 
              'ě': 'e',
              'š': 's',
              'č': 'c',
              'ř': 'r',
              'ž': 'z',
              'ý': 'y',
              'á': 'a',
              'í': 'i',
              'é': 'e',
              'ú': 'u',
              'ů': 'u',
              'ǒ': 'o',
              'ó': 'p',
            };
            return map[c] ? map[c] : c;
        })
        .join('') 

        task['path'] = [params.subject, $semester['abbr'], $user.username, title].join('/')
    }
  }

  async function loadTask(id) {
    const req = await fetch('/api/tasks/' + id);
    task = await req.json();
    openedFiles = {};
    push('/task/edit/' + task.id);
  }


  async function save() {
      let res = await fetch('/api/tasks/' + task.id, {
        method: 'POST',
        body: JSON.stringify(task),
      })

      await Promise.all(Object.entries(openedFiles).map(([path, content]) => {
        return fetch(task.files_uri + path, {
          method: 'PUT',
          body: content,
        });
      }));
    }
</script>

{#if task != null}
	<div class="input-group mb-1">
    <AutoComplete bind:value={task.path} onChange={loadTask} on:click={() => syncPathWithTitle = false} />
    <input type="number" min="1" class="form-control" style="max-width: 120px" bind:value={task.max_points} placeholder="Max points">
	</div>

	<div class="form-group">
    <table class="table table-hover"> 
			{#each task.classes as clazz} 
      <tr class:table-success={clazz.assigned}>
        <td>{ clazz.name }</td>
        <td>
          <TimeRange timeOffsetInWeek={clazz.week_offset} bind:from={clazz.assigned} bind:to={clazz.deadline} semesterBeginDate={$semester.begin} />
        </td>
        <td style="width: 1%">
          <button style="border: 0; background: none" on:click|preventDefault={() => {clazz.assigned = null; clazz.deadline = null}}>&times;</button>
        </td>
			{/each}
    </table>
	</div>

  <div class="form-group">
    <Manager files={task.files} bind:openedFiles={openedFiles} files_uri={task.files_uri} />
	</div>

  <button class="btn btn-primary" on:click|preventDefault={save}>Save</button>
{/if}
