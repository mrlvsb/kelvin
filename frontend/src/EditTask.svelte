<script>
  import Manager from './Manager.svelte';
  import AutoComplete from './Autocomplete.svelte';
  import TimeRange from './TimeRange.svelte'
  import {onMount} from 'svelte';
  import {push} from 'svelte-spa-router'
  import {semester, user} from './global.js'
  import {fetch} from './api.js'
  import {fs, currentPath, cwd, openedFiles} from './fs.js'
  import SyncLoader from './SyncLoader.svelte';

  export let params = {}

  let task = null;
  let syncPathWithTitle = params.subject;
	let syncing = false;

  onMount(async () => {
      if(params.id) {
        loadTask(params.id);
      } else {
          const res = await fetch('/api/subject/' + params.subject);
          const json = await res.json();

          task = {
              'classes': json['classes'].filter(c => c.teacher_username == $user.username),
              'path': [params.subject, $semester['abbr'], $user.username].join('/'),
          };
          fs.createFile('readme.md', '# Task Title');
          fs.open('readme.md');
      }
  });

  $: if(syncPathWithTitle) {
    const readme = $openedFiles['/readme.md'];
    if(readme && task) {
      let parts = [params.subject, $semester['abbr'], $user.username];

      let classes = task['classes'].filter(c => c.assigned);
      if(classes.length == 1) {
        parts.push(classes[0].timeslot);
      }

      const title = readme.content.split('\n')[0]
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
        .join('');

        if(title) {
          parts.push(title);
        }

        task['path'] =  parts.join('/')
    }
  }

  async function loadTask(id) {
    const req = await fetch('/api/tasks/' + id);
    task = await req.json();
    fs.setRoot(task.files, task.files_uri);
    fs.open('readme.md');
    push('/task/edit/' + task.id);
  }


  async function save() {
    syncing = true;
    let res = await fetch('/api/tasks/' + (task.id ? task.id : ''), {
      method: 'POST',
      body: JSON.stringify(task),
    })

    const json = await res.json();
    task['classes'] = json['classes'];
    task['errors'] = json['errors'];
    fs.setEndpointUrl(json.files_uri);

    await openedFiles.save();

    if(!task.id) {
      push('/task/edit/' + json.id);
    }
    syncing = false;
  }

  function keydown(evt) {
    if(evt.ctrlKey && String.fromCharCode(event.which).toLowerCase() == 's') {
      save();
      evt.preventDefault();
    }
  }
</script>

<style>
td:first-of-type, td:last-of-type {
  vertical-align: middle;
  width: 1%;
}
</style>

<svelte:window on:keydown={keydown} />

{#if task != null}
<div style="position: relative">
	{#if syncing}
	<div style="position: absolute; top: 50%; left: 50%">
		<SyncLoader />
	</div>
	{/if}
	<div>
		{#if task['errors'] && task['errors'].length}
		<div class="alert alert-danger">
			<ul class="m-0">
				{#each task['errors'] as error}
					<li>{error}</li>
				{/each}
			</ul>
		</div>
		{/if}

		<div class="input-group mb-1">
			<AutoComplete bind:value={task.path} onChange={loadTask} on:click={() => syncPathWithTitle = false} />
			<input type="number" min="1" class="form-control" style="max-width: 120px" bind:value={task.max_points} placeholder="Max points">
      {#if task.task_link}
      <div class="input-group-append">
        <a class="btn btn-outline-info" href={task.task_link} target=_blank><span class="iconify" data-icon="bx:bx-link-external"></span></a>
      </div>
      {/if}
		</div>

		<div class="form-group">
			<table class="table table-hover"> 
				{#each task.classes as clazz} 
				<tr class:table-success={clazz.assigned}>
					<td>{ clazz.timeslot }</td>
					<td>
						<TimeRange timeOffsetInWeek={clazz.week_offset} bind:from={clazz.assigned} bind:to={clazz.deadline} semesterBeginDate={$semester.begin} />
					</td>
					<td>
						<button style="border: 0; background: none" on:click|preventDefault={() => {clazz.assigned = null; clazz.deadline = null}}>&times;</button>
					</td>
				{/each}
			</table>
		</div>

		<div class="form-group">
			<Manager />
		</div>

		<button class="btn btn-primary" on:click|preventDefault={save}>Save</button>
	</div>
</div>
{/if}