<script>
import Manager from './Manager.svelte';
import AutoComplete from './Autocomplete.svelte';
import TimeRange from './TimeRange.svelte';
import { onMount } from 'svelte';
import { push } from 'svelte-spa-router';
import { semester, user } from './global.js';
import { fetch } from './api.js';
import { fs, currentPath, cwd, openedFiles } from './fs.js';
import SyncLoader from './SyncLoader.svelte';
import Modal from './Modal.svelte';

export let params = {};

let task = null;
let syncPathWithTitle = params.subject;
let taskLink = null;
let deleteModal = false;

let syncing = false;
let errors = [];
let savedPath = null;

function isClassVisible(cls) {
  return cls.teacher === $user.username || cls.assignment_id || showAllClasses;
}

let showAllClasses = false;
let shownClasses = [];
$: {
  if (task) {
    shownClasses = task.classes
      .filter((cls) => cls.teacher === $user.username || cls.assignment_id || showAllClasses)
      .sort((a, b) => {
        function key(cls) {
          return cls.teacher === $user.username || cls.assignment_id !== undefined;
        }

        return key(b) - key(a);
      });
  }
}

$: {
  if (task) {
    const clazz = task.classes.find((clazz) => clazz.assignment_id >= 1);
    if (clazz) {
      taskLink = `/task/${clazz.assignment_id}/${$user.username}/`;
    } else {
      taskLink = task.task_link;
    }
  }
}

async function prepareCreatingTask() {
  const res = await fetch('/api/subject/' + params.subject);
  const json = await res.json();

  task = {
    classes: json['classes'],
    path: [params.subject, $semester['abbr'], $user.username].join('/')
  };
  fs.createFile('readme.md', '# Task Title');
  fs.open('readme.md');
}

onMount(async () => {
  if (params.id) {
    loadTask(params.id);
  } else {
    await prepareCreatingTask();
  }
});

