<style>
.tree {
  width: 200px;
}
.tree ul {
  list-style: none;
  padding: 0;
}

.tree ul li {
  cursor: pointer;
  overflow-x: hidden;
}

.newdir {
  white-space: nowrap;
}

ul input {
  width: max-content;
  padding: 0px;
}

.action-buttons span {
  cursor: pointer;
}

.nav-item span {
  padding: 3px 6px;
}

:global(.editor-container .CodeMirror) {
  border-top: 0;
  min-height: 600px;
}
</style>

<script>
  import {clickOutside} from './utils.js';
  import {fs, currentPath, cwd, openedFiles, currentOpenedFile} from './fs.js'
  import Editor from './Editor.svelte'
  import Tests from './Tests.svelte'
  import {fetch} from './api.js'

  export let taskid;

  let renamingPath = null;
  let ctxMenu = null;
  let newDirName = false;
  let testsShown = false;
  let testsActivated = false;

  function finishRename(e) {
    if(e.keyCode == 13) {
      fs.rename(renamingPath, e.target.value);
      renamingPath = null;
    }
  }

  function showCtxMenu(e, path) {
    ctxMenu = {
      left: e.pageX,
      top: e.pageY,
      selected: $currentPath + '/' + path,
    };
  }

  async function remove(path) {
    await fs.remove(path);
  }

  function createDir(e) {
    if(e.keyCode == 13) {
      newDirName = false;
      fs.mkdir(e.target.value);
    }
  }

  async function addToUploadQueue(evt) {
    for(const file of evt.target.files) {
      await fs.upload(file.name, file);
    }
  }

  async function openConfigYaml() {
    const fileName = '/config.yml';

    if(!await fs.open(fileName)) {
      fs.createFile(fileName, `
# https://github.com/mrlvsb/kelvin/blob/master/README.pipeline.md
# You can also use CTRL+Space for autocompleting
pipeline:
  # compile submitted source codes
  - type: gcc
  # flags: -Wall -Wextra -g -fsanitize=address -lm -Wno-unused-variable

  # add hints from clang-tidy as comments
  #- type: clang-tidy 

  # run tests
  #- type: tests

  # run custom commands
  #- type: run
  #  commands:
  #    - ./main 123 | wc -l

  # automatically assign points from the test results
  #- type: auto_grader
      
`.trim());

      await fs.open(fileName);
    }
  }

  async function reevaluate() {
    await fetch(`/api/reevaluate_task/${taskid}`, {method: 'POST'});
  }
</script>

<div>
  {$currentPath}
</div>
<div class="d-flex">
  <div class="tree">
    <div class="action-buttons">
      <span on:click={() => renamingPath = '/' + fs.createFile('newfile.txt')}>
        <span class="iconify" data-icon="bx:bxs-file-plus"></span>
      </span>
      <span on:click={() => newDirName = ''}>
        <span class="iconify" data-icon="ic:sharp-create-new-folder"></span>
      </span>
      <span>
        <label for="manager-file-upload">
          <span class="iconify" data-icon="ic:sharp-file-upload"></span>
        <label>
        <input id="manager-file-upload" type="file" style="display: none" multiple
               onclick="this.value=null;"
               on:change={addToUploadQueue}>
      </span>
      <span on:click={openConfigYaml}>
        <span class="iconify" data-icon="vscode-icons:file-type-light-config"></span>
      </span>
      <span on:click={() => testsActivated = testsShown = true}>
        <span class="iconify" data-icon="fa6-solid:t"></span>
      </span>
    </div>
    <ul>
      {#if $currentPath != '/'}
        <li on:click={() => currentPath.up()}>
          <span class="iconify" data-icon="ic:baseline-folder"></span>
          ..
        </li>
      {/if}
      {#if newDirName !== false}
      <li class="newdir">
          <span class="iconify" data-icon='ic:baseline-folder'></span>
          <input type="text" on:keyup|preventDefault={createDir} autofocus>
      </li>
      {/if}
      {#each $cwd as inode (inode)}
        <li on:contextmenu|preventDefault={(e) => showCtxMenu(e, inode.name)} style="white-space: nowrap">
          <span class="iconify" data-icon="{inode.type == 'dir' ? 'ic:baseline-folder' : 'ic:outline-insert-drive-file'}"></span>
          {#if renamingPath == $currentPath + '/' + inode.name}
            <input value={inode.name} on:keyup={finishRename} autofocus>
          {:else}
            <span on:click={() => fs.open(inode.name)}>{inode.name}</span>
          {/if}
          </li>
      {/each}
    </ul>
  </div>
  <div class="w-100" style="overflow: hidden">
    <ul class="nav nav-tabs">
      {#each Object.entries($openedFiles).filter(([_, inode]) => !inode.hide_tab) as [path, file]}
      <li class="nav-item" style="cursor: pointer">
        <span class="nav-link" class:active={!testsShown && path === $currentOpenedFile}>
          <span on:click={() => {testsShown = false; fs.open(path, {hide_tab: false})}}>{path.split('/').slice(-1)[0]}</span>
          <span on:click={() => fs.close(path)}><span class="iconify" data-icon="fa:times"></span></span>
        </span>
      </li>
      {/each}
      {#if testsActivated}
      <li class="nav-item" style="cursor: pointer">
        <span class="nav-link" class:active={testsShown}>
          <span on:click={() => testsShown = true}>Tests</span>
        </span>
      </li>
      {/if}
    </ul>

    {#if $currentOpenedFile}
      <div class="editor-container">
        {#if $currentOpenedFile === '/config.yml'}
        <div style="position: absolute; z-index: 3; right: 5px;">
          <button class="btn btn-link p-0" title="Reevaluate all submits" on:click={reevaluate}>
            <span class="iconify" data-icon="bx:bx-refresh"></span> 
          </button>
          <a href="https://github.com/mrlvsb/kelvin/blob/master/README.pipeline.md" target="_blank">
            <span class="iconify" data-icon="entypo:help"></span>
          </a>
        </div>
        {/if}

        {#if testsShown}
          <Tests />
        {:else}
          <Editor filename={$currentOpenedFile} bind:value={$openedFiles[$currentOpenedFile].content} />
        {/if}
      </div>
    {/if}
  </div>
</div>

{#if ctxMenu && ctxMenu.selected != '/readme.md'}
  <div class="dropdown-menu show" style="position: fixed; top: {ctxMenu.top}px; left: {ctxMenu.left}px" use:clickOutside on:click_outside={() => ctxMenu = null}>
    <button class="dropdown-item" on:click|preventDefault={() => {renamingPath = ctxMenu.selected; ctxMenu = null}}><span class="iconify" data-icon="wpf:rename"></span> rename</button>
    <button class="dropdown-item" on:click|preventDefault={() => {remove(ctxMenu.selected); ctxMenu = null}}><span class="iconify" data-icon="wpf:delete"></span> delete</button>
  </div>
{/if}