$: if (syncPathWithTitle) {
  const readme = $openedFiles['/readme.md'];
  if (readme && task) {
    let parts = [params.subject, $semester['abbr'], $user.username];

    let classes = task['classes'].filter((c) => c.assigned);
    if (classes.length == 1) {
      parts.push(classes[0].timeslot);
    }

    const title = readme.content
      .split('\n')[0]
      .toLowerCase()
      .replace(/^\s*#\s*|\s*$/g, '')
      .replace(/( |\/|\\)/g, '_')
      .split('')
      .map((c) => {
        const map = {
          ě: 'e',
          š: 's',
          č: 'c',
          ř: 'r',
          ž: 'z',
          ý: 'y',
          á: 'a',
          í: 'i',
          é: 'e',
          ú: 'u',
          ů: 'u',
          ǒ: 'o',
          ó: 'p'
        };
        return map[c] ? map[c] : c;
      })
      .join('');

    if (title) {
      parts.push(title);
    }

    task['path'] = parts.join('/');
  }
}

async function loadTask(id) {
  const req = await fetch('/api/tasks/' + id);
  task = await req.json();
  savedPath = task['path'];
  fs.setRoot(task.files, task.files_uri);
  fs.open('readme.md');
  push('/task/edit/' + task.id);
}

async function save() {
  syncing = true;
  const res = await fetch('/api/tasks/' + (task.id ? task.id : ''), {
    method: 'POST',
    body: JSON.stringify(task)
  });

  const json = await res.json();
  errors = json['errors'];
  if (errors.length == 0) {
    task['classes'] = json['classes'];
    savedPath = json['path'];
    task['can_delete'] = json['can_delete'];
    fs.setEndpointUrl(json.files_uri);

    await openedFiles.save();

    if (!task.id) {
      push('/task/edit/' + json.id);
    }
  }
  syncing = false;
}

function keydown(evt) {
  if (evt.ctrlKey && String.fromCharCode(event.which).toLowerCase() == 's') {
    save();
    evt.preventDefault();
  }
}

function setAssignedDateToVisible(assigned) {
  task.classes = task.classes.map((cl) => {
    if (isClassVisible(cl)) cl.assigned = assigned;
    return cl;
  });
}

function setDeadlineToAssigned(deadline) {
  task.classes = task.classes.map((cl) => {
    if (cl.assigned) cl.deadline = deadline;
    return cl;
  });
}

function assignPointsToAll(max_pts) {
  task.classes = task.classes.map((cl) => {
    if (cl.assigned) {
      cl.max_points = max_pts;
    }
    return cl;
  });
}

function assignSameToAll(templateClass) {
  task.classes = task.classes.map((cl) => {
    if (isClassVisible(cl)) {
      cl.max_points = templateClass.max_points;
      cl.assigned = templateClass.assigned;
      cl.deadline = templateClass.deadline;
    }
    return cl;
  });
}

async function duplicateTask() {
  let res = await fetch(`/api/tasks/${task.id}/duplicate`, {
    method: 'POST'
  });

  let json = await res.json();
  push('/task/edit/' + json.id);
  await loadTask(json.id);
}

async function deleteTask(proceed) {
  deleteModal = false;
  if (proceed) {
    const res = await fetch(`/api/tasks/${task.id}`, {
      method: 'DELETE'
    });

    const json = await res.json();
    if (json['errors']) {
      errors = json['errors'];
    } else {
      errors = [];
      push('/task/add/' + task.subject_abbr);
      fs.setRoot([], undefined);
      await prepareCreatingTask();
    }
  }
}
</script>

<svelte:window on:keydown={keydown} />

{#if task != null}
  <div class="container-fluid">
    <div style="position: relative">
      {#if syncing}
        <div style="position: absolute; top: 50%; left: 50%; z-index: 1">
          <SyncLoader />
        </div>
      {/if}
      <div>
        {#if errors && errors.length}
          <div class="alert alert-danger">
            <ul class="m-0">
              {#each errors as error}
                <li style="white-space: pre-line">{error}</li>
              {/each}
            </ul>
          </div>
        {/if}

        <div class="input-group mb-1">
          <AutoComplete
            bind:value={task.path}
            onChange={loadTask}
            on:click={() => (syncPathWithTitle = false)} />
          {#if taskLink}
            <button class="btn btn-outline-info" title="Plagiarism check">
              <a href={task.plagcheck_link} target="_blank" class="text-decoration: none;">
                <span class="iconify" data-icon="bx:bx-check-double"></span>
              </a>
            </button>
            <button class="btn btn-outline-info" title="Show all source codes">
              <a href="/task/show/{task.id}" target="_blank">
                <span class="iconify" data-icon="bx-bx-code-alt"></span>
              </a>
            </button>
            <button class="btn btn-outline-info" title="Show task stats">
              <a href="/statistics/task/{task.id}" target="_blank">
                <span class="iconify" data-icon="bx-bx-bar-chart-alt-2"></span>
              </a>
            </button>
            <button
              class="btn btn-outline-info"
              title="Duplicate this task"
              on:click={duplicateTask}>
              <span class="iconify" data-icon="ant-design:copy-outlined"></span>
            </button>
            <button class="btn btn-outline-info" title="Open task">
              <a href={taskLink} target="_blank"
                ><span class="iconify" data-icon="bx:bx-link-external"></span></a>
            </button>
            <button
              class="btn btn-outline-danger"
              disabled={!task['can_delete']}
              on:click={() => (deleteModal = true)}>
              <span class="iconify" data-icon="akar-icons:trash-can"></span>
            </button>
            <Modal
              open={deleteModal}
              onClosed={deleteTask}
              proceedButtonLabel="Delete"
              title="Delete task">
              Do you really want to delete the task with path <strong>{savedPath}</strong>?
              <strong>Readme.md</strong>
              and all files will be <strong>DELETED!</strong>
            </Modal>
          {/if}
        </div>

        <div class="mb-2">
          <table class="table table-hover table-striped mb-0">
            <tbody>
              {#each shownClasses as clazz}
                <tr class:table-success={clazz.assigned}>
                  <td>
                    {clazz.timeslot}
                    <span class="opacity-50">({clazz.code})</span>
                  </td>
                  <td>{clazz.teacher}</td>
                  <td>
                    <div class="row">
                      <TimeRange
                        timeOffsetInWeek={clazz.week_offset}
                        bind:from={clazz.assigned}
                        bind:to={clazz.deadline}
                        semesterBeginDate={$semester.begin}
                        onFromDuplicateClick={setAssignedDateToVisible}
                        onToDuplicateClick={setDeadlineToAssigned} />
                      <div class="col-md">
                        <div class="input-group">
                          <input
                            class="form-control form-control-sm"
                            type="number"
                            min="0"
                            step="1"
                            disabled={!clazz.assigned}
                            bind:value={clazz.max_points}
                            placeholder="Max points" />
                          <button
                            class="btn btn-sm btn-secondary"
                            disabled={!clazz.assigned}
                            on:click|preventDefault={() => assignPointsToAll(clazz.max_points)}
                            title="Set points to all assigned classes">
                            <span class="iconify" data-icon="mdi:content-duplicate"></span>
                          </button>
                        </div>
                      </div>
                    </div>
                  </td>
                  <td>
                    <button
                      class="btn btn-sm p-0"
                      on:click={() => assignSameToAll(clazz)}
                      title="Set same assigned date, deadline and points to all visible classes">
                      <span class="iconify" data-icon="mdi:content-duplicate"></span>
                    </button>
                    <button
                      class="btn-close"
                      on:click={() => {
                        clazz.assigned = null;
                        clazz.deadline = null;
                        clazz.max_points = null;
                      }}
                      aria-label="Unassign class"
                      disabled={!(clazz.assigned || clazz.deadline)}></button>
                  </td>
                </tr>{/each}
            </tbody>
          </table>
          {#if task && (task.classes.length > shownClasses.length || showAllClasses)}
            <button
              on:click|preventDefault={() => (showAllClasses = !showAllClasses)}
              class="btn p-0">
              <span class="iconify" data-icon="la:eye"></span> Show all classes
            </button>
          {/if}
        </div>

        <div title="All tasks with the same plagiarism key will be checked together">
          <label for="plagiarism-key">Plagiarism key:</label>
          <input type="text" id="plagiarism-key" maxlength="255" bind:value={task.plagiarism_key} />
        </div>

        <div class="mb-1">
          <Manager taskid={task.id} />
        </div>

        <button class="btn btn-primary" on:click|preventDefault={save}>Save</button>
      </div>
    </div>
  </div>
{/if}

<style>
td:not(:nth-of-type(3)) {
  vertical-align: middle;
  width: 1%;
  white-space: nowrap;
}
.btn > a,
.btn > a:visited,
.btn > a:hover,
.btn > a:active {
  color: inherit;
}
</style>
